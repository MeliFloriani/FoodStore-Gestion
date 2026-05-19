"""
Integration tests for the Productos API endpoints.

Tasks 6.3–6.10:
  - test_get_productos_public_no_auth: GET /api/v1/productos → 200 PaginatedProductos
  - test_get_producto_detail_not_found_returns_404: GET /{fake_id} → 404
  - test_get_producto_ingredientes_non_existent_product_returns_404: GET /{fake_id}/ingredientes → 404
  - test_post_productos_requires_admin_jwt: no token → 401; STOCK → 403; ADMIN → 201
  - test_patch_disponibilidad_allows_stock_role: STOCK → 200; CLIENT → 403
  - test_patch_disponibilidad_no_token_returns_401: no token → 401
  - test_delete_producto_soft_deletes: ADMIN → 204; GET → 404
  - test_add_ingrediente_duplicate_returns_409: same ingredient twice → 409
  - test_delete_ingrediente_from_producto_returns_204: ADMIN → 204
  - test_productos_route_registered: inspect route list

Uses the SAVEPOINT-based seeded_session and async_client fixtures.
"""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient

from app.core.uow import get_uow
from app.main import app
from tests.fixtures.uow import make_uow_override

PRODUCTOS_URL = "/api/v1/productos/"
PRODUCTOS_BASE = "/api/v1/productos"


# ---------------------------------------------------------------------------
# Helpers — register + login + role assignment (same pattern as test_ingredientes)
# ---------------------------------------------------------------------------


async def _register_and_get_token(
    client: AsyncClient,
    email: str,
    password: str = "Secur3Pass!",
) -> str:
    """Register a user (auto-assigns CLIENT role) and return access_token."""
    reg = await client.post(
        "/api/v1/auth/register",
        json={
            "nombre": "Test",
            "apellido": "User",
            "email": email,
            "password": password,
        },
    )
    assert reg.status_code == 201, f"Registration failed: {reg.text}"
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert login.status_code == 200, f"Login failed: {login.text}"
    return login.json()["access_token"]


async def _make_role_user(
    client: AsyncClient,
    seeded_session,
    role_code: str,
    suffix: str = "",
) -> str:
    """Register a user, assign a specific role, return access_token."""
    from app.models.user import UsuarioRol
    from app.repositories.user import RolRepository

    email = f"prod_{role_code.lower()}_{suffix}_{uuid.uuid4().hex[:6]}@test.com"
    token = await _register_and_get_token(client, email)

    # Get user ID from /me
    me_resp = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert me_resp.status_code == 200
    user_id = uuid.UUID(me_resp.json()["id"])

    # Assign role via repository
    rol_repo = RolRepository(seeded_session)
    rol = await rol_repo.get_by_codigo(role_code)
    assert rol is not None, f"{role_code} role not seeded"

    ur = UsuarioRol(usuario_id=user_id, rol_id=rol.id, asignado_por_id=None)
    seeded_session.add(ur)
    await seeded_session.flush()

    # Re-login to get token with updated roles
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "Secur3Pass!"},
    )
    assert login.status_code == 200
    return login.json()["access_token"]


async def _create_product(client: AsyncClient, admin_token: str, **kwargs) -> dict:
    """Helper to create a product with ADMIN token and return response JSON."""
    payload = {
        "nombre": f"Producto_{uuid.uuid4().hex[:8]}",
        "precio_base": "10.00",
        "stock_cantidad": 5,
        "disponible": True,
    }
    payload.update(kwargs)
    resp = await client.post(
        PRODUCTOS_URL,
        json=payload,
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 201, f"Product creation failed: {resp.text}"
    return resp.json()


# ---------------------------------------------------------------------------
# Task 6.3 — GET /api/v1/productos returns 200 PaginatedProductos (public)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_productos_public_no_auth(
    seeded_session, async_client: AsyncClient
) -> None:
    """GET /api/v1/productos without auth returns 200 with PaginatedProductos shape.

    Task 6.3.
    """
    app.dependency_overrides[get_uow] = make_uow_override(seeded_session)
    try:
        response = await async_client.get(PRODUCTOS_URL)
        assert response.status_code == 200, f"Expected 200, got: {response.text}"
        body = response.json()
        assert "items" in body, f"Missing 'items' in response: {body}"
        assert "total" in body
        assert "page" in body
        assert "size" in body
        assert "pages" in body
        assert isinstance(body["items"], list)
    finally:
        app.dependency_overrides.pop(get_uow, None)


