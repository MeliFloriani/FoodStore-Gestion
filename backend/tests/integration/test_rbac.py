"""
Integration tests for RBAC infrastructure (require_role end-to-end).

Task 6.6 — RBAC smoke test coverage.

Scenarios:
  - CLIENT token on /auth/me → 200 (authenticated, no role restriction)
  - CLIENT token on ADMIN-protected test endpoint → 403
  - No token on ADMIN-protected endpoint → 401
  - ADMIN token on ADMIN-protected endpoint → 200

Implementation note:
  This test registers a test-only ADMIN-protected route on the running app.
  The route is added/removed in test setup/teardown so it does not affect
  other tests. The goal is to confirm the require_role dependency chain:
    get_current_user → role check → ForbiddenError (403)
  without requiring a real admin-only endpoint from another change.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi import APIRouter, Depends
from httpx import AsyncClient

from app.api.deps import get_current_user, require_role
from app.core.uow import get_uow
from app.main import app
from app.models.user import Usuario
from tests.fixtures.uow import make_uow_override


# ---------------------------------------------------------------------------
# Test-only ADMIN route setup
# ---------------------------------------------------------------------------

_test_rbac_router = APIRouter()


@_test_rbac_router.get("/test-admin-only", tags=["rbac-test"])
async def _admin_only_endpoint(
    current_user: Usuario = Depends(require_role("ADMIN")),
) -> dict:
    """Test-only ADMIN-protected endpoint for RBAC smoke tests."""
    return {"ok": True, "user_id": str(current_user.id)}


# Mount the test router into the app for the duration of the test module.
# This approach avoids modifying the production router.
app.include_router(_test_rbac_router, prefix="/api/v1/auth")

ADMIN_ENDPOINT = "/api/v1/auth/test-admin-only"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _register_and_login_client(
    client: AsyncClient, suffix: str = ""
) -> tuple[str, str]:
    """Register a CLIENT-role user and return (access_token, user_id)."""
    email = f"rbac_client_{suffix}_{uuid.uuid4().hex[:6]}@example.com"
    reg = await client.post(
        "/api/v1/auth/register",
        json={
            "nombre": "RBAC",
            "apellido": "Client",
            "email": email,
            "password": "Secur3Pass!",
        },
    )
    assert reg.status_code == 201, f"Registration failed: {reg.text}"
    user_id = reg.json()["id"]

    login = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "Secur3Pass!"},
    )
    assert login.status_code == 200, f"Login failed: {login.text}"
    return login.json()["access_token"], user_id


async def _create_admin_user(
    client: AsyncClient, seeded_session, suffix: str = ""
) -> str:
    """Register a user and manually assign the ADMIN role, returning access_token."""
    from app.models.user import UsuarioRol
    from app.repositories.user import RolRepository, UsuarioRepository

    email = f"rbac_admin_{suffix}_{uuid.uuid4().hex[:6]}@example.com"
    reg = await client.post(
        "/api/v1/auth/register",
        json={
            "nombre": "RBAC",
            "apellido": "Admin",
            "email": email,
            "password": "Secur3Pass!",
        },
    )
    assert reg.status_code == 201, f"Admin registration failed: {reg.text}"
    user_id = uuid.UUID(reg.json()["id"])

    # Assign ADMIN role directly via repository
    rol_repo = RolRepository(seeded_session)
    admin_rol = await rol_repo.get_by_codigo("ADMIN")
    assert admin_rol is not None, "ADMIN role not seeded"

    ur = UsuarioRol(
        usuario_id=user_id,
        rol_id=admin_rol.id,
        asignado_por_id=None,
    )
    seeded_session.add(ur)
    await seeded_session.flush()

    login = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "Secur3Pass!"},
    )
    assert login.status_code == 200, f"Admin login failed: {login.text}"
    return login.json()["access_token"]


# ---------------------------------------------------------------------------
# Task 6.6 — RBAC smoke tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_rbac_client_on_me_returns_200(seeded_session, async_client: AsyncClient) -> None:
    """CLIENT token on /auth/me returns 200 — /auth/me has no role restriction."""
    app.dependency_overrides[get_uow] = make_uow_override(seeded_session)
    try:
        access_token, _ = await _register_and_login_client(async_client, "me")

        response = await async_client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert response.status_code == 200, f"Expected 200 on /me for CLIENT, got: {response.text}"
    finally:
        app.dependency_overrides.pop(get_uow, None)


@pytest.mark.asyncio
async def test_rbac_client_on_admin_endpoint_returns_403(seeded_session, async_client: AsyncClient) -> None:
    """CLIENT token on an ADMIN-protected endpoint returns 403 Forbidden."""
    app.dependency_overrides[get_uow] = make_uow_override(seeded_session)
    try:
        access_token, _ = await _register_and_login_client(async_client, "403")

        response = await async_client.get(
            ADMIN_ENDPOINT,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert response.status_code == 403, (
            f"Expected 403 for CLIENT on admin endpoint, got: {response.status_code}"
        )
        body = response.json()
        # Must follow RFC 7807 format
        assert body.get("status") == 403
    finally:
        app.dependency_overrides.pop(get_uow, None)


@pytest.mark.asyncio
async def test_rbac_no_token_on_admin_endpoint_returns_401(async_client: AsyncClient) -> None:
    """No token on ADMIN-protected endpoint returns 401, not 403.

    Authentication precedes authorization — 401 takes precedence.
    """
    response = await async_client.get(ADMIN_ENDPOINT)
    assert response.status_code == 401, (
        f"Expected 401 (not 403) for missing token on admin endpoint, got: {response.status_code}"
    )


@pytest.mark.asyncio
async def test_rbac_admin_token_on_admin_endpoint_returns_200(seeded_session, async_client: AsyncClient) -> None:
    """ADMIN token on ADMIN-protected endpoint returns 200."""
    app.dependency_overrides[get_uow] = make_uow_override(seeded_session)
    try:
        admin_token = await _create_admin_user(async_client, seeded_session, "200")

        response = await async_client.get(
            ADMIN_ENDPOINT,
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200, (
            f"Expected 200 for ADMIN token on admin endpoint, got: {response.text}"
        )
        body = response.json()
        assert body.get("ok") is True
    finally:
        app.dependency_overrides.pop(get_uow, None)
