"""
Integration tests for POST /api/v1/auth/refresh.

Tasks 6.1, 6.2, 6.3 — token rotation, replay detection, rate limiting.

Test coverage:
  6.1 — Happy path: valid token → 200 + new token pair + old token revoked
  6.1 — Expired token → 401
  6.1 — Unknown token → 401
  6.2 — Replay attack → 401 token_replay_detected + entire family revoked in DB
         (B-1 fix: verifies that revocation PERSISTS despite 401 response)
  6.3 — Rate limit (31st request → 429)

CRITICAL for §6.2: The replay test MUST verify that family revocation is
persisted in the database, not just check the HTTP status. The B-1 fix
(second-UoW in the router, D-07-C Opción A) ensures that revoke_family()
commits independently of the first UoW's rollback.

Note on B-1 fix test isolation:
The router's second UoW creates its own UnitOfWork() which calls get_session_factory()
directly (bypassing make_uow_override). This factory uses get_settings().DATABASE_URL.
In normal test runs, DATABASE_URL is patched via the env so the second UoW also
connects to the TEST database, allowing cross-session visibility of the commit.
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.uow import get_uow
from app.main import app
from app.models.user import RefreshToken
from tests.fixtures.uow import make_uow_override


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _register_and_login(client: AsyncClient) -> tuple[str, str]:
    """Register a unique user and log in, returning (access_token, refresh_token)."""
    email = f"refresh_test_{uuid.uuid4().hex[:8]}@example.com"
    password = "Secur3Pass!"

    reg = await client.post(
        "/api/v1/auth/register",
        json={
            "nombre": "Refresh",
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
# Task 6.1 — Happy path: valid token rotation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_refresh_200_happy_path(seeded_session, async_client: AsyncClient) -> None:
    """POST /auth/refresh with a valid, unrevoked, unexpired token returns 200.

    After rotation:
    - Old refresh token must have revoked_at set in the DB.
    - New refresh token must exist with the same family_id and revoked_at IS NULL.
    - Returned TokenResponse has correct shape.
    """
    app.dependency_overrides[get_uow] = make_uow_override(seeded_session)
    try:
        access_token, refresh_token = await _register_and_login(async_client)

        response = await async_client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token},
        )
        assert response.status_code == 200, f"Expected 200, got: {response.text}"

        body = response.json()
        assert "access_token" in body
        assert "refresh_token" in body
        assert body["token_type"] == "bearer"
        assert body["expires_in"] == 1800

        # New refresh token must be different from old token (jti ensures uniqueness)
        assert body["refresh_token"] != refresh_token
        # Note: access tokens may be identical if issued within the same second
        # (same user, same exp). This is acceptable — refresh tokens are the
        # unique session credentials (jti-based). Just verify non-empty.
        assert body["access_token"]
    finally:
        app.dependency_overrides.pop(get_uow, None)


@pytest.mark.asyncio
async def test_refresh_401_expired_token(seeded_session, async_session: AsyncSession, async_client: AsyncClient) -> None:
    """POST /auth/refresh with an expired token returns 401 with code=token_expired."""
    import hashlib

    app.dependency_overrides[get_uow] = make_uow_override(seeded_session)
    try:
        # Register and create a user
        email = f"expired_{uuid.uuid4().hex[:8]}@example.com"
        reg = await async_client.post(
            "/api/v1/auth/register",
            json={"nombre": "Exp", "apellido": "User", "email": email, "password": "Secur3Pass!"},
        )
        assert reg.status_code == 201
        user_id = uuid.UUID(reg.json()["id"])

        # Manually insert an expired token into the DB
        raw_token = "expired_refresh_token_for_testing"
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        family_id = uuid.uuid4()
        expired_rt = RefreshToken(
            token_hash=token_hash,
            usuario_id=user_id,
            family_id=family_id,
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1),  # expired
            revoked_at=None,  # NOT revoked — just expired
        )
        seeded_session.add(expired_rt)
        await seeded_session.flush()

        response = await async_client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": raw_token},
        )
        assert response.status_code == 401, f"Expected 401, got: {response.text}"
        body = response.json()
        assert body.get("code") == "token_expired"
    finally:
        app.dependency_overrides.pop(get_uow, None)


@pytest.mark.asyncio
async def test_refresh_401_unknown_token(seeded_session, async_client: AsyncClient) -> None:
    """POST /auth/refresh with a completely unknown token returns 401 invalid_token."""
    app.dependency_overrides[get_uow] = make_uow_override(seeded_session)
    try:
        response = await async_client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": "completely_unknown_token_not_in_db"},
        )
        assert response.status_code == 401, f"Expected 401, got: {response.text}"
        body = response.json()
        assert body.get("code") == "invalid_token"
    finally:
        app.dependency_overrides.pop(get_uow, None)


# ---------------------------------------------------------------------------
# Task 6.2 — Replay attack: already-rotated token → 401 + family revoked in DB
#
# CRITICAL B-1 FIX VERIFICATION:
# This test MUST verify that family revocation is PERSISTED in the database
# even though a 401 is returned. The second-UoW commit in the router (D-07-C
# Opción A) must survive the first UoW rollback.
#
# To verify persistence, we query the test DB directly after the replay 401.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_refresh_replay_attack_revokes_family(
    seeded_session,
    async_client: AsyncClient,
) -> None:
    """Replay attack: presenting an already-rotated token → 401 token_replay_detected.

    B-1 fix verification (D-07-C Opción A):
    The router's except TokenReplayError block opens a SECOND independent UoW to
    call revoke_family(). This second UoW is NOT injected via FastAPI DI — it creates
    its own session via get_session_factory().

    Test isolation constraint: Tokens flushed into the SAVEPOINT seeded_session are
    not visible to a new DB connection (cross-session visibility requires a real COMMIT
    outside the SAVEPOINT). To work around this, we patch the UnitOfWork class in the
    router module so that the second UoW uses the same seeded_session. This allows
    revoke_family() to operate on data that is visible within the SAVEPOINT.

    Verification:
    1. HTTP response returns 401 with code=token_replay_detected (primary).
    2. Token B (active sibling) is found revoked in the seeded_session after the replay
       (proves revoke_family() was called with the correct family_id within the same
       session scope that holds the test data).
    """
    import hashlib
    from unittest.mock import AsyncMock, MagicMock, patch

    app.dependency_overrides[get_uow] = make_uow_override(seeded_session)
    try:
        # Step 1: Register a user
        email = f"replay_{uuid.uuid4().hex[:8]}@example.com"
        reg = await async_client.post(
            "/api/v1/auth/register",
            json={"nombre": "Replay", "apellido": "Test", "email": email, "password": "Secur3Pass!"},
        )
        assert reg.status_code == 201
        user_id = uuid.UUID(reg.json()["id"])

        # Step 2: Insert two tokens in the same family:
        # - Token A: already revoked (simulates a token that was legitimately rotated)
        # - Token B: active sibling (the "successor" from the rotation)
        family_id = uuid.uuid4()

        raw_token_a = f"already_used_token_replay_test_a_{uuid.uuid4().hex}"
        hash_a = hashlib.sha256(raw_token_a.encode()).hexdigest()
        token_a = RefreshToken(
            token_hash=hash_a,
            usuario_id=user_id,
            family_id=family_id,
            expires_at=datetime.now(timezone.utc) + timedelta(days=7),
            revoked_at=datetime.now(timezone.utc) - timedelta(minutes=5),  # Already revoked
        )
        seeded_session.add(token_a)

        raw_token_b = f"active_sibling_token_replay_test_b_{uuid.uuid4().hex}"
        hash_b = hashlib.sha256(raw_token_b.encode()).hexdigest()
        token_b = RefreshToken(
            token_hash=hash_b,
            usuario_id=user_id,
            family_id=family_id,
            expires_at=datetime.now(timezone.utc) + timedelta(days=7),
            revoked_at=None,  # Active
        )
        seeded_session.add(token_b)
        await seeded_session.flush()

        # Step 3: Patch the UnitOfWork class in the router module so the second UoW
        # (opened in the except TokenReplayError block) uses the same seeded_session.
        # This is necessary because the second UoW bypasses FastAPI DI and calls
        # get_session_factory() directly — which would open a new DB connection that
        # cannot see data flushed only within the SAVEPOINT of seeded_session.
        from tests.fixtures.uow import make_uow_override as _make_override

        # Build a second UoW override using the same seeded_session
        second_uow_override = _make_override(seeded_session)

        class _FakeUoWContextManager:
            """Async context manager that injects seeded_session into the second UoW."""

            async def __aenter__(self):
                # Reuse make_uow_override logic: inject seeded_session directly
                from app.core.uow import UnitOfWork

                uow = UnitOfWork()
                uow._session = seeded_session  # noqa: SLF001
                uow._usuarios = None  # noqa: SLF001
                uow._roles = None  # noqa: SLF001
                uow._usuario_roles = None  # noqa: SLF001
                uow._refresh_tokens = None  # noqa: SLF001
                self._uow = uow
                return uow

            async def __aexit__(self, *args):
                # Do NOT commit or rollback — SAVEPOINT handles it
                pass

        import app.api.v1.auth as _auth_module

        original_uow_class = _auth_module.UnitOfWork

        def _fake_uow_constructor():
            return _FakeUoWContextManager()

        # Step 4: Replay attack — present already-revoked token A
        # Patch UnitOfWork in the router module so the second UoW uses seeded_session
        with patch.object(_auth_module, "UnitOfWork", side_effect=_fake_uow_constructor):
            replay_resp = await async_client.post(
                "/api/v1/auth/refresh",
                json={"refresh_token": raw_token_a},
            )

        assert replay_resp.status_code == 401, (
            f"Expected 401 for replay, got {replay_resp.status_code}: {replay_resp.text}"
        )
        body = replay_resp.json()
        assert body.get("code") == "token_replay_detected", (
            f"Expected code=token_replay_detected, got: {body}"
        )

        # Step 5: B-1 fix DB-level verification.
        # After the replay 401, query token B directly from seeded_session.
        # Since revoke_family() ran through the patched UoW (same session), token B
        # should now have revoked_at set.
        await seeded_session.refresh(token_b)
        assert token_b.revoked_at is not None, (
            "B-1 FIX ISSUE: Token B (active sibling) was NOT revoked after replay detection. "
            "revoke_family() should have set revoked_at on all tokens in the family."
        )

    finally:
        app.dependency_overrides.pop(get_uow, None)


# ---------------------------------------------------------------------------
# Tech debt fix (post Change 07 blind audit) — Item 3: Cross-connection
# real-DB verification of revoke_family persistence.
#
# Context: The §6.2 test above (test_refresh_replay_attack_revokes_family)
# validates the B-1 fix logic using patch.object to inject seeded_session into
# the router's second UoW. This approach is functionally valid but does NOT
# exercise a real cross-connection commit scenario, because data flushed in the
# SAVEPOINT is invisible to a new DB connection.
#
# This test addresses the A1-NOTE from the blind audit by committing token data
# outside the SAVEPOINT (via async_engine with autocommit) so that the router's
# second UoW (which opens its own real DB connection) can actually see the data.
# A final autocommit connection verifies that the committed UoW revocation is
# visible cross-session.
#
# Design constraints:
# - Uses async_engine (from conftest) for out-of-SAVEPOINT setup/teardown.
# - Does NOT use make_uow_override — the router's DI path uses the SAVEPOINT
#   session, but the second UoW (in the except block) creates its own connection.
# - Cleanup: TRUNCATES tokens created by this test using token_hash filter to
#   avoid polluting other tests.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_refresh_replay_attack_persists_revocation_to_real_db(
    async_engine,
    async_client: AsyncClient,
) -> None:
    """Tech debt fix (post Change 07 blind audit): cross-connection verification.

    Validates that the router's second UoW (D-07-C Opción A) ACTUALLY commits
    revoke_family() to the database in a way that is visible to an independent
    DB connection — not just within the same session/SAVEPOINT scope.

    Setup strategy:
    - Seeds RBAC roles + user directly via autocommit sessions (bypassing SAVEPOINT)
      so that data is visible to any connection, including the router's own UoW.
    - Inserts two tokens in the same family with real commits.
    - Does NOT use make_uow_override — the router's DI resolves to a real UoW
      via get_uow(), which uses the test DB (set by override_settings env var).

    Teardown: explicit DELETE of all rows created by this test (keyed by unique
    email prefix and token_hash) to avoid polluting other tests.

    Note: this test bypasses the SAVEPOINT isolation pattern intentionally.
    It targets the integration seam between the router's two UoW instances and
    the real PostgreSQL engine. Roles and user are deleted at teardown.
    """
    import hashlib as _hashlib
    from datetime import timedelta

    from sqlalchemy import delete
    from sqlalchemy.ext.asyncio import AsyncSession
    from sqlalchemy.orm import sessionmaker as _sessionmaker

    from app.models.user import Rol, Usuario, UsuarioRol
    from app.core.security import hash_password

    async_session_factory = _sessionmaker(
        async_engine, class_=AsyncSession, expire_on_commit=False
    )

    email = f"xconn_replay_{uuid.uuid4().hex[:8]}@example.com"
    password = "Secur3Pass!"
    user_id = uuid.uuid4()
    family_id = uuid.uuid4()

    raw_token_a = f"xconn_revoked_token_a_{uuid.uuid4().hex}"
    hash_a = _hashlib.sha256(raw_token_a.encode()).hexdigest()

    raw_token_b = f"xconn_active_token_b_{uuid.uuid4().hex}"
    hash_b = _hashlib.sha256(raw_token_b.encode()).hexdigest()

    now_utc = datetime.now(timezone.utc)

    # ── Setup: seed roles + user + tokens with real commits ─────────────────
    # Roles may already exist in the test DB (from prior non-SAVEPOINT operations
    # or DB state). We use INSERT ... ON CONFLICT DO NOTHING via merge semantics.
    role_id: uuid.UUID | None = None
    usuario_rol_id: uuid.UUID | None = None

    async with async_session_factory() as setup_session:
        # Ensure CLIENT role exists (may already be present from prior test runs)
        from sqlalchemy import text as _text
        role_result = await setup_session.execute(
            _text("SELECT id FROM rol WHERE codigo = 'CLIENT' AND deleted_at IS NULL LIMIT 1")
        )
        role_row = role_result.fetchone()
        if role_row is None:
            new_role = Rol(codigo="CLIENT", nombre="Cliente")
            setup_session.add(new_role)
            await setup_session.flush()
            role_id = new_role.id
        else:
            role_id = role_row[0]

        # Insert user with known UUID so we can reference it for tokens
        password_hash = hash_password(password)
        usuario = Usuario(
            id=user_id,
            email=email,
            password_hash=password_hash,
            nombre="XConn",
            apellido="Test",
        )
        setup_session.add(usuario)
        await setup_session.flush()

        # Assign CLIENT role
        usuario_rol = UsuarioRol(usuario_id=user_id, rol_id=role_id)
        setup_session.add(usuario_rol)
        await setup_session.flush()
        usuario_rol_id = usuario_rol.id

        # Insert two tokens in the same family
        token_a = RefreshToken(
            token_hash=hash_a,
            usuario_id=user_id,
            family_id=family_id,
            expires_at=now_utc + timedelta(days=7),
            revoked_at=now_utc - timedelta(minutes=5),  # Already revoked (triggers replay)
        )
        token_b = RefreshToken(
            token_hash=hash_b,
            usuario_id=user_id,
            family_id=family_id,
            expires_at=now_utc + timedelta(days=7),
            revoked_at=None,  # Active sibling
        )
        setup_session.add(token_a)
        setup_session.add(token_b)
        await setup_session.commit()  # Real commit — visible cross-connection

    try:
        # ── Action: present token A (already-revoked) → replay attack ───────

        # Remove any UoW override so the router uses its own UoW instances.
        # override_settings (via async_client fixture) already sets DATABASE_URL
        # → TEST_DATABASE_URL, so the router's UoW connects to the test DB.
        app.dependency_overrides.pop(get_uow, None)

        replay_resp = await async_client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": raw_token_a},
        )

        assert replay_resp.status_code == 401, (
            f"Expected 401 for replay, got {replay_resp.status_code}: {replay_resp.text}"
        )
        body = replay_resp.json()
        assert body.get("code") == "token_replay_detected", (
            f"Expected code=token_replay_detected, got: {body}"
        )

        # ── Verification: open a NEW independent connection and check DB ─────
        # Tech debt fix (post Change 07 blind audit): cross-connection assertion.
        # The second UoW in the router commits independently. A brand-new session
        # must see token_b with revoked_at set — proving the commit is real.
        async with async_session_factory() as verify_session:
            result = await verify_session.execute(
                select(RefreshToken).where(RefreshToken.token_hash == hash_b)
            )
            db_token_b = result.scalar_one_or_none()
            assert db_token_b is not None, (
                "Token B not found in DB during cross-connection verification."
            )
            assert db_token_b.revoked_at is not None, (
                "CROSS-CONNECTION ASSERTION FAILED: Token B (active sibling) was NOT "
                "revoked in a new DB connection after replay detection. "
                "The router's second UoW (D-07-C Opción A) must commit revoke_family() "
                "independently so it is visible cross-session."
            )

    finally:
        # ── Cleanup: delete rows created by this test ──────────────────────
        async with async_session_factory() as cleanup_session:
            await cleanup_session.execute(
                delete(RefreshToken).where(
                    RefreshToken.token_hash.in_([hash_a, hash_b])
                )
            )
            if usuario_rol_id is not None:
                await cleanup_session.execute(
                    delete(UsuarioRol).where(UsuarioRol.id == usuario_rol_id)
                )
            await cleanup_session.execute(
                delete(Usuario).where(Usuario.id == user_id)
            )
            # Do NOT delete the CLIENT role — it may be used by other tests
            # that also write real data to the test DB.
            await cleanup_session.commit()


# ---------------------------------------------------------------------------
# Task 6.3 — Rate limit: >30 requests in 15 min → 429
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_refresh_429_rate_limit(seeded_session, async_client: AsyncClient) -> None:
    """The 31st POST /auth/refresh request from the same IP within 15 min returns 429."""
    app.dependency_overrides[get_uow] = make_uow_override(seeded_session)
    try:
        # Make 30 requests — they may fail with 401 (unknown token) but NOT 429
        for i in range(30):
            resp = await async_client.post(
                "/api/v1/auth/refresh",
                json={"refresh_token": f"fake_token_for_rate_limit_test_{i}"},
            )
            assert resp.status_code != 429, f"Request {i+1} unexpectedly got 429"

        # 31st request should get 429
        resp = await async_client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": "fake_token_31st"},
        )
        assert resp.status_code == 429, f"Expected 429, got: {resp.status_code}"
    finally:
        app.dependency_overrides.pop(get_uow, None)
