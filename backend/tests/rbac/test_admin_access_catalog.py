"""
RBAC smoke tests for catalog management endpoints — Change 22.

Verifies:
  - ADMIN role can create categorias, ingredientes, productos.
  - ADMIN role can patch disponibilidad and delete ingredientes.
  - ADMIN role can delete a leaf categoria (no active children).
  - STOCK role cannot POST /productos (ADMIN-only endpoint).

All tests use the seeded_session + async_client fixtures with the
SAVEPOINT-based rollback pattern for test isolation.
"""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient

from app.core.uow import get_uow
from app.main import app
from tests.fixtures.uow import make_uow_override


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _register_and_login(
    client: AsyncClient,
    email: str,
    password: str = "Secur3Pass!",
) -> str:
    """Register a user (gets CLIENT role) and return access_token."""
    reg = await client.post(
        "/api/v1/auth/register",
        json={
            "nombre": "Test",
            "apellido": "RBAC",
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


async def _promote_to_role(session, email: str, role_code: str) -> None:
    """Assign a role to a user by manipulating the session directly."""
    from sqlalchemy import select

    from app.models.user import Rol, Usuario, UsuarioRol

    result = await session.execute(select(Usuario).where(Usuario.email == email))
    user = result.scalar_one_or_none()
    assert user is not None, f"User {email} not found"

    result = await session.execute(select(Rol).where(Rol.codigo == role_code))
    rol = result.scalar_one_or_none()
    assert rol is not None, f"Role {role_code} not seeded"

    ur = UsuarioRol(usuario_id=user.id, rol_id=rol.id, asignado_por_id=None)
    session.add(ur)
    await session.flush()


async def _make_role_token(
    client: AsyncClient,
    session,
    role_code: str,
    suffix: str = "",
) -> str:
    """Register, promote to role, re-login, return fresh access_token."""
    email = f"rbac_{role_code.lower()}_{suffix}_{uuid.uuid4().hex[:6]}@test.com"
    await _register_and_login(client, email)
    await _promote_to_role(session, email, role_code)
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "Secur3Pass!"},
    )
    assert login.status_code == 200, f"Re-login failed: {login.text}"
    return login.json()["access_token"]


