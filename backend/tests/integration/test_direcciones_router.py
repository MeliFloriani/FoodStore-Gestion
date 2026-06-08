"""
Integration tests for the Direcciones API endpoints.

Change 14: delivery-addresses-management.

Tasks 6.6-6.9:
  - test_crear_primera_direccion_es_principal: POST creates first address → es_principal=True
  - test_marcar_principal_flujo_completo: create two, mark second as principal → first loses flag
  - test_acceso_direccion_ajena_404: access someone else's address → 404
  - test_delete_principal_auto_promueve: DELETE principal with others → auto-promote
  - test_endpoints_sin_token_401: all endpoints return 401 without token
  - test_endpoint_post_returns_201: POST returns 201 with correct body
  - test_endpoint_delete_returns_204: DELETE returns 204 no body
  - test_patch_principal_sin_body_returns_200: PATCH /{id}/principal without body → 200

Uses the SAVEPOINT-based async_session and seeded_session fixtures.
"""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient

from app.core.uow import get_uow
from app.main import app
from tests.fixtures.uow import make_uow_override

DIRECCIONES_URL = "/api/v1/direcciones/"
DIRECCIONES_BASE = "/api/v1/direcciones"

# ---------------------------------------------------------------------------
# Helpers
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


def _auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _new_email() -> str:
    return f"dir_test_{uuid.uuid4().hex[:8]}@test.com"


def _valid_address_body(**kwargs) -> dict:
    base = {"linea1": "Av. Siempre Viva 742"}
    base.update(kwargs)
    return base


# ---------------------------------------------------------------------------
# Task 6.6 + 6.7 — Crear primera dirección → es_principal=True
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_crear_primera_direccion_es_principal(
    seeded_session, async_client: AsyncClient
) -> None:
    """POST first address → es_principal=True, HTTP 201."""
    app.dependency_overrides[get_uow] = make_uow_override(seeded_session)
    try:
        token = await _register_and_get_token(async_client, _new_email())

        resp = await async_client.post(
            DIRECCIONES_URL,
            json=_valid_address_body(alias="Casa"),
            headers=_auth_headers(token),
        )
        assert resp.status_code == 201, f"Expected 201, got: {resp.text}"
        body = resp.json()
        assert body["es_principal"] is True
        assert body["linea1"] == "Av. Siempre Viva 742"
        assert body["alias"] == "Casa"
        assert "id" in body
    finally:
        app.dependency_overrides.pop(get_uow, None)


@pytest.mark.asyncio
async def test_crear_segunda_direccion_no_es_principal(
    seeded_session, async_client: AsyncClient
) -> None:
    """POST second address → es_principal=False, first remains principal."""
    app.dependency_overrides[get_uow] = make_uow_override(seeded_session)
    try:
        token = await _register_and_get_token(async_client, _new_email())

        # Create first address
        resp1 = await async_client.post(
            DIRECCIONES_URL,
            json=_valid_address_body(alias="Casa"),
            headers=_auth_headers(token),
        )
        assert resp1.status_code == 201
        assert resp1.json()["es_principal"] is True

        # Create second address
        resp2 = await async_client.post(
            DIRECCIONES_URL,
            json=_valid_address_body(linea1="Calle Falsa 123", alias="Trabajo"),
            headers=_auth_headers(token),
        )
        assert resp2.status_code == 201, f"Expected 201, got: {resp2.text}"
        assert resp2.json()["es_principal"] is False
    finally:
        app.dependency_overrides.pop(get_uow, None)


# ---------------------------------------------------------------------------
# Task 6.7 — Marcar segunda como principal → primera pierde es_principal
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_marcar_principal_flujo_completo(
    seeded_session, async_client: AsyncClient
) -> None:
    """Create two addresses; mark second as principal → first loses the flag."""
    app.dependency_overrides[get_uow] = make_uow_override(seeded_session)
    try:
        token = await _register_and_get_token(async_client, _new_email())

        # Create first address (auto-principal)
        r1 = await async_client.post(
            DIRECCIONES_URL,
            json=_valid_address_body(alias="Primera"),
            headers=_auth_headers(token),
        )
        assert r1.status_code == 201
        id_primera = r1.json()["id"]

        # Create second address (not principal)
        r2 = await async_client.post(
            DIRECCIONES_URL,
            json=_valid_address_body(linea1="Otro 456", alias="Segunda"),
            headers=_auth_headers(token),
        )
        assert r2.status_code == 201
        id_segunda = r2.json()["id"]

        # Mark second as principal
        patch_resp = await async_client.patch(
            f"{DIRECCIONES_BASE}/{id_segunda}/principal",
            headers=_auth_headers(token),
        )
        assert patch_resp.status_code == 200, f"Expected 200, got: {patch_resp.text}"
        assert patch_resp.json()["es_principal"] is True

        # Verify first is no longer principal via GET
        get_first = await async_client.get(
            f"{DIRECCIONES_BASE}/{id_primera}",
            headers=_auth_headers(token),
        )
        assert get_first.status_code == 200
        assert get_first.json()["es_principal"] is False
    finally:
        app.dependency_overrides.pop(get_uow, None)


