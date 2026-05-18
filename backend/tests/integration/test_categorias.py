"""
Integration tests for the Categorias API endpoints.

Tasks 6.3-6.6:
  - test_get_categorias_public_no_auth: GET /api/v1/categorias → 200 without token
  - test_get_categoria_by_id_public_no_auth: GET with valid/invalid id → 200/404
  - test_post_categorias_requires_admin_or_stock: 401/403/201
  - test_delete_categoria_blocked_by_active_children: DELETE with child → 409
  - test_categorias_route_registered: all 5 routes exist

Uses the SAVEPOINT-based async_session and seeded_session fixtures.
"""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient

from app.core.uow import get_uow
from app.main import app
from tests.fixtures.uow import make_uow_override

CATEGORIAS_URL = "/api/v1/categorias/"
CATEGORIAS_BASE = "/api/v1/categorias"


# ---------------------------------------------------------------------------
# Helpers — register + login helpers (same pattern as test_rbac.py)
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

    email = f"cat_{role_code.lower()}_{suffix}_{uuid.uuid4().hex[:6]}@test.com"
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


# ---------------------------------------------------------------------------
# Task 6.3 — GET /api/v1/categorias is public (no auth required)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_categorias_public_no_auth(seeded_session, async_client: AsyncClient) -> None:
    """GET /api/v1/categorias returns 200 without any Authorization header."""
    app.dependency_overrides[get_uow] = make_uow_override(seeded_session)
    try:
        response = await async_client.get(CATEGORIAS_URL)
        assert response.status_code == 200, f"Expected 200, got: {response.text}"
        body = response.json()
        assert isinstance(body, list), f"Expected list, got: {type(body)}"
    finally:
        app.dependency_overrides.pop(get_uow, None)


