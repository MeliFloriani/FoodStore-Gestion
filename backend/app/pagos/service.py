"""
Pago service — business logic for the pagos module.

Change 19 — payments-mercadopago-integration (Checkout Pro migration).

Functions:
  start_checkout_pro(): POST /api/v1/pagos — create MP Checkout Pro preference.
  get_latest_payment(): GET /api/v1/pagos/{pedido_id}/latest — latest Pago row.
  process_webhook(): POST /api/v1/pagos/webhook — IPN handler (inline synchronous).

Design decisions:
  D-02: Webhook processing is inline synchronous — no BackgroundTasks.
  D-03: Webhook always re-queries MP API — never trusts webhook payload alone.
  D-04: SYSTEM actor uses actor_user_id=None (NULL in historial.cambiado_por_id).
  D-05: Single UoW for Pago + FSM transition + stock decrement in approved path.
  D-08: HMAC-SHA256 with timestamp freshness check (300s window).
  D-09: mp_client singleton from integrations/mercadopago_client.py.

Checkout Pro flow:
  - start_checkout_pro() calls mp_client.create_preference() instead of create_payment().
  - mp_payment_id stays NULL until webhook fires and assigns the real MP payment ID.
  - Webhook lookup uses external_reference (pedido_id) to find the pending Pago row.
  - Idempotency: if Pago.mp_payment_id is already set to this mp_payment_id → skip.

Service raises HTTPException — never the router, never the repository.
No session.commit() in this file — UnitOfWork owns the commit.
"""

from __future__ import annotations

import hmac
import hashlib
import logging
import time
import uuid
from typing import Any

from fastapi import HTTPException

from app.core.config import get_settings
from app.core.logging import get_logger
from app.integrations.mercadopago_client import MercadoPagoAPIError, mp_client
from app.models.order import HistorialEstadoPedido, Pago
from app.pagos.schemas import PagoCreateRequest, PagoResponse

logger = get_logger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Helper: build PagoResponse from ORM object
# ─────────────────────────────────────────────────────────────────────────────


def _pago_to_response(
    pago: Pago,
    preference_id: str | None = None,
    init_point: str | None = None,
    sandbox_init_point: str | None = None,
) -> PagoResponse:
    """Construct a PagoResponse from a Pago ORM object.

    The transient Checkout Pro fields (preference_id, init_point,
    sandbox_init_point) are NOT stored in the DB. They must be passed
    explicitly when available, or default to None (e.g., for GET /latest).

    Using explicit construction instead of model_validate(pago) avoids
    MagicMock read issues in tests where the ORM object is mocked.
    """
    return PagoResponse(
        id=pago.id,
        pedido_id=pago.pedido_id,
        mp_payment_id=pago.mp_payment_id,
        mp_preference_id=pago.mp_preference_id,
        mp_status=pago.mp_status,
        mp_status_detail=pago.mp_status_detail,
        idempotency_key=pago.idempotency_key,
        external_reference=pago.external_reference,
        monto=pago.monto,
        created_at=pago.created_at,
        preference_id=preference_id,
        init_point=init_point,
        sandbox_init_point=sandbox_init_point,
    )


# ─────────────────────────────────────────────────────────────────────────────
# start_checkout_pro (replaces create_payment)
# ─────────────────────────────────────────────────────────────────────────────


