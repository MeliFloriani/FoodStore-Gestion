"""
Tests de integración para el router pedidos_validar.

Cubre los escenarios del spec RBAC y comportamiento HTTP:
  - 401 sin token
  - 403 con rol incorrecto (STOCK)
  - 422 con body mal formado
  - 200 con token CLIENT y carrito válido

Tasks cubiertos: 4.11–4.15.

Usa ASGITransport + make_uow_override (mismo patrón que test_productos.py).
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import AsyncClient

from app.core.uow import get_uow
from app.main import app

VALIDAR_URL = "/api/v1/pedidos/validar"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _register_and_login(client: AsyncClient, email: str) -> str:
    """Register a new user and return the access_token (CLIENT role auto-assigned)."""
    reg = await client.post(
        "/api/v1/auth/register",
        json={
            "nombre": "Test",
            "apellido": "Router",
            "email": email,
            "password": "Secur3Pass!",
        },
    )
    assert reg.status_code == 201, f"Register failed: {reg.text}"
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "Secur3Pass!"},
    )
    assert login.status_code == 200, f"Login failed: {login.text}"
    return login.json()["access_token"]


async def _make_stock_user(client: AsyncClient, seeded_session) -> str:
    """Create a user with STOCK role only and return access_token."""
    from app.models.user import UsuarioRol
    from app.repositories.user import RolRepository

    email = f"stock_{uuid.uuid4().hex[:8]}@test.com"

    # Register (gets CLIENT role)
    reg = await client.post(
        "/api/v1/auth/register",
        json={
            "nombre": "Stock",
            "apellido": "User",
            "email": email,
            "password": "Secur3Pass!",
        },
    )
    assert reg.status_code == 201

    login = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "Secur3Pass!"},
    )
    assert login.status_code == 200
    token = login.json()["access_token"]

    # Get user ID
    me = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert me.status_code == 200
    user_id = uuid.UUID(me.json()["id"])

    # Remove CLIENT role and assign STOCK only
    # Assign STOCK role
    rol_repo = RolRepository(seeded_session)
    stock_rol = await rol_repo.get_by_codigo("STOCK")
    assert stock_rol is not None

    # Remove CLIENT role assignment by querying it
    from sqlalchemy import select
    from app.models.user import UsuarioRol as URModel

    stmt = select(URModel).where(URModel.usuario_id == user_id)
    result = await seeded_session.execute(stmt)
    for ur in result.scalars().all():
        await seeded_session.delete(ur)
    await seeded_session.flush()

    # Add STOCK role
    ur = UsuarioRol(usuario_id=user_id, rol_id=stock_rol.id, asignado_por_id=None)
    seeded_session.add(ur)
    await seeded_session.flush()

    # Re-login to get token with STOCK role
    login2 = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "Secur3Pass!"},
    )
    assert login2.status_code == 200
    return login2.json()["access_token"]


def _valid_payload(producto_id: str | None = None) -> dict:
    """Return a minimal valid request payload for the validar endpoint."""
    return {
        "items": [
            {
                "producto_id": producto_id or str(uuid.uuid4()),
                "cantidad": 1,
                "personalizacion": [],
                "precio": "100.00",
            }
        ]
    }


def _make_mock_uow_for_router(producto_id_str: str) -> MagicMock:
    """Build a mock UoW that returns a valid product for the given ID."""
    pid = uuid.UUID(producto_id_str)
    producto = MagicMock()
    producto.id = pid
    producto.precio_base = 100.00
    producto.stock_cantidad = 5
    producto.disponible = True
    producto.deleted_at = None

    repo = MagicMock()
    repo.get_by_ids = AsyncMock(return_value=[producto])

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []

    mock_session = MagicMock()
    mock_session.execute = AsyncMock(return_value=mock_result)

    uow = MagicMock()
    uow.productos = repo
    uow.session = mock_session

    return uow


# ---------------------------------------------------------------------------
# Task 4.11 — Fixture: async_client with seeded_session
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_router_fixture_is_accessible(seeded_session, async_client: AsyncClient):
    """Task 4.11: Verificar que el router responde a una petición base."""
    from tests.fixtures.uow import make_uow_override

    app.dependency_overrides[get_uow] = make_uow_override(seeded_session)
    try:
        response = await async_client.post(
            VALIDAR_URL,
            json=_valid_payload(),
        )
        # Without auth, should be 401
        assert response.status_code in (200, 401, 422)
    finally:
        app.dependency_overrides.pop(get_uow, None)


# ---------------------------------------------------------------------------
# Task 4.12 — 401 sin token
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_validar_sin_token_retorna_401(seeded_session, async_client: AsyncClient):
    """Task 4.12: POST /api/v1/pedidos/validar sin Authorization header → 401."""
    from tests.fixtures.uow import make_uow_override

    app.dependency_overrides[get_uow] = make_uow_override(seeded_session)
    try:
        response = await async_client.post(
            VALIDAR_URL,
            json=_valid_payload(),
        )
        assert response.status_code == 401, (
            f"Expected 401 (no token), got: {response.status_code} {response.text}"
        )
    finally:
        app.dependency_overrides.pop(get_uow, None)


# ---------------------------------------------------------------------------
# Task 4.13 — 403 con rol STOCK
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_validar_con_rol_stock_retorna_403(seeded_session, async_client: AsyncClient):
    """Task 4.13: POST /api/v1/pedidos/validar con token STOCK → 403 Forbidden."""
    from tests.fixtures.uow import make_uow_override

    app.dependency_overrides[get_uow] = make_uow_override(seeded_session)
    try:
        stock_token = await _make_stock_user(async_client, seeded_session)
        response = await async_client.post(
            VALIDAR_URL,
            json=_valid_payload(),
            headers={"Authorization": f"Bearer {stock_token}"},
        )
        assert response.status_code == 403, (
            f"Expected 403 (STOCK role), got: {response.status_code} {response.text}"
        )
    finally:
        app.dependency_overrides.pop(get_uow, None)


# ---------------------------------------------------------------------------
# Task 4.14 — 422 con body mal formado
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_validar_body_mal_formado_retorna_422(
    seeded_session, async_client: AsyncClient
) -> None:
    """Task 4.14: POST /api/v1/pedidos/validar con body inválido → 422 Unprocessable Entity."""
    from tests.fixtures.uow import make_uow_override

    email = f"client422_{uuid.uuid4().hex[:8]}@test.com"
    app.dependency_overrides[get_uow] = make_uow_override(seeded_session)
    try:
        token = await _register_and_login(async_client, email)

        # Enviar items vacía (min_length=1 falla)
        response = await async_client.post(
            VALIDAR_URL,
            json={"items": []},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 422, (
            f"Expected 422 (empty items), got: {response.status_code} {response.text}"
        )
    finally:
        app.dependency_overrides.pop(get_uow, None)


# ---------------------------------------------------------------------------
# Task 4.15 — 200 con token CLIENT y carrito válido
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_validar_con_token_client_carrito_valido_retorna_200_ok(
    seeded_session, async_client: AsyncClient
) -> None:
    """Task 4.15: POST /api/v1/pedidos/validar con CLIENT token y carrito válido → 200 ok=True."""
    pid_str = str(uuid.uuid4())
    mock_uow = _make_mock_uow_for_router(pid_str)

    async def _override():
        yield mock_uow

    email = f"client200_{uuid.uuid4().hex[:8]}@test.com"
    # We need the auth layer to work, but mock the business layer
    from tests.fixtures.uow import make_uow_override

    app.dependency_overrides[get_uow] = make_uow_override(seeded_session)
    try:
        token = await _register_and_login(async_client, email)

        # Now override with the business mock that returns a valid product
        # We need to temporarily patch the service to return a valid response
        from unittest.mock import patch
        from app.schemas.pedidos_validar import (
            ValidarPreCheckoutResponse,
            ItemValidadoRead,
        )

        mock_response = ValidarPreCheckoutResponse(
            ok=True,
            items=[
                ItemValidadoRead(
                    producto_id=pid_str,
                    cantidad_solicitada=1,
                    stock_disponible=5,
                    precio_actual="100.00",
                    precio_percibido="100.00",
                    vigente=True,
                    disponible=True,
                )
            ],
            cambios=[],
        )

        with patch(
            "app.api.v1.pedidos_validar.pedidos_validar_service.validar_pre_checkout",
            new=AsyncMock(return_value=mock_response),
        ):
            response = await async_client.post(
                VALIDAR_URL,
                json=_valid_payload(pid_str),
                headers={"Authorization": f"Bearer {token}"},
            )

        assert response.status_code == 200, (
            f"Expected 200, got: {response.status_code} {response.text}"
        )
        body = response.json()
        assert body["ok"] is True
        assert body["cambios"] == []
    finally:
        app.dependency_overrides.pop(get_uow, None)
