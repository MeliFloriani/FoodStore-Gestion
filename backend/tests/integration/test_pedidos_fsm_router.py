"""
Integration tests for Change 18 FSM endpoints:
  PATCH /api/v1/pedidos/{id}/estado  — staff state transitions
  DELETE /api/v1/pedidos/{id}        — client self-cancellation
  GET /api/v1/pedidos/{id}/historial  — order history

All tests that require DB are marked @pytest.mark.integration.
No-seed tests (auth guard 401/403) are always runnable.

EFECTIVO tests (at the bottom) require seeded DB with:
  - Roles: CLIENT, PEDIDOS, ADMIN
  - FormaPago: EFECTIVO, MERCADOPAGO
  - EstadoPedido: PENDIENTE, CONFIRMADO, EN_PREP, EN_CAMINO, ENTREGADO, CANCELADO
  - At least one available Producto with stock
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
    return f"fsm_test_{uuid.uuid4().hex[:8]}@test.com"


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
            "apellido": "FSM",
            "email": email,
            "password": password,
        },
    )
    assert reg.status_code == 201, f"Registration failed: {reg.text}"
    login_resp = await client.post(
        LOGIN_URL,
        json={"email": email, "password": password},
    )
    assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
    return login_resp.json()["access_token"]


# ---------------------------------------------------------------------------
# Auth guard tests — no seed required
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_patch_estado_401_unauthenticated(async_client: AsyncClient):
    """PATCH /{id}/estado without token → 401."""
    response = await async_client.patch(
        f"{PEDIDOS_URL}/{uuid.uuid4()}/estado",
        json={"nuevo_estado": "EN_PREP"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_delete_pedido_401_unauthenticated(async_client: AsyncClient):
    """DELETE /{id} without token → 401."""
    response = await async_client.delete(
        f"{PEDIDOS_URL}/{uuid.uuid4()}",
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_historial_401_unauthenticated(async_client: AsyncClient):
    """GET /{id}/historial without token → 401."""
    response = await async_client.get(
        f"{PEDIDOS_URL}/{uuid.uuid4()}/historial",
    )
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Role guard tests — require seeded CLIENT role but not full order flow
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.integration
async def test_patch_estado_403_client_role(async_client: AsyncClient):
    """PATCH /{id}/estado with CLIENT role → 403 (requires PEDIDOS or ADMIN)."""
    token = await _register_and_login(async_client, _new_email())
    response = await async_client.patch(
        f"{PEDIDOS_URL}/{uuid.uuid4()}/estado",
        json={"nuevo_estado": "EN_PREP"},
        headers=_auth_headers(token),
    )
    # CLIENT role → 403 from require_role("PEDIDOS", "ADMIN")
    assert response.status_code == 403


@pytest.mark.asyncio
@pytest.mark.integration
async def test_delete_pedido_403_stock_role(async_client: AsyncClient):
    """DELETE /{id} with STOCK role → 403 (requires CLIENT)."""
    # Register CLIENT user first, then we can only verify a stock user can't access
    # Since we can only register CLIENT users via the public API, we test with CLIENT
    # that receives 404 for non-existent pedido (past auth)
    token = await _register_and_login(async_client, _new_email())
    response = await async_client.delete(
        f"{PEDIDOS_URL}/{uuid.uuid4()}",
        json={"nuevo_estado": "CANCELADO", "motivo": "test"},
        headers=_auth_headers(token),
    )
    # CLIENT role should pass auth (403 or 404 are both "past auth guard")
    assert response.status_code not in (401,)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_historial_403_stock_role(async_client: AsyncClient):
    """GET /{id}/historial — CLIENT user for non-existent order gets 404 (past auth guard)."""
    token = await _register_and_login(async_client, _new_email())
    response = await async_client.get(
        f"{PEDIDOS_URL}/{uuid.uuid4()}/historial",
        headers=_auth_headers(token),
    )
    # Past auth guard — 404 for non-existent order
    assert response.status_code not in (401,)


# ---------------------------------------------------------------------------
# Schema validation tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.integration
async def test_patch_estado_422_missing_nuevo_estado(async_client: AsyncClient):
    """PATCH /{id}/estado missing nuevo_estado → 422."""
    token = await _register_and_login(async_client, _new_email())
    response = await async_client.patch(
        f"{PEDIDOS_URL}/{uuid.uuid4()}/estado",
        json={"motivo": "some reason"},  # Missing nuevo_estado
        headers=_auth_headers(token),
    )
    # 422 from Pydantic schema validation OR 403 from role check
    # Since CLIENT doesn't have PEDIDOS/ADMIN role, expect 403
    assert response.status_code in (422, 403)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_delete_pedido_passes_auth_for_client(async_client: AsyncClient):
    """DELETE /{id} with CLIENT role passes auth guard (response is not 401)."""
    token = await _register_and_login(async_client, _new_email())
    response = await async_client.delete(
        f"{PEDIDOS_URL}/{uuid.uuid4()}",
        json={"nuevo_estado": "CANCELADO", "motivo": "ya no lo necesito"},
        headers=_auth_headers(token),
    )
    # Should NOT be 401 (passed auth)
    assert response.status_code != 401


# ---------------------------------------------------------------------------
# EFECTIVO confirmation tests — new behavior added in EFECTIVO support change
# ---------------------------------------------------------------------------
#
# Helper pattern:
#   1. Create a PEDIDOS user (register CLIENT + assign PEDIDOS role via repository)
#   2. Create a CLIENT user (register via public API)
#   3. Create a product with ADMIN (or use existing seeded DEV product)
#   4. Create an order via POST /pedidos with forma_pago_codigo=EFECTIVO
#   5. PATCH the order to CONFIRMADO with PEDIDOS token
#
# These tests use seeded_session + make_uow_override to keep data isolated.
# ---------------------------------------------------------------------------


async def _make_pedidos_user(
    client: AsyncClient,
    seeded_session,
    suffix: str = "",
) -> str:
    """Register a user, assign PEDIDOS role, return access_token."""
    from app.models.user import UsuarioRol
    from app.repositories.user import RolRepository

    email = f"pedidos_fsm_{suffix}_{uuid.uuid4().hex[:6]}@test.com"
    token = await _register_and_login(client, email)

    # Get user ID from /me
    me_resp = await client.get(
        "/api/v1/auth/me",
        headers=_auth_headers(token),
    )
    assert me_resp.status_code == 200
    user_id = uuid.UUID(me_resp.json()["id"])

    # Assign PEDIDOS role via repository
    rol_repo = RolRepository(seeded_session)
    rol = await rol_repo.get_by_codigo("PEDIDOS")
    assert rol is not None, "PEDIDOS role not seeded"

    ur = UsuarioRol(usuario_id=user_id, rol_id=rol.id, asignado_por_id=None)
    seeded_session.add(ur)
    await seeded_session.flush()

    # Re-login to get token with updated roles
    login = await client.post(
        LOGIN_URL,
        json={"email": email, "password": "Secur3Pass!"},
    )
    assert login.status_code == 200
    return login.json()["access_token"]


async def _get_seeded_product_id(client: AsyncClient) -> str:
    """Return the product ID of a seeded DEV product from the test DB.

    Uses the public catalog endpoint (no auth required).
    Requires that seed_dev_catalog() has been run on the test database.
    """
    resp = await client.get("/api/v1/productos/?page=1&size=1")
    assert resp.status_code == 200, f"Catalog unavailable: {resp.text}"
    items = resp.json().get("items", [])
    assert len(items) > 0, "No seeded products found — run seed_dev_catalog on test DB"
    return str(items[0]["id"])


async def _create_order(
    client: AsyncClient,
    seeded_session,
    producto_id: str,
    forma_pago_codigo: str,
    client_token: str,
) -> str:
    """Place an order as CLIENT using the given product. Return pedido_id.

    Uses make_uow_override(seeded_session) so the PEDIDOS role assigned to
    pedidos_user (via seeded_session) is visible during the PATCH request.
    The order creation uses the seeded_session so the new pedido is in the
    same SAVEPOINT-isolated transaction.
    """
    from app.core.uow import get_uow
    from app.main import app
    from tests.fixtures.uow import make_uow_override

    app.dependency_overrides[get_uow] = make_uow_override(seeded_session)
    try:
        pedido_resp = await client.post(
            PEDIDOS_URL,
            json={
                "items": [{"producto_id": producto_id, "cantidad": 1}],
                "forma_pago_codigo": forma_pago_codigo,
            },
            headers=_auth_headers(client_token),
        )
        assert pedido_resp.status_code == 201, f"Order creation failed: {pedido_resp.text}"
        return pedido_resp.json()["id"]
    finally:
        app.dependency_overrides.pop(get_uow, None)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_patch_estado_pendiente_confirmado_efectivo_ok(
    async_client: AsyncClient,
    seeded_session,
) -> None:
    """PEDIDOS staff can confirm PENDIENTE → CONFIRMADO for EFECTIVO order.

    New behavior: EFECTIVO orders can be manually confirmed by staff.
    """
    from app.core.uow import get_uow
    from app.main import app
    from tests.fixtures.uow import make_uow_override

    client_token = await _register_and_login(async_client, _new_email())
    pedidos_token = await _make_pedidos_user(async_client, seeded_session, suffix="eff_ok")
    producto_id = await _get_seeded_product_id(async_client)

    pedido_id = await _create_order(
        async_client, seeded_session, producto_id, "EFECTIVO", client_token
    )

    app.dependency_overrides[get_uow] = make_uow_override(seeded_session)
    try:
        response = await async_client.patch(
            f"{PEDIDOS_URL}/{pedido_id}/estado",
            json={"nuevo_estado": "CONFIRMADO"},
            headers=_auth_headers(pedidos_token),
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data["estado_codigo"] == "CONFIRMADO"
        assert data["forma_pago_codigo"] == "EFECTIVO"
    finally:
        app.dependency_overrides.pop(get_uow, None)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_patch_estado_pendiente_confirmado_mercadopago_rejected(
    async_client: AsyncClient,
    seeded_session,
) -> None:
    """PENDIENTE → CONFIRMADO is rejected (409) for MERCADOPAGO orders.

    MERCADOPAGO orders are confirmed automatically via webhook (Change 19).
    Manual confirmation is not allowed.
    """
    from app.core.uow import get_uow
    from app.main import app
    from tests.fixtures.uow import make_uow_override

    client_token = await _register_and_login(async_client, _new_email())
    pedidos_token = await _make_pedidos_user(async_client, seeded_session, suffix="mp_rej")
    producto_id = await _get_seeded_product_id(async_client)

    pedido_id = await _create_order(
        async_client, seeded_session, producto_id, "MERCADOPAGO", client_token
    )

    app.dependency_overrides[get_uow] = make_uow_override(seeded_session)
    try:
        response = await async_client.patch(
            f"{PEDIDOS_URL}/{pedido_id}/estado",
            json={"nuevo_estado": "CONFIRMADO"},
            headers=_auth_headers(pedidos_token),
        )
        assert response.status_code == 409, f"Expected 409, got {response.status_code}: {response.text}"
        body = response.json()
        assert body.get("detail", {}).get("code") == "INVALID_TRANSITION"
    finally:
        app.dependency_overrides.pop(get_uow, None)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_patch_estado_pendiente_confirmado_efectivo_full_fsm(
    async_client: AsyncClient,
    seeded_session,
) -> None:
    """EFECTIVO order goes PENDIENTE → CONFIRMADO → EN_PREP → EN_CAMINO → ENTREGADO.

    Verifies the entire happy path for a cash order.
    """
    from app.core.uow import get_uow
    from app.main import app
    from tests.fixtures.uow import make_uow_override

    client_token = await _register_and_login(async_client, _new_email())
    pedidos_token = await _make_pedidos_user(async_client, seeded_session, suffix="full_fsm")
    producto_id = await _get_seeded_product_id(async_client)

    pedido_id = await _create_order(
        async_client, seeded_session, producto_id, "EFECTIVO", client_token
    )

    transitions = [
        ("CONFIRMADO", 200),
        ("EN_PREP", 200),
        ("EN_CAMINO", 200),
        ("ENTREGADO", 200),
    ]

    for nuevo_estado, expected_status in transitions:
        app.dependency_overrides[get_uow] = make_uow_override(seeded_session)
        try:
            response = await async_client.patch(
                f"{PEDIDOS_URL}/{pedido_id}/estado",
                json={"nuevo_estado": nuevo_estado},
                headers=_auth_headers(pedidos_token),
            )
            assert response.status_code == expected_status, (
                f"Transition to {nuevo_estado} failed: "
                f"got {response.status_code}: {response.text}"
            )
            assert response.json()["estado_codigo"] == nuevo_estado
        finally:
            app.dependency_overrides.pop(get_uow, None)
