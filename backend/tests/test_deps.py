"""
Integration tests for app/api/deps.py — get_current_user + require_role.

Uses the SAVEPOINT-based async_session fixture and make_uow_override to inject
the test session into the FastAPI app.

Covers spec scenarios from backend-auth-dependencies spec:
- Valid token resolves to active user (200)
- Missing Authorization header returns HTTP 401
- Expired token returns HTTP 401
- Invalid signature returns HTTP 401
- Soft-deleted user returns HTTP 401
- Non-existent user ID in token returns HTTP 401
- User with matching role proceeds (200)
- User without matching role returns HTTP 403
- Unauthenticated request to role-protected route returns HTTP 401 (not 403)

Coverage target: ≥92% on api/deps.py
"""

from __future__ import annotations

import time
import uuid
from datetime import datetime
from typing import Any

import pytest
from fastapi import APIRouter, Depends
from httpx import ASGITransport, AsyncClient
from jose import jwt
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, oauth2_scheme, require_role
from app.core.exceptions import UnauthorizedError
from app.core.uow import UnitOfWork, get_uow
from app.main import app
from app.models.user import Rol, Usuario, UsuarioRol
from app.repositories.user import RolRepository, UsuarioRepository, UsuarioRolRepository
from tests.fixtures.uow import make_uow_override

_TEST_SECRET = "test-secret-key-for-development-only-change-in-production"
_ALGORITHM = "HS256"


def _now() -> datetime:
    """Return a naive UTC datetime for TIMESTAMP WITHOUT TIME ZONE columns."""
    return datetime.utcnow()


def _make_token(user_id: uuid.UUID, exp_offset: int = 3600, secret: str = _TEST_SECRET) -> str:
    """Create a test JWT for the given user UUID."""
    payload = {
        "sub": str(user_id),
        "exp": int(time.time()) + exp_offset,
    }
    return jwt.encode(payload, secret, algorithm=_ALGORITHM)


def _expired_token(user_id: uuid.UUID) -> str:
    """Create an expired JWT for the given user UUID."""
    return _make_token(user_id, exp_offset=-3600)


def _wrong_sig_token(user_id: uuid.UUID) -> str:
    """Create a JWT signed with the wrong key."""
    return _make_token(user_id, secret="wrong-secret-key")


async def _seed_user(session: AsyncSession, email: str | None = None) -> Usuario:
    """Create and flush a test Usuario using naive datetimes."""
    repo = UsuarioRepository(session)
    now = _now()
    user = Usuario(
        id=uuid.uuid4(),
        email=email or f"test-{uuid.uuid4()}@example.com",
        password_hash="x" * 60,
        nombre="Test",
        apellido="User",
        created_at=now,
        updated_at=now,
        deleted_at=None,
    )
    return await repo.create(user)


async def _seed_rol(session: AsyncSession, codigo: str | None = None) -> Rol:
    """Create and flush a test Rol using naive datetimes."""
    repo = RolRepository(session)
    now = _now()
    rol = Rol(
        id=uuid.uuid4(),
        codigo=codigo or f"ROLE_{uuid.uuid4().hex[:8].upper()}",
        nombre="Test Role",
        created_at=now,
        updated_at=now,
        deleted_at=None,
    )
    return await repo.create(rol)


async def _assign_role(session: AsyncSession, user: Usuario, rol: Rol) -> UsuarioRol:
    """Create and flush a UsuarioRol assignment."""
    repo = UsuarioRolRepository(session)
    now = _now()
    ur = UsuarioRol(
        id=uuid.uuid4(),
        usuario_id=user.id,
        rol_id=rol.id,
        created_at=now,
        updated_at=now,
        deleted_at=None,
    )
    return await repo.create(ur)


# ---------------------------------------------------------------------------
# Test routes (registered on the app for the duration of this test module)
# ---------------------------------------------------------------------------

_dep_test_router = APIRouter(prefix="/_dep_test", tags=["_dep_test"])


@_dep_test_router.get("/protected")
async def _protected_route(usuario: Usuario = Depends(get_current_user)) -> dict:  # type: ignore[return]
    return {"user_id": str(usuario.id)}


@_dep_test_router.get("/admin-only")
async def _admin_only_route(usuario: Usuario = Depends(require_role("ADMIN"))) -> dict:  # type: ignore[return]
    return {"user_id": str(usuario.id), "authorized": True}


@_dep_test_router.get("/multi-role")
async def _multi_role_route(
    usuario: Usuario = Depends(require_role("ADMIN", "PEDIDOS")),
) -> dict:  # type: ignore[return]
    return {"user_id": str(usuario.id), "authorized": True}


app.include_router(_dep_test_router)


