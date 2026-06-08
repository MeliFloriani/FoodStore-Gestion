"""
Unit tests for the FSM state transition service (Change 18).

Tests the module-level functions in app.services.state_transition:
- validate_transition_allowed
- transition_state
- cancel_own_client

Uses unittest.mock to isolate the service from the real database.
All UoW interactions are mocked — these are pure unit tests.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.services.state_transition import (
    ALLOWED_TRANSITIONS,
    STATES_REQUIRING_STOCK_RESTORE,
    TERMINAL_STATES,
    cancel_own_client,
    transition_state,
    validate_transition_allowed,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_rol(codigo: str) -> MagicMock:
    """Create a fake Rol with a given codigo."""
    rol = MagicMock()
    rol.codigo = codigo
    return rol


def _make_usuario_rol(rol_codigo: str) -> MagicMock:
    """Create a fake UsuarioRol with .rol.codigo = rol_codigo."""
    ur = MagicMock()
    ur.rol = _make_rol(rol_codigo)
    ur.deleted_at = None
    return ur


def _make_user(roles: list[str], user_id: uuid.UUID | None = None) -> MagicMock:
    """Create a fake Usuario with given role codes."""
    user = MagicMock()
    user.id = user_id or uuid.uuid4()
    user.usuario_roles = [_make_usuario_rol(r) for r in roles]
    return user


def _make_pedido(
    estado_codigo: str,
    pedido_id: uuid.UUID | None = None,
    usuario_id: uuid.UUID | None = None,
) -> MagicMock:
    """Create a fake Pedido ORM object."""
    pedido = MagicMock()
    pedido.id = pedido_id or uuid.uuid4()
    pedido.estado_codigo = estado_codigo
    pedido.usuario_id = usuario_id or uuid.uuid4()
    return pedido


def _make_uow(pedido: MagicMock | None = None) -> MagicMock:
    """Create a fake UoW with mocked pedidos and historial_pedido repos."""
    uow = MagicMock()
    uow.pedidos = MagicMock()
    uow.pedidos.get_for_update = AsyncMock(return_value=pedido)
    uow.pedidos.update_estado = AsyncMock(return_value=pedido)
    uow.historial_pedido = MagicMock()
    uow.historial_pedido.append = AsyncMock(return_value=MagicMock())
    uow._session = MagicMock()
    uow._session.execute = AsyncMock(
        return_value=MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[]))))
    )
    uow._session.flush = AsyncMock()
    return uow


# ---------------------------------------------------------------------------
# validate_transition_allowed
# ---------------------------------------------------------------------------


class TestValidateTransitionAllowed:
    """Tests for the FSM + RBAC validation helper."""

    def test_terminal_state_raises_409(self):
        """Any transition from a terminal state raises 409 TERMINAL_STATE."""
        with pytest.raises(HTTPException) as exc_info:
            validate_transition_allowed("ENTREGADO", "CANCELADO", ["ADMIN"])
        assert exc_info.value.status_code == 409
        assert exc_info.value.detail["code"] == "TERMINAL_STATE"

    def test_cancelado_is_terminal(self):
        """CANCELADO is a terminal state — no further transitions."""
        with pytest.raises(HTTPException) as exc_info:
            validate_transition_allowed("CANCELADO", "EN_PREP", ["ADMIN"])
        assert exc_info.value.status_code == 409
        assert exc_info.value.detail["code"] == "TERMINAL_STATE"

    def test_invalid_transition_raises_409(self):
        """Transition not in FSM map raises 409 INVALID_TRANSITION."""
        with pytest.raises(HTTPException) as exc_info:
            validate_transition_allowed("PENDIENTE", "EN_CAMINO", ["ADMIN"])
        assert exc_info.value.status_code == 409
        assert exc_info.value.detail["code"] == "INVALID_TRANSITION"

    def test_en_camino_cannot_be_cancelled(self):
        """EN_CAMINO → CANCELADO is not in the FSM map (Integrador §3.4)."""
        with pytest.raises(HTTPException) as exc_info:
            validate_transition_allowed("EN_CAMINO", "CANCELADO", ["ADMIN"])
        assert exc_info.value.status_code == 409
        assert exc_info.value.detail["code"] == "INVALID_TRANSITION"

    def test_role_mismatch_raises_403(self):
        """User lacking the required role for this specific transition gets 403."""
        # EN_PREP → CANCELADO is ADMIN-only; CLIENT should be rejected
        with pytest.raises(HTTPException) as exc_info:
            validate_transition_allowed("EN_PREP", "CANCELADO", ["CLIENT"])
        assert exc_info.value.status_code == 403
        assert exc_info.value.detail["code"] == "CANCEL_NOT_ALLOWED_FOR_ROLE"

    def test_pedidos_cannot_cancel_en_prep(self):
        """PEDIDOS role cannot cancel EN_PREP (only ADMIN can — RN-RB08)."""
        with pytest.raises(HTTPException) as exc_info:
            validate_transition_allowed("EN_PREP", "CANCELADO", ["PEDIDOS"])
        assert exc_info.value.status_code == 403
        assert exc_info.value.detail["code"] == "CANCEL_NOT_ALLOWED_FOR_ROLE"

    def test_admin_can_cancel_en_prep(self):
        """ADMIN can cancel EN_PREP — no exception raised."""
        # Should not raise
        validate_transition_allowed("EN_PREP", "CANCELADO", ["ADMIN"])

    def test_pedidos_can_advance_confirmado_to_en_prep(self):
        """PEDIDOS can advance CONFIRMADO → EN_PREP."""
        validate_transition_allowed("CONFIRMADO", "EN_PREP", ["PEDIDOS"])

    def test_admin_can_advance_confirmado_to_en_prep(self):
        """ADMIN can advance CONFIRMADO → EN_PREP."""
        validate_transition_allowed("CONFIRMADO", "EN_PREP", ["ADMIN"])

    def test_pedidos_can_advance_en_camino_to_entregado(self):
        """PEDIDOS can advance EN_CAMINO → ENTREGADO."""
        validate_transition_allowed("EN_CAMINO", "ENTREGADO", ["PEDIDOS"])

    def test_admin_can_cancel_confirmado(self):
        """ADMIN can cancel CONFIRMADO."""
        validate_transition_allowed("CONFIRMADO", "CANCELADO", ["ADMIN"])

    def test_pedidos_can_cancel_confirmado(self):
        """PEDIDOS can cancel CONFIRMADO."""
        validate_transition_allowed("CONFIRMADO", "CANCELADO", ["PEDIDOS"])

    def test_admin_can_cancel_pendiente(self):
        """ADMIN can cancel PENDIENTE via PATCH."""
        validate_transition_allowed("PENDIENTE", "CANCELADO", ["ADMIN"])

    def test_pedidos_can_cancel_pendiente(self):
        """PEDIDOS can cancel PENDIENTE via PATCH."""
        validate_transition_allowed("PENDIENTE", "CANCELADO", ["PEDIDOS"])


# ---------------------------------------------------------------------------
# transition_state
# ---------------------------------------------------------------------------


class TestTransitionState:
    """Tests for the staff FSM transition function."""

    @pytest.mark.asyncio
    async def test_confirmado_to_en_prep_ok(self):
        """PEDIDOS user can advance CONFIRMADO → EN_PREP."""
        pedido_id = uuid.uuid4()
        pedido = _make_pedido("CONFIRMADO", pedido_id=pedido_id)
        uow = _make_uow(pedido)
        user = _make_user(["PEDIDOS"])

        updated = await transition_state(uow, pedido_id, "EN_PREP", None, user)

        uow.pedidos.get_for_update.assert_awaited_once_with(pedido_id)
        uow.pedidos.update_estado.assert_awaited_once_with(pedido_id, "EN_PREP")
        uow.historial_pedido.append.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_order_not_found_raises_404(self):
        """Returns 404 when the order does not exist."""
        uow = _make_uow(None)  # get_for_update returns None
        user = _make_user(["ADMIN"])

        with pytest.raises(HTTPException) as exc_info:
            await transition_state(uow, uuid.uuid4(), "EN_PREP", None, user)
        assert exc_info.value.status_code == 404
        assert exc_info.value.detail["code"] == "ORDER_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_terminal_state_raises_409(self):
        """Transition from terminal state raises 409."""
        pedido = _make_pedido("ENTREGADO")
        uow = _make_uow(pedido)
        user = _make_user(["ADMIN"])

        with pytest.raises(HTTPException) as exc_info:
            await transition_state(uow, pedido.id, "CANCELADO", "motivo", user)
        assert exc_info.value.status_code == 409
        assert exc_info.value.detail["code"] == "TERMINAL_STATE"

    @pytest.mark.asyncio
    async def test_invalid_transition_raises_409(self):
        """Invalid FSM transition raises 409."""
        pedido = _make_pedido("PENDIENTE")
        uow = _make_uow(pedido)
        user = _make_user(["ADMIN"])

        with pytest.raises(HTTPException) as exc_info:
            await transition_state(uow, pedido.id, "EN_CAMINO", None, user)
        assert exc_info.value.status_code == 409
        assert exc_info.value.detail["code"] == "INVALID_TRANSITION"

    @pytest.mark.asyncio
    async def test_cancelado_requires_motivo(self):
        """Cancellation without motivo raises 422 MOTIVO_REQUIRED."""
        pedido = _make_pedido("CONFIRMADO")
        uow = _make_uow(pedido)
        user = _make_user(["PEDIDOS"])

        with pytest.raises(HTTPException) as exc_info:
            await transition_state(uow, pedido.id, "CANCELADO", None, user)
        assert exc_info.value.status_code == 422
        assert exc_info.value.detail["code"] == "MOTIVO_REQUIRED"

    @pytest.mark.asyncio
    async def test_pedidos_cannot_cancel_en_prep_raises_403(self):
        """PEDIDOS role cannot cancel EN_PREP — 403."""
        pedido = _make_pedido("EN_PREP")
        uow = _make_uow(pedido)
        user = _make_user(["PEDIDOS"])

        with pytest.raises(HTTPException) as exc_info:
            await transition_state(uow, pedido.id, "CANCELADO", "motivo", user)
        assert exc_info.value.status_code == 403
        assert exc_info.value.detail["code"] == "CANCEL_NOT_ALLOWED_FOR_ROLE"

    @pytest.mark.asyncio
    async def test_admin_can_cancel_en_prep(self):
        """ADMIN can cancel EN_PREP — no exception."""
        pedido_id = uuid.uuid4()
        pedido = _make_pedido("EN_PREP", pedido_id=pedido_id)
        uow = _make_uow(pedido)
        user = _make_user(["ADMIN"])

        with patch(
            "app.services.state_transition._restore_stock", new_callable=AsyncMock
        ) as mock_restore:
            await transition_state(uow, pedido_id, "CANCELADO", "motivo de cancelación", user)
            mock_restore.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_stock_restored_for_confirmado_cancellation(self):
        """Stock is restored when cancelling from CONFIRMADO."""
        pedido_id = uuid.uuid4()
        pedido = _make_pedido("CONFIRMADO", pedido_id=pedido_id)
        uow = _make_uow(pedido)
        user = _make_user(["PEDIDOS"])

        with patch(
            "app.services.state_transition._restore_stock", new_callable=AsyncMock
        ) as mock_restore:
            await transition_state(uow, pedido_id, "CANCELADO", "quiero cancelar", user)
            mock_restore.assert_awaited_once_with(uow, pedido_id)

    @pytest.mark.asyncio
    async def test_no_stock_restore_for_non_cancel_transition(self):
        """Stock is NOT restored for non-cancellation transitions."""
        pedido_id = uuid.uuid4()
        pedido = _make_pedido("CONFIRMADO", pedido_id=pedido_id)
        uow = _make_uow(pedido)
        user = _make_user(["PEDIDOS"])

        with patch(
            "app.services.state_transition._restore_stock", new_callable=AsyncMock
        ) as mock_restore:
            await transition_state(uow, pedido_id, "EN_PREP", None, user)
            mock_restore.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_historial_appended_with_correct_fields(self):
        """Historial is appended with correct estado_desde, estado_hasta, actor."""
        pedido_id = uuid.uuid4()
        user_id = uuid.uuid4()
        pedido = _make_pedido("CONFIRMADO", pedido_id=pedido_id)
        uow = _make_uow(pedido)
        user = _make_user(["PEDIDOS"], user_id=user_id)

        await transition_state(uow, pedido_id, "EN_PREP", None, user)

        uow.historial_pedido.append.assert_awaited_once()
        call_args = uow.historial_pedido.append.call_args[0][0]
        assert call_args.estado_desde == "CONFIRMADO"
        assert call_args.estado_hasta == "EN_PREP"
        assert call_args.cambiado_por_id == user_id


# ---------------------------------------------------------------------------
# cancel_own_client
# ---------------------------------------------------------------------------


class TestCancelOwnClient:
    """Tests for the client self-cancellation function."""

    @pytest.mark.asyncio
    async def test_client_cancels_pendiente_ok(self):
        """CLIENT can cancel their own PENDIENTE order."""
        user_id = uuid.uuid4()
        pedido_id = uuid.uuid4()
        pedido = _make_pedido("PENDIENTE", pedido_id=pedido_id, usuario_id=user_id)
        uow = _make_uow(pedido)
        user = _make_user(["CLIENT"], user_id=user_id)

        await cancel_own_client(uow, pedido_id, "ya no quiero", user)

        uow.pedidos.update_estado.assert_awaited_once_with(pedido_id, "CANCELADO")
        uow.historial_pedido.append.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_client_cancels_confirmado_ok(self):
        """CLIENT can cancel their own CONFIRMADO order (stock restored)."""
        user_id = uuid.uuid4()
        pedido_id = uuid.uuid4()
        pedido = _make_pedido("CONFIRMADO", pedido_id=pedido_id, usuario_id=user_id)
        uow = _make_uow(pedido)
        user = _make_user(["CLIENT"], user_id=user_id)

        with patch(
            "app.services.state_transition._restore_stock", new_callable=AsyncMock
        ) as mock_restore:
            await cancel_own_client(uow, pedido_id, "cambié de opinión", user)
            mock_restore.assert_awaited_once_with(uow, pedido_id)

        uow.pedidos.update_estado.assert_awaited_once_with(pedido_id, "CANCELADO")

    @pytest.mark.asyncio
    async def test_order_not_found_raises_404(self):
        """Returns 404 when order does not exist."""
        uow = _make_uow(None)
        user = _make_user(["CLIENT"])

        with pytest.raises(HTTPException) as exc_info:
            await cancel_own_client(uow, uuid.uuid4(), "motivo", user)
        assert exc_info.value.status_code == 404
        assert exc_info.value.detail["code"] == "ORDER_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_other_user_order_raises_403(self):
        """CLIENT trying to cancel another user's order raises 403 ORDER_NOT_OWNED."""
        pedido_owner_id = uuid.uuid4()
        other_user_id = uuid.uuid4()
        pedido_id = uuid.uuid4()
        pedido = _make_pedido("PENDIENTE", pedido_id=pedido_id, usuario_id=pedido_owner_id)
        uow = _make_uow(pedido)
        user = _make_user(["CLIENT"], user_id=other_user_id)

        with pytest.raises(HTTPException) as exc_info:
            await cancel_own_client(uow, pedido_id, "motivo", user)
        assert exc_info.value.status_code == 403
        assert exc_info.value.detail["code"] == "ORDER_NOT_OWNED"

    @pytest.mark.asyncio
    async def test_en_prep_raises_409(self):
        """CLIENT cannot cancel EN_PREP order via DELETE endpoint."""
        user_id = uuid.uuid4()
        pedido_id = uuid.uuid4()
        pedido = _make_pedido("EN_PREP", pedido_id=pedido_id, usuario_id=user_id)
        uow = _make_uow(pedido)
        user = _make_user(["CLIENT"], user_id=user_id)

        with pytest.raises(HTTPException) as exc_info:
            await cancel_own_client(uow, pedido_id, "motivo", user)
        assert exc_info.value.status_code == 409
        assert exc_info.value.detail["code"] == "INVALID_TRANSITION"

    @pytest.mark.asyncio
    async def test_en_camino_raises_409(self):
        """CLIENT cannot cancel EN_CAMINO order."""
        user_id = uuid.uuid4()
        pedido_id = uuid.uuid4()
        pedido = _make_pedido("EN_CAMINO", pedido_id=pedido_id, usuario_id=user_id)
        uow = _make_uow(pedido)
        user = _make_user(["CLIENT"], user_id=user_id)

        with pytest.raises(HTTPException) as exc_info:
            await cancel_own_client(uow, pedido_id, "motivo", user)
        assert exc_info.value.status_code == 409
        assert exc_info.value.detail["code"] == "INVALID_TRANSITION"

    @pytest.mark.asyncio
    async def test_missing_motivo_raises_422(self):
        """Missing motivo raises 422 MOTIVO_REQUIRED."""
        user_id = uuid.uuid4()
        pedido_id = uuid.uuid4()
        pedido = _make_pedido("PENDIENTE", pedido_id=pedido_id, usuario_id=user_id)
        uow = _make_uow(pedido)
        user = _make_user(["CLIENT"], user_id=user_id)

        with pytest.raises(HTTPException) as exc_info:
            await cancel_own_client(uow, pedido_id, None, user)
        assert exc_info.value.status_code == 422
        assert exc_info.value.detail["code"] == "MOTIVO_REQUIRED"

    @pytest.mark.asyncio
    async def test_empty_motivo_raises_422(self):
        """Empty string motivo is treated as missing → 422."""
        user_id = uuid.uuid4()
        pedido_id = uuid.uuid4()
        pedido = _make_pedido("PENDIENTE", pedido_id=pedido_id, usuario_id=user_id)
        uow = _make_uow(pedido)
        user = _make_user(["CLIENT"], user_id=user_id)

        with pytest.raises(HTTPException) as exc_info:
            await cancel_own_client(uow, pedido_id, "", user)
        assert exc_info.value.status_code == 422
        assert exc_info.value.detail["code"] == "MOTIVO_REQUIRED"

    @pytest.mark.asyncio
    async def test_historial_appended_with_actor_user_id(self):
        """Historial row is appended with cambiado_por_id = client user id."""
        user_id = uuid.uuid4()
        pedido_id = uuid.uuid4()
        pedido = _make_pedido("PENDIENTE", pedido_id=pedido_id, usuario_id=user_id)
        uow = _make_uow(pedido)
        user = _make_user(["CLIENT"], user_id=user_id)

        await cancel_own_client(uow, pedido_id, "ya no lo necesito", user)

        call_args = uow.historial_pedido.append.call_args[0][0]
        assert call_args.estado_desde == "PENDIENTE"
        assert call_args.estado_hasta == "CANCELADO"
        assert call_args.cambiado_por_id == user_id


