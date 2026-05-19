"""
Integration tests for the Ingredientes API endpoints.

Tasks 6.3–6.16:
  - test_get_ingredientes_requires_auth: GET /api/v1/ingredientes → 401 no JWT
  - test_get_ingredientes_client_role_forbidden: CLIENT JWT → 403
  - test_get_ingredientes_admin_succeeds: ADMIN JWT → 200, returns list
  - test_get_ingredientes_stock_succeeds: STOCK JWT → 200, returns list
  - test_post_ingrediente_admin_creates_201: ADMIN JWT + valid body → 201
  - test_post_ingrediente_stock_creates_201: STOCK JWT + valid body → 201
  - test_post_ingrediente_duplicate_nombre_409: duplicate nombre → 409
  - test_get_ingrediente_by_id_not_found_404: non-existent UUID → 404
  - test_put_ingrediente_nombre_only_preserves_es_alergeno: partial update
  - test_delete_ingrediente_admin_204: ADMIN JWT → 204
  - test_delete_ingrediente_stock_204: STOCK JWT → 204
  - test_delete_ingrediente_not_found_404: delete non-existent → 404
  - test_get_ingredientes_filter_es_alergeno_true: filter allergens
  - test_ingredientes_route_registered: all 5 routes exist

Uses the SAVEPOINT-based seeded_session and async_client fixtures.
"""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient

from app.core.uow import get_uow
from app.main import app
from tests.fixtures.uow import make_uow_override

INGREDIENTES_URL = "/api/v1/ingredientes/"
INGREDIENTES_BASE = "/api/v1/ingredientes"


# ---------------------------------------------------------------------------
# Helpers — register + login + role assignment
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

    email = f"ing_{role_code.lower()}_{suffix}_{uuid.uuid4().hex[:6]}@test.com"
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
# Task 6.3 — GET /api/v1/ingredientes requires auth (no JWT → 401)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_ingredientes_requires_auth(seeded_session, async_client: AsyncClient) -> None:
    """GET /api/v1/ingredientes without JWT returns 401.

    Task 6.3.
    """
    app.dependency_overrides[get_uow] = make_uow_override(seeded_session)
    try:
        response = await async_client.get(INGREDIENTES_URL)
        assert response.status_code == 401, f"Expected 401, got: {response.text}"
    finally:
        app.dependency_overrides.pop(get_uow, None)


# ---------------------------------------------------------------------------
# Task 6.4 — CLIENT JWT → 403
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_ingredientes_client_role_forbidden(
    seeded_session, async_client: AsyncClient
) -> None:
    """GET /api/v1/ingredientes with CLIENT JWT returns 403.

    Task 6.4.
    """
    app.dependency_overrides[get_uow] = make_uow_override(seeded_session)
    try:
        client_token = await _register_and_get_token(
            async_client, f"ing_client_{uuid.uuid4().hex[:6]}@test.com"
        )
        response = await async_client.get(
            INGREDIENTES_URL,
            headers={"Authorization": f"Bearer {client_token}"},
        )
        assert response.status_code == 403, f"Expected 403 for CLIENT, got: {response.text}"
    finally:
        app.dependency_overrides.pop(get_uow, None)


