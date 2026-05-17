"""
Integration tests for POST /api/v1/auth/logout.

Task 6.4 — logout endpoint coverage.

Scenarios:
  - Valid refresh token is revoked (204)
  - Unknown token still returns 204 (idempotent)
  - Already-revoked token returns 204 (idempotent)
  - No Bearer token → still 204 (access token not required)
  - Missing body field → 422
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.core.uow import get_uow
from app.main import app
from app.models.user import RefreshToken
from tests.fixtures.uow import make_uow_override


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _register_and_login(client: AsyncClient) -> tuple[str, str]:
    """Register a unique user and log in, returning (access_token, refresh_token)."""
    email = f"logout_test_{uuid.uuid4().hex[:8]}@example.com"
    password = "Secur3Pass!"

    reg = await client.post(
        "/api/v1/auth/register",
        json={
            "nombre": "Logout",
            "apellido": "Test",
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
    body = login.json()
    return body["access_token"], body["refresh_token"]


# ---------------------------------------------------------------------------
# Task 6.4 — Valid refresh token revoked on logout (204)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_logout_204_valid_token(seeded_session, async_client: AsyncClient) -> None:
    """POST /auth/logout with a valid refresh token returns 204 and revokes the token.

    Tech debt fix (post Change 07 blind audit): added DB-level assertion to verify
    revoked_at is set on the RefreshToken row after logout, mirroring the §6.2 replay
    test's rigor. Verifies the logout endpoint actually persists revocation to the DB.
    """
    app.dependency_overrides[get_uow] = make_uow_override(seeded_session)
    try:
        _, refresh_token = await _register_and_login(async_client)

        response = await async_client.post(
            "/api/v1/auth/logout",
            json={"refresh_token": refresh_token},
        )
        assert response.status_code == 204, f"Expected 204, got: {response.text}"
        assert response.content == b""  # No body

        # Tech debt fix (post Change 07 blind audit): DB-level assertion —
        # verify that revoked_at is actually set in the database after logout.
        # This mirrors the §6.2 replay test rigor (D-07-C verification pattern).
        token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()
        result = await seeded_session.execute(
            select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        )
        db_token = result.scalar_one_or_none()
        assert db_token is not None, (
            "RefreshToken row not found in DB after logout — seeded_session scope issue?"
        )
        assert db_token.revoked_at is not None, (
            "DB-LEVEL ASSERTION FAILED: RefreshToken.revoked_at is still None after logout. "
            "The logout endpoint must set revoked_at via revoke_by_hash()."
        )
        # Verify revocation timestamp is recent (within 5 seconds of test execution)
        revoked_delta = datetime.now(timezone.utc) - db_token.revoked_at.replace(
            tzinfo=timezone.utc if db_token.revoked_at.tzinfo is None else db_token.revoked_at.tzinfo
        )
        assert revoked_delta.total_seconds() < 5, (
            f"revoked_at timestamp is unexpectedly old: {db_token.revoked_at} "
            f"(delta: {revoked_delta.total_seconds():.1f}s)"
        )
    finally:
        app.dependency_overrides.pop(get_uow, None)


@pytest.mark.asyncio
async def test_logout_204_unknown_token(async_client: AsyncClient) -> None:
    """POST /auth/logout with an unknown refresh token returns 204 (idempotent)."""
    response = await async_client.post(
        "/api/v1/auth/logout",
        json={"refresh_token": "completely_unknown_token_should_still_return_204"},
    )
    assert response.status_code == 204, f"Expected 204, got: {response.text}"


@pytest.mark.asyncio
async def test_logout_204_already_revoked(seeded_session, async_client: AsyncClient) -> None:
    """POST /auth/logout with an already-revoked token returns 204 (idempotent)."""
    app.dependency_overrides[get_uow] = make_uow_override(seeded_session)
    try:
        _, refresh_token = await _register_and_login(async_client)

        # First logout
        r1 = await async_client.post(
            "/api/v1/auth/logout",
            json={"refresh_token": refresh_token},
        )
        assert r1.status_code == 204

        # Second logout of the same token — must also return 204
        r2 = await async_client.post(
            "/api/v1/auth/logout",
            json={"refresh_token": refresh_token},
        )
        assert r2.status_code == 204, f"Second logout should still return 204, got: {r2.text}"
    finally:
        app.dependency_overrides.pop(get_uow, None)


@pytest.mark.asyncio
async def test_logout_204_no_bearer_token(seeded_session, async_client: AsyncClient) -> None:
    """POST /auth/logout without Authorization header returns 204.

    The endpoint does NOT require a valid access token (D-07-D).
    """
    app.dependency_overrides[get_uow] = make_uow_override(seeded_session)
    try:
        _, refresh_token = await _register_and_login(async_client)

        # Explicitly no Authorization header
        response = await async_client.post(
            "/api/v1/auth/logout",
            json={"refresh_token": refresh_token},
            headers={"Authorization": ""},  # No Bearer token
        )
        assert response.status_code == 204, f"Expected 204 without Bearer, got: {response.text}"
    finally:
        app.dependency_overrides.pop(get_uow, None)


@pytest.mark.asyncio
async def test_logout_422_missing_body(async_client: AsyncClient) -> None:
    """POST /auth/logout without refresh_token field returns 422."""
    response = await async_client.post(
        "/api/v1/auth/logout",
        json={},  # Missing refresh_token
    )
    assert response.status_code == 422, f"Expected 422 for missing field, got: {response.text}"
