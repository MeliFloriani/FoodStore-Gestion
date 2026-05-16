"""
Integration tests for POST /api/v1/auth/login.

Tasks 1.5 (stub xfail), 7.7, 7.8, 7.9, 7.10 (real tests added after router implementation).
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.core.uow import get_uow
from app.main import app
from tests.fixtures.uow import make_uow_override


# ---------------------------------------------------------------------------
# Helper — register a user then log in
# ---------------------------------------------------------------------------


async def _register_user(client: AsyncClient, email: str, password: str) -> None:
    """Helper to register a test user for login tests."""
    resp = await client.post(
        "/api/v1/auth/register",
        json={
            "nombre": "Test",
            "apellido": "User",
            "email": email,
            "password": password,
        },
    )
    assert resp.status_code == 201, f"Registration failed: {resp.text}"


# ---------------------------------------------------------------------------
# Task 7.7 — 200 happy path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_login_200_happy_path(seeded_session, async_client: AsyncClient) -> None:
    """POST /api/v1/auth/login with valid credentials returns 200 and TokenResponse."""
    app.dependency_overrides[get_uow] = make_uow_override(seeded_session)
    try:
        email = "login_happy@example.com"
        password = "Secur3Pass!"
        await _register_user(async_client, email, password)

        response = await async_client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": password},
        )
        assert response.status_code == 200
        body = response.json()
        assert "access_token" in body
        assert "refresh_token" in body
        assert body["token_type"] == "bearer"
        assert body["expires_in"] == 1800
    finally:
        app.dependency_overrides.pop(get_uow, None)


# ---------------------------------------------------------------------------
# Task 7.8 — 401 wrong password
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_login_401_wrong_password(seeded_session, async_client: AsyncClient) -> None:
    """POST /api/v1/auth/login with wrong password returns 401 with code invalid_credentials."""
    app.dependency_overrides[get_uow] = make_uow_override(seeded_session)
    try:
        email = "login_wrong_pw@example.com"
        password = "Secur3Pass!"
        await _register_user(async_client, email, password)

        response = await async_client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": "WrongPassword!"},
        )
        assert response.status_code == 401
        body = response.json()
        assert body.get("code") == "invalid_credentials"
    finally:
        app.dependency_overrides.pop(get_uow, None)


# ---------------------------------------------------------------------------
# Task 7.9 — 401 non-existent email
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_login_401_nonexistent_email(async_client: AsyncClient) -> None:
    """POST /api/v1/auth/login with unknown email returns 401 — same shape as wrong password."""
    response = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "nobody@example.com", "password": "AnyPassword123!"},
    )
    assert response.status_code == 401
    body = response.json()
    assert body.get("code") == "invalid_credentials"


# ---------------------------------------------------------------------------
# Task 7.10 — 429 rate limit (6th request triggers 429)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_login_429_rate_limit(seeded_session, async_client: AsyncClient) -> None:
    """The 6th login request from the same IP within the rate-limit window returns 429.

    The @limiter.limit("5/15minutes") decorator on the login endpoint limits to 5 per window.
    The cache_clear autouse fixture resets the limiter between tests.
    """
    app.dependency_overrides[get_uow] = make_uow_override(seeded_session)
    try:
        # Make 5 requests — they should all go through (401 or 200, not 429)
        for i in range(5):
            resp = await async_client.post(
                "/api/v1/auth/login",
                json={"email": f"ratelimit_{i}@example.com", "password": "AnyPass123!"},
            )
            assert resp.status_code != 429, f"Request {i+1} unexpectedly got 429"

        # 6th request should get 429
        resp = await async_client.post(
            "/api/v1/auth/login",
            json={"email": "ratelimit_6@example.com", "password": "AnyPass123!"},
        )
        assert resp.status_code == 429
    finally:
        app.dependency_overrides.pop(get_uow, None)
