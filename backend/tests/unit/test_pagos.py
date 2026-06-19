"""
Unit tests for the pagos module.

Change 19 — payments-mercadopago-integration (Checkout Pro migration).

Test coverage:
  - MercadoPagoClient: create_preference, get_payment, MercadoPagoAPIError (task 3.5 / 19.1)
  - PagoRepository: get_by_mp_payment_id, get_latest_by_pedido_id (task 6.2)
  - PagoService.start_checkout_pro: all error paths + success (tasks 19.2, 19.3)
  - PagoService idempotency: same idempotency_key returns existing row (task 19.2)
  - Webhook: signature verification (tasks 11.9, 17.3, 17.4)
  - Webhook: approved flow, idempotency, rejected, stock rollback (tasks 17.5-17.8)
  - Webhook: assigns mp_payment_id on first webhook (task 19.4)
  - PagoRepository: get_latest_payment_404, two rows (tasks 17.9, 17.10)
  - Additional: stale timestamp, non-approved → approved path (tasks 17.11, 17.12)

Design decisions:
  - All tests are unit tests using mocks — no real DB or MP API calls.
  - Integration tests requiring real PostgreSQL are marked @pytest.mark.integration.
  - Tests mock uow, mp_client, and async repo methods as needed.
"""

from __future__ import annotations

import hashlib
import hmac
import time
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.pagos.schemas import PagoCreateRequest, PagoResponse
from app.pagos.service import InsufficientStockError, verify_webhook_signature


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────


def make_pago(
    pedido_id: uuid.UUID | None = None,
    mp_payment_id: int | None = None,
    mp_preference_id: str | None = None,
    mp_status: str = "pending",
    mp_status_detail: str | None = None,
    idempotency_key: str | None = None,
    external_reference: str | None = None,
    monto: float = 150.00,
    created_at: datetime | None = None,
) -> MagicMock:
    """Create a mock Pago ORM object."""
    pago = MagicMock()
    pago.id = uuid.uuid4()
    pago.pedido_id = pedido_id or uuid.uuid4()
    pago.mp_payment_id = mp_payment_id
    pago.mp_preference_id = mp_preference_id or f"PREF-{uuid.uuid4()}"
    pago.mp_status = mp_status
    pago.mp_status_detail = mp_status_detail
    pago.idempotency_key = idempotency_key or str(uuid.uuid4())
    pago.external_reference = external_reference or str(pago.pedido_id)
    pago.monto = Decimal(str(monto))
    pago.created_at = created_at or datetime.now(timezone.utc)
    pago.deleted_at = None
    return pago


def make_pedido(
    estado_codigo: str = "PENDIENTE",
    forma_pago_codigo: str = "MERCADOPAGO",
    usuario_id: uuid.UUID | None = None,
    total: float = 150.00,
) -> MagicMock:
    """Create a mock Pedido ORM object."""
    pedido = MagicMock()
    pedido.id = uuid.uuid4()
    pedido.usuario_id = usuario_id or uuid.uuid4()
    pedido.estado_codigo = estado_codigo
    pedido.forma_pago_codigo = forma_pago_codigo
    pedido.total = Decimal(str(total))
    return pedido


def make_current_user(user_id: uuid.UUID | None = None, roles: list[str] | None = None) -> MagicMock:
    """Create a mock authenticated user."""
    user = MagicMock()
    user.id = user_id or uuid.uuid4()
    # Build usuario_roles with rol.codigo
    user_roles_list = []
    for role in (roles or ["CLIENT"]):
        ur = MagicMock()
        ur.rol = MagicMock()
        ur.rol.codigo = role
        ur.deleted_at = None
        user_roles_list.append(ur)
    user.usuario_roles = user_roles_list
    return user


def make_uow() -> MagicMock:
    """Create a mock UnitOfWork."""
    uow = MagicMock()
    uow.pagos = AsyncMock()
    uow.pedidos = AsyncMock()
    uow.historial_pedido = AsyncMock()
    uow.productos = AsyncMock()
    uow._session = AsyncMock()
    return uow


