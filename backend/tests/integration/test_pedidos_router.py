"""
Integration tests for POST /api/v1/pedidos endpoint (Change 17).

Epic 8 del tasks.md: tests del router con cliente HTTP y autenticación.

Tests are split into:
1. No-seed tests (always runnable): auth guard (401), schema validation (422 on bad shape)
2. Integration tests requiring seeded DB: marked @pytest.mark.integration

Note: The test database must have seeded:
  - Rol: CLIENT
  - EstadoPedido: PENDIENTE
  - FormaPago: EFECTIVO
  to run the integration-marked tests.
"""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient

PEDIDOS_URL = "/api/v1/pedidos"
REGISTER_URL = "/api/v1/auth/register"
LOGIN_URL = "/api/v1/auth/login"


def _auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _new_email() -> str:
    return f"pedido_test_{uuid.uuid4().hex[:8]}@test.com"


async def _register_and_login(
    client: AsyncClient,
    email: str,
    password: str = "Secur3Pass!",
) -> str:
    """Register and login a user. Requires seeded DB (CLIENT role)."""
    reg = await client.post(
        REGISTER_URL,
        json={
            "nombre": "Test",
            "apellido": "Pedidos",
            "email": email,
            "password": password,
        },
    )
    assert reg.status_code == 201, f"Registration failed: {reg.text}"
    login = await client.post(
        LOGIN_URL,
        json={"email": email, "password": password},
    )
    assert login.status_code == 200, f"Login failed: {login.text}"
    return login.json()["access_token"]


# ---------------------------------------------------------------------------
# Task 8.2: Unauthenticated → 401
# No seed data needed — auth guard runs before any DB query.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_post_pedidos_401_unauthenticated(async_client: AsyncClient):
    """POST /api/v1/pedidos without token → 401."""
    response = await async_client.post(
        PEDIDOS_URL,
        json={
            "items": [{"producto_id": str(uuid.uuid4()), "cantidad": 1}],
            "forma_pago_codigo": "EFECTIVO",
        },
    )
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Schema validation: 422 on bad body shape (can verify without token if
# FastAPI validates schema before auth — but with auth guard first, need token)
# These tests require seeded DB. Marked @pytest.mark.integration.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.integration  # Requires seeded CLIENT role in test DB
async def test_post_pedidos_422_malformed_body(async_client: AsyncClient):
    """POST /api/v1/pedidos with malformed body → 422."""
    token = await _register_and_login(async_client, _new_email())
    response = await async_client.post(
        PEDIDOS_URL,
        json={"items": "not-a-list", "forma_pago_codigo": "EFECTIVO"},
        headers=_auth_headers(token),
    )
    assert response.status_code == 422


@pytest.mark.asyncio
@pytest.mark.integration  # Requires seeded CLIENT role in test DB
async def test_post_pedidos_422_missing_forma_pago(async_client: AsyncClient):
    """POST /api/v1/pedidos missing forma_pago_codigo → 422."""
    token = await _register_and_login(async_client, _new_email())
    response = await async_client.post(
        PEDIDOS_URL,
        json={
            "items": [{"producto_id": str(uuid.uuid4()), "cantidad": 1}],
            # Missing forma_pago_codigo
        },
        headers=_auth_headers(token),
    )
    assert response.status_code == 422


@pytest.mark.asyncio
@pytest.mark.integration  # Requires seeded CLIENT role in test DB
async def test_post_pedidos_client_role_reaches_service(async_client: AsyncClient):
    """CLIENT role user passes auth+role guard (response is not 401 or 403)."""
    token = await _register_and_login(async_client, _new_email())
    # Schema-valid but empty items → 422 from Pydantic (not 401/403)
    response = await async_client.post(
        PEDIDOS_URL,
        json={"items": [], "forma_pago_codigo": "EFECTIVO"},
        headers=_auth_headers(token),
    )
    assert response.status_code not in (401, 403), (
        f"Expected not 401/403 (auth/role failure), got {response.status_code}: {response.text}"
    )