# ---------------------------------------------------------------------------
# Task 6.4 — GET /api/v1/productos/{fake_id} returns 404
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_producto_detail_not_found_returns_404(
    seeded_session, async_client: AsyncClient
) -> None:
    """GET /api/v1/productos/{non_existent_id} returns 404 PRODUCT_NOT_FOUND.

    Task 6.4.
    """
    app.dependency_overrides[get_uow] = make_uow_override(seeded_session)
    try:
        fake_id = str(uuid.uuid4())
        response = await async_client.get(f"{PRODUCTOS_BASE}/{fake_id}")
        assert response.status_code == 404, f"Expected 404, got: {response.text}"
        body = response.json()
        assert body.get("code") == "PRODUCT_NOT_FOUND", (
            f"Expected code='PRODUCT_NOT_FOUND', got: {body}"
        )
    finally:
        app.dependency_overrides.pop(get_uow, None)


# ---------------------------------------------------------------------------
# Task 6.4b — GET /api/v1/productos/{fake_id}/ingredientes returns 404 (not 200 empty)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_producto_ingredientes_non_existent_product_returns_404(
    seeded_session, async_client: AsyncClient
) -> None:
    """GET /api/v1/productos/{non_existent_id}/ingredientes returns 404 PRODUCT_NOT_FOUND.

    Task 6.4b: must be 404, NOT 200 with empty list.
    """
    app.dependency_overrides[get_uow] = make_uow_override(seeded_session)
    try:
        fake_id = str(uuid.uuid4())
        response = await async_client.get(f"{PRODUCTOS_BASE}/{fake_id}/ingredientes")
        assert response.status_code == 404, (
            f"Expected 404, got: {response.status_code} {response.text}"
        )
        body = response.json()
        assert body.get("code") == "PRODUCT_NOT_FOUND", (
            f"Expected code='PRODUCT_NOT_FOUND', got: {body}"
        )
    finally:
        app.dependency_overrides.pop(get_uow, None)


