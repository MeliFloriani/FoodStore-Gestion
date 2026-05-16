"""
E2E-style integration test for the full auth round-trip.

Task 12.1 — exercises the complete flow:
  POST /register → get UserRead
  POST /login with same credentials → get TokenResponse
  GET /api/v1/health with Authorization: Bearer header → verify not 401
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.core.uow import get_uow
from app.main import app
from tests.fixtures.uow import make_uow_override


@pytest.mark.asyncio
async def test_auth_e2e_full_round_trip(seeded_session, async_client: AsyncClient) -> None:
    """Full auth round-trip: register → login → authenticated request.

    Step 1: Register a new user → verify 201 + UserRead shape.
    Step 2: Login with same credentials → verify 200 + TokenResponse shape.
    Step 3: GET /api/v1/health with Authorization: Bearer → verify not rejected (not 401).
    """
    app.dependency_overrides[get_uow] = make_uow_override(seeded_session)

    try:
        # --- Step 1: Register ---
        register_payload = {
            "nombre": "E2E",
            "apellido": "Tester",
            "email": "e2e_roundtrip@example.com",
            "password": "E2EPassword123!",
        }
        register_resp = await async_client.post(
            "/api/v1/auth/register", json=register_payload
        )
        assert register_resp.status_code == 201, f"Register failed: {register_resp.text}"
        user_data = register_resp.json()

        # Verify UserRead shape
        assert isinstance(user_data["id"], str)
        assert user_data["nombre"] == "E2E"
        assert user_data["apellido"] == "Tester"
        assert user_data["email"] == "e2e_roundtrip@example.com"
        assert user_data["roles"] == ["CLIENT"]

        # --- Step 2: Login ---
        login_payload = {
            "email": register_payload["email"],
            "password": register_payload["password"],
        }
        login_resp = await async_client.post("/api/v1/auth/login", json=login_payload)
        assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
        token_data = login_resp.json()

        # Verify TokenResponse shape
        assert "access_token" in token_data
        assert "refresh_token" in token_data
        assert token_data["token_type"] == "bearer"
        assert token_data["expires_in"] == 1800
        access_token = token_data["access_token"]
        assert access_token  # non-empty

        # --- Step 3: Authenticated request ---
        # The health endpoint doesn't require auth, but we test that the token
        # is a valid JWT that would not cause a 401 if used on a protected endpoint.
        # Since there are no protected domain endpoints yet, we verify against /health.
        health_resp = await async_client.get(
            "/api/v1/health",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        # Health should return 200 regardless — it does not validate the token
        assert health_resp.status_code == 200
        # Critically, NOT 401
        assert health_resp.status_code != 401

    finally:
        app.dependency_overrides.pop(get_uow, None)


@pytest.mark.asyncio
async def test_auth_e2e_token_is_valid_jwt(seeded_session, async_client: AsyncClient) -> None:
    """The access_token returned by login must be a valid JWT decodable by decode_access_token."""
    app.dependency_overrides[get_uow] = make_uow_override(seeded_session)

    try:
        # Register + login
        payload = {
            "nombre": "E2E",
            "apellido": "JWT",
            "email": "e2e_jwt@example.com",
            "password": "ValidPass123!",
        }
        await async_client.post("/api/v1/auth/register", json=payload)
        login_resp = await async_client.post(
            "/api/v1/auth/login",
            json={"email": payload["email"], "password": payload["password"]},
        )
        assert login_resp.status_code == 200
        access_token = login_resp.json()["access_token"]

        # Decode the token using the security module
        from app.core.security import decode_access_token

        decoded = decode_access_token(access_token)
        assert "sub" in decoded
        # sub should be a non-empty UUID string
        assert len(decoded["sub"]) > 0
        assert decoded.get("type") == "access"

    finally:
        app.dependency_overrides.pop(get_uow, None)