async def start_checkout_pro(uow, current_user, data: PagoCreateRequest) -> PagoResponse:
    """Create a MercadoPago Checkout Pro preference for an order.

    Steps:
      1. Load Pedido. Raise 404 ORDER_NOT_FOUND if not found.
      2. Verify pedido.usuario_id == current_user.id. Raise 403 ORDER_NOT_OWNED.
      3. Verify pedido.estado_codigo == "PENDIENTE". Raise 409 ORDER_NOT_PAYABLE.
      4. Verify pedido.forma_pago_codigo == "MERCADOPAGO". Raise 409 PAYMENT_METHOD_MISMATCH.
      5. Check idempotency: if a Pago with same idempotency_key exists, return it.
      6. Build items list from pedido (title, unit_price, quantity, currency_id).
      7. Build back_urls from FRONTEND_BASE_URL setting.
      8. Call mp_client.create_preference(...). Raise 502 MP_PREFERENCE_ERROR on failure.
      9. Insert Pago row with mp_preference_id, mp_payment_id=None, mp_status="pending".
      10. Return PagoResponse with preference_id, init_point, sandbox_init_point.

    Args:
        uow: Active UnitOfWork.
        current_user: Authenticated Usuario instance (from require_role("CLIENT")).
        data: PagoCreateRequest with pedido_id and idempotency_key.

    Returns:
        PagoResponse for the newly created Pago row.

    Raises:
        HTTPException 404: Pedido not found (ORDER_NOT_FOUND).
        HTTPException 403: Pedido belongs to another user (ORDER_NOT_OWNED).
        HTTPException 409: Order not in PENDIENTE state (ORDER_NOT_PAYABLE).
        HTTPException 409: Order uses non-MP payment method (PAYMENT_METHOD_MISMATCH).
        HTTPException 502: MP API returned an error (MP_PREFERENCE_ERROR).
    """
    settings = get_settings()

    # Step 1: Load Pedido
    pedido = await uow.pedidos.get_by_id(data.pedido_id)
    if pedido is None:
        raise HTTPException(
            status_code=404,
            detail={"detail": "El pedido no fue encontrado.", "code": "ORDER_NOT_FOUND"},
        )

    # Step 2: Ownership check
    if pedido.usuario_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail={"detail": "No tiene permiso sobre este pedido.", "code": "ORDER_NOT_OWNED"},
        )

    # Step 3: State check — only PENDIENTE orders can be paid
    if pedido.estado_codigo != "PENDIENTE":
        raise HTTPException(
            status_code=409,
            detail={
                "detail": "El pedido no está en estado pagable.",
                "code": "ORDER_NOT_PAYABLE",
            },
        )

    # Step 4: Payment method check — must be MERCADOPAGO
    if pedido.forma_pago_codigo != "MERCADOPAGO":
        raise HTTPException(
            status_code=409,
            detail={
                "detail": "La forma de pago del pedido no es MercadoPago.",
                "code": "PAYMENT_METHOD_MISMATCH",
            },
        )

    # Step 5: Idempotency check — return existing Pago for same idempotency_key
    existing = await uow.pagos.get_by_idempotency_key(data.idempotency_key)
    if existing is not None:
        # init_point/sandbox_init_point are not stored in DB — return None for them.
        # preference_id is surfaced from the stored mp_preference_id column.
        return _pago_to_response(existing, preference_id=existing.mp_preference_id)

    # Step 6: Build items from pedido
    # Attempt to load items; fall back to single line-item from pedido.total
    items: list[dict[str, Any]] = []
    try:
        # Try to load detalles if the pedido has them loaded
        detalles = getattr(pedido, "detalles", None)
        if detalles:
            for detalle in detalles:
                title = getattr(detalle, "nombre_producto", f"Producto {detalle.producto_id}")
                items.append({
                    "title": str(title),
                    "unit_price": float(detalle.precio_unitario),
                    "quantity": int(detalle.cantidad),
                    "currency_id": "ARS",
                })
    except Exception:
        pass

    if not items:
        # Fallback: single item representing the full order total
        items = [
            {
                "title": f"Pedido {pedido.id}",
                "unit_price": float(pedido.total),
                "quantity": 1,
                "currency_id": "ARS",
            }
        ]

    # Step 7: Build back_urls.
    # Strip trailing slash defensively so URL concatenation never produces "//checkout".
    frontend_base = getattr(settings, "FRONTEND_BASE_URL", "") or "http://localhost:5173"
    frontend_base = frontend_base.rstrip("/")
    pedido_id_str = str(pedido.id)
    back_urls = {
        "success": f"{frontend_base}/checkout/return?status=success&pedido_id={pedido_id_str}",
        "pending": f"{frontend_base}/checkout/return?status=pending&pedido_id={pedido_id_str}",
        "failure": f"{frontend_base}/checkout/return?status=failure&pedido_id={pedido_id_str}",
    }

    # auto_return="approved" only when back_urls are HTTPS (required by MP
    # for production credentials). HTTP back_urls (local dev) must omit
    # auto_return to avoid MP rejecting the preference with
    # "invalid_auto_return".
    _frontend_has_https = frontend_base.startswith("https://")
    auto_return: str | None = "approved" if _frontend_has_https else None

    # Safe debug log — no tokens, no card data, only routing metadata.
    logger.info(
        "mp_preference_payload_built",
        pedido_id=pedido_id_str,
        items_count=len(items),
        external_reference=pedido_id_str,
        notification_url=settings.MP_NOTIFICATION_URL,
        back_urls=back_urls,
        auto_return=auto_return,
    )

    # Step 8: Call MP Preferences API (or mock for development).
    # Mock mode only activates in development when no real MP credentials
    # are configured. If MP_ACCESS_TOKEN is a real token (APP_USR- or TEST-),
    # call the real MP API even in development mode.
    _mp_token = settings.MP_ACCESS_TOKEN or ""
    _has_real_creds = _mp_token.startswith("APP_USR-") or _mp_token.startswith("TEST-")

    if settings.ENVIRONMENT == "development" and not _has_real_creds:
        # Dev mode, no real MP credentials: return mock preference that
        # redirects directly to the frontend return page for local testing.
        mock_pref_id = f"mock_dev_pref_{pedido_id_str}"
        mock_init = (
            f"{frontend_base}/checkout/return"
            f"?status=success&pedido_id={pedido_id_str}&payment_id=1"
        )
        logger.info(
            "mp_preference_mock_dev",
            pedido_id=pedido_id_str,
            mock_init_point=mock_init,
        )
        preference_id = mock_pref_id
        init_point = mock_init
        sandbox_init_point = mock_init
    else:
        try:
            mp_response = mp_client.create_preference(
                items=items,
                external_reference=pedido_id_str,
                notification_url=settings.MP_NOTIFICATION_URL,
                back_urls=back_urls,
                idempotency_key=data.idempotency_key,
                auto_return=auto_return,
            )
        except MercadoPagoAPIError as exc:
            logger.error(
                "mp_preference_create_failed",
                pedido_id=pedido_id_str,
                status_code=exc.status_code,
                detail=str(exc.detail),
            )
            raise HTTPException(
                status_code=502,
                detail={"detail": "Error al crear la preferencia de pago.", "code": "MP_PREFERENCE_ERROR"},
            )

        preference_id: str = mp_response.get("id") or ""
        init_point: str | None = mp_response.get("init_point")
        sandbox_init_point: str | None = mp_response.get("sandbox_init_point")

    # Step 9: Insert Pago row
    pago = Pago(
        pedido_id=data.pedido_id,
        mp_preference_id=preference_id,
        mp_payment_id=None,  # Assigned by webhook after user pays
        mp_status="pending",
        mp_status_detail=None,
        external_reference=pedido_id_str,
        idempotency_key=data.idempotency_key,
        monto=pedido.total,
    )
    pago = await uow.pagos.create(pago)

    # Step 10: Build and return response.
    # preference_id, init_point, sandbox_init_point are transient from MP API.
    return _pago_to_response(pago, preference_id=preference_id, init_point=init_point, sandbox_init_point=sandbox_init_point)