# ---------------------------------------------------------------------------
# Task 6.5 — POST /api/v1/productos requires ADMIN JWT
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_post_productos_requires_admin_jwt(
    seeded_session, async_client: AsyncClient
) -> None:
    """POST /api/v1/productos: no token → 401; STOCK → 403; ADMIN → 201.

    Task 6.5.
    """
    app.dependency_overrides[get_uow] = make_uow_override(seeded_session)
    try:
        payload = {
            "nombre": f"Test Prod {uuid.uuid4().hex[:8]}",
            "precio_base": "10.00",
        }

        # No token → 401
        r_no_auth = await async_client.post(PRODUCTOS_URL, json=payload)
        assert r_no_auth.status_code == 401, (
            f"Expected 401 without token, got: {r_no_auth.status_code} {r_no_auth.text}"
        )

        # STOCK token → 403
        stock_token = await _make_role_user(async_client, seeded_session, "STOCK", suffix="post_stock")
        r_stock = await async_client.post(
            PRODUCTOS_URL,
            json=payload,
            headers={"Authorization": f"Bearer {stock_token}"},
        )
        assert r_stock.status_code == 403, (
            f"Expected 403 for STOCK, got: {r_stock.status_code} {r_stock.text}"
        )

        # ADMIN token → 201
        admin_token = await _make_role_user(async_client, seeded_session, "ADMIN", suffix="post_admin")
        r_admin = await async_client.post(
            PRODUCTOS_URL,
            json=payload,
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r_admin.status_code == 201, (
            f"Expected 201 for ADMIN, got: {r_admin.status_code} {r_admin.text}"
        )
        body = r_admin.json()
        assert "id" in body
        assert body["nombre"] == payload["nombre"]
        assert body["precio_base"] == "10.00"  # serialized as string (H-02)
    finally:
        app.dependency_overrides.pop(get_uow, None)


# ---------------------------------------------------------------------------
# Task 6.6 — PATCH /disponibilidad allows STOCK role → 200; CLIENT → 403
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_patch_disponibilidad_allows_stock_role(
    seeded_session, async_client: AsyncClient
) -> None:
    """PATCH /api/v1/productos/{id}/disponibilidad: STOCK → 200; CLIENT → 403.

    Task 6.6.
    """
    app.dependency_overrides[get_uow] = make_uow_override(seeded_session)
    try:
        admin_token = await _make_role_user(async_client, seeded_session, "ADMIN", suffix="disp_admin")
        stock_token = await _make_role_user(async_client, seeded_session, "STOCK", suffix="disp_stock")
        client_token = await _register_and_get_token(
            async_client, f"prod_client_{uuid.uuid4().hex[:6]}@test.com"
        )

        # Create product with admin
        prod = await _create_product(async_client, admin_token)
        prod_id = prod["id"]

        # STOCK → 200
        r_stock = await async_client.patch(
            f"{PRODUCTOS_BASE}/{prod_id}/disponibilidad",
            json={"disponible": False},
            headers={"Authorization": f"Bearer {stock_token}"},
        )
        assert r_stock.status_code == 200, (
            f"Expected 200 for STOCK, got: {r_stock.status_code} {r_stock.text}"
        )
        assert r_stock.json()["disponible"] is False

        # CLIENT → 403
        r_client = await async_client.patch(
            f"{PRODUCTOS_BASE}/{prod_id}/disponibilidad",
            json={"disponible": True},
            headers={"Authorization": f"Bearer {client_token}"},
        )
        assert r_client.status_code == 403, (
            f"Expected 403 for CLIENT, got: {r_client.status_code} {r_client.text}"
        )
    finally:
        app.dependency_overrides.pop(get_uow, None)


# ---------------------------------------------------------------------------
# Task 6.6b — PATCH /disponibilidad without token returns 401 (not 403)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_patch_disponibilidad_no_token_returns_401(
    seeded_session, async_client: AsyncClient
) -> None:
    """PATCH /api/v1/productos/{id}/disponibilidad without token returns 401.

    Task 6.6b: 401 (missing_token) is evaluated BEFORE 403 (forbidden).
    """
    app.dependency_overrides[get_uow] = make_uow_override(seeded_session)
    try:
        admin_token = await _make_role_user(async_client, seeded_session, "ADMIN", suffix="disp401")
        prod = await _create_product(async_client, admin_token)
        prod_id = prod["id"]

        # No token → 401 (not 403)
        r = await async_client.patch(
            f"{PRODUCTOS_BASE}/{prod_id}/disponibilidad",
            json={"disponible": False},
        )
        assert r.status_code == 401, (
            f"Expected 401 without token, got: {r.status_code} {r.text}"
        )
    finally:
        app.dependency_overrides.pop(get_uow, None)


# ---------------------------------------------------------------------------
# Task 6.7 — DELETE /api/v1/productos/{id} soft-deletes; GET → 404
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_producto_soft_deletes(
    seeded_session, async_client: AsyncClient
) -> None:
    """DELETE /api/v1/productos/{id}: ADMIN → 204; subsequent GET → 404.

    Task 6.7.
    """
    app.dependency_overrides[get_uow] = make_uow_override(seeded_session)
    try:
        admin_token = await _make_role_user(async_client, seeded_session, "ADMIN", suffix="del")

        # Create product
        prod = await _create_product(async_client, admin_token)
        prod_id = prod["id"]

        # Delete → 204
        r_delete = await async_client.delete(
            f"{PRODUCTOS_BASE}/{prod_id}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r_delete.status_code == 204, (
            f"Expected 204 on delete, got: {r_delete.status_code} {r_delete.text}"
        )

        # GET → 404 (soft-deleted)
        r_get = await async_client.get(f"{PRODUCTOS_BASE}/{prod_id}")
        assert r_get.status_code == 404, (
            f"Expected 404 after soft-delete, got: {r_get.status_code} {r_get.text}"
        )
        assert r_get.json().get("code") == "PRODUCT_NOT_FOUND"
    finally:
        app.dependency_overrides.pop(get_uow, None)


