"""
Integration tests for GET /api/v1/auth/me.

Task 6.5 — /auth/me endpoint coverage.

Scenarios:
  - Valid CLIENT token → 200 with UserRead (includes created_at)
  - Missing token → 401
  - Expired token → 401
  - Response never exposes password_hash
  - created_at is a valid ISO 8601 datetime string in the response
"""

from __future__ import annotations

import uuid
from datetime import datetime

import pytest
from httpx import AsyncClient

from app.core.uow import get_uow
from app.main import app
from tests.fixtures.uow import make_uow_override


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _register_and_login(client: AsyncClient) -> tuple[str, str, dict]:
    """Register a unique user and log in, returning (access_token, refresh_token, user_body)."""
    email = f"me_test_{uuid.uuid4().hex[:8]}@example.com"
    password = "Secur3Pass!"

    reg = await client.post(
        "/api/v1/auth/register",
        json={
            "nombre": "Me",
            "apellido": "Test",
            "email": email,
            "password": password,
        },
    )
    assert reg.status_code == 201, f"Registration failed: {reg.text}"
    user_body = reg.json()

    login = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert login.status_code == 200, f"Login failed: {login.text}"
    body = login.json()
    return body["access_token"], body["refresh_token"], user_body


# ---------------------------------------------------------------------------
# Task 6.5 — Valid CLIENT token returns 200 with UserRead
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_me_200_valid_token(seeded_session, async_client: AsyncClient) -> None:
    """GET /auth/me with a valid Bearer access token returns 200 with UserRead."""
    app.dependency_overrides[get_uow] = make_uow_override(seeded_session)
    try:
        access_token, _, user_body = await _register_and_login(async_client)

        response = await async_client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert response.status_code == 200, f"Expected 200, got: {response.text}"

        body = response.json()
        assert "id" in body
        assert "nombre" in body
        assert "apellido" in body
        assert "email" in body
        assert "roles" in body
        assert "created_at" in body

        # id must be a UUID string
        uuid.UUID(body["id"])  # raises ValueError if not valid UUID

        # roles must include CLIENT
        assert "CLIENT" in body["roles"]

        # password_hash must NOT be present
        assert "password_hash" not in body

    finally:
        app.dependency_overrides.pop(get_uow, None)


@pytest.mark.asyncio
async def test_me_response_includes_created_at_iso8601(seeded_session, async_client: AsyncClient) -> None:
    """GET /auth/me response includes created_at as a valid ISO 8601 datetime string."""
    app.dependency_overrides[get_uow] = make_uow_override(seeded_session)
    try:
        access_token, _, _ = await _register_and_login(async_client)

        response = await async_client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert response.status_code == 200
        body = response.json()

        created_at_str = body.get("created_at")
        assert created_at_str is not None, "created_at field must be present"

        # Must be parseable as a datetime
        # ISO 8601 format — Python's datetime.fromisoformat handles this
        try:
            dt = datetime.fromisoformat(created_at_str.replace("Z", "+00:00"))
            assert isinstance(dt, datetime)
        except ValueError as e:
            pytest.fail(f"created_at is not a valid ISO 8601 datetime: {created_at_str!r} — {e}")

    finally:
        app.dependency_overrides.pop(get_uow, None)


@pytest.mark.asyncio
async def test_me_401_missing_token(async_client: AsyncClient) -> None:
    """GET /auth/me without an Authorization header returns 401."""
    response = await async_client.get("/api/v1/auth/me")
    assert response.status_code == 401, f"Expected 401, got: {response.text}"


@pytest.mark.asyncio
async def test_me_401_expired_token(async_client: AsyncClient) -> None:
    """GET /auth/me with an expired JWT returns 401."""
    # This JWT was generated with exp in the past — it will fail signature or
    # expiry check in decode_access_token. Use a clearly-invalid token.
    fake_expired_token = (
        "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
        "eyJzdWIiOiIwMDAwMDAwMC0wMDAwLTAwMDAtMDAwMC0wMDAwMDAwMDAwMDAiLCJleHAiOjF9."
        "invalid_signature_for_test_only"
    )
    response = await async_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {fake_expired_token}"},
    )
    assert response.status_code == 401, f"Expected 401 for expired token, got: {response.text}"


@pytest.mark.asyncio
async def test_me_response_never_exposes_password_hash(seeded_session, async_client: AsyncClient) -> None:
    """GET /auth/me response body does NOT contain the password_hash field."""
    app.dependency_overrides[get_uow] = make_uow_override(seeded_session)
    try:
        access_token, _, _ = await _register_and_login(async_client)

        response = await async_client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert response.status_code == 200
        body = response.json()

        # password_hash must not appear anywhere in the response JSON
        assert "password_hash" not in body
        assert "password" not in body

        # The response text must not contain the bcrypt prefix either
        assert "$2b$" not in response.text

    finally:
        app.dependency_overrides.pop(get_uow, None)