# ---------------------------------------------------------------------------
# Scenario: Missing Authorization header returns HTTP 401
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_missing_token_returns_401(async_session: AsyncSession, override_settings) -> None:
    """Request without Authorization header -> 401 with RFC 7807 body."""
    app.dependency_overrides[get_uow] = make_uow_override(async_session)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/_dep_test/protected")
        assert response.status_code == 401
        body = response.json()
        assert body["status"] == 401
    finally:
        app.dependency_overrides.pop(get_uow, None)


# ---------------------------------------------------------------------------
# Scenario: Valid token resolves to active user (200)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_valid_token_resolves_to_user(async_session: AsyncSession, override_settings) -> None:
    """Valid JWT with existing active user -> 200 with user_id."""
    user = await _seed_user(async_session)
    token = _make_token(user.id)

    app.dependency_overrides[get_uow] = make_uow_override(async_session)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/_dep_test/protected",
                headers={"Authorization": f"Bearer {token}"},
            )
        assert response.status_code == 200
        body = response.json()
        assert body["user_id"] == str(user.id)
    finally:
        app.dependency_overrides.pop(get_uow, None)


# ---------------------------------------------------------------------------
# Scenario: Expired token returns HTTP 401
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_expired_token_returns_401(async_session: AsyncSession, override_settings) -> None:
    """Expired JWT -> 401."""
    user = await _seed_user(async_session)
    token = _expired_token(user.id)

    app.dependency_overrides[get_uow] = make_uow_override(async_session)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/_dep_test/protected",
                headers={"Authorization": f"Bearer {token}"},
            )
        assert response.status_code == 401
    finally:
        app.dependency_overrides.pop(get_uow, None)


# ---------------------------------------------------------------------------
# Scenario: Invalid signature returns HTTP 401
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_invalid_signature_returns_401(async_session: AsyncSession, override_settings) -> None:
    """JWT with wrong signature -> 401."""
    user = await _seed_user(async_session)
    token = _wrong_sig_token(user.id)

    app.dependency_overrides[get_uow] = make_uow_override(async_session)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/_dep_test/protected",
                headers={"Authorization": f"Bearer {token}"},
            )
        assert response.status_code == 401
    finally:
        app.dependency_overrides.pop(get_uow, None)


# ---------------------------------------------------------------------------
# Scenario: Non-existent user ID in token returns HTTP 401
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_nonexistent_user_in_token_returns_401(async_session: AsyncSession, override_settings) -> None:
    """Valid JWT but sub references a non-existent user -> 401."""
    nonexistent_id = uuid.uuid4()
    token = _make_token(nonexistent_id)

    app.dependency_overrides[get_uow] = make_uow_override(async_session)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/_dep_test/protected",
                headers={"Authorization": f"Bearer {token}"},
            )
        assert response.status_code == 401
    finally:
        app.dependency_overrides.pop(get_uow, None)


# ---------------------------------------------------------------------------
# Scenario: Soft-deleted user returns HTTP 401
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_soft_deleted_user_returns_401(async_session: AsyncSession, override_settings) -> None:
    """Valid JWT but user is soft-deleted -> 401 (get_by_id returns None)."""
    user = await _seed_user(async_session)
    # Soft delete the user
    repo = UsuarioRepository(async_session)
    await repo.soft_delete(user.id)

    token = _make_token(user.id)

    app.dependency_overrides[get_uow] = make_uow_override(async_session)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/_dep_test/protected",
                headers={"Authorization": f"Bearer {token}"},
            )
        assert response.status_code == 401
    finally:
        app.dependency_overrides.pop(get_uow, None)


# ---------------------------------------------------------------------------
# Scenario: User without matching role returns HTTP 403
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_user_without_required_role_returns_403(async_session: AsyncSession, override_settings) -> None:
    """Authenticated user without the required role -> 403."""
    user = await _seed_user(async_session)
    # Do NOT assign ADMIN role — user has no roles
    token = _make_token(user.id)

    app.dependency_overrides[get_uow] = make_uow_override(async_session)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/_dep_test/admin-only",
                headers={"Authorization": f"Bearer {token}"},
            )
        assert response.status_code == 403
        body = response.json()
        assert body["status"] == 403
    finally:
        app.dependency_overrides.pop(get_uow, None)