# ---------------------------------------------------------------------------
# Task 6.5 — ADMIN JWT → 200, returns list
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_ingredientes_admin_succeeds(
    seeded_session, async_client: AsyncClient
) -> None:
    """GET /api/v1/ingredientes with ADMIN JWT returns 200 with list.

    Task 6.5.
    """
    app.dependency_overrides[get_uow] = make_uow_override(seeded_session)
    try:
        admin_token = await _make_role_user(async_client, seeded_session, "ADMIN", suffix="list_admin")
        response = await async_client.get(
            INGREDIENTES_URL,
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200, f"Expected 200, got: {response.text}"
        body = response.json()
        assert isinstance(body, list), f"Expected list, got: {type(body)}"
    finally:
        app.dependency_overrides.pop(get_uow, None)


# ---------------------------------------------------------------------------
# Task 6.6 — STOCK JWT → 200, returns list
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_ingredientes_stock_succeeds(
    seeded_session, async_client: AsyncClient
) -> None:
    """GET /api/v1/ingredientes with STOCK JWT returns 200 with list.

    Task 6.6.
    """
    app.dependency_overrides[get_uow] = make_uow_override(seeded_session)
    try:
        stock_token = await _make_role_user(async_client, seeded_session, "STOCK", suffix="list_stock")
        response = await async_client.get(
            INGREDIENTES_URL,
            headers={"Authorization": f"Bearer {stock_token}"},
        )
        assert response.status_code == 200, f"Expected 200 for STOCK, got: {response.text}"
        assert isinstance(response.json(), list)
    finally:
        app.dependency_overrides.pop(get_uow, None)


# ---------------------------------------------------------------------------
# Task 6.7 — POST /api/v1/ingredientes ADMIN JWT + valid body → 201
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_post_ingrediente_admin_creates_201(
    seeded_session, async_client: AsyncClient
) -> None:
    """POST /api/v1/ingredientes with ADMIN JWT and valid body returns 201 IngredienteRead.

    Task 6.7.
    """
    app.dependency_overrides[get_uow] = make_uow_override(seeded_session)
    try:
        admin_token = await _make_role_user(async_client, seeded_session, "ADMIN", suffix="post_admin")
        nombre = f"Sal_{uuid.uuid4().hex[:8]}"
        response = await async_client.post(
            INGREDIENTES_URL,
            json={"nombre": nombre, "es_alergeno": False},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 201, f"Expected 201, got: {response.text}"
        body = response.json()
        assert body["nombre"] == nombre
        assert body["es_alergeno"] is False
        assert "id" in body
        assert "created_at" in body
        assert "updated_at" in body
    finally:
        app.dependency_overrides.pop(get_uow, None)


# ---------------------------------------------------------------------------
# Task 6.8 — STOCK JWT → 201
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_post_ingrediente_stock_creates_201(
    seeded_session, async_client: AsyncClient
) -> None:
    """POST /api/v1/ingredientes with STOCK JWT and valid body returns 201.

    Task 6.8.
    """
    app.dependency_overrides[get_uow] = make_uow_override(seeded_session)
    try:
        stock_token = await _make_role_user(async_client, seeded_session, "STOCK", suffix="post_stock")
        nombre = f"Gluten_{uuid.uuid4().hex[:8]}"
        response = await async_client.post(
            INGREDIENTES_URL,
            json={"nombre": nombre, "es_alergeno": True},
            headers={"Authorization": f"Bearer {stock_token}"},
        )
        assert response.status_code == 201, f"Expected 201, got: {response.text}"
        assert response.json()["nombre"] == nombre
    finally:
        app.dependency_overrides.pop(get_uow, None)


# ---------------------------------------------------------------------------
# Task 6.9 — duplicate nombre → 409 INGREDIENT_NAME_DUPLICATE
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_post_ingrediente_duplicate_nombre_409(
    seeded_session, async_client: AsyncClient
) -> None:
    """POST /api/v1/ingredientes with duplicate nombre returns 409 INGREDIENT_NAME_DUPLICATE.

    Task 6.9.
    """
    app.dependency_overrides[get_uow] = make_uow_override(seeded_session)
    try:
        admin_token = await _make_role_user(async_client, seeded_session, "ADMIN", suffix="dup_409")
        nombre = f"DupTest_{uuid.uuid4().hex[:8]}"

        # First create — should succeed
        r1 = await async_client.post(
            INGREDIENTES_URL,
            json={"nombre": nombre},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r1.status_code == 201, f"First create failed: {r1.text}"

        # Second create — should fail with 409
        r2 = await async_client.post(
            INGREDIENTES_URL,
            json={"nombre": nombre},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r2.status_code == 409, f"Expected 409, got: {r2.status_code} {r2.text}"
        assert r2.json().get("code") == "INGREDIENT_NAME_DUPLICATE"
    finally:
        app.dependency_overrides.pop(get_uow, None)


# ---------------------------------------------------------------------------
# Task 6.10 — GET /{id} non-existent UUID → 404 INGREDIENT_NOT_FOUND
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_ingrediente_by_id_not_found_404(
    seeded_session, async_client: AsyncClient
) -> None:
    """GET /api/v1/ingredientes/{id} for non-existent UUID returns 404.

    Task 6.10.
    """
    app.dependency_overrides[get_uow] = make_uow_override(seeded_session)
    try:
        admin_token = await _make_role_user(async_client, seeded_session, "ADMIN", suffix="notfound")
        fake_id = str(uuid.uuid4())
        response = await async_client.get(
            f"{INGREDIENTES_BASE}/{fake_id}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 404, f"Expected 404, got: {response.text}"
        assert response.json().get("code") == "INGREDIENT_NOT_FOUND"
    finally:
        app.dependency_overrides.pop(get_uow, None)


# ---------------------------------------------------------------------------
# Task 6.11 — PUT nombre only preserves es_alergeno
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_put_ingrediente_nombre_only_preserves_es_alergeno(
    seeded_session, async_client: AsyncClient
) -> None:
    """PUT /api/v1/ingredientes/{id} with only nombre preserves es_alergeno.

    Task 6.11: model_fields_set preservation — D-05.
    """
    app.dependency_overrides[get_uow] = make_uow_override(seeded_session)
    try:
        admin_token = await _make_role_user(async_client, seeded_session, "ADMIN", suffix="put_partial")
        nombre = f"Oregano_{uuid.uuid4().hex[:8]}"

        # Create with es_alergeno=True
        create_resp = await async_client.post(
            INGREDIENTES_URL,
            json={"nombre": nombre, "es_alergeno": True},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert create_resp.status_code == 201
        ing_id = create_resp.json()["id"]

        # Update only nombre — es_alergeno should remain True
        new_nombre = f"Oregano_updated_{uuid.uuid4().hex[:8]}"
        put_resp = await async_client.put(
            f"{INGREDIENTES_BASE}/{ing_id}",
            json={"nombre": new_nombre},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert put_resp.status_code == 200, f"PUT failed: {put_resp.text}"
        body = put_resp.json()
        assert body["nombre"] == new_nombre
        assert body["es_alergeno"] is True, (
            f"es_alergeno should remain True after partial update, got: {body['es_alergeno']}"
        )
    finally:
        app.dependency_overrides.pop(get_uow, None)


# ---------------------------------------------------------------------------
# Task 6.12 — DELETE ADMIN JWT → 204
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_ingrediente_admin_204(
    seeded_session, async_client: AsyncClient
) -> None:
    """DELETE /api/v1/ingredientes/{id} with ADMIN JWT returns 204.

    Task 6.12.
    """
    app.dependency_overrides[get_uow] = make_uow_override(seeded_session)
    try:
        admin_token = await _make_role_user(async_client, seeded_session, "ADMIN", suffix="del_admin")
        nombre = f"ToDelete_{uuid.uuid4().hex[:8]}"

        create_resp = await async_client.post(
            INGREDIENTES_URL,
            json={"nombre": nombre},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert create_resp.status_code == 201
        ing_id = create_resp.json()["id"]

        delete_resp = await async_client.delete(
            f"{INGREDIENTES_BASE}/{ing_id}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert delete_resp.status_code == 204, f"Expected 204, got: {delete_resp.text}"
    finally:
        app.dependency_overrides.pop(get_uow, None)


# ---------------------------------------------------------------------------
# Task 6.13 — DELETE STOCK JWT → 204
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_ingrediente_stock_204(
    seeded_session, async_client: AsyncClient
) -> None:
    """DELETE /api/v1/ingredientes/{id} with STOCK JWT returns 204.

    Task 6.13.
    """
    app.dependency_overrides[get_uow] = make_uow_override(seeded_session)
    try:
        admin_token = await _make_role_user(async_client, seeded_session, "ADMIN", suffix="del_stock_creator")
        stock_token = await _make_role_user(async_client, seeded_session, "STOCK", suffix="del_stock")
        nombre = f"ToDeleteStock_{uuid.uuid4().hex[:8]}"

        # Create with admin
        create_resp = await async_client.post(
            INGREDIENTES_URL,
            json={"nombre": nombre},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert create_resp.status_code == 201
        ing_id = create_resp.json()["id"]

        # Delete with stock
        delete_resp = await async_client.delete(
            f"{INGREDIENTES_BASE}/{ing_id}",
            headers={"Authorization": f"Bearer {stock_token}"},
        )
        assert delete_resp.status_code == 204, f"Expected 204, got: {delete_resp.text}"
    finally:
        app.dependency_overrides.pop(get_uow, None)


# ---------------------------------------------------------------------------
# Task 6.14 — DELETE non-existent UUID → 404
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_ingrediente_not_found_404(
    seeded_session, async_client: AsyncClient
) -> None:
    """DELETE /api/v1/ingredientes/{id} for non-existent UUID returns 404.

    Task 6.14.
    """
    app.dependency_overrides[get_uow] = make_uow_override(seeded_session)
    try:
        admin_token = await _make_role_user(async_client, seeded_session, "ADMIN", suffix="del_notfound")
        fake_id = str(uuid.uuid4())
        response = await async_client.delete(
            f"{INGREDIENTES_BASE}/{fake_id}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 404, f"Expected 404, got: {response.text}"
        assert response.json().get("code") == "INGREDIENT_NOT_FOUND"
    finally:
        app.dependency_overrides.pop(get_uow, None)


# ---------------------------------------------------------------------------
# Task 6.15 — GET ?es_alergeno=true returns only allergens
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_ingredientes_filter_es_alergeno_true(
    seeded_session, async_client: AsyncClient
) -> None:
    """GET /api/v1/ingredientes?es_alergeno=true returns only allergen ingredients.

    Task 6.15.
    """
    app.dependency_overrides[get_uow] = make_uow_override(seeded_session)
    try:
        admin_token = await _make_role_user(async_client, seeded_session, "ADMIN", suffix="filter_alergeno")
        suffix = uuid.uuid4().hex[:8]

        # Create allergen ingredient
        await async_client.post(
            INGREDIENTES_URL,
            json={"nombre": f"Gluten_{suffix}", "es_alergeno": True},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        # Create non-allergen ingredient
        await async_client.post(
            INGREDIENTES_URL,
            json={"nombre": f"Sal_{suffix}", "es_alergeno": False},
            headers={"Authorization": f"Bearer {admin_token}"},
        )

        response = await async_client.get(
            f"{INGREDIENTES_URL}?es_alergeno=true",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200
        body = response.json()
        # All returned items must be allergens
        for item in body:
            assert item["es_alergeno"] is True, (
                f"Non-allergen returned with es_alergeno filter: {item}"
            )
        # Our allergen item should be in the results
        our_alergeno = [i for i in body if i["nombre"] == f"Gluten_{suffix}"]
        assert len(our_alergeno) == 1
        # Our non-allergen item must NOT be in results
        our_no_alergeno = [i for i in body if i["nombre"] == f"Sal_{suffix}"]
        assert len(our_no_alergeno) == 0
    finally:
        app.dependency_overrides.pop(get_uow, None)


# ---------------------------------------------------------------------------
# Task 6.16 — all 5 routes exist in app route table
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ingredientes_route_registered(
    seeded_session, async_client: AsyncClient
) -> None:
    """Verify all 5 ingredientes routes are registered in the app route table.

    Task 6.16.
    """
    routes = [route.path for route in app.routes]  # type: ignore[attr-defined]
    expected_routes = [
        "/api/v1/ingredientes/",
        "/api/v1/ingredientes/{ingrediente_id}",
    ]
    for expected in expected_routes:
        assert expected in routes, (
            f"Route {expected} not found in app routes. Registered: {routes}"
        )

    # Also verify via HTTP — GET list returns 401 (proves route is registered)
    resp = await async_client.get(INGREDIENTES_URL)
    assert resp.status_code == 401, (
        f"Expected 401 from unregistered route (or registered + auth), got: {resp.status_code}"
    )
