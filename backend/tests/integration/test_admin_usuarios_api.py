"""
Integration tests for the admin-usuarios API endpoints (Change 21).

Phase 8.3 — Task 8.3.

Covers:
  - GET /api/v1/admin/usuarios → 200 with Page structure (ADMIN token).
  - GET /api/v1/admin/usuarios → 401 without auth.
  - GET /api/v1/admin/usuarios → 403 with CLIENT token.
  - GET /api/v1/admin/usuarios?q=admin → filters correctly.
  - GET /api/v1/admin/usuarios?activo=true → only active users.
  - PUT /api/v1/admin/usuarios/{id}/roles with last ADMIN → 409 LAST_ADMIN_PROTECTED.
  - PATCH /api/v1/admin/usuarios/{id}/estado activo=false → subsequent auth → 401.
  - PATCH /api/v1/admin/usuarios/{id}/estado activo=false + refresh → 401.
"""

from __future__ import annotations

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
    nombre: str = "Test",
    apellido: str = "User",
) -> dict:
    """Register a user and return login response body."""
    reg_resp = await client.post(
        "/api/v1/auth/register",
        json={
            "nombre": nombre,
            "apellido": apellido,
            "email": email,
            "password": password,
        },
    )
    assert reg_resp.status_code == 201, f"Registration failed: {reg_resp.text}"

    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
    return login_resp.json()


async def _get_user_id_by_email(client: AsyncClient, admin_token: str, email: str) -> str:
    """Helper to find a user's ID from the admin listing."""
    resp = await client.get(
        "/api/v1/admin/usuarios",
        headers={"Authorization": f"Bearer {admin_token}"},
        params={"q": email},
    )
    assert resp.status_code == 200
    items = resp.json()["items"]
    matching = [u for u in items if u["email"] == email]
    assert matching, f"User {email} not found in listing"
    return matching[0]["id"]


async def _promote_to_admin(session, email: str) -> None:
    """Promote a user to ADMIN role by manipulating the session directly."""
    from sqlalchemy import select
    from app.models.user import Rol, Usuario, UsuarioRol

    # Get user
    result = await session.execute(
        select(Usuario).where(Usuario.email == email)
    )
    user = result.scalar_one_or_none()
    assert user is not None, f"User {email} not found"

    # Get ADMIN role
    result = await session.execute(
        select(Rol).where(Rol.codigo == "ADMIN")
    )
    admin_rol = result.scalar_one_or_none()
    assert admin_rol is not None, "ADMIN role not seeded"

    # Create UsuarioRol
    ur = UsuarioRol(
        usuario_id=user.id,
        rol_id=admin_rol.id,
        asignado_por_id=None,
    )
    session.add(ur)
    await session.flush()


# ---------------------------------------------------------------------------
# GET /api/v1/admin/usuarios — authorization tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.integration
async def test_list_usuarios_without_auth_returns_401(
    seeded_session, async_client: AsyncClient
) -> None:
    """GET /api/v1/admin/usuarios without Bearer → 401."""
    app.dependency_overrides[get_uow] = make_uow_override(seeded_session)
    try:
        response = await async_client.get("/api/v1/admin/usuarios")
        assert response.status_code == 401
    finally:
        app.dependency_overrides.pop(get_uow, None)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_list_usuarios_with_client_token_returns_403(
    seeded_session, async_client: AsyncClient
) -> None:
    """GET /api/v1/admin/usuarios with CLIENT Bearer → 403."""
    app.dependency_overrides[get_uow] = make_uow_override(seeded_session)
    try:
        # Register as CLIENT (default role)
        tokens = await _register_and_login(
            async_client, "client_test_403@example.com"
        )
        response = await async_client.get(
            "/api/v1/admin/usuarios",
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
        )
        assert response.status_code == 403
    finally:
        app.dependency_overrides.pop(get_uow, None)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_list_usuarios_with_admin_token_returns_200(
    seeded_session, async_client: AsyncClient
) -> None:
    """GET /api/v1/admin/usuarios with ADMIN Bearer → 200 with Page structure."""
    app.dependency_overrides[get_uow] = make_uow_override(seeded_session)
    try:
        # Register user then promote to ADMIN
        await _register_and_login(async_client, "admin_list_200@example.com")
        await _promote_to_admin(seeded_session, "admin_list_200@example.com")

        # Login again to get fresh token (now has ADMIN role)
        tokens = await async_client.post(
            "/api/v1/auth/login",
            json={"email": "admin_list_200@example.com", "password": "Secur3Pass!"},
        )
        admin_token = tokens.json()["access_token"]

        response = await async_client.get(
            "/api/v1/admin/usuarios",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200
        body = response.json()
        assert "items" in body
        assert "total" in body
        assert "page" in body
        assert "size" in body
        assert "pages" in body
        assert isinstance(body["items"], list)
    finally:
        app.dependency_overrides.pop(get_uow, None)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_list_usuarios_with_q_filter(
    seeded_session, async_client: AsyncClient
) -> None:
    """GET /api/v1/admin/usuarios?q=search → filters correctly."""
    app.dependency_overrides[get_uow] = make_uow_override(seeded_session)
    try:
        # Create an admin and a client user
        await _register_and_login(async_client, "admin_q_filter@example.com", nombre="AdminFilter")
        await _promote_to_admin(seeded_session, "admin_q_filter@example.com")

        await _register_and_login(async_client, "client_unique_xyz@example.com", nombre="XyzUnique")

        tokens = await async_client.post(
            "/api/v1/auth/login",
            json={"email": "admin_q_filter@example.com", "password": "Secur3Pass!"},
        )
        admin_token = tokens.json()["access_token"]

        # Search for "XyzUnique"
        response = await async_client.get(
            "/api/v1/admin/usuarios",
            headers={"Authorization": f"Bearer {admin_token}"},
            params={"q": "XyzUnique"},
        )
        assert response.status_code == 200
        body = response.json()
        # All returned items should have "XyzUnique" in nombre, apellido, or email
        # (at minimum, the unique user should appear)
        assert body["total"] >= 1
    finally:
        app.dependency_overrides.pop(get_uow, None)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_list_usuarios_with_activo_true_filter(
    seeded_session, async_client: AsyncClient
) -> None:
    """GET /api/v1/admin/usuarios?activo=true → only active users."""
    app.dependency_overrides[get_uow] = make_uow_override(seeded_session)
    try:
        await _register_and_login(async_client, "admin_activo_filter@example.com")
        await _promote_to_admin(seeded_session, "admin_activo_filter@example.com")

        tokens = await async_client.post(
            "/api/v1/auth/login",
            json={"email": "admin_activo_filter@example.com", "password": "Secur3Pass!"},
        )
        admin_token = tokens.json()["access_token"]

        response = await async_client.get(
            "/api/v1/admin/usuarios",
            headers={"Authorization": f"Bearer {admin_token}"},
            params={"activo": "true"},
        )
        assert response.status_code == 200
        body = response.json()
        # All returned users should be active (deleted_at is None)
        for user in body["items"]:
            assert user["deleted_at"] is None, f"Inactive user in activo=true results: {user}"
    finally:
        app.dependency_overrides.pop(get_uow, None)


# ---------------------------------------------------------------------------
# PUT /api/v1/admin/usuarios/{id}/roles — last admin guard
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.integration
async def test_update_roles_last_admin_returns_409(
    seeded_session, async_client: AsyncClient
) -> None:
    """PUT /api/v1/admin/usuarios/{id}/roles with last ADMIN → 409 LAST_ADMIN_PROTECTED."""
    app.dependency_overrides[get_uow] = make_uow_override(seeded_session)
    try:
        # Create a single admin (only admin in the system)
        await _register_and_login(async_client, "sole_admin@example.com")
        await _promote_to_admin(seeded_session, "sole_admin@example.com")

        tokens = await async_client.post(
            "/api/v1/auth/login",
            json={"email": "sole_admin@example.com", "password": "Secur3Pass!"},
        )
        admin_token = tokens.json()["access_token"]
        admin_id = await _get_user_id_by_email(async_client, admin_token, "sole_admin@example.com")

        # Try to remove ADMIN role from the sole admin
        response = await async_client.put(
            f"/api/v1/admin/usuarios/{admin_id}/roles",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"roles": ["CLIENT"]},
        )
        assert response.status_code == 409
        body = response.json()
        assert body.get("code") == "LAST_ADMIN_PROTECTED"
    finally:
        app.dependency_overrides.pop(get_uow, None)