# Backward compat alias (kept for any internal callers)
create_payment = start_checkout_pro


# ─────────────────────────────────────────────────────────────────────────────
# get_latest_payment
# ─────────────────────────────────────────────────────────────────────────────


async def get_latest_payment(uow, current_user, pedido_id: uuid.UUID) -> PagoResponse:
    """Return the latest Pago row for a given pedido.

    Ownership check: CLIENT must own the pedido. PEDIDOS/ADMIN can access any.

    Args:
        uow: Active UnitOfWork.
        current_user: Authenticated user (CLIENT, PEDIDOS, or ADMIN).
        pedido_id: UUID of the pedido whose latest payment is requested.

    Returns:
        PagoResponse for the most recent Pago row.

    Raises:
        HTTPException 404: Pedido not found (ORDER_NOT_FOUND).
        HTTPException 403: Pedido belongs to another user (ORDER_NOT_OWNED).
        HTTPException 404: No Pago exists for this pedido (PAYMENT_NOT_FOUND).
    """
    # Load pedido for ownership check
    pedido = await uow.pedidos.get_by_id(pedido_id)
    if pedido is None:
        raise HTTPException(
            status_code=404,
            detail={"detail": "El pedido no fue encontrado.", "code": "ORDER_NOT_FOUND"},
        )

    # Determine user roles
    user_role_codes = _get_user_roles(current_user)

    # CLIENT must own the pedido; PEDIDOS/ADMIN can access any
    if "CLIENT" in user_role_codes and pedido.usuario_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail={"detail": "No tiene permiso sobre este pedido.", "code": "ORDER_NOT_OWNED"},
        )

    # Get latest payment
    pago = await uow.pagos.get_latest_by_pedido_id(pedido_id)
    if pago is None:
        raise HTTPException(
            status_code=404,
            detail={"detail": "No se encontró ningún pago para este pedido.", "code": "PAYMENT_NOT_FOUND"},
        )

    return _pago_to_response(pago)