# ---------------------------------------------------------------------------
# Task 6.3b — GET /api/v1/categorias/{id} is public (no auth required)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_categoria_by_id_public_no_auth(seeded_session, async_client: AsyncClient) -> None:
    """GET /api/v1/categorias/{id} is public: 200 for existing, 404 for missing."""
    app.dependency_overrides[get_uow] = make_uow_override(seeded_session)
    try:
        # First create a category with ADMIN token
        admin_token = await _make_role_user(
            async_client, seeded_session, "ADMIN", suffix="get_by_id"
        )
        unique_name = f"TestGetById_{uuid.uuid4().hex[:8]}"
        create_resp = await async_client.post(
            CATEGORIAS_URL,
            json={"nombre": unique_name},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert create_resp.status_code == 201, f"Create failed: {create_resp.text}"
        cat_id = create_resp.json()["id"]

        # 200 for existing id — no token
        response = await async_client.get(f"{CATEGORIAS_BASE}/{cat_id}")
        assert response.status_code == 200, f"Expected 200 for existing id, got: {response.text}"
        body = response.json()
        assert body["id"] == cat_id

        # 404 for non-existent id — no token
        fake_id = str(uuid.uuid4())
        not_found_response = await async_client.get(f"{CATEGORIAS_BASE}/{fake_id}")
        assert not_found_response.status_code == 404, (
            f"Expected 404 for non-existent id, got: {not_found_response.status_code}"
        )
        error_body = not_found_response.json()
        assert error_body.get("code") == "CATEGORY_NOT_FOUND"
    finally:
        app.dependency_overrides.pop(get_uow, None)


# ---------------------------------------------------------------------------
# Task 6.4 — POST /api/v1/categorias requires ADMIN or STOCK role
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_post_categorias_requires_admin_or_stock(
    seeded_session, async_client: AsyncClient
) -> None:
    """POST /api/v1/categorias: 401 no token, 403 CLIENT, 201 ADMIN, 201 STOCK."""
    app.dependency_overrides[get_uow] = make_uow_override(seeded_session)
    try:
        # 401 — no token at all
        no_auth_resp = await async_client.post(
            CATEGORIAS_URL,
            json={"nombre": "Noauth"},
        )
        assert no_auth_resp.status_code == 401, (
            f"Expected 401 without token, got: {no_auth_resp.status_code}"
        )

        # 403 — CLIENT token
        client_token = await _register_and_get_token(
            async_client, f"cat_client_{uuid.uuid4().hex[:6]}@test.com"
        )
        client_resp = await async_client.post(
            CATEGORIAS_URL,
            json={"nombre": "ClientAttempt"},
            headers={"Authorization": f"Bearer {client_token}"},
        )
        assert client_resp.status_code == 403, (
            f"Expected 403 for CLIENT role, got: {client_resp.status_code}"
        )

        # 201 — ADMIN token
        admin_token = await _make_role_user(
            async_client, seeded_session, "ADMIN", suffix="post_admin"
        )
        admin_name = f"AdminCategory_{uuid.uuid4().hex[:8]}"
        admin_resp = await async_client.post(
            CATEGORIAS_URL,
            json={"nombre": admin_name},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert admin_resp.status_code == 201, (
            f"Expected 201 for ADMIN, got: {admin_resp.status_code} — {admin_resp.text}"
        )
        assert admin_resp.json()["nombre"] == admin_name

        # 201 — STOCK token
        stock_token = await _make_role_user(
            async_client, seeded_session, "STOCK", suffix="post_stock"
        )
        stock_name = f"StockCategory_{uuid.uuid4().hex[:8]}"
        stock_resp = await async_client.post(
            CATEGORIAS_URL,
            json={"nombre": stock_name},
            headers={"Authorization": f"Bearer {stock_token}"},
        )
        assert stock_resp.status_code == 201, (
            f"Expected 201 for STOCK, got: {stock_resp.status_code} — {stock_resp.text}"
        )
        assert stock_resp.json()["nombre"] == stock_name
    finally:
        app.dependency_overrides.pop(get_uow, None)


# ---------------------------------------------------------------------------
# Task 6.5 — DELETE /api/v1/categorias/{id} blocked by active children → 409
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_categoria_blocked_by_active_children(
    seeded_session, async_client: AsyncClient
) -> None:
    """DELETE /api/v1/categorias/{id} returns 409 when category has active children."""
    app.dependency_overrides[get_uow] = make_uow_override(seeded_session)
    try:
        admin_token = await _make_role_user(
            async_client, seeded_session, "ADMIN", suffix="del_child"
        )
        headers = {"Authorization": f"Bearer {admin_token}"}

        # Create parent (unique name per test run)
        parent_name = f"ParentToDelete_{uuid.uuid4().hex[:8]}"
        parent_resp = await async_client.post(
            CATEGORIAS_URL,
            json={"nombre": parent_name},
            headers=headers,
        )
        assert parent_resp.status_code == 201, f"Parent creation failed: {parent_resp.text}"
        parent_id = parent_resp.json()["id"]

        # Create child under parent (unique name per test run)
        child_name = f"ActiveChild_{uuid.uuid4().hex[:8]}"
        child_resp = await async_client.post(
            CATEGORIAS_URL,
            json={"nombre": child_name, "parent_id": parent_id},
            headers=headers,
        )
        assert child_resp.status_code == 201, f"Child creation failed: {child_resp.text}"

        # Attempt to delete parent — must return 409
        delete_resp = await async_client.delete(
            f"{CATEGORIAS_BASE}/{parent_id}",
            headers=headers,
        )
        assert delete_resp.status_code == 409, (
            f"Expected 409 when deleting parent with active child, got: {delete_resp.status_code}"
        )
        body = delete_resp.json()
        assert body.get("code") == "CATEGORY_HAS_ACTIVE_CHILDREN", (
            f"Expected CATEGORY_HAS_ACTIVE_CHILDREN code, got: {body}"
        )
    finally:
        app.dependency_overrides.pop(get_uow, None)


# ---------------------------------------------------------------------------
# Task 6.6 — All 5 category routes are registered
# ---------------------------------------------------------------------------


def test_categorias_route_registered() -> None:
    """All 5 /api/v1/categorias routes are registered in the app."""
    # Build a dict: path → set of methods
    route_map: dict[str, set[str]] = {}
    for route in app.routes:  # type: ignore[attr-defined]
        if hasattr(route, "path") and hasattr(route, "methods") and route.methods:
            path = route.path
            route_map.setdefault(path, set()).update(route.methods)

    categorias_prefix = "/api/v1/categorias"

    # Check at least one categorias route exists
    cat_routes = {p: m for p, m in route_map.items() if "categorias" in p}
    assert len(cat_routes) > 0, (
        f"No categorias routes found. All routes: {list(route_map.keys())}"
    )

    # Check all 5 methods exist across categorias routes
    all_methods: set[str] = set()
    for path, methods in cat_routes.items():
        all_methods.update(methods)

    assert "GET" in all_methods, "GET method not found in categorias routes"
    assert "POST" in all_methods, "POST method not found in categorias routes"
    assert "PUT" in all_methods, "PUT method not found in categorias routes"
    assert "DELETE" in all_methods, "DELETE method not found in categorias routes"

    # Verify both collection and item routes exist
    collection_paths = [p for p in cat_routes if not "{" in p]
    item_paths = [p for p in cat_routes if "{category_id}" in p]
    assert len(collection_paths) >= 1, "Collection route (/) not found"
    assert len(item_paths) >= 1, "Item route (/{category_id}) not found"