# ---------------------------------------------------------------------------
# Task 6.8 — Acceso a dirección ajena → 404
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_acceso_direccion_ajena_404(
    seeded_session, async_client: AsyncClient
) -> None:
    """GET / PATCH / DELETE on another user's address → 404 (not 403)."""
    app.dependency_overrides[get_uow] = make_uow_override(seeded_session)
    try:
        token_a = await _register_and_get_token(async_client, _new_email())
        token_b = await _register_and_get_token(async_client, _new_email())

        # User A creates an address
        r = await async_client.post(
            DIRECCIONES_URL,
            json=_valid_address_body(),
            headers=_auth_headers(token_a),
        )
        assert r.status_code == 201
        addr_id = r.json()["id"]

        # User B tries to access it → 404
        get_resp = await async_client.get(
            f"{DIRECCIONES_BASE}/{addr_id}",
            headers=_auth_headers(token_b),
        )
        assert get_resp.status_code == 404, f"Expected 404, got: {get_resp.status_code}"

        # User B tries to delete it → 404
        del_resp = await async_client.delete(
            f"{DIRECCIONES_BASE}/{addr_id}",
            headers=_auth_headers(token_b),
        )
        assert del_resp.status_code == 404, f"Expected 404, got: {del_resp.status_code}"
    finally:
        app.dependency_overrides.pop(get_uow, None)


# ---------------------------------------------------------------------------
# Task 6.9 — DELETE principal con otras activas → auto-promote
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_principal_auto_promueve(
    seeded_session, async_client: AsyncClient
) -> None:
    """DELETE principal address with others active → another becomes principal."""
    app.dependency_overrides[get_uow] = make_uow_override(seeded_session)
    try:
        token = await _register_and_get_token(async_client, _new_email())

        # Create first (principal)
        r1 = await async_client.post(
            DIRECCIONES_URL,
            json=_valid_address_body(alias="Principal"),
            headers=_auth_headers(token),
        )
        assert r1.status_code == 201
        id_principal = r1.json()["id"]

        # Create second (not principal)
        r2 = await async_client.post(
            DIRECCIONES_URL,
            json=_valid_address_body(linea1="Otra 99", alias="Otra"),
            headers=_auth_headers(token),
        )
        assert r2.status_code == 201
        id_otra = r2.json()["id"]

        # Delete the principal
        del_resp = await async_client.delete(
            f"{DIRECCIONES_BASE}/{id_principal}",
            headers=_auth_headers(token),
        )
        assert del_resp.status_code == 204, f"Expected 204, got: {del_resp.text}"

        # The other address should now be principal
        get_otra = await async_client.get(
            f"{DIRECCIONES_BASE}/{id_otra}",
            headers=_auth_headers(token),
        )
        assert get_otra.status_code == 200
        assert get_otra.json()["es_principal"] is True
    finally:
        app.dependency_overrides.pop(get_uow, None)


# ---------------------------------------------------------------------------
# Endpoint sans token → 401
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_endpoints_sin_token_401(
    seeded_session, async_client: AsyncClient
) -> None:
    """All direcciones endpoints return 401 without Authorization header."""
    app.dependency_overrides[get_uow] = make_uow_override(seeded_session)
    try:
        fake_id = str(uuid.uuid4())

        endpoints_and_methods = [
            ("POST", DIRECCIONES_URL, {"linea1": "X"}),
            ("GET", DIRECCIONES_URL, None),
            ("GET", f"{DIRECCIONES_BASE}/{fake_id}", None),
            ("PATCH", f"{DIRECCIONES_BASE}/{fake_id}/principal", None),
            ("PATCH", f"{DIRECCIONES_BASE}/{fake_id}", {"alias": "Y"}),
            ("DELETE", f"{DIRECCIONES_BASE}/{fake_id}", None),
        ]

        for method, url, body in endpoints_and_methods:
            if method == "POST":
                resp = await async_client.post(url, json=body)
            elif method == "GET":
                resp = await async_client.get(url)
            elif method == "PATCH":
                resp = await async_client.patch(url, json=body)
            elif method == "DELETE":
                resp = await async_client.delete(url)
            else:
                continue

            assert resp.status_code == 401, (
                f"{method} {url} expected 401, got {resp.status_code}: {resp.text}"
            )
    finally:
        app.dependency_overrides.pop(get_uow, None)


# ---------------------------------------------------------------------------
# Task 6.6 — DELETE retorna 204 sin body
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_retorna_204_sin_body(
    seeded_session, async_client: AsyncClient
) -> None:
    """DELETE returns HTTP 204 with empty body."""
    app.dependency_overrides[get_uow] = make_uow_override(seeded_session)
    try:
        token = await _register_and_get_token(async_client, _new_email())

        r = await async_client.post(
            DIRECCIONES_URL,
            json=_valid_address_body(),
            headers=_auth_headers(token),
        )
        assert r.status_code == 201
        addr_id = r.json()["id"]

        del_resp = await async_client.delete(
            f"{DIRECCIONES_BASE}/{addr_id}",
            headers=_auth_headers(token),
        )
        assert del_resp.status_code == 204
        assert del_resp.content == b""
    finally:
        app.dependency_overrides.pop(get_uow, None)


# ---------------------------------------------------------------------------
# PATCH /{id}/principal without body → 200
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_patch_principal_sin_body_retorna_200(
    seeded_session, async_client: AsyncClient
) -> None:
    """PATCH /{id}/principal without body returns HTTP 200."""
    app.dependency_overrides[get_uow] = make_uow_override(seeded_session)
    try:
        token = await _register_and_get_token(async_client, _new_email())

        r = await async_client.post(
            DIRECCIONES_URL,
            json=_valid_address_body(),
            headers=_auth_headers(token),
        )
        assert r.status_code == 201
        addr_id = r.json()["id"]

        patch_resp = await async_client.patch(
            f"{DIRECCIONES_BASE}/{addr_id}/principal",
            headers=_auth_headers(token),
            # No body — the endpoint does not require one
        )
        assert patch_resp.status_code == 200, f"Expected 200, got: {patch_resp.text}"
        assert patch_resp.json()["es_principal"] is True
    finally:
        app.dependency_overrides.pop(get_uow, None)