def make_valid_x_signature(
    data_id: str,
    request_id: str,
    webhook_secret: str,
    ts: int | None = None,
) -> tuple[str, str]:
    """Generate a valid x-signature header for testing.

    Returns (x_signature, ts_str) tuple.
    """
    if ts is None:
        ts = int(time.time())
    ts_str = str(ts)
    composed = f"id:{data_id};request-id:{request_id};ts:{ts_str}"
    signature = hmac.new(
        webhook_secret.encode("utf-8"),
        composed.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    x_signature = f"ts={ts_str},v1={signature}"
    return x_signature, ts_str


# ─────────────────────────────────────────────────────────────────────────────
# Task 3.5 / 19.1 — MercadoPagoClient tests
# ─────────────────────────────────────────────────────────────────────────────


class TestMercadoPagoClient:
    """Tests for MercadoPagoClient.create_preference and get_payment."""

    def test_create_preference_raises_on_400(self):
        """MercadoPagoAPIError raised when MP API returns status >= 400 (19.1)."""
        from app.integrations.mercadopago_client import MercadoPagoAPIError, MercadoPagoClient

        client = MercadoPagoClient.__new__(MercadoPagoClient)
        mock_sdk = MagicMock()
        client._sdk = mock_sdk

        mock_sdk.preference().create.return_value = {
            "status": 400,
            "response": {"message": "Bad request", "error": "bad_request"},
        }

        with pytest.raises(MercadoPagoAPIError) as exc_info:
            client.create_preference(
                items=[{"title": "Pedido test", "unit_price": 100.0, "quantity": 1, "currency_id": "ARS"}],
                external_reference=str(uuid.uuid4()),
                notification_url="https://example.com/webhook",
                back_urls={"success": "https://example.com/return?status=success&pedido_id=x"},
                idempotency_key="test-key-123",
            )

        assert exc_info.value.status_code == 400

    def test_get_payment_raises_on_404(self):
        """MercadoPagoAPIError is raised when get_payment returns 404 (task 3.5)."""
        from app.integrations.mercadopago_client import MercadoPagoAPIError, MercadoPagoClient

        client = MercadoPagoClient.__new__(MercadoPagoClient)
        mock_sdk = MagicMock()
        client._sdk = mock_sdk

        mock_sdk.payment().get.return_value = {
            "status": 404,
            "response": {"message": "Not found"},
        }

        with pytest.raises(MercadoPagoAPIError) as exc_info:
            client.get_payment(9999999)

        assert exc_info.value.status_code == 404

    def test_create_preference_passes_idempotency_key(self):
        """create_preference passes X-Idempotency-Key header (19.1)."""
        from app.integrations.mercadopago_client import MercadoPagoClient

        client = MercadoPagoClient.__new__(MercadoPagoClient)
        mock_sdk = MagicMock()
        client._sdk = mock_sdk

        mock_sdk.preference().create.return_value = {
            "status": 201,
            "response": {
                "id": "PREF-123",
                "init_point": "https://www.mercadopago.com.ar/checkout/v1/redirect?pref_id=PREF-123",
                "sandbox_init_point": "https://sandbox.mercadopago.com.ar/checkout/v1/redirect?pref_id=PREF-123",
            },
        }

        result = client.create_preference(
            items=[{"title": "Pedido", "unit_price": 100.0, "quantity": 1, "currency_id": "ARS"}],
            external_reference="pedido-uuid",
            notification_url="https://example.com/webhook",
            back_urls={"success": "https://example.com/return?status=success&pedido_id=x"},
            idempotency_key="my-idempotency-key-abc123",
        )

        # Verify the SDK was called with request_options that have X-Idempotency-Key
        call_args = mock_sdk.preference().create.call_args
        request_options = call_args[0][1]  # Second positional arg
        assert request_options.custom_headers.get("X-Idempotency-Key") == "my-idempotency-key-abc123"
        assert result["id"] == "PREF-123"
        assert "init_point" in result
        assert "sandbox_init_point" in result

    def test_get_payment_success(self):
        """get_payment returns dict on success (task 3.5)."""
        from app.integrations.mercadopago_client import MercadoPagoClient

        client = MercadoPagoClient.__new__(MercadoPagoClient)
        mock_sdk = MagicMock()
        client._sdk = mock_sdk

        mock_sdk.payment().get.return_value = {
            "status": 200,
            "response": {"id": 123, "status": "approved"},
        }

        result = client.get_payment(123)
        assert result["status"] == "approved"
        assert result["id"] == 123


# ─────────────────────────────────────────────────────────────────────────────
# Task 6.2 — PagoRepository tests
# ─────────────────────────────────────────────────────────────────────────────


class TestPagoRepository:
    """Tests for PagoRepository query methods (task 6.2)."""

    @pytest.mark.asyncio
    async def test_get_by_mp_payment_id_returns_none_on_miss(self):
        """get_by_mp_payment_id returns None when no row matches (task 6.2)."""
        from app.pagos.repository import PagoRepository

        execute_result = MagicMock()
        execute_result.scalars.return_value.first.return_value = None

        session = AsyncMock()
        session.execute.return_value = execute_result

        repo = PagoRepository(session)
        result = await repo.get_by_mp_payment_id(9999999)

        assert result is None

    @pytest.mark.asyncio
    async def test_get_latest_by_pedido_id_returns_most_recent(self):
        """get_latest_by_pedido_id returns the row with later created_at (task 6.2)."""
        from app.pagos.repository import PagoRepository

        pedido_id = uuid.uuid4()
        older_pago = make_pago(
            pedido_id=pedido_id,
            created_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
        )
        newer_pago = make_pago(
            pedido_id=pedido_id,
            created_at=datetime(2025, 1, 2, tzinfo=timezone.utc),
        )

        execute_result = MagicMock()
        execute_result.scalars.return_value.first.return_value = newer_pago

        session = AsyncMock()
        session.execute.return_value = execute_result

        repo = PagoRepository(session)
        result = await repo.get_latest_by_pedido_id(pedido_id)

        assert result == newer_pago
        assert result.created_at > older_pago.created_at


# ─────────────────────────────────────────────────────────────────────────────
# Tasks 19.2, 19.3 — PagoService.start_checkout_pro
# ─────────────────────────────────────────────────────────────────────────────


class TestStartCheckoutProService:
    """Unit tests for start_checkout_pro service function (Checkout Pro)."""

    def _make_request(self, pedido_id: uuid.UUID | None = None, idempotency_key: str | None = None) -> PagoCreateRequest:
        return PagoCreateRequest(
            pedido_id=pedido_id or uuid.uuid4(),
            idempotency_key=idempotency_key or str(uuid.uuid4()),
        )

    @pytest.mark.asyncio
    async def test_start_checkout_pro_404_unknown_pedido(self):
        """start_checkout_pro raises 404 ORDER_NOT_FOUND for unknown pedido (19.3)."""
        from app.pagos.service import start_checkout_pro

        uow = make_uow()
        uow.pedidos.get_by_id.return_value = None
        current_user = make_current_user()
        data = self._make_request()

        with pytest.raises(HTTPException) as exc_info:
            await start_checkout_pro(uow=uow, current_user=current_user, data=data)

        assert exc_info.value.status_code == 404
        assert exc_info.value.detail["code"] == "ORDER_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_start_checkout_pro_403_not_owned(self):
        """start_checkout_pro raises 403 ORDER_NOT_OWNED when pedido belongs to another user."""
        from app.pagos.service import start_checkout_pro

        other_user_id = uuid.uuid4()
        pedido = make_pedido(usuario_id=other_user_id)
        uow = make_uow()
        uow.pedidos.get_by_id.return_value = pedido

        current_user = make_current_user(user_id=uuid.uuid4())  # Different user
        data = self._make_request(pedido_id=pedido.id)

        with pytest.raises(HTTPException) as exc_info:
            await start_checkout_pro(uow=uow, current_user=current_user, data=data)

        assert exc_info.value.status_code == 403
        assert exc_info.value.detail["code"] == "ORDER_NOT_OWNED"

    @pytest.mark.asyncio
    async def test_start_checkout_pro_409_not_payable(self):
        """start_checkout_pro raises 409 ORDER_NOT_PAYABLE for non-PENDIENTE order."""
        from app.pagos.service import start_checkout_pro

        user_id = uuid.uuid4()
        pedido = make_pedido(estado_codigo="CONFIRMADO", usuario_id=user_id)
        uow = make_uow()
        uow.pedidos.get_by_id.return_value = pedido

        current_user = make_current_user(user_id=user_id)
        data = self._make_request(pedido_id=pedido.id)

        with pytest.raises(HTTPException) as exc_info:
            await start_checkout_pro(uow=uow, current_user=current_user, data=data)

        assert exc_info.value.status_code == 409
        assert exc_info.value.detail["code"] == "ORDER_NOT_PAYABLE"

    @pytest.mark.asyncio
    async def test_start_checkout_pro_409_payment_method_mismatch(self):
        """start_checkout_pro raises 409 PAYMENT_METHOD_MISMATCH for non-MP pedido."""
        from app.pagos.service import start_checkout_pro

        user_id = uuid.uuid4()
        pedido = make_pedido(forma_pago_codigo="EFECTIVO", usuario_id=user_id)
        uow = make_uow()
        uow.pedidos.get_by_id.return_value = pedido

        current_user = make_current_user(user_id=user_id)
        data = self._make_request(pedido_id=pedido.id)

        with pytest.raises(HTTPException) as exc_info:
            await start_checkout_pro(uow=uow, current_user=current_user, data=data)

        assert exc_info.value.status_code == 409
        assert exc_info.value.detail["code"] == "PAYMENT_METHOD_MISMATCH"

    @pytest.mark.asyncio
    async def test_start_checkout_pro_502_mp_error(self):
        """start_checkout_pro raises 502 MP_PREFERENCE_ERROR when MP API fails."""
        from app.integrations.mercadopago_client import MercadoPagoAPIError
        from app.pagos.service import start_checkout_pro

        user_id = uuid.uuid4()
        pedido = make_pedido(usuario_id=user_id)
        uow = make_uow()
        uow.pedidos.get_by_id.return_value = pedido
        uow.pagos.get_by_idempotency_key.return_value = None

        current_user = make_current_user(user_id=user_id)
        data = self._make_request(pedido_id=pedido.id)

        with patch("app.pagos.service.mp_client") as mock_mp:
            mock_mp.create_preference.side_effect = MercadoPagoAPIError(
                "MP error", status_code=422
            )
            with patch("app.pagos.service.get_settings") as mock_settings:
                mock_settings.return_value.MP_NOTIFICATION_URL = "https://example.com/webhook"
                mock_settings.return_value.FRONTEND_BASE_URL = "http://localhost:5173"

                with pytest.raises(HTTPException) as exc_info:
                    await start_checkout_pro(uow=uow, current_user=current_user, data=data)

        assert exc_info.value.status_code == 502
        assert exc_info.value.detail["code"] == "MP_PREFERENCE_ERROR"

    @pytest.mark.asyncio
    async def test_start_checkout_pro_creates_preference(self):
        """start_checkout_pro inserts Pago row with preference_id (task 19.2)."""
        from app.pagos.service import start_checkout_pro

        user_id = uuid.uuid4()
        pedido = make_pedido(usuario_id=user_id)
        pedido_id_str = str(pedido.id)
        idempotency_key = str(uuid.uuid4())

        mp_response = {
            "id": "PREF-ABC123",
            "init_point": "https://www.mercadopago.com.ar/checkout/v1/redirect?pref_id=PREF-ABC123",
            "sandbox_init_point": "https://sandbox.mercadopago.com.ar/checkout/v1/redirect?pref_id=PREF-ABC123",
        }

        expected_pago = make_pago(
            pedido_id=pedido.id,
            mp_payment_id=None,  # NULL until webhook
            mp_preference_id="PREF-ABC123",
            mp_status="pending",
            idempotency_key=idempotency_key,
        )
        expected_pago.external_reference = pedido_id_str

        uow = make_uow()
        uow.pedidos.get_by_id.return_value = pedido
        uow.pagos.get_by_idempotency_key.return_value = None
        uow.pagos.create.return_value = expected_pago

        current_user = make_current_user(user_id=user_id)
        data = PagoCreateRequest(pedido_id=pedido.id, idempotency_key=idempotency_key)

        with patch("app.pagos.service.mp_client") as mock_mp:
            mock_mp.create_preference.return_value = mp_response
            with patch("app.pagos.service.get_settings") as mock_settings:
                mock_settings.return_value.MP_NOTIFICATION_URL = "https://example.com/webhook"
                mock_settings.return_value.FRONTEND_BASE_URL = "http://localhost:5173"

                result = await start_checkout_pro(uow=uow, current_user=current_user, data=data)

        # Verify Pago was created
        uow.pagos.create.assert_called_once()
        created_pago_arg = uow.pagos.create.call_args[0][0]

        # mp_payment_id must be None (assigned later by webhook)
        assert created_pago_arg.mp_payment_id is None

        # mp_preference_id must be set
        assert created_pago_arg.mp_preference_id == "PREF-ABC123"

        # external_reference must be the pedido UUID string
        assert created_pago_arg.external_reference == pedido_id_str

        # Response must include preference data
        assert isinstance(result, PagoResponse)
        assert result.preference_id == "PREF-ABC123"
        assert result.init_point is not None
        assert result.sandbox_init_point is not None

    @pytest.mark.asyncio
    async def test_start_checkout_pro_idempotent_returns_existing(self):
        """start_checkout_pro returns existing Pago when same idempotency_key (task 19.2)."""
        from app.pagos.service import start_checkout_pro

        user_id = uuid.uuid4()
        pedido = make_pedido(usuario_id=user_id)
        idempotency_key = str(uuid.uuid4())

        existing_pago = make_pago(
            pedido_id=pedido.id,
            mp_preference_id="PREF-EXISTING",
            mp_status="pending",
            idempotency_key=idempotency_key,
        )

        uow = make_uow()
        uow.pedidos.get_by_id.return_value = pedido
        uow.pagos.get_by_idempotency_key.return_value = existing_pago

        current_user = make_current_user(user_id=user_id)
        data = PagoCreateRequest(pedido_id=pedido.id, idempotency_key=idempotency_key)

        with patch("app.pagos.service.get_settings") as mock_settings:
            mock_settings.return_value.MP_NOTIFICATION_URL = "https://example.com/webhook"
            mock_settings.return_value.FRONTEND_BASE_URL = "http://localhost:5173"

            result = await start_checkout_pro(uow=uow, current_user=current_user, data=data)

        # Should NOT have created a new Pago
        uow.pagos.create.assert_not_called()
        assert isinstance(result, PagoResponse)
        assert result.preference_id == "PREF-EXISTING"


# ─────────────────────────────────────────────────────────────────────────────
# Tasks 17.3, 17.4, 11.9 — Webhook signature verification
# ─────────────────────────────────────────────────────────────────────────────


class TestWebhookSignatureVerification:
    """Tests for verify_webhook_signature (tasks 11.9, 17.3, 17.4)."""

    def test_valid_signature_passes(self):
        """Correct signature passes verification without raising (task 17.3)."""
        data_id = "123456"
        request_id = "req-uuid-1234"
        secret = "my-webhook-secret"

        x_sig, _ = make_valid_x_signature(data_id, request_id, secret)

        # Should not raise
        verify_webhook_signature(x_sig, request_id, data_id, secret)

    def test_invalid_signature_raises_400(self):
        """Tampered data_id raises INVALID_SIGNATURE (task 17.4)."""
        data_id = "123"
        request_id = "req-uuid"
        secret = "my-secret"

        x_sig, _ = make_valid_x_signature(data_id, request_id, secret)

        with pytest.raises(HTTPException) as exc_info:
            verify_webhook_signature(x_sig, request_id, "456", secret)

        assert exc_info.value.status_code == 400
        assert exc_info.value.detail["code"] == "INVALID_SIGNATURE"

    def test_wrong_secret_raises_400(self):
        """Wrong secret raises INVALID_SIGNATURE (task 11.9)."""
        data_id = "123"
        request_id = "req-uuid"

        x_sig, _ = make_valid_x_signature(data_id, request_id, "correct-secret")

        with pytest.raises(HTTPException) as exc_info:
            verify_webhook_signature(x_sig, request_id, data_id, "wrong-secret")

        assert exc_info.value.status_code == 400
        assert exc_info.value.detail["code"] == "INVALID_SIGNATURE"

    def test_stale_timestamp_raises_webhook_expired(self):
        """Stale timestamp (> 5 minutes) raises WEBHOOK_EXPIRED (task 17.11)."""
        data_id = "123"
        request_id = "req-uuid"
        secret = "my-secret"

        stale_ts = int(time.time()) - 360  # 6 minutes ago
        x_sig, _ = make_valid_x_signature(data_id, request_id, secret, ts=stale_ts)

        with pytest.raises(HTTPException) as exc_info:
            verify_webhook_signature(x_sig, request_id, data_id, secret)

        assert exc_info.value.status_code == 400
        assert exc_info.value.detail["code"] == "WEBHOOK_EXPIRED"

    def test_fresh_timestamp_passes(self):
        """Timestamp within 5 minutes passes freshness check (task 17.11)."""
        data_id = "123"
        request_id = "req-uuid"
        secret = "my-secret"

        fresh_ts = int(time.time()) - 60  # 1 minute ago (within 300s window)
        x_sig, _ = make_valid_x_signature(data_id, request_id, secret, ts=fresh_ts)

        # Should not raise
        verify_webhook_signature(x_sig, request_id, data_id, secret)

    def test_missing_ts_raises_invalid_signature(self):
        """Missing ts in x-signature raises INVALID_SIGNATURE."""
        with pytest.raises(HTTPException) as exc_info:
            verify_webhook_signature(
                "v1=somehash",  # No ts= part
                "req-uuid",
                "data-id",
                "secret",
            )
        assert exc_info.value.status_code == 400
        assert exc_info.value.detail["code"] == "INVALID_SIGNATURE"


# ─────────────────────────────────────────────────────────────────────────────
# Task 17.5 — test_webhook_approved_triggers_confirmado
# ─────────────────────────────────────────────────────────────────────────────


class TestWebhookApprovedFlow:
    """Tests for the approved payment webhook processing path."""

    @pytest.mark.asyncio
    async def test_webhook_approved_triggers_confirmado(self):
        """Approved webhook → pedido CONFIRMADO + historial + stock decremented (task 17.5)."""
        from app.pagos.service import process_webhook

        secret = "test-secret"
        data_id = "123456"
        request_id = "req-uuid-test"
        pedido_id = uuid.uuid4()

        x_sig, _ = make_valid_x_signature(data_id, request_id, secret)

        # Checkout Pro: existing Pago has mp_payment_id already set (prior webhook assigned it)
        existing_pago = make_pago(
            pedido_id=pedido_id,
            mp_payment_id=int(data_id),
            mp_status="pending",
        )

        pedido = make_pedido(
            estado_codigo="PENDIENTE",
            usuario_id=uuid.uuid4(),
        )
        pedido.id = pedido_id

        detalle = MagicMock()
        detalle.producto_id = uuid.uuid4()
        detalle.cantidad = 2

        uow = make_uow()
        uow.pagos.get_by_mp_payment_id.return_value = existing_pago
        uow.pedidos.get_for_update.return_value = pedido
        uow.pedidos.update_estado.return_value = pedido
        uow.historial_pedido.append.return_value = None
        uow.productos.decrement_stock.return_value = MagicMock()  # Non-None = success

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [detalle]
        uow._session.execute.return_value = mock_result
        uow._session.flush = AsyncMock()

        with patch("app.pagos.service.get_settings") as mock_settings:
            mock_settings.return_value.MP_WEBHOOK_SECRET = secret
            with patch("app.pagos.service.mp_client") as mock_mp:
                mock_mp.get_payment.return_value = {
                    "status": "approved",
                    "status_detail": "accredited",
                    "external_reference": str(pedido_id),
                    "id": int(data_id),
                }

                result = await process_webhook(
                    webhook_type="payment",
                    data_id=data_id,
                    x_signature=x_sig,
                    x_request_id=request_id,
                    uow=uow,
                )

        assert result == {"status": "ok"}
        uow.pedidos.update_estado.assert_called_once_with(pedido_id, "CONFIRMADO")
        uow.historial_pedido.append.assert_called_once()
        historial_arg = uow.historial_pedido.append.call_args[0][0]
        assert historial_arg.estado_desde == "PENDIENTE"
        assert historial_arg.estado_hasta == "CONFIRMADO"
        assert historial_arg.cambiado_por_id is None  # D-04: SYSTEM actor
        assert historial_arg.motivo == "Pago aprobado MP"
        uow.productos.decrement_stock.assert_called_once_with(detalle.producto_id, detalle.cantidad)

    @pytest.mark.asyncio
    async def test_webhook_assigns_payment_id_first_time(self):
        """First webhook: assigns mp_payment_id to Pago row that had mp_payment_id=None (task 19.4)."""
        from app.pagos.service import process_webhook

        secret = "test-secret"
        data_id = "999888"
        request_id = "req-uuid-first"
        pedido_id = uuid.uuid4()

        x_sig, _ = make_valid_x_signature(data_id, request_id, secret)

        # Checkout Pro: Pago exists but mp_payment_id is NULL (preference created, not yet paid)
        pending_pago = make_pago(
            pedido_id=pedido_id,
            mp_payment_id=None,  # Not yet assigned
            mp_status="pending",
        )

        uow = make_uow()
        uow.pagos.get_by_mp_payment_id.return_value = None  # No row with this mp_payment_id
        uow.pagos.get_latest_by_pedido_id.return_value = pending_pago
        uow._session.flush = AsyncMock()

        with patch("app.pagos.service.get_settings") as mock_settings:
            mock_settings.return_value.MP_WEBHOOK_SECRET = secret
            with patch("app.pagos.service.mp_client") as mock_mp:
                mock_mp.get_payment.return_value = {
                    "status": "pending",
                    "status_detail": "pending_waiting_payment",
                    "external_reference": str(pedido_id),
                    "id": int(data_id),
                }

                result = await process_webhook(
                    webhook_type="payment",
                    data_id=data_id,
                    x_signature=x_sig,
                    x_request_id=request_id,
                    uow=uow,
                )

        assert result == {"status": "ok"}
        # mp_payment_id should now be assigned
        assert pending_pago.mp_payment_id == int(data_id)

    @pytest.mark.asyncio
    async def test_webhook_duplicate_idempotency_skipped(self):
        """Duplicate webhook for already-approved payment is skipped (task 17.6)."""
        from app.pagos.service import process_webhook

        secret = "test-secret"
        data_id = "123456"
        request_id = "req-uuid-dup"
        pedido_id = uuid.uuid4()

        x_sig, _ = make_valid_x_signature(data_id, request_id, secret)

        existing_pago = make_pago(
            pedido_id=pedido_id,
            mp_payment_id=int(data_id),
            mp_status="approved",  # Already approved!
        )

        uow = make_uow()
        uow.pagos.get_by_mp_payment_id.return_value = existing_pago

        with patch("app.pagos.service.get_settings") as mock_settings:
            mock_settings.return_value.MP_WEBHOOK_SECRET = secret
            with patch("app.pagos.service.mp_client") as mock_mp:
                mock_mp.get_payment.return_value = {
                    "status": "approved",
                    "status_detail": "accredited",
                    "external_reference": str(pedido_id),
                    "id": int(data_id),
                }

                result = await process_webhook(
                    webhook_type="payment",
                    data_id=data_id,
                    x_signature=x_sig,
                    x_request_id=request_id,
                    uow=uow,
                )

        assert result == {"status": "ok"}
        uow.pedidos.update_estado.assert_not_called()
        uow.historial_pedido.append.assert_not_called()

    @pytest.mark.asyncio
    async def test_webhook_rejected_stays_pendiente(self):
        """Rejected webhook updates pago only, no FSM transition (task 17.7)."""
        from app.pagos.service import process_webhook

        secret = "test-secret"
        data_id = "654321"
        request_id = "req-uuid-rej"
        pedido_id = uuid.uuid4()

        x_sig, _ = make_valid_x_signature(data_id, request_id, secret)

        existing_pago = make_pago(
            pedido_id=pedido_id,
            mp_payment_id=int(data_id),
            mp_status="pending",
        )

        uow = make_uow()
        uow.pagos.get_by_mp_payment_id.return_value = existing_pago
        uow._session.flush = AsyncMock()

        with patch("app.pagos.service.get_settings") as mock_settings:
            mock_settings.return_value.MP_WEBHOOK_SECRET = secret
            with patch("app.pagos.service.mp_client") as mock_mp:
                mock_mp.get_payment.return_value = {
                    "status": "rejected",
                    "status_detail": "cc_rejected_bad_filled_cvv",
                    "external_reference": str(pedido_id),
                    "id": int(data_id),
                }

                result = await process_webhook(
                    webhook_type="payment",
                    data_id=data_id,
                    x_signature=x_sig,
                    x_request_id=request_id,
                    uow=uow,
                )

        assert result == {"status": "ok"}
        assert existing_pago.mp_status == "rejected"
        uow.pedidos.update_estado.assert_not_called()
        uow.historial_pedido.append.assert_not_called()

    @pytest.mark.asyncio
    async def test_webhook_insufficient_stock_raises_error(self):
        """Approved webhook with insufficient stock raises InsufficientStockError (task 17.8)."""
        from app.pagos.service import process_webhook, InsufficientStockError

        secret = "test-secret"
        data_id = "789012"
        request_id = "req-uuid-stock"
        pedido_id = uuid.uuid4()

        x_sig, _ = make_valid_x_signature(data_id, request_id, secret)

        existing_pago = make_pago(
            pedido_id=pedido_id,
            mp_payment_id=int(data_id),
            mp_status="pending",
        )

        pedido = make_pedido(estado_codigo="PENDIENTE", usuario_id=uuid.uuid4())
        pedido.id = pedido_id

        detalle = MagicMock()
        detalle.producto_id = uuid.uuid4()
        detalle.cantidad = 5

        uow = make_uow()
        uow.pagos.get_by_mp_payment_id.return_value = existing_pago
        uow.pedidos.get_for_update.return_value = pedido
        uow.pedidos.update_estado.return_value = pedido
        uow.historial_pedido.append.return_value = None
        uow.productos.decrement_stock.return_value = None  # Insufficient stock!

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [detalle]
        uow._session.execute.return_value = mock_result
        uow._session.flush = AsyncMock()

        with patch("app.pagos.service.get_settings") as mock_settings:
            mock_settings.return_value.MP_WEBHOOK_SECRET = secret
            with patch("app.pagos.service.mp_client") as mock_mp:
                mock_mp.get_payment.return_value = {
                    "status": "approved",
                    "status_detail": "accredited",
                    "external_reference": str(pedido_id),
                    "id": int(data_id),
                }

                with pytest.raises(InsufficientStockError):
                    await process_webhook(
                        webhook_type="payment",
                        data_id=data_id,
                        x_signature=x_sig,
                        x_request_id=request_id,
                        uow=uow,
                    )

    @pytest.mark.asyncio
    async def test_webhook_non_payment_type_returns_200(self):
        """Non-payment webhook type returns 200 immediately with no DB work (task 11.8)."""
        from app.pagos.service import process_webhook

        secret = "test-secret"
        data_id = "abc123"
        request_id = "req-uuid-mp"

        x_sig, _ = make_valid_x_signature(data_id, request_id, secret)

        uow = make_uow()

        with patch("app.pagos.service.get_settings") as mock_settings:
            mock_settings.return_value.MP_WEBHOOK_SECRET = secret

            result = await process_webhook(
                webhook_type="merchant_order",
                data_id=data_id,
                x_signature=x_sig,
                x_request_id=request_id,
                uow=uow,
            )

        assert result == {"status": "ok"}
        uow.pagos.get_by_mp_payment_id.assert_not_called()

    @pytest.mark.asyncio
    async def test_webhook_orphan_logs_and_returns_200(self):
        """Orphan webhook (no Pago found) logs ORPHAN_WEBHOOK and returns 200 (task 11.9)."""
        from app.pagos.service import process_webhook

        secret = "test-secret"
        data_id = "999999"
        request_id = "req-uuid-orphan"
        pedido_id = uuid.uuid4()

        x_sig, _ = make_valid_x_signature(data_id, request_id, secret)

        uow = make_uow()
        uow.pagos.get_by_mp_payment_id.return_value = None
        uow.pagos.get_latest_by_pedido_id.return_value = None

        with patch("app.pagos.service.get_settings") as mock_settings:
            mock_settings.return_value.MP_WEBHOOK_SECRET = secret
            with patch("app.pagos.service.mp_client") as mock_mp:
                mock_mp.get_payment.return_value = {
                    "status": "approved",
                    "status_detail": "accredited",
                    "external_reference": str(pedido_id),
                    "id": int(data_id),
                }

                result = await process_webhook(
                    webhook_type="payment",
                    data_id=data_id,
                    x_signature=x_sig,
                    x_request_id=request_id,
                    uow=uow,
                )

        assert result == {"status": "ok"}
        uow.pedidos.update_estado.assert_not_called()


# ─────────────────────────────────────────────────────────────────────────────
# Tasks 17.9, 17.10 — get_latest_payment service
# ─────────────────────────────────────────────────────────────────────────────


class TestGetLatestPaymentService:
    """Tests for get_latest_payment service function."""

    @pytest.mark.asyncio
    async def test_get_latest_payment_returns_newest(self):
        """getLatestPayment returns the most recently created Pago (task 17.9)."""
        from app.pagos.service import get_latest_payment

        user_id = uuid.uuid4()
        pedido_id = uuid.uuid4()

        pedido = make_pedido(usuario_id=user_id)
        pedido.id = pedido_id

        newer_pago = make_pago(
            pedido_id=pedido_id,
            created_at=datetime(2025, 6, 2, tzinfo=timezone.utc),
        )

        uow = make_uow()
        uow.pedidos.get_by_id.return_value = pedido
        uow.pagos.get_latest_by_pedido_id.return_value = newer_pago

        current_user = make_current_user(user_id=user_id, roles=["CLIENT"])

        result = await get_latest_payment(uow=uow, current_user=current_user, pedido_id=pedido_id)

        assert isinstance(result, PagoResponse)
        uow.pagos.get_latest_by_pedido_id.assert_called_once_with(pedido_id)

    @pytest.mark.asyncio
    async def test_get_latest_payment_404_no_pago(self):
        """getLatestPayment raises 404 PAYMENT_NOT_FOUND when no Pago exists (task 17.10)."""
        from app.pagos.service import get_latest_payment

        user_id = uuid.uuid4()
        pedido_id = uuid.uuid4()
        pedido = make_pedido(usuario_id=user_id)
        pedido.id = pedido_id

        uow = make_uow()
        uow.pedidos.get_by_id.return_value = pedido
        uow.pagos.get_latest_by_pedido_id.return_value = None

        current_user = make_current_user(user_id=user_id, roles=["CLIENT"])

        with pytest.raises(HTTPException) as exc_info:
            await get_latest_payment(uow=uow, current_user=current_user, pedido_id=pedido_id)

        assert exc_info.value.status_code == 404
        assert exc_info.value.detail["code"] == "PAYMENT_NOT_FOUND"


# ─────────────────────────────────────────────────────────────────────────────
# Task 17.11 — stale timestamp test (explicit)
# ─────────────────────────────────────────────────────────────────────────────


def test_webhook_stale_timestamp():
    """Stale timestamp (> 5 min) returns HTTP 400 WEBHOOK_EXPIRED (task 17.11)."""
    data_id = "100"
    request_id = "req-ts-test"
    secret = "stale-secret"

    stale_ts = int(time.time()) - 400  # 6+ minutes ago
    x_sig, _ = make_valid_x_signature(data_id, request_id, secret, ts=stale_ts)

    with pytest.raises(HTTPException) as exc_info:
        verify_webhook_signature(x_sig, request_id, data_id, secret)

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail["code"] == "WEBHOOK_EXPIRED"


# ─────────────────────────────────────────────────────────────────────────────
# Task 17.12 — existing pago non-approved → approved
# ─────────────────────────────────────────────────────────────────────────────


class TestWebhookNonApprovedBecomesApproved:
    """Task 17.12: existing pago with mp_status=pending, re-query returns approved."""

    @pytest.mark.asyncio
    async def test_webhook_existing_pago_non_approved_becomes_approved(self):
        """Pago exists with mp_status='pending', MP re-query returns 'approved' → full processing (task 17.12)."""
        from app.pagos.service import process_webhook

        secret = "test-secret"
        data_id = "555555"
        request_id = "req-uuid-upgrade"
        pedido_id = uuid.uuid4()

        x_sig, _ = make_valid_x_signature(data_id, request_id, secret)

        existing_pago = make_pago(
            pedido_id=pedido_id,
            mp_payment_id=int(data_id),
            mp_status="pending",  # NOT approved
        )

        pedido = make_pedido(estado_codigo="PENDIENTE", usuario_id=uuid.uuid4())
        pedido.id = pedido_id

        detalle = MagicMock()
        detalle.producto_id = uuid.uuid4()
        detalle.cantidad = 1

        uow = make_uow()
        uow.pagos.get_by_mp_payment_id.return_value = existing_pago
        uow.pedidos.get_for_update.return_value = pedido
        uow.pedidos.update_estado.return_value = pedido
        uow.historial_pedido.append.return_value = None
        uow.productos.decrement_stock.return_value = MagicMock()  # Success

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [detalle]
        uow._session.execute.return_value = mock_result
        uow._session.flush = AsyncMock()

        with patch("app.pagos.service.get_settings") as mock_settings:
            mock_settings.return_value.MP_WEBHOOK_SECRET = secret
            with patch("app.pagos.service.mp_client") as mock_mp:
                mock_mp.get_payment.return_value = {
                    "status": "approved",
                    "status_detail": "accredited",
                    "external_reference": str(pedido_id),
                    "id": int(data_id),
                }

                result = await process_webhook(
                    webhook_type="payment",
                    data_id=data_id,
                    x_signature=x_sig,
                    x_request_id=request_id,
                    uow=uow,
                )

        assert result == {"status": "ok"}
        uow.pedidos.update_estado.assert_called_once_with(pedido_id, "CONFIRMADO")
        uow.historial_pedido.append.assert_called_once()
        uow.productos.decrement_stock.assert_called_once()
        assert existing_pago.mp_status == "approved"


# ─────────────────────────────────────────────────────────────────────────────
# Sandbox e2e test (task 18.6) — opt-in
# ─────────────────────────────────────────────────────────────────────────────

# This test lives in backend/tests/test_pagos_e2e.py to keep it separate.
# See that file for the @pytest.mark.e2e sandbox test.


# ─────────────────────────────────────────────────────────────────────────────
# MP-flow bugfix — Checkout Pro preference payload assertions
# ─────────────────────────────────────────────────────────────────────────────


class TestStartCheckoutProPreferencePayload:
    """Verify the payload sent to mp_client.create_preference (MP-flow fix)."""

    @pytest.mark.asyncio
    async def _run_and_capture_preference_call(
        self,
        frontend_base_url: str = "http://localhost:5173",
    ):
        """Helper: drive start_checkout_pro and return the captured create_preference kwargs.

        Returns (call_kwargs, pedido_id_str, notification_url).
        """
        from app.pagos.service import start_checkout_pro

        user_id = uuid.uuid4()
        pedido = make_pedido(usuario_id=user_id)
        pedido_id_str = str(pedido.id)
        idempotency_key = str(uuid.uuid4())
        notification_url = "https://example.com/api/v1/pagos/webhook"

        mp_response = {
            "id": "PREF-XYZ",
            "init_point": "https://www.mercadopago.com.ar/checkout/v1/redirect?pref_id=PREF-XYZ",
            "sandbox_init_point": "https://sandbox.mercadopago.com.ar/checkout/v1/redirect?pref_id=PREF-XYZ",
        }
        expected_pago = make_pago(
            pedido_id=pedido.id,
            mp_preference_id="PREF-XYZ",
            idempotency_key=idempotency_key,
        )

        uow = make_uow()
        uow.pedidos.get_by_id.return_value = pedido
        uow.pagos.get_by_idempotency_key.return_value = None
        uow.pagos.create.return_value = expected_pago

        current_user = make_current_user(user_id=user_id)
        data = PagoCreateRequest(pedido_id=pedido.id, idempotency_key=idempotency_key)

        with patch("app.pagos.service.mp_client") as mock_mp:
            mock_mp.create_preference.return_value = mp_response
            with patch("app.pagos.service.get_settings") as mock_settings:
                mock_settings.return_value.MP_NOTIFICATION_URL = notification_url
                mock_settings.return_value.FRONTEND_BASE_URL = frontend_base_url

                await start_checkout_pro(uow=uow, current_user=current_user, data=data)

            call_kwargs = mock_mp.create_preference.call_args.kwargs

        return call_kwargs, pedido_id_str, notification_url

    @pytest.mark.asyncio
    async def test_start_checkout_pro_sends_back_urls_success_pending_failure(self):
        """back_urls contains the 3 keys derived from FRONTEND_BASE_URL."""
        call_kwargs, pedido_id_str, _ = await self._run_and_capture_preference_call(
            frontend_base_url="http://localhost:5173",
        )
        back_urls = call_kwargs["back_urls"]
        assert set(back_urls.keys()) == {"success", "pending", "failure"}
        assert back_urls["success"] == (
            f"http://localhost:5173/checkout/return?status=success&pedido_id={pedido_id_str}"
        )
        assert back_urls["pending"] == (
            f"http://localhost:5173/checkout/return?status=pending&pedido_id={pedido_id_str}"
        )
        assert back_urls["failure"] == (
            f"http://localhost:5173/checkout/return?status=failure&pedido_id={pedido_id_str}"
        )

    @pytest.mark.asyncio
    async def test_start_checkout_pro_sends_auto_return_approved_on_localhost(self):
        """auto_return == 'approved' even when FRONTEND_BASE_URL is http+localhost (MP-flow fix)."""
        call_kwargs, _, _ = await self._run_and_capture_preference_call(
            frontend_base_url="http://localhost:5173",
        )
        assert call_kwargs["auto_return"] == "approved"

    @pytest.mark.asyncio
    async def test_start_checkout_pro_sends_auto_return_approved_on_https(self):
        """auto_return == 'approved' on HTTPS too (no regression)."""
        call_kwargs, _, _ = await self._run_and_capture_preference_call(
            frontend_base_url="https://app.example.com",
        )
        assert call_kwargs["auto_return"] == "approved"

    @pytest.mark.asyncio
    async def test_start_checkout_pro_sends_notification_url(self):
        """notification_url comes from settings.MP_NOTIFICATION_URL."""
        call_kwargs, _, notification_url = await self._run_and_capture_preference_call()
        assert call_kwargs["notification_url"] == notification_url

    @pytest.mark.asyncio
    async def test_start_checkout_pro_sends_external_reference_as_pedido_id(self):
        """external_reference equals str(pedido.id)."""
        call_kwargs, pedido_id_str, _ = await self._run_and_capture_preference_call()
        assert call_kwargs["external_reference"] == pedido_id_str


# ─────────────────────────────────────────────────────────────────────────────
# reconcile_payment service tests (MP-flow fix)
# ─────────────────────────────────────────────────────────────────────────────


class TestReconcilePayment:
    """Tests for the new reconcile_payment service function."""

    def _make_pedido_with_owner(self, user_id: uuid.UUID, pedido_id: uuid.UUID | None = None) -> MagicMock:
        pedido = make_pedido(usuario_id=user_id)
        if pedido_id is not None:
            pedido.id = pedido_id
        return pedido

    @pytest.mark.asyncio
    async def test_reconcile_approved_confirms_pedido(self):
        """Reconcile with payment_id mocked to approved → pedido CONFIRMADO + historial."""
        from app.pagos.service import reconcile_payment

        user_id = uuid.uuid4()
        pedido_id = uuid.uuid4()
        payment_id = 4242

        pedido = self._make_pedido_with_owner(user_id, pedido_id)
        pago = make_pago(pedido_id=pedido_id, mp_payment_id=None, mp_status="pending")

        detalle = MagicMock()
        detalle.producto_id = uuid.uuid4()
        detalle.cantidad = 1

        uow = make_uow()
        uow.pedidos.get_by_id.return_value = pedido
        uow.pagos.get_latest_by_pedido_id.return_value = pago
        uow.pedidos.get_for_update.return_value = pedido
        uow.pedidos.update_estado.return_value = pedido
        uow.historial_pedido.append.return_value = None
        uow.productos.decrement_stock.return_value = MagicMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [detalle]
        uow._session.execute.return_value = mock_result
        uow._session.flush = AsyncMock()

        current_user = make_current_user(user_id=user_id)

        with patch("app.pagos.service.mp_client") as mock_mp:
            mock_mp.get_payment.return_value = {
                "status": "approved",
                "status_detail": "accredited",
                "external_reference": str(pedido_id),
                "id": payment_id,
            }

            result = await reconcile_payment(
                uow=uow,
                current_user=current_user,
                pedido_id=pedido_id,
                payment_id=payment_id,
                external_reference=str(pedido_id),
            )

        assert result["status"] == "ok"
        assert result["mp_status"] == "approved"
        assert result["already_processed"] is False
        uow.pedidos.update_estado.assert_called_once_with(pedido_id, "CONFIRMADO")
        uow.historial_pedido.append.assert_called_once()
        historial_arg = uow.historial_pedido.append.call_args[0][0]
        assert historial_arg.estado_desde == "PENDIENTE"
        assert historial_arg.estado_hasta == "CONFIRMADO"
        assert historial_arg.cambiado_por_id is None  # SYSTEM actor
        uow.productos.decrement_stock.assert_called_once()
        assert pago.mp_payment_id == payment_id  # first-time assignment

    @pytest.mark.asyncio
    async def test_reconcile_pending_keeps_pedido_pendiente(self):
        """Reconcile with status=pending → no FSM transition, mp_status updated."""
        from app.pagos.service import reconcile_payment

        user_id = uuid.uuid4()
        pedido_id = uuid.uuid4()
        pedido = self._make_pedido_with_owner(user_id, pedido_id)
        pago = make_pago(pedido_id=pedido_id, mp_payment_id=None, mp_status="pending")

        uow = make_uow()
        uow.pedidos.get_by_id.return_value = pedido
        uow.pagos.get_latest_by_pedido_id.return_value = pago
        uow._session.flush = AsyncMock()

        current_user = make_current_user(user_id=user_id)

        with patch("app.pagos.service.mp_client") as mock_mp:
            mock_mp.get_payment.return_value = {
                "status": "in_process",
                "status_detail": "pending_review_manual",
                "external_reference": str(pedido_id),
                "id": 7,
            }

            result = await reconcile_payment(
                uow=uow,
                current_user=current_user,
                pedido_id=pedido_id,
                payment_id=7,
                external_reference=None,
            )

        assert result["mp_status"] == "in_process"
        uow.pedidos.update_estado.assert_not_called()
        uow.historial_pedido.append.assert_not_called()

    @pytest.mark.asyncio
    async def test_reconcile_rejected_keeps_pedido_pendiente(self):
        """Reconcile with status=rejected → pago.mp_status=rejected, pedido sigue PENDIENTE."""
        from app.pagos.service import reconcile_payment

        user_id = uuid.uuid4()
        pedido_id = uuid.uuid4()
        pedido = self._make_pedido_with_owner(user_id, pedido_id)
        pago = make_pago(pedido_id=pedido_id, mp_payment_id=None, mp_status="pending")

        uow = make_uow()
        uow.pedidos.get_by_id.return_value = pedido
        uow.pagos.get_latest_by_pedido_id.return_value = pago
        uow._session.flush = AsyncMock()

        current_user = make_current_user(user_id=user_id)

        with patch("app.pagos.service.mp_client") as mock_mp:
            mock_mp.get_payment.return_value = {
                "status": "rejected",
                "status_detail": "cc_rejected_other_reason",
                "external_reference": str(pedido_id),
                "id": 8,
            }

            result = await reconcile_payment(
                uow=uow,
                current_user=current_user,
                pedido_id=pedido_id,
                payment_id=8,
                external_reference=None,
            )

        assert result["mp_status"] == "rejected"
        assert pago.mp_status == "rejected"
        uow.pedidos.update_estado.assert_not_called()

    @pytest.mark.asyncio
    async def test_reconcile_idempotent_when_already_approved(self):
        """Reconcile on an already-approved Pago short-circuits with already_processed=True."""
        from app.pagos.service import reconcile_payment

        user_id = uuid.uuid4()
        pedido_id = uuid.uuid4()
        pedido = self._make_pedido_with_owner(user_id, pedido_id)
        pedido.estado_codigo = "CONFIRMADO"
        pago = make_pago(pedido_id=pedido_id, mp_payment_id=999, mp_status="approved")

        uow = make_uow()
        uow.pedidos.get_by_id.return_value = pedido
        uow.pagos.get_latest_by_pedido_id.return_value = pago

        current_user = make_current_user(user_id=user_id)

        # No mp_client.get_payment patch — idempotency must short-circuit before MP call
        result = await reconcile_payment(
            uow=uow,
            current_user=current_user,
            pedido_id=pedido_id,
            payment_id=999,
            external_reference=str(pedido_id),
        )

        assert result["already_processed"] is True
        assert result["mp_status"] == "approved"
        assert result["pedido_estado"] == "CONFIRMADO"
        uow.pedidos.update_estado.assert_not_called()
        uow.historial_pedido.append.assert_not_called()

    @pytest.mark.asyncio
    async def test_reconcile_external_reference_mismatch_returns_409(self):
        """MP returns payment whose external_reference != pedido_id → 409."""
        from app.pagos.service import reconcile_payment

        user_id = uuid.uuid4()
        pedido_id = uuid.uuid4()
        other_pedido_id = uuid.uuid4()
        pedido = self._make_pedido_with_owner(user_id, pedido_id)
        pago = make_pago(pedido_id=pedido_id, mp_payment_id=None, mp_status="pending")

        uow = make_uow()
        uow.pedidos.get_by_id.return_value = pedido
        uow.pagos.get_latest_by_pedido_id.return_value = pago
        uow._session.flush = AsyncMock()

        current_user = make_current_user(user_id=user_id)

        with patch("app.pagos.service.mp_client") as mock_mp:
            mock_mp.get_payment.return_value = {
                "status": "approved",
                "status_detail": "accredited",
                "external_reference": str(other_pedido_id),  # wrong!
                "id": 11,
            }

            with pytest.raises(HTTPException) as exc_info:
                await reconcile_payment(
                    uow=uow,
                    current_user=current_user,
                    pedido_id=pedido_id,
                    payment_id=11,
                    external_reference=None,
                )

        assert exc_info.value.status_code == 409
        assert exc_info.value.detail["code"] == "EXTERNAL_REFERENCE_MISMATCH"
        uow.pedidos.update_estado.assert_not_called()

    @pytest.mark.asyncio
    async def test_reconcile_efectivo_pedido_returns_409(self):
        """Pedido with forma_pago=EFECTIVO → 409 PAYMENT_METHOD_MISMATCH."""
        from app.pagos.service import reconcile_payment

        user_id = uuid.uuid4()
        pedido_id = uuid.uuid4()
        pedido = make_pedido(usuario_id=user_id, forma_pago_codigo="EFECTIVO")
        pedido.id = pedido_id

        uow = make_uow()
        uow.pedidos.get_by_id.return_value = pedido

        current_user = make_current_user(user_id=user_id)

        with pytest.raises(HTTPException) as exc_info:
            await reconcile_payment(
                uow=uow,
                current_user=current_user,
                pedido_id=pedido_id,
                payment_id=1,
                external_reference=None,
            )

        assert exc_info.value.status_code == 409
        assert exc_info.value.detail["code"] == "PAYMENT_METHOD_MISMATCH"

    @pytest.mark.asyncio
    async def test_reconcile_other_user_pedido_returns_404(self):
        """User who doesn't own the pedido → 404 ORDER_NOT_FOUND (no info leak)."""
        from app.pagos.service import reconcile_payment

        owner_id = uuid.uuid4()
        other_user_id = uuid.uuid4()
        pedido_id = uuid.uuid4()
        pedido = self._make_pedido_with_owner(owner_id, pedido_id)

        uow = make_uow()
        uow.pedidos.get_by_id.return_value = pedido

        other_user = make_current_user(user_id=other_user_id)

        with pytest.raises(HTTPException) as exc_info:
            await reconcile_payment(
                uow=uow,
                current_user=other_user,
                pedido_id=pedido_id,
                payment_id=1,
                external_reference=None,
            )

        assert exc_info.value.status_code == 404
        assert exc_info.value.detail["code"] == "ORDER_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_reconcile_payment_id_missing_returns_400(self):
        """payment_id missing → 400 PAYMENT_ID_REQUIRED."""
        from app.pagos.service import reconcile_payment

        user_id = uuid.uuid4()
        pedido_id = uuid.uuid4()
        pedido = self._make_pedido_with_owner(user_id, pedido_id)
        pago = make_pago(pedido_id=pedido_id, mp_payment_id=None, mp_status="pending")

        uow = make_uow()
        uow.pedidos.get_by_id.return_value = pedido
        uow.pagos.get_latest_by_pedido_id.return_value = pago

        current_user = make_current_user(user_id=user_id)

        with pytest.raises(HTTPException) as exc_info:
            await reconcile_payment(
                uow=uow,
                current_user=current_user,
                pedido_id=pedido_id,
                payment_id=None,
                external_reference=None,
            )

        assert exc_info.value.status_code == 400
        assert exc_info.value.detail["code"] == "PAYMENT_ID_REQUIRED"

    @pytest.mark.asyncio
    async def test_reconcile_pedido_not_found_returns_404(self):
        """Pedido not found → 404 ORDER_NOT_FOUND."""
        from app.pagos.service import reconcile_payment

        pedido_id = uuid.uuid4()
        uow = make_uow()
        uow.pedidos.get_by_id.return_value = None

        current_user = make_current_user()

        with pytest.raises(HTTPException) as exc_info:
            await reconcile_payment(
                uow=uow,
                current_user=current_user,
                pedido_id=pedido_id,
                payment_id=1,
                external_reference=None,
            )

        assert exc_info.value.status_code == 404
        assert exc_info.value.detail["code"] == "ORDER_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_reconcile_no_pago_returns_404(self):
        """No Pago row for pedido → 404 PAYMENT_NOT_FOUND."""
        from app.pagos.service import reconcile_payment

        user_id = uuid.uuid4()
        pedido_id = uuid.uuid4()
        pedido = self._make_pedido_with_owner(user_id, pedido_id)

        uow = make_uow()
        uow.pedidos.get_by_id.return_value = pedido
        uow.pagos.get_latest_by_pedido_id.return_value = None

        current_user = make_current_user(user_id=user_id)

        with pytest.raises(HTTPException) as exc_info:
            await reconcile_payment(
                uow=uow,
                current_user=current_user,
                pedido_id=pedido_id,
                payment_id=1,
                external_reference=None,
            )

        assert exc_info.value.status_code == 404
        assert exc_info.value.detail["code"] == "PAYMENT_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_reconcile_mp_api_error_returns_502(self):
        """MP API error → 502 MP_RECONCILE_ERROR."""
        from app.integrations.mercadopago_client import MercadoPagoAPIError
        from app.pagos.service import reconcile_payment

        user_id = uuid.uuid4()
        pedido_id = uuid.uuid4()
        pedido = self._make_pedido_with_owner(user_id, pedido_id)
        pago = make_pago(pedido_id=pedido_id, mp_payment_id=None, mp_status="pending")

        uow = make_uow()
        uow.pedidos.get_by_id.return_value = pedido
        uow.pagos.get_latest_by_pedido_id.return_value = pago

        current_user = make_current_user(user_id=user_id)

        with patch("app.pagos.service.mp_client") as mock_mp:
            mock_mp.get_payment.side_effect = MercadoPagoAPIError("MP boom", status_code=500)

            with pytest.raises(HTTPException) as exc_info:
                await reconcile_payment(
                    uow=uow,
                    current_user=current_user,
                    pedido_id=pedido_id,
                    payment_id=42,
                    external_reference=None,
                )

        assert exc_info.value.status_code == 502
        assert exc_info.value.detail["code"] == "MP_RECONCILE_ERROR"
