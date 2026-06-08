"""
RBAC smoke tests for pedidos management endpoints — Change 22.

Verifies:
  - ADMIN role can list pedidos (GET /) → 200 (may be empty list, proves not 403).
  - ADMIN role can access GET /{id} → passes auth guard (not 401/403).
  - ADMIN role can access GET /{id}/historial → passes auth guard (not 401/403).
  - ADMIN role can advance pedido estado → passes auth guard (not 401/403).
  - ADMIN role cannot DELETE a pedido → 403 (CLIENT-only endpoint per Change 18 D-12).
  - STOCK role cannot list pedidos → 403.

Architecture note:
  The pedidos router uses `async with UnitOfWork() as uow:` internally (NOT
  Depends(get_uow) injection). As a result, tests that create orders require a
  live PostgreSQL connection. Tests here focus on RBAC checks:
    - Role guards that respond 403 before any DB access work without data.
    - Role guards that respond 200/404 (auth passed, data not found) also verify RBAC.
  If the test database is unavailable, tests will fail with a connection error —
  this is expected and is NOT a code defect.

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
    exclusive: bool = False,
) -> str:
    """Register, promote to role, re-login, return fresh access_token.

    If exclusive=True, the CLIENT role assigned at registration is removed so
    the user has only the target role. This is required for tests that verify
    a role does NOT have access (e.g. ADMIN-only cannot pass require_role("CLIENT")).
    """
    from sqlalchemy import delete, select

    from app.models.user import Rol, UsuarioRol

    email = f"ped_{role_code.lower()}_{suffix}_{uuid.uuid4().hex[:6]}@test.com"
    await _register_and_login(client, email)
    await _promote_to_role(session, email, role_code)

    if exclusive:
        # Remove the CLIENT role that was auto-assigned during registration
        client_rol_result = await session.execute(
            select(Rol).where(Rol.codigo == "CLIENT")
        )
        client_rol = client_rol_result.scalar_one_or_none()
        if client_rol is not None:
            from app.models.user import Usuario as UsuarioModel
            user_result = await session.execute(
                select(UsuarioModel).where(UsuarioModel.email == email)
            )
            user = user_result.scalar_one_or_none()
            if user is not None:
                await session.execute(
                    delete(UsuarioRol).where(
                        UsuarioRol.usuario_id == user.id,
                        UsuarioRol.rol_id == client_rol.id,
                    )
                )
                await session.flush()

    login = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "Secur3Pass!"},
    )
    assert login.status_code == 200, f"Re-login failed: {login.text}"
    return login.json()["access_token"]


# ---------------------------------------------------------------------------
# Task 5.2 — ADMIN can list pedidos → 200
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_admin_can_list_pedidos(
    seeded_session, async_client: AsyncClient
) -> None:
    """GET /api/v1/pedidos/ with ADMIN token → 200 (list may be empty, but not 403).

    The pedidos list endpoint opens its own UoW internally. The ADMIN role passes
    require_role("CLIENT", "PEDIDOS", "ADMIN"), so the response must be 200 even
    when the list is empty. Confirms role guard allows ADMIN.
    """
    app.dependency_overrides[get_uow] = make_uow_override(seeded_session)
    try:
        admin_token = await _make_role_token(
            async_client, seeded_session, "ADMIN", suffix="list"
        )
        resp = await async_client.get(
            "/api/v1/pedidos",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200, (
            f"Expected 200 for ADMIN list pedidos, got: {resp.status_code} {resp.text}"
        )
        body = resp.json()
        assert "items" in body, f"Missing 'items' key: {body}"
        assert isinstance(body["items"], list)
    finally:
        app.dependency_overrides.pop(get_uow, None)


# ---------------------------------------------------------------------------
# Task 5.3 — ADMIN can GET pedido detail → passes auth guard (not 401/403)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_admin_can_get_pedido_detail(
    seeded_session, async_client: AsyncClient
) -> None:
    """GET /api/v1/pedidos/{id} with ADMIN token → not 401 or 403 (auth guard passes).

    Since the pedidos router opens its own UoW (not injectable), and the test
    database may be isolated, we use a non-existent UUID. The service returns
    404 (ORDER_NOT_FOUND) after auth passes — confirming RBAC grants access.
    A 404 is explicitly NOT a 401 or 403, proving the ADMIN role is authorized.
    """
    app.dependency_overrides[get_uow] = make_uow_override(seeded_session)
    try:
        admin_token = await _make_role_token(
            async_client, seeded_session, "ADMIN", suffix="detail"
        )
        fake_pedido_id = str(uuid.uuid4())
        resp = await async_client.get(
            f"/api/v1/pedidos/{fake_pedido_id}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        # Auth guard passes → response is NOT 401 (unauthenticated) or 403 (forbidden)
        assert resp.status_code not in (401, 403), (
            f"ADMIN must not receive 401/403 on GET /pedidos/{{id}}, "
            f"got: {resp.status_code} {resp.text}"
        )
        # Expected 404: order not found (past the auth+role guard)
        assert resp.status_code == 404, (
            f"Expected 404 for non-existent pedido (auth passed), "
            f"got: {resp.status_code} {resp.text}"
        )
    finally:
        app.dependency_overrides.pop(get_uow, None)


# ---------------------------------------------------------------------------
# Task 5.4 — ADMIN can GET pedido historial → passes auth guard (not 401/403)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_admin_can_get_pedido_historial(
    seeded_session, async_client: AsyncClient
) -> None:
    """GET /api/v1/pedidos/{id}/historial with ADMIN token → not 401 or 403.

    Uses a non-existent UUID so the response is 404 (ORDER_NOT_FOUND), proving
    the ADMIN role passes the require_role("CLIENT", "PEDIDOS", "ADMIN") guard.
    """
    app.dependency_overrides[get_uow] = make_uow_override(seeded_session)
    try:
        admin_token = await _make_role_token(
            async_client, seeded_session, "ADMIN", suffix="historial"
        )
        fake_pedido_id = str(uuid.uuid4())
        resp = await async_client.get(
            f"/api/v1/pedidos/{fake_pedido_id}/historial",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        # Auth guard passes → must not be 401 or 403
        assert resp.status_code not in (401, 403), (
            f"ADMIN must not receive 401/403 on GET /pedidos/{{id}}/historial, "
            f"got: {resp.status_code} {resp.text}"
        )
        # 404 means the order wasn't found — auth and role check passed
        assert resp.status_code == 404, (
            f"Expected 404 for non-existent pedido historial (auth passed), "
            f"got: {resp.status_code} {resp.text}"
        )
    finally:
        app.dependency_overrides.pop(get_uow, None)


# ---------------------------------------------------------------------------
# Task 5.5 — ADMIN can advance pedido estado → passes auth guard (not 401/403)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_admin_can_advance_pedido_estado(
    seeded_session, async_client: AsyncClient
) -> None:
    """PATCH /api/v1/pedidos/{id}/estado with ADMIN token → not 401 or 403.

    Uses a non-existent UUID so the response is 404 (ORDER_NOT_FOUND), proving
    the ADMIN role passes the require_role("PEDIDOS", "ADMIN") guard.
    """
    app.dependency_overrides[get_uow] = make_uow_override(seeded_session)
    try:
        admin_token = await _make_role_token(
            async_client, seeded_session, "ADMIN", suffix="estado"
        )
        fake_pedido_id = str(uuid.uuid4())
        resp = await async_client.patch(
            f"/api/v1/pedidos/{fake_pedido_id}/estado",
            json={"nuevo_estado": "CONFIRMADO"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        # Auth guard passes → must not be 401 or 403
        assert resp.status_code not in (401, 403), (
            f"ADMIN must not receive 401/403 on PATCH /pedidos/{{id}}/estado, "
            f"got: {resp.status_code} {resp.text}"
        )
        # 404 means the order wasn't found — auth and role check passed
        assert resp.status_code == 404, (
            f"Expected 404 for non-existent pedido (auth passed), "
            f"got: {resp.status_code} {resp.text}"
        )
    finally:
        app.dependency_overrides.pop(get_uow, None)


# ---------------------------------------------------------------------------
# Task 5.6 — ADMIN cannot DELETE a pedido → 403 (CLIENT-only path)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_admin_cannot_delete_pedido(
    seeded_session, async_client: AsyncClient
) -> None:
    """DELETE /api/v1/pedidos/{id} with ADMIN token → 403 (CLIENT-only endpoint).

    Per Change 18 D-12: DELETE /{id} uses require_role("CLIENT") exclusively.
    ADMIN does NOT have the CLIENT role, so the require_role guard must return 403.
    This confirms the endpoint intentionally restricts ADMIN from deleting orders.
    """
    app.dependency_overrides[get_uow] = make_uow_override(seeded_session)
    try:
        # exclusive=True: removes the auto-assigned CLIENT role so the user
        # has ONLY ADMIN. This ensures require_role("CLIENT") correctly returns 403.
        admin_token = await _make_role_token(
            async_client, seeded_session, "ADMIN", suffix="del_403", exclusive=True
        )
        fake_pedido_id = str(uuid.uuid4())
        resp = await async_client.delete(
            f"/api/v1/pedidos/{fake_pedido_id}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 403, (
            f"Expected 403 for ADMIN-only DELETE /pedidos/{{id}} (CLIENT-only endpoint), "
            f"got: {resp.status_code} {resp.text}"
        )
    finally:
        app.dependency_overrides.pop(get_uow, None)


# ---------------------------------------------------------------------------
# Task 5.7 — STOCK cannot list pedidos → 403
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stock_cannot_list_pedidos(
    seeded_session, async_client: AsyncClient
) -> None:
    """GET /api/v1/pedidos/ with STOCK token → 403.

    STOCK role is explicitly excluded from require_role("CLIENT", "PEDIDOS", "ADMIN").
    """
    app.dependency_overrides[get_uow] = make_uow_override(seeded_session)
    try:
        # exclusive=True: removes the auto-assigned CLIENT role so the user
        # has ONLY STOCK. This ensures require_role("CLIENT","PEDIDOS","ADMIN")
        # correctly returns 403 for a STOCK-only user.
        stock_token = await _make_role_token(
            async_client, seeded_session, "STOCK", suffix="list_403", exclusive=True
        )
        resp = await async_client.get(
            "/api/v1/pedidos",
            headers={"Authorization": f"Bearer {stock_token}"},
        )
        assert resp.status_code == 403, (
            f"Expected 403 for STOCK-only GET /pedidos, got: {resp.status_code} {resp.text}"
        )
    finally:
        app.dependency_overrides.pop(get_uow, None)