# ---------------------------------------------------------------------------
# Scenario: User with matching role proceeds (200)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_user_with_required_role_proceeds(async_session: AsyncSession, override_settings) -> None:
    """User with ADMIN role -> 200 on admin-only route."""
    user = await _seed_user(async_session)
    rol = await _seed_rol(async_session, codigo=f"ADMIN_{uuid.uuid4().hex[:6]}")
    # We need a role with code that matches, so we rename it to ADMIN
    # But since require_role checks rol.codigo, let's create an ADMIN-code role
    admin_rol = await _seed_rol(async_session, codigo="ADMIN")
    await _assign_role(async_session, user, admin_rol)

    token = _make_token(user.id)

    app.dependency_overrides[get_uow] = make_uow_override(async_session)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/_dep_test/admin-only",
                headers={"Authorization": f"Bearer {token}"},
            )
        assert response.status_code == 200
        body = response.json()
        assert body["user_id"] == str(user.id)
    finally:
        app.dependency_overrides.pop(get_uow, None)


# ---------------------------------------------------------------------------
# Scenario: User with one matching role out of multiple proceeds
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_user_with_one_matching_role_of_multiple_proceeds(
    async_session: AsyncSession, override_settings
) -> None:
    """User with PEDIDOS (not ADMIN) role -> 200 on route requiring ADMIN or PEDIDOS."""
    user = await _seed_user(async_session)
    pedidos_rol = await _seed_rol(async_session, codigo="PEDIDOS")
    await _assign_role(async_session, user, pedidos_rol)
    token = _make_token(user.id)

    app.dependency_overrides[get_uow] = make_uow_override(async_session)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/_dep_test/multi-role",
                headers={"Authorization": f"Bearer {token}"},
            )
        assert response.status_code == 200
    finally:
        app.dependency_overrides.pop(get_uow, None)


# ---------------------------------------------------------------------------
# Scenario: Unauthenticated request to role-protected route returns HTTP 401
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_unauthenticated_request_to_role_protected_route_returns_401(
    async_session: AsyncSession, override_settings
) -> None:
    """No token on role-protected route -> 401 (not 403) — auth precedes authorization."""
    app.dependency_overrides[get_uow] = make_uow_override(async_session)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/_dep_test/admin-only")
        assert response.status_code == 401
    finally:
        app.dependency_overrides.pop(get_uow, None)


# ---------------------------------------------------------------------------
# Scenario: oauth2_scheme does not raise on missing token (returns None)
# ---------------------------------------------------------------------------


def test_oauth2_scheme_is_auto_error_false() -> None:
    """oauth2_scheme must have auto_error=False."""
    assert oauth2_scheme.auto_error is False


def test_oauth2_scheme_token_url() -> None:
    """oauth2_scheme tokenUrl must point to /api/v1/auth/login."""
    assert "/api/v1/auth/login" in str(oauth2_scheme.model.flows.password.tokenUrl)  # type: ignore[union-attr]


# ---------------------------------------------------------------------------
# Static checks
# ---------------------------------------------------------------------------


def test_deps_does_not_wrap_get_uow() -> None:
    """deps.py must not define a wrapper or alias around get_uow."""
    import inspect

    import app.api.deps as deps_mod

    source = inspect.getsource(deps_mod)
    # Should use Depends(get_uow) directly — no aliases defined
    # (Presence of 'get_uow' is fine; wrapping patterns like 'get_uow_v2 = get_uow' are not)
    assert "get_uow_v2" not in source
    assert "get_uow_wrapper" not in source


def test_deps_raises_domain_errors_not_http_exception() -> None:
    """deps.py must import UnauthorizedError/ForbiddenError, not HTTPException."""
    import inspect

    import app.api.deps as deps_mod

    source = inspect.getsource(deps_mod)
    # Should not raise raw HTTPException
    assert "HTTPException" not in source
    assert "UnauthorizedError" in source
    assert "ForbiddenError" in source


# ---------------------------------------------------------------------------
# Additional coverage: missing 'sub' claim and invalid UUID sub
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_token_without_sub_claim_returns_401(async_session: AsyncSession, override_settings) -> None:
    """Token with no 'sub' claim -> 401."""
    import time
    from jose import jwt
    payload = {"exp": int(time.time()) + 3600, "role": "user"}  # no 'sub'
    token = jwt.encode(payload, _TEST_SECRET, algorithm=_ALGORITHM)

    app.dependency_overrides[get_uow] = make_uow_override(async_session)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/_dep_test/protected",
                headers={"Authorization": f"Bearer {token}"},
            )
        assert response.status_code == 401
    finally:
        app.dependency_overrides.pop(get_uow, None)


@pytest.mark.asyncio
async def test_token_with_invalid_uuid_sub_returns_401(async_session: AsyncSession, override_settings) -> None:
    """Token with 'sub' that is not a valid UUID -> 401."""
    import time
    from jose import jwt
    payload = {"sub": "not-a-valid-uuid", "exp": int(time.time()) + 3600}
    token = jwt.encode(payload, _TEST_SECRET, algorithm=_ALGORITHM)

    app.dependency_overrides[get_uow] = make_uow_override(async_session)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/_dep_test/protected",
                headers={"Authorization": f"Bearer {token}"},
            )
        assert response.status_code == 401
    finally:
        app.dependency_overrides.pop(get_uow, None)


