"""
Integration tests for POST /api/v1/auth/register.

Tasks 1.4 (stub xfail), 7.4, 7.5, 7.6 (real tests added after router implementation).
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import AsyncClient

from app.core.uow import get_uow
from app.main import app
from tests.fixtures.uow import make_uow_override


# ---------------------------------------------------------------------------
# Task 1.4 — stub integration tests (xfail until router exists)
# These are converted to real tests in tasks 7.4, 7.5, 7.6
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_register_201_happy_path(async_session, async_client: AsyncClient) -> None:
    """POST /api/v1/auth/register with valid payload returns 201 and UserRead body."""
    app.dependency_overrides[get_uow] = make_uow_override(async_session)
    try:
        response = await async_client.post(
            "/api/v1/auth/register",
            json={
                "nombre": "Juan",
                "apellido": "Pérez",
                "email": "juan_register@example.com",
                "password": "Secur3Pass!",
            },
        )
        assert response.status_code == 201
        body = response.json()
        assert isinstance(body["id"], str)
        assert body["nombre"] == "Juan"
        assert body["apellido"] == "Pérez"
        assert body["email"] == "juan_register@example.com"
        assert body["roles"] == ["CLIENT"]
    finally:
        app.dependency_overrides.pop(get_uow, None)


@pytest.mark.asyncio
async def test_register_409_duplicate_email(async_session, async_client: AsyncClient) -> None:
    """POST /api/v1/auth/register with duplicate email returns 409."""
    app.dependency_overrides[get_uow] = make_uow_override(async_session)
    try:
        payload = {
            "nombre": "Juan",
            "apellido": "Pérez",
            "email": "duplicate_register@example.com",
            "password": "Secur3Pass!",
        }
        # First registration
        r1 = await async_client.post("/api/v1/auth/register", json=payload)
        assert r1.status_code == 201
        # Second registration — same email
        r2 = await async_client.post("/api/v1/auth/register", json=payload)
        assert r2.status_code == 409
    finally:
        app.dependency_overrides.pop(get_uow, None)


@pytest.mark.asyncio
async def test_register_422_short_password(async_client: AsyncClient) -> None:
    """POST /api/v1/auth/register with short password returns 422."""
    response = await async_client.post(
        "/api/v1/auth/register",
        json={
            "nombre": "Juan",
            "apellido": "Pérez",
            "email": "short_pw@example.com",
            "password": "short",
        },
    )
    assert response.status_code == 422