def _get_user_roles(current_user) -> set[str]:
    """Extract role codes from the current_user's active usuario_roles."""
    return {
        ur.rol.codigo
        for ur in current_user.usuario_roles
        if ur.rol is not None and ur.deleted_at is None
    }


# ─────────────────────────────────────────────────────────────────────────────
# Webhook signature verification (D-08)
# ─────────────────────────────────────────────────────────────────────────────


def verify_webhook_signature(
    x_signature: str,
    x_request_id: str,
    data_id: str,
    webhook_secret: str,
) -> None:
    """Verify the MercadoPago IPN webhook HMAC-SHA256 signature.

    Algorithm (D-08):
      1. Parse x-signature header: extract ts and v1 parts.
      2. Freshness check: abs(time.time() - int(ts)) <= 300.
         If stale → raise HTTP 400 WEBHOOK_EXPIRED (BEFORE HMAC computation).
      3. Compose signed string: "id:{data_id};request-id:{request_id};ts:{ts}".
      4. Compute HMAC-SHA256(key=webhook_secret, msg=composed_string).
      5. Constant-time compare with v1 via hmac.compare_digest.
      6. If mismatch → raise HTTP 400 INVALID_SIGNATURE.

    Args:
        x_signature: Value of the x-signature header (format: "ts=<ts>,v1=<hex>").
        x_request_id: Value of the x-request-id header (UUID).
        data_id: Value of the data.id query parameter (mp_payment_id as string).
        webhook_secret: MP_WEBHOOK_SECRET from settings.

    Raises:
        HTTPException 400: Stale timestamp (WEBHOOK_EXPIRED).
        HTTPException 400: Invalid HMAC signature (INVALID_SIGNATURE).
    """
    # Parse x-signature: "ts=<timestamp>,v1=<hmac_hex>"
    ts_value: str | None = None
    v1_value: str | None = None

    for part in x_signature.split(","):
        part = part.strip()
        if part.startswith("ts="):
            ts_value = part[3:]
        elif part.startswith("v1="):
            v1_value = part[3:]

    if ts_value is None or v1_value is None:
        raise HTTPException(
            status_code=400,
            detail={
                "detail": "Invalid webhook signature",
                "code": "INVALID_SIGNATURE",
            },
        )

    # Step 2: Freshness check — BEFORE HMAC computation (prevent replay attacks)
    try:
        ts_int = int(ts_value)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail={
                "detail": "Invalid webhook signature",
                "code": "INVALID_SIGNATURE",
            },
        )

    if abs(time.time() - ts_int) > 300:
        raise HTTPException(
            status_code=400,
            detail={
                "detail": "Webhook timestamp expired",
                "code": "WEBHOOK_EXPIRED",
            },
        )

    # Step 3: Compose the signed string
    composed = f"id:{data_id};request-id:{x_request_id};ts:{ts_value}"

    # Step 4: Compute HMAC-SHA256
    expected = hmac.new(  # type: ignore[attr-defined]  # hmac.new is the standard API
        webhook_secret.encode("utf-8"),
        composed.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    # Step 5: Constant-time comparison (prevents timing attacks)
    if not hmac.compare_digest(expected, v1_value):
        raise HTTPException(
            status_code=400,
            detail={
                "detail": "Invalid webhook signature",
                "code": "INVALID_SIGNATURE",
            },
        )


# ─────────────────────────────────────────────────────────────────────────────
# process_webhook (D-02: inline synchronous, no BackgroundTasks)
# ─────────────────────────────────────────────────────────────────────────────


async def process_webhook(
    webhook_type: str,
    data_id: str,
    x_signature: str,
    x_request_id: str,
    uow,
) -> dict[str, str]:
    """Process a MercadoPago IPN webhook notification.

    D-02: Processing is inline synchronous. Returns HTTP 200 after UoW completes.
    D-03: Always re-queries MP API — never trusts webhook payload status.
    D-04: SYSTEM actor: actor_user_id=None, motivo="Pago aprobado MP".
    D-05: Single UoW for Pago update + FSM transition + stock decrement.

    Checkout Pro webhook flow:
      - MP sends type=payment with data.id = mp_payment_id (actual payment ID).
      - We re-query GET /v1/payments/{id} to get external_reference (=pedido_id)
        and real status.
      - We look up the pending Pago row by external_reference.
      - First time: assign mp_payment_id to the Pago row (it was NULL after preference).
      - Idempotency: if mp_payment_id already assigned and status=approved → skip.

    Verification flow:
      1. Verify HMAC signature + timestamp freshness (D-08).
         Return 400 on failure (never 200 for invalid signatures).
      2. Return 200 immediately for non-payment webhook types.
      3. Re-query MP API for the real payment status (D-03).
      4. Find Pago row:
         a. Try get_by_mp_payment_id (already assigned from prior webhook).
         b. If not found, try get_latest_by_pedido_id via external_reference.
         c. If Pago found and mp_payment_id already set == this id AND status=approved
            → idempotency skip.
         d. Assign mp_payment_id if not yet set.
      5. Approved path: lock pedido → update Pago → state_transition → decrement_stock.
      6. Non-approved path: update Pago.mp_status only.

    Args:
        webhook_type: Query param `type` (e.g. "payment", "merchant_order").
        data_id: Query param `data.id` (mp_payment_id as string).
        x_signature: x-signature header value.
        x_request_id: x-request-id header value.
        uow: Active UnitOfWork.

    Returns:
        {"status": "ok"} on successful processing or non-payment event.

    Raises:
        HTTPException 400: Invalid signature or stale timestamp.
    """
    settings = get_settings()

    # Step 1: Verify HMAC signature + timestamp freshness
    verify_webhook_signature(
        x_signature=x_signature,
        x_request_id=x_request_id,
        data_id=data_id,
        webhook_secret=settings.MP_WEBHOOK_SECRET,
    )

    # Step 2: Ignore non-payment webhook types
    if webhook_type != "payment":
        logger.info("webhook.non_payment_type", webhook_type=webhook_type, data_id=data_id)
        return {"status": "ok"}

    # Step 3: Re-query MP API for real payment status (D-03 / RN-PA04)
    try:
        mp_payment_id_int = int(data_id)
        mp_payment = mp_client.get_payment(mp_payment_id_int)
    except MercadoPagoAPIError as exc:
        logger.error(
            "webhook.mp_requery_failed",
            data_id=data_id,
            status_code=exc.status_code,
        )
        # Return 200 to avoid MP retrying; log the error
        return {"status": "ok"}
    except (ValueError, TypeError):
        logger.error("webhook.invalid_data_id", data_id=data_id)
        return {"status": "ok"}

    real_status: str = mp_payment.get("status", "unknown")
    real_status_detail: str | None = mp_payment.get("status_detail")
    external_reference: str | None = mp_payment.get("external_reference")

    # Step 4a: Try to find Pago by mp_payment_id (already assigned from prior webhook)
    existing_pago = await uow.pagos.get_by_mp_payment_id(mp_payment_id_int)

    if existing_pago is not None and existing_pago.mp_status == "approved":
        # Already processed approved payment — skip to prevent double-transition
        logger.info(
            "webhook.idempotency_skip",
            mp_payment_id=mp_payment_id_int,
            pedido_id=str(existing_pago.pedido_id),
        )
        return {"status": "ok"}

    if existing_pago is None:
        # Step 4b: Lookup by external_reference (Checkout Pro path — mp_payment_id was NULL)
        if external_reference is None:
            logger.error(
                "ORPHAN_WEBHOOK",
                mp_payment_id=mp_payment_id_int,
                external_reference=None,
            )
            return {"status": "ok"}

        try:
            pedido_id_from_ext = uuid.UUID(external_reference)
        except (ValueError, AttributeError):
            logger.error(
                "ORPHAN_WEBHOOK",
                mp_payment_id=mp_payment_id_int,
                external_reference=external_reference,
            )
            return {"status": "ok"}

        # Search for a pending Pago row (mp_payment_id IS NULL) for this pedido
        pending_pago = await uow.pagos.get_latest_by_pedido_id(pedido_id_from_ext)
        if pending_pago is not None and pending_pago.mp_payment_id is None:
            # Assign mp_payment_id for the first time (Checkout Pro first webhook)
            existing_pago = pending_pago
            existing_pago.mp_payment_id = mp_payment_id_int
            await uow._session.flush()
        else:
            logger.error(
                "ORPHAN_WEBHOOK",
                mp_payment_id=mp_payment_id_int,
                external_reference=external_reference,
            )
            return {"status": "ok"}

    # At this point, existing_pago is not None
    pago = existing_pago
    pedido_id = pago.pedido_id

    # Step 5/6: Process based on real payment status
    if real_status == "approved":
        # Full approved path: lock pedido + update pago + FSM + stock (D-05)
        await _process_approved_payment(
            uow=uow,
            pago=pago,
            mp_payment_id=mp_payment_id_int,
            pedido_id=pedido_id,
            real_status_detail=real_status_detail,
        )
    else:
        # Non-approved: update mp_status only (no FSM transition)
        pago.mp_status = real_status
        pago.mp_status_detail = real_status_detail
        await uow._session.flush()
        logger.info(
            "webhook.pago_status_updated",
            mp_payment_id=mp_payment_id_int,
            pedido_id=str(pedido_id),
            new_status=real_status,
        )

    return {"status": "ok"}


async def _process_approved_payment(
    uow,
    pago: Pago,
    mp_payment_id: int,
    pedido_id: uuid.UUID,
    real_status_detail: str | None,
) -> None:
    """Execute the atomic UoW block for an approved payment.

    D-05: Single UoW for: Pago update + FSM transition + stock decrement.

    Steps:
      1. Lock pedido via get_for_update (SELECT FOR UPDATE).
      2. Update pago.mp_status = "approved".
      3. Append HistorialEstadoPedido via state_transition logic.
      4. Decrement stock for each DetallePedido item.
         If any decrement returns None (insufficient stock): raise to trigger UoW rollback.

    Note: This function does NOT call its own UoW. It runs inside the caller's
    UoW (from the router via get_uow dependency). The caller handles the rollback
    logging if an exception is raised.
    """
    from sqlalchemy import select as sa_select
    from app.models.order import DetallePedido

    # Step 1: Pessimistic lock on Pedido
    pedido = await uow.pedidos.get_for_update(pedido_id)
    if pedido is None:
        raise RuntimeError(f"Pedido {pedido_id} not found during webhook approved processing")

    # Step 2: Update Pago status
    pago.mp_status = "approved"
    pago.mp_payment_id = mp_payment_id
    pago.mp_status_detail = real_status_detail
    await uow._session.flush()

    # Step 3: FSM transition — PENDIENTE → CONFIRMADO via SYSTEM actor
    # Check if already CONFIRMADO to be idempotent
    if pedido.estado_codigo != "PENDIENTE":
        logger.info(
            "webhook.pedido_already_non_pendiente",
            pedido_id=str(pedido_id),
            estado_codigo=pedido.estado_codigo,
        )
        # Still return OK — payment was already processed
        return

    # Directly write the FSM transition (replicating transition_state for SYSTEM actor)
    # We use state_transition service internals but with actor_user_id=None (SYSTEM)
    nuevo_estado = "CONFIRMADO"
    pedido_updated = await uow.pedidos.update_estado(pedido_id, nuevo_estado)

    historial = HistorialEstadoPedido(
        pedido_id=pedido_id,
        estado_desde=pedido.estado_codigo,  # "PENDIENTE"
        estado_hasta=nuevo_estado,  # "CONFIRMADO"
        motivo="Pago aprobado MP",
        cambiado_por_id=None,  # D-04: SYSTEM actor = NULL
    )
    await uow.historial_pedido.append(historial)

    # Step 4: Decrement stock for each DetallePedido item
    stmt = sa_select(DetallePedido).where(DetallePedido.pedido_id == pedido_id)
    result = await uow._session.execute(stmt)
    detalles = result.scalars().all()

    for detalle in detalles:
        decremented = await uow.productos.decrement_stock(detalle.producto_id, detalle.cantidad)
        if decremented is None:
            # Insufficient stock — raise to trigger UoW rollback
            raise InsufficientStockError(
                f"Insufficient stock for producto {detalle.producto_id} "
                f"(qty needed: {detalle.cantidad})"
            )

    logger.info(
        "webhook.approved_processed",
        pedido_id=str(pedido_id),
        mp_payment_id=mp_payment_id,
        items_decremented=len(detalles),
    )


class InsufficientStockError(Exception):
    """Raised when decrement_stock returns None (insufficient stock)."""
    pass


# ─────────────────────────────────────────────────────────────────────────────
# reconcile_payment — frontend-driven fallback when webhook can't reach localhost
# ─────────────────────────────────────────────────────────────────────────────


async def reconcile_payment(
    uow,
    current_user,
    pedido_id: uuid.UUID,
    payment_id: int | None,
    external_reference: str | None,
) -> dict[str, Any]:
    """Reconcile a Pago against MercadoPago after the user returned from Checkout Pro.

    Use case: in local development MP webhook servers cannot reach localhost,
    so the Pago stays in ``mp_status="pending"`` even after the user paid.
    The frontend CheckoutReturnPage calls this endpoint with the ``payment_id``
    that MP appended to the back_url to force a re-query and FSM transition.

    Reuses the exact same code path as the webhook handler
    (``_process_approved_payment``) so the FSM, historial entry and stock
    decrement remain consistent.

    Steps:
      1. Load Pedido; ownership check vs current_user (404 if not owned).
      2. Verify pedido.forma_pago_codigo == "MERCADOPAGO" (409 otherwise).
      3. Load latest Pago for the pedido (404 if none).
      4. If pago.mp_status is already "approved" → idempotency short-circuit.
      5. Require payment_id (we do not implement MP search-by-external-reference).
      6. Re-query MP API for the real payment.
      7. Validate mp_payment["external_reference"] == str(pedido_id) (409 otherwise).
      8. Assign mp_payment_id on the Pago if still NULL.
      9. If real status == "approved" → reuse _process_approved_payment.
         Else → update mp_status / mp_status_detail only.

    Args:
        uow: Active UnitOfWork.
        current_user: Authenticated user (the pedido owner).
        pedido_id: UUID of the order to reconcile.
        payment_id: MercadoPago payment ID from the back_url query param.
        external_reference: Echo of external_reference from the back_url (optional,
            used only for coherence; pedido_id is the authoritative key).

    Returns:
        dict with keys: ``status`` ("ok"), ``mp_status``, ``pedido_estado``,
        and ``already_processed`` (bool).

    Raises:
        HTTPException 400: payment_id missing (PAYMENT_ID_REQUIRED).
        HTTPException 404: pedido not found or not owned (ORDER_NOT_FOUND).
        HTTPException 409: pedido not MERCADOPAGO (PAYMENT_METHOD_MISMATCH).
        HTTPException 404: no Pago row for this pedido (PAYMENT_NOT_FOUND).
        HTTPException 409: external_reference mismatch (EXTERNAL_REFERENCE_MISMATCH).
        HTTPException 502: MP API error (MP_RECONCILE_ERROR).
    """
    # Step 1: Load pedido + ownership check.
    # We return 404 (not 403) when the pedido belongs to another user to avoid
    # leaking pedido existence to unauthorized callers.
    pedido = await uow.pedidos.get_by_id(pedido_id)
    if pedido is None or pedido.usuario_id != current_user.id:
        raise HTTPException(
            status_code=404,
            detail={"detail": "El pedido no fue encontrado.", "code": "ORDER_NOT_FOUND"},
        )

    # Step 2: Payment method check — only MP pedidos can be reconciled.
    if pedido.forma_pago_codigo != "MERCADOPAGO":
        raise HTTPException(
            status_code=409,
            detail={
                "detail": "La forma de pago del pedido no es MercadoPago.",
                "code": "PAYMENT_METHOD_MISMATCH",
            },
        )

    # Step 3: Load latest Pago row for this pedido.
    pago = await uow.pagos.get_latest_by_pedido_id(pedido_id)
    if pago is None:
        raise HTTPException(
            status_code=404,
            detail={"detail": "No se encontró ningún pago para este pedido.", "code": "PAYMENT_NOT_FOUND"},
        )

    # Step 4: Idempotency — never reprocess a terminal-approved Pago.
    if pago.mp_status == "approved":
        return {
            "status": "ok",
            "mp_status": "approved",
            "pedido_estado": pedido.estado_codigo,
            "already_processed": True,
        }

    # Step 5: payment_id is required. external_reference-only lookup would
    # require MP search API; we keep this minimal and explicit.
    if payment_id is None:
        raise HTTPException(
            status_code=400,
            detail={
                "detail": "Se requiere payment_id para reconciliar el pago.",
                "code": "PAYMENT_ID_REQUIRED",
            },
        )

    # Step 6: Re-query MP API (same source of truth as the webhook).
    settings_for_reconcile = get_settings()
    _mp_token = settings_for_reconcile.MP_ACCESS_TOKEN or ""
    _has_real_creds = _mp_token.startswith("APP_USR-") or _mp_token.startswith("TEST-")

    if settings_for_reconcile.ENVIRONMENT == "development" and not _has_real_creds:
        # Dev mode, no real MP credentials: simulate approved payment.
        real_status = "approved"
        real_status_detail = "mock_dev_approved"
        logger.info(
            "reconcile.mock_dev_approved",
            pedido_id=str(pedido_id),
            payment_id=payment_id,
        )
    else:
        try:
            mp_payment = mp_client.get_payment(payment_id)
        except MercadoPagoAPIError as exc:
            logger.error(
                "reconcile.mp_requery_failed",
                pedido_id=str(pedido_id),
                payment_id=payment_id,
                status_code=exc.status_code,
            )
            raise HTTPException(
                status_code=502,
                detail={
                    "detail": "Error al consultar MercadoPago.",
                    "code": "MP_RECONCILE_ERROR",
                },
            )

        real_status: str = mp_payment.get("status", "unknown")
        real_status_detail: str | None = mp_payment.get("status_detail")
        mp_external_reference: str | None = mp_payment.get("external_reference")

        # Step 7: external_reference must match the pedido_id we received.
        if mp_external_reference != str(pedido_id) or (
            external_reference is not None and external_reference != str(pedido_id)
        ):
            logger.error(
                "reconcile.external_reference_mismatch",
                pedido_id=str(pedido_id),
                payment_id=payment_id,
                mp_external_reference=mp_external_reference,
                client_external_reference=external_reference,
            )
            raise HTTPException(
                status_code=409,
                detail={
                    "detail": "El pago no corresponde a este pedido.",
                    "code": "EXTERNAL_REFERENCE_MISMATCH",
                },
            )

    # Step 8: Assign mp_payment_id if still NULL (first-time path).
    if pago.mp_payment_id is None:
        pago.mp_payment_id = payment_id
        await uow._session.flush()

    # Step 9: Branch on real_status.
    if real_status == "approved":
        # Reuse the exact webhook FSM path so historial + stock decrement run.
        await _process_approved_payment(
            uow=uow,
            pago=pago,
            mp_payment_id=payment_id,
            pedido_id=pedido_id,
            real_status_detail=real_status_detail,
        )
    else:
        # Non-approved: update mp_status only (no FSM transition).
        pago.mp_status = real_status
        pago.mp_status_detail = real_status_detail
        await uow._session.flush()
        logger.info(
            "reconcile.pago_status_updated",
            payment_id=payment_id,
            pedido_id=str(pedido_id),
            new_status=real_status,
        )

    # Re-fetch pedido state for the response (FSM may have advanced).
    # Use existing loaded pedido reference — _process_approved_payment updated it.
    pedido_after = await uow.pedidos.get_by_id(pedido_id)
    pedido_estado = pedido_after.estado_codigo if pedido_after is not None else pedido.estado_codigo

    return {
        "status": "ok",
        "mp_status": pago.mp_status,
        "pedido_estado": pedido_estado,
        "already_processed": False,
    }