# ---------------------------------------------------------------------------
# Task 4.2 — ADMIN can create categoria → 201
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_admin_can_create_categoria(
    seeded_session, async_client: AsyncClient
) -> None:
    """POST /api/v1/categorias/ with ADMIN token → 201."""
    app.dependency_overrides[get_uow] = make_uow_override(seeded_session)
    try:
        admin_token = await _make_role_token(
            async_client, seeded_session, "ADMIN", suffix="cat_create"
        )
        nombre = f"CatAdmin_{uuid.uuid4().hex[:8]}"
        resp = await async_client.post(
            "/api/v1/categorias/",
            json={"nombre": nombre},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 201, (
            f"Expected 201 for ADMIN create categoria, got: {resp.status_code} {resp.text}"
        )
        body = resp.json()
        assert body["nombre"] == nombre
        assert "id" in body
    finally:
        app.dependency_overrides.pop(get_uow, None)


# ---------------------------------------------------------------------------
# Task 4.3 — ADMIN can create ingrediente → 201
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_admin_can_create_ingrediente(
    seeded_session, async_client: AsyncClient
) -> None:
    """POST /api/v1/ingredientes/ with ADMIN token → 201."""
    app.dependency_overrides[get_uow] = make_uow_override(seeded_session)
    try:
        admin_token = await _make_role_token(
            async_client, seeded_session, "ADMIN", suffix="ing_create"
        )
        nombre = f"IngAdmin_{uuid.uuid4().hex[:8]}"
        resp = await async_client.post(
            "/api/v1/ingredientes/",
            json={"nombre": nombre, "es_alergeno": False},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 201, (
            f"Expected 201 for ADMIN create ingrediente, got: {resp.status_code} {resp.text}"
        )
        body = resp.json()
        assert body["nombre"] == nombre
        assert "id" in body
    finally:
        app.dependency_overrides.pop(get_uow, None)


# ---------------------------------------------------------------------------
# Task 4.4 — ADMIN can create producto → 201
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_admin_can_create_producto(
    seeded_session, async_client: AsyncClient
) -> None:
    """POST /api/v1/productos/ with ADMIN token → 201."""
    app.dependency_overrides[get_uow] = make_uow_override(seeded_session)
    try:
        admin_token = await _make_role_token(
            async_client, seeded_session, "ADMIN", suffix="prod_create"
        )
        nombre = f"ProdAdmin_{uuid.uuid4().hex[:8]}"
        resp = await async_client.post(
            "/api/v1/productos/",
            json={
                "nombre": nombre,
                "precio_base": "15.00",
                "stock_cantidad": 10,
                "disponible": True,
            },
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 201, (
            f"Expected 201 for ADMIN create producto, got: {resp.status_code} {resp.text}"
        )
        body = resp.json()
        assert body["nombre"] == nombre
        assert "id" in body
    finally:
        app.dependency_overrides.pop(get_uow, None)


# ---------------------------------------------------------------------------
# Task 4.5 — ADMIN can patch disponibilidad → 200
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_admin_can_patch_disponibilidad(
    seeded_session, async_client: AsyncClient
) -> None:
    """PATCH /api/v1/productos/{id}/disponibilidad with ADMIN token → 200."""
    app.dependency_overrides[get_uow] = make_uow_override(seeded_session)
    try:
        admin_token = await _make_role_token(
            async_client, seeded_session, "ADMIN", suffix="disp_admin"
        )
        # Create a product first
        nombre = f"ProdDisp_{uuid.uuid4().hex[:8]}"
        create_resp = await async_client.post(
            "/api/v1/productos/",
            json={
                "nombre": nombre,
                "precio_base": "20.00",
                "stock_cantidad": 5,
                "disponible": True,
            },
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert create_resp.status_code == 201, f"Create failed: {create_resp.text}"
        prod_id = create_resp.json()["id"]

        # ADMIN patches disponibilidad
        patch_resp = await async_client.patch(
            f"/api/v1/productos/{prod_id}/disponibilidad",
            json={"disponible": False},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert patch_resp.status_code == 200, (
            f"Expected 200 for ADMIN patch disponibilidad, got: {patch_resp.status_code} {patch_resp.text}"
        )
        assert patch_resp.json()["disponible"] is False
    finally:
        app.dependency_overrides.pop(get_uow, None)


# ---------------------------------------------------------------------------
# Task 4.6 — ADMIN can delete leaf categoria → 204
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_admin_can_delete_leaf_categoria(
    seeded_session, async_client: AsyncClient
) -> None:
    """DELETE /api/v1/categorias/{id} with ADMIN token on leaf categoria → 204."""
    app.dependency_overrides[get_uow] = make_uow_override(seeded_session)
    try:
        admin_token = await _make_role_token(
            async_client, seeded_session, "ADMIN", suffix="cat_del"
        )
        # Create a leaf category (no children, no products)
        nombre = f"LeafCat_{uuid.uuid4().hex[:8]}"
        create_resp = await async_client.post(
            "/api/v1/categorias/",
            json={"nombre": nombre},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert create_resp.status_code == 201, f"Create failed: {create_resp.text}"
        cat_id = create_resp.json()["id"]

        # ADMIN deletes the leaf categoria
        del_resp = await async_client.delete(
            f"/api/v1/categorias/{cat_id}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert del_resp.status_code == 204, (
            f"Expected 204 for ADMIN delete leaf categoria, got: {del_resp.status_code} {del_resp.text}"
        )
    finally:
        app.dependency_overrides.pop(get_uow, None)


# ---------------------------------------------------------------------------
# Task 4.7 — ADMIN can delete ingrediente → 204
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_admin_can_delete_ingrediente(
    seeded_session, async_client: AsyncClient
) -> None:
    """DELETE /api/v1/ingredientes/{id} with ADMIN token → 204."""
    app.dependency_overrides[get_uow] = make_uow_override(seeded_session)
    try:
        admin_token = await _make_role_token(
            async_client, seeded_session, "ADMIN", suffix="ing_del"
        )
        # Create an ingrediente
        nombre = f"IngDel_{uuid.uuid4().hex[:8]}"
        create_resp = await async_client.post(
            "/api/v1/ingredientes/",
            json={"nombre": nombre, "es_alergeno": True},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert create_resp.status_code == 201, f"Create failed: {create_resp.text}"
        ing_id = create_resp.json()["id"]

        # ADMIN deletes the ingrediente
        del_resp = await async_client.delete(
            f"/api/v1/ingredientes/{ing_id}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert del_resp.status_code == 204, (
            f"Expected 204 for ADMIN delete ingrediente, got: {del_resp.status_code} {del_resp.text}"
        )
    finally:
        app.dependency_overrides.pop(get_uow, None)


# ---------------------------------------------------------------------------
# Task 4.8 — STOCK cannot create producto → 403
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stock_cannot_create_producto(
    seeded_session, async_client: AsyncClient
) -> None:
    """POST /api/v1/productos/ with STOCK token → 403 (ADMIN-only endpoint)."""
    app.dependency_overrides[get_uow] = make_uow_override(seeded_session)
    try:
        stock_token = await _make_role_token(
            async_client, seeded_session, "STOCK", suffix="prod_stock"
        )
        resp = await async_client.post(
            "/api/v1/productos/",
            json={
                "nombre": f"StockProd_{uuid.uuid4().hex[:8]}",
                "precio_base": "10.00",
            },
            headers={"Authorization": f"Bearer {stock_token}"},
        )
        assert resp.status_code == 403, (
            f"Expected 403 for STOCK create producto, got: {resp.status_code} {resp.text}"
        )
    finally:
        app.dependency_overrides.pop(get_uow, None)