# ---------------------------------------------------------------------------
# Task 6.8 — POST /ingredientes duplicate returns 409
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_add_ingrediente_duplicate_returns_409(
    seeded_session, async_client: AsyncClient
) -> None:
    """POST /api/v1/productos/{id}/ingredientes twice with same ingredient → 409.

    Task 6.8.
    """
    app.dependency_overrides[get_uow] = make_uow_override(seeded_session)
    try:
        admin_token = await _make_role_user(async_client, seeded_session, "ADMIN", suffix="dup_ing")

        # Create product
        prod = await _create_product(async_client, admin_token)
        prod_id = prod["id"]

        # Create ingredient
        suffix = uuid.uuid4().hex[:8]
        ing_resp = await async_client.post(
            "/api/v1/ingredientes/",
            json={"nombre": f"Gluten_{suffix}", "es_alergeno": True},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert ing_resp.status_code == 201, f"Failed to create ingredient: {ing_resp.text}"
        ing_id = ing_resp.json()["id"]

        # First association → 201
        r1 = await async_client.post(
            f"{PRODUCTOS_BASE}/{prod_id}/ingredientes",
            json={"ingrediente_id": ing_id, "es_removible": True},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r1.status_code == 201, f"First add should succeed: {r1.text}"

        # Second association → 409
        r2 = await async_client.post(
            f"{PRODUCTOS_BASE}/{prod_id}/ingredientes",
            json={"ingrediente_id": ing_id, "es_removible": False},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r2.status_code == 409, (
            f"Expected 409 on duplicate ingredient, got: {r2.status_code} {r2.text}"
        )
        assert r2.json().get("code") == "PRODUCT_INGREDIENT_DUPLICATE"
    finally:
        app.dependency_overrides.pop(get_uow, None)


# ---------------------------------------------------------------------------
# Task 6.9 — DELETE /ingredientes/{ing_id} returns 204
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_ingrediente_from_producto_returns_204(
    seeded_session, async_client: AsyncClient
) -> None:
    """DELETE /api/v1/productos/{id}/ingredientes/{ing_id}: ADMIN → 204.

    Task 6.9.
    """
    app.dependency_overrides[get_uow] = make_uow_override(seeded_session)
    try:
        admin_token = await _make_role_user(async_client, seeded_session, "ADMIN", suffix="rem_ing")

        # Create product and ingredient
        prod = await _create_product(async_client, admin_token)
        prod_id = prod["id"]

        suffix = uuid.uuid4().hex[:8]
        ing_resp = await async_client.post(
            "/api/v1/ingredientes/",
            json={"nombre": f"Sal_{suffix}", "es_alergeno": False},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert ing_resp.status_code == 201
        ing_id = ing_resp.json()["id"]

        # Associate
        r_add = await async_client.post(
            f"{PRODUCTOS_BASE}/{prod_id}/ingredientes",
            json={"ingrediente_id": ing_id, "es_removible": True},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r_add.status_code == 201

        # Remove → 204
        r_del = await async_client.delete(
            f"{PRODUCTOS_BASE}/{prod_id}/ingredientes/{ing_id}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r_del.status_code == 204, (
            f"Expected 204 on remove ingredient, got: {r_del.status_code} {r_del.text}"
        )
    finally:
        app.dependency_overrides.pop(get_uow, None)


# ---------------------------------------------------------------------------
# Task 6.10 — All productos routes are registered in app route table
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_productos_route_registered(
    seeded_session, async_client: AsyncClient
) -> None:
    """All 9 productos routes are registered in the app route table.

    Task 6.10.
    """
    routes = [route.path for route in app.routes]  # type: ignore[attr-defined]

    expected_routes = [
        "/api/v1/productos/",
        "/api/v1/productos/{producto_id}",
        "/api/v1/productos/{producto_id}/disponibilidad",
        "/api/v1/productos/{producto_id}/ingredientes",
        "/api/v1/productos/{producto_id}/ingredientes/{ing_id}",
    ]
    for expected in expected_routes:
        assert expected in routes, (
            f"Route {expected} not found in app routes. Registered routes: {routes}"
        )

    # Also verify via HTTP — GET list returns 200 (proves route is registered)
    resp = await async_client.get(PRODUCTOS_URL)
    assert resp.status_code == 200, (
        f"Expected 200 from GET /productos/, got: {resp.status_code}"
    )
