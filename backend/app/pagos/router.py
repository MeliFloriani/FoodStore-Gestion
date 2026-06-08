"""
Pagos router — HTTP endpoints for the payments module.

Change 19 — payments-mercadopago-integration (Checkout Pro migration).

Endpoints (mounted at prefix="/pagos" in build_v1_router):
  POST /              → POST /api/v1/pagos         (start Checkout Pro, CLIENT)
  POST /webhook       → POST /api/v1/pagos/webhook  (IPN handler, public)
  POST /crear         → POST /api/v1/pagos/crear    (alias for POST /, D-11)
  GET  /{pedido_id}/latest → GET /api/v1/pagos/{pedido_id}/latest (CLIENT+PEDIDOS+ADMIN)

Declaration order (task 10.2/10.4):
  1. POST /           (static — must be first)
  2. POST /webhook    (static — must be before dynamic routes)
  3. POST /crear      (static alias — must be before dynamic routes)
  4. GET  /{pedido_id}/latest  (dynamic — last to avoid shadowing static paths)

Design decisions:
  D-02: Webhook handler is inline synchronous — no BackgroundTasks.
  D-11: POST /crear is an alias for POST / for Integrador §5.4 compatibility.
  Checkout Pro: POST / returns preference_id + init_point + sandbox_init_point.
    Frontend redirects user to init_point (prod) or sandbox_init_point (dev).
  Stock rollback path: if _process_approved_payment raises InsufficientStockError,
    the router catches it, logs STOCK_DECREMENT_FAILED_AFTER_PAYMENT_APPROVED,
    and returns HTTP 200 (stock error must not cause MP retries).

session.commit() is NEVER called here — UnitOfWork owns the commit via get_uow.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Header, Query, Request, status

from app.api.deps import require_role
from app.core.uow import UnitOfWork, get_uow  # get_uow used in create/get endpoints
from app.models.user import Usuario
from app.pagos.schemas import (
    PagoCreateRequest,
    PagoReconcileRequest,
    PagoReconcileResponse,
    PagoResponse,
)
from app.core.logging import get_logger

logger = get_logger(__name__)

pagos_router = APIRouter()


# ─────────────────────────────────────────────────────────────────────────────
# POST / — Create MP payment (CLIENT only)
# ─────────────────────────────────────────────────────────────────────────────


async def _handle_create_payment(
    data: PagoCreateRequest,
    uow: UnitOfWork,
    current_user: Usuario,
) -> PagoResponse:
    """Shared handler for POST / and POST /crear.

    Called by both the canonical endpoint and the alias (D-11).
    Delegates to start_checkout_pro() which creates an MP Checkout Pro preference.
    """
    from app.pagos.service import start_checkout_pro

    return await start_checkout_pro(uow=uow, current_user=current_user, data=data)


@pagos_router.post(
    "/",
    response_model=PagoResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Iniciar pago MercadoPago Checkout Pro",
    tags=["pagos"],
)
async def create_payment_endpoint(
    data: PagoCreateRequest,
    uow: UnitOfWork = Depends(get_uow),
    current_user: Usuario = Depends(require_role("CLIENT")),
) -> PagoResponse:
    """POST /api/v1/pagos — create a MercadoPago Checkout Pro preference.

    Auth: CLIENT role required.
    Body: { pedido_id: UUID, idempotency_key: str (min 8 chars) }
    Response: 201 PagoResponse with preference_id, init_point, sandbox_init_point.

    Frontend redirects the user to sandbox_init_point (dev) or init_point (prod).

    Error codes:
      404 ORDER_NOT_FOUND — pedido_id does not exist.
      403 ORDER_NOT_OWNED — pedido belongs to another user.
      409 ORDER_NOT_PAYABLE — order is not in PENDIENTE state.
      409 PAYMENT_METHOD_MISMATCH — order forma_pago_codigo != MERCADOPAGO.
      502 MP_PREFERENCE_ERROR — MercadoPago preference creation failed.
    """
    return await _handle_create_payment(data=data, uow=uow, current_user=current_user)


# ─────────────────────────────────────────────────────────────────────────────
# POST /webhook — IPN handler (public, no JWT)
# ─────────────────────────────────────────────────────────────────────────────


@pagos_router.post(
    "/webhook",
    summary="MercadoPago IPN webhook handler",
    tags=["pagos"],
)
async def webhook_endpoint(
    request: Request,
    webhook_type: str = Query(alias="type", default=""),
    data_id: str = Query(alias="data.id", default=""),
    x_signature: str = Header(alias="x-signature", default=""),
    x_request_id: str = Header(alias="x-request-id", default=""),
) -> dict[str, str]:
    """POST /api/v1/pagos/webhook — receive MercadoPago IPN notifications.

    Auth: Public (no JWT). Verified via HMAC-SHA256 x-signature header.

    D-02: Processing is inline synchronous. Returns HTTP 200 after UoW commits.
    D-08: HMAC verification with 5-minute timestamp freshness window.

    Returns HTTP 400 for:
      INVALID_SIGNATURE — HMAC mismatch.
      WEBHOOK_EXPIRED — timestamp older than 5 minutes.

    Returns HTTP 200 for all other cases (including processing errors that
    should not cause MP to retry, e.g. insufficient stock after approved payment).

    Note: This handler opens its OWN UoW (not via Depends(get_uow)) to handle
    the InsufficientStockError path — when stock fails, we need the UoW to
    rollback (which happens inside the 'async with UnitOfWork()' block) and then
    still return HTTP 200 to prevent MercadoPago from retrying.
    """
    from app.pagos.service import InsufficientStockError, process_webhook

    # Open a dedicated UoW for the webhook handler.
    # This allows us to handle the stock rollback path while still returning 200.
    # The InsufficientStockError path:
    #   1. _process_approved_payment raises InsufficientStockError
    #   2. process_webhook propagates it out of the 'async with UnitOfWork()' block
    #   3. UoW.__aexit__ sees the exception and rollbacks the transaction
    #   4. We catch InsufficientStockError OUTSIDE the 'async with' block
    #   5. Return 200 to MP (preventing retries)
    stock_error: InsufficientStockError | None = None
    try:
        async with UnitOfWork() as uow:
            result = await process_webhook(
                webhook_type=webhook_type,
                data_id=data_id,
                x_signature=x_signature,
                x_request_id=x_request_id,
                uow=uow,
            )
    except InsufficientStockError as exc:
        # D-05 / task 11.6: stock decrement failed after payment approved.
        # UoW has already rolled back (the 'async with' block re-raised the exception).
        # Log structured error and return 200 to prevent MP retries.
        logger.error(
            "STOCK_DECREMENT_FAILED_AFTER_PAYMENT_APPROVED",
            data_id=data_id,
            error=str(exc),
        )
        return {"status": "ok"}

    return result


# ─────────────────────────────────────────────────────────────────────────────
# POST /crear — alias for POST / (D-11, Integrador §5.4 compatibility)
# ─────────────────────────────────────────────────────────────────────────────


@pagos_router.post(
    "/crear",
    response_model=PagoResponse,
    status_code=status.HTTP_201_CREATED,
    summary="[Alias] Iniciar pago MercadoPago Checkout Pro (compatibilidad Integrador §5.4)",
    tags=["pagos"],
)
async def create_payment_alias_endpoint(
    data: PagoCreateRequest,
    uow: UnitOfWork = Depends(get_uow),
    current_user: Usuario = Depends(require_role("CLIENT")),
) -> PagoResponse:
    """POST /api/v1/pagos/crear — alias for POST /api/v1/pagos.

    Added for Integrador §5.4 rubric compatibility (D-11).
    Same handler, same auth, same response as POST /.
    """
    return await _handle_create_payment(data=data, uow=uow, current_user=current_user)


# ─────────────────────────────────────────────────────────────────────────────
# POST /reconcile — frontend-driven reconcile when MP webhook can't reach localhost
# ─────────────────────────────────────────────────────────────────────────────


@pagos_router.post(
    "/reconcile",
    response_model=PagoReconcileResponse,
    summary="Reconciliar pago contra MercadoPago (fallback de webhook)",
    tags=["pagos"],
)
async def reconcile_payment_endpoint(
    data: PagoReconcileRequest,
    uow: UnitOfWork = Depends(get_uow),
    current_user: Usuario = Depends(require_role("CLIENT")),
) -> PagoReconcileResponse:
    """POST /api/v1/pagos/reconcile — re-query MP and apply the same state
    transitions as the webhook would.

    Used by the frontend CheckoutReturnPage when MP redirects the user back
    to /checkout/return. In local development the MP webhook servers cannot
    reach localhost, so this endpoint lets the client trigger reconciliation.

    Auth: CLIENT (owner of the pedido).
    Body: { pedido_id: UUID, payment_id: int | None, external_reference: str | None }

    Error codes:
      400 PAYMENT_ID_REQUIRED — payment_id missing.
      404 ORDER_NOT_FOUND — pedido not found or not owned by current user.
      409 PAYMENT_METHOD_MISMATCH — pedido.forma_pago_codigo != MERCADOPAGO.
      404 PAYMENT_NOT_FOUND — no Pago row exists for this pedido.
      409 EXTERNAL_REFERENCE_MISMATCH — MP payment.external_reference != pedido_id.
      502 MP_RECONCILE_ERROR — MercadoPago API call failed.
    """
    from app.pagos.service import reconcile_payment

    result = await reconcile_payment(
        uow=uow,
        current_user=current_user,
        pedido_id=data.pedido_id,
        payment_id=data.payment_id,
        external_reference=data.external_reference,
    )
    return PagoReconcileResponse(**result)


# ─────────────────────────────────────────────────────────────────────────────
# GET /{pedido_id}/latest — latest Pago for a pedido (CLIENT+PEDIDOS+ADMIN)
# ─────────────────────────────────────────────────────────────────────────────


@pagos_router.get(
    "/{pedido_id}/latest",
    response_model=PagoResponse,
    summary="Obtener último pago de un pedido",
    tags=["pagos"],
)
async def get_latest_payment_endpoint(
    pedido_id: uuid.UUID,
    uow: UnitOfWork = Depends(get_uow),
    current_user: Usuario = Depends(require_role("CLIENT", "PEDIDOS", "ADMIN")),
) -> PagoResponse:
    """GET /api/v1/pagos/{pedido_id}/latest — latest Pago for a given pedido.

    Auth: CLIENT (own pedido only), PEDIDOS (any), ADMIN (any).

    Error codes:
      404 ORDER_NOT_FOUND — pedido_id does not exist.
      403 ORDER_NOT_OWNED — CLIENT attempting to view another user's payment.
      404 PAYMENT_NOT_FOUND — no Pago exists for this pedido.
    """
    from app.pagos.service import get_latest_payment

    return await get_latest_payment(
        uow=uow,
        current_user=current_user,
        pedido_id=pedido_id,
    )