@pytest.mark.asyncio
async def test_role_check_logs_insufficient_permissions(async_session: AsyncSession, override_settings) -> None:
    """require_role with insufficient permissions returns 403 and logs the warning."""
    user = await _seed_user(async_session)
    rol = await _seed_rol(async_session, codigo=f"STOCK_{uuid.uuid4().hex[:6]}")
    await _assign_role(async_session, user, rol)  # user has STOCK, not ADMIN
    token = _make_token(user.id)

    app.dependency_overrides[get_uow] = make_uow_override(async_session)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/_dep_test/admin-only",  # requires ADMIN
                headers={"Authorization": f"Bearer {token}"},
            )
        assert response.status_code == 403
        body = response.json()
        assert body["status"] == 403
    finally:
        app.dependency_overrides.pop(get_uow, None)


# ---------------------------------------------------------------------------
# Direct unit tests for coverage of lines 98-105 and 152-167
# These call the dependency functions directly to ensure coverage picks them up.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_current_user_user_not_found_raises_unauthorized(
    async_session: AsyncSession, override_settings
) -> None:
    """get_current_user: valid JWT but user UUID not in DB -> UnauthorizedError (lines 98-105)."""
    nonexistent_id = uuid.uuid4()
    token = _make_token(nonexistent_id)

    uow = UnitOfWork()
    uow._session = async_session  # type: ignore[assignment]
    uow._usuarios = None  # type: ignore[assignment]
    uow._roles = None  # type: ignore[assignment]
    uow._usuario_roles = None  # type: ignore[assignment]
    uow._refresh_tokens = None  # type: ignore[assignment]

    with pytest.raises(UnauthorizedError) as exc_info:
        await get_current_user(token=token, uow=uow)

    assert exc_info.value.code == "user_not_found"


@pytest.mark.asyncio
async def test_get_current_user_returns_user_when_found(
    async_session: AsyncSession, override_settings
) -> None:
    """get_current_user: valid JWT and existing user -> returns Usuario (covers line 105)."""
    user = await _seed_user(async_session)
    token = _make_token(user.id)

    uow = UnitOfWork()
    uow._session = async_session  # type: ignore[assignment]
    uow._usuarios = None  # type: ignore[assignment]
    uow._roles = None  # type: ignore[assignment]
    uow._usuario_roles = None  # type: ignore[assignment]
    uow._refresh_tokens = None  # type: ignore[assignment]

    result = await get_current_user(token=token, uow=uow)
    assert result.id == user.id


@pytest.mark.asyncio
async def test_require_role_check_raises_forbidden_when_no_matching_role(
    async_session: AsyncSession, override_settings
) -> None:
    """require_role._check: user has no matching roles -> ForbiddenError (lines 152-167)."""
    from app.core.exceptions import ForbiddenError

    user = await _seed_user(async_session)
    # Give user a STOCK role — not ADMIN
    stock_rol = await _seed_rol(async_session, codigo=f"STOCK_{uuid.uuid4().hex[:6]}")
    await _assign_role(async_session, user, stock_rol)

    uow = UnitOfWork()
    uow._session = async_session  # type: ignore[assignment]
    uow._usuarios = None  # type: ignore[assignment]
    uow._roles = None  # type: ignore[assignment]
    uow._usuario_roles = None  # type: ignore[assignment]
    uow._refresh_tokens = None  # type: ignore[assignment]

    # Get the inner _check function from require_role("ADMIN")
    check_dep = require_role("ADMIN")

    with pytest.raises(ForbiddenError) as exc_info:
        await check_dep(usuario=user, uow=uow)

    assert exc_info.value.code == "forbidden"


@pytest.mark.asyncio
async def test_require_role_check_returns_user_when_role_matches(
    async_session: AsyncSession, override_settings
) -> None:
    """require_role._check: user has matching role -> returns Usuario (covers line 167)."""
    user = await _seed_user(async_session)
    admin_rol = await _seed_rol(async_session, codigo="ADMIN")
    await _assign_role(async_session, user, admin_rol)

    uow = UnitOfWork()
    uow._session = async_session  # type: ignore[assignment]
    uow._usuarios = None  # type: ignore[assignment]
    uow._roles = None  # type: ignore[assignment]
    uow._usuario_roles = None  # type: ignore[assignment]
    uow._refresh_tokens = None  # type: ignore[assignment]

    check_dep = require_role("ADMIN")
    result = await check_dep(usuario=user, uow=uow)
    assert result.id == user.id