# ---------------------------------------------------------------------------
# FSM constants sanity checks
# ---------------------------------------------------------------------------


class TestFSMConstants:
    """Sanity checks for the FSM constants."""

    def test_terminal_states(self):
        """ENTREGADO and CANCELADO are terminal states."""
        assert "ENTREGADO" in TERMINAL_STATES
        assert "CANCELADO" in TERMINAL_STATES

    def test_stock_restore_states(self):
        """Stock is restored from CONFIRMADO and EN_PREP."""
        assert "CONFIRMADO" in STATES_REQUIRING_STOCK_RESTORE
        assert "EN_PREP" in STATES_REQUIRING_STOCK_RESTORE
        assert "PENDIENTE" not in STATES_REQUIRING_STOCK_RESTORE

    def test_pendiente_to_confirmado_not_in_fsm(self):
        """PENDIENTE → CONFIRMADO is NOT in ALLOWED_TRANSITIONS (it's Change 19)."""
        pendiente_transitions = ALLOWED_TRANSITIONS.get("PENDIENTE", {})
        assert "CONFIRMADO" not in pendiente_transitions

    def test_client_not_in_any_allowed_role(self):
        """CLIENT role is not in ALLOWED_TRANSITIONS — clients use DELETE endpoint."""
        for _from_state, transitions in ALLOWED_TRANSITIONS.items():
            for _to_state, roles in transitions.items():
                assert "CLIENT" not in roles