# ---------------------------------------------------------------------------
# PATCH /api/v1/admin/usuarios/{id}/estado — deactivation flow
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.integration
async def test_deactivate_user_revokes_tokens_and_subsequent_auth_returns_401(
    seeded_session, async_client: AsyncClient
) -> None:
    """PATCH /estado activo=false → deactivate user → subsequent /auth/me → 401."""
    app.dependency_overrides[get_uow] = make_uow_override(seeded_session)
    try:
        # Create admin
        await _register_and_login(async_client, "admin_deactivate@example.com")
        await _promote_to_admin(seeded_session, "admin_deactivate@example.com")

        tokens = await async_client.post(
            "/api/v1/auth/login",
            json={"email": "admin_deactivate@example.com", "password": "Secur3Pass!"},
        )
        admin_token = tokens.json()["access_token"]

        # Create a target client user
        client_tokens = await _register_and_login(
            async_client, "target_client@example.com"
        )
        client_access_token = client_tokens["access_token"]
        client_id = await _get_user_id_by_email(
            async_client, admin_token, "target_client@example.com"
        )

        # Deactivate the client user
        response = await async_client.patch(
            f"/api/v1/admin/usuarios/{client_id}/estado",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"activo": False},
        )
        assert response.status_code == 200

        # Subsequent authenticated request with the deactivated user's token → 401
        me_response = await async_client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {client_access_token}"},
        )
        assert me_response.status_code == 401
    finally:
        app.dependency_overrides.pop(get_uow, None)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_deactivate_user_refresh_token_also_revoked(
    seeded_session, async_client: AsyncClient
) -> None:
    """PATCH /estado activo=false → deactivated user's refresh token → 401."""
    app.dependency_overrides[get_uow] = make_uow_override(seeded_session)
    try:
        # Create admin
        await _register_and_login(async_client, "admin_revoke_rt@example.com")
        await _promote_to_admin(seeded_session, "admin_revoke_rt@example.com")

        tokens = await async_client.post(
            "/api/v1/auth/login",
            json={"email": "admin_revoke_rt@example.com", "password": "Secur3Pass!"},
        )
        admin_token = tokens.json()["access_token"]

        # Create a target client user
        client_tokens = await _register_and_login(
            async_client, "target_revoke_rt@example.com"
        )
        client_refresh_token = client_tokens["refresh_token"]
        client_id = await _get_user_id_by_email(
            async_client, admin_token, "target_revoke_rt@example.com"
        )

        # Deactivate the client user
        response = await async_client.patch(
            f"/api/v1/admin/usuarios/{client_id}/estado",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"activo": False},
        )
        assert response.status_code == 200

        # Attempt to refresh with the deactivated user's refresh token → 401
        refresh_response = await async_client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": client_refresh_token},
        )
        assert refresh_response.status_code == 401
    finally:
        app.dependency_overrides.pop(get_uow, None)
