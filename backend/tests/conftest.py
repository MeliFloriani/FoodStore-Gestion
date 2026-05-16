"""
Pytest fixtures for the backend test suite.

Design decisions:
- D-16 / P-03: override_settings fixture clears ALL four lru_cache getters
  (get_settings, get_engine, get_session_factory, get_limiter) before AND after
  the override. Without this, cached instances from prior tests bleed through.
- P-05: async_client uses ASGITransport(app=app) — the deprecated AsyncClient(app=...)
  form is not used.
- test_db_session provides an isolated AsyncSession per test via rollback teardown.
- Change 04 additions (§9):
  - async_engine: function-scoped engine for integration tests.
  - async_connection: wraps engine in engine.begin() for SAVEPOINT isolation.
  - async_session: creates AsyncSession inside begin_nested() (SAVEPOINT).
  - cache_clear (autouse): prevents lru_cache pollution between tests (MED-05).
  See backend/tests/README.md for the full SAVEPOINT pattern explanation.
"""

from __future__ import annotations

import os

import pytest
import pytest_asyncio
from dotenv import load_dotenv

# Load .env so TEST_DATABASE_URL and SECRET_KEY are available in os.environ
# (mirrors the pattern in test_migrations.py — load_dotenv does not override already-set vars)
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncConnection,
    AsyncEngine,
    AsyncSession,
    create_async_engine,
)
from sqlalchemy.orm import sessionmaker

from app.core.config import Settings, get_settings
from app.core.rate_limit import get_limiter
from app.db.session import get_engine, get_session_factory
from app.main import app


# ---------------------------------------------------------------------------
# lru_cache pollution guard (autouse — runs before and after EVERY test)
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def cache_clear() -> None:  # type: ignore[return]
    """Clear all lru_cache singletons before and after each test.

    Prevents cached Settings, engine, session factory, and rate limiter instances
    from one test bleeding into another (addresses MED-05 / D-16 / P-03).

    Rate limiter storage reset: slowapi's MemoryStorage accumulates hits across
    tests when the module-level `_limiter` in auth.py holds onto the same
    Limiter instance. We reset the storage directly so rate-limit integration
    tests start from a clean slate on every test run.
    """
    get_settings.cache_clear()
    get_engine.cache_clear()
    get_session_factory.cache_clear()
    get_limiter.cache_clear()
    # Reset in-memory rate limit counters so tests don't bleed into each other.
    # Import lazily to avoid triggering Settings at collection time.
    try:
        from app.api.v1.auth import _limiter as auth_limiter
        auth_limiter._storage.reset()
    except Exception:
        pass
    yield
    get_settings.cache_clear()
    get_engine.cache_clear()
    get_session_factory.cache_clear()
    get_limiter.cache_clear()
    try:
        from app.api.v1.auth import _limiter as auth_limiter
        auth_limiter._storage.reset()
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Settings override — clears all lazy caches before and after
# ---------------------------------------------------------------------------


@pytest.fixture
def override_settings() -> None:  # type: ignore[return]
    """Override Settings with test database URL for the duration of a test.

    Protocol (P-03 / D-16):
    1. Clear all four lru_cache singletons BEFORE setting overrides.
    2. Register dependency override so FastAPI Depends(get_settings) returns test settings.
    3. Yield (test runs).
    4. Clear dependency overrides.
    5. Clear all four lru_cache singletons AFTER clearing overrides.

    This ensures no cached state leaks between tests.
    """

    def _override() -> Settings:
        return Settings(
            DATABASE_URL=os.environ["TEST_DATABASE_URL"],
            SECRET_KEY="test-secret-key-for-unit-tests-only-32-chars-minimum",
            ENVIRONMENT="test",
            BACKEND_CORS_ORIGINS=["http://localhost:5173"],
            API_V1_PREFIX="/api/v1",
            LOG_LEVEL="WARNING",
            RATE_LIMIT_DEFAULT="1000/minute",
        )

    # Clear before — ensure stale cached singletons don't linger
    get_settings.cache_clear()
    get_engine.cache_clear()
    get_session_factory.cache_clear()
    get_limiter.cache_clear()

    app.dependency_overrides[get_settings] = _override

    yield

    # Teardown — clear overrides and caches
    app.dependency_overrides.clear()
    get_settings.cache_clear()
    get_engine.cache_clear()
    get_session_factory.cache_clear()
    get_limiter.cache_clear()


# ---------------------------------------------------------------------------
# Async HTTP client
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def async_client(override_settings):  # type: ignore[return]
    """AsyncClient that speaks ASGI directly to the app.

    Uses ASGITransport — the deprecated AsyncClient(app=...) form is not used (P-05).
    Depends on override_settings so the test database is used for every request.
    """
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client


# ---------------------------------------------------------------------------
# Isolated database session for unit-style DB tests (legacy — kept for Change 02)
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def test_db_session(override_settings):  # type: ignore[return]
    """AsyncSession connected to the test database, rolled back after each test.

    Provides test isolation: changes made within a test are never committed.
    """
    test_url = os.environ["TEST_DATABASE_URL"]
    engine = create_async_engine(test_url, echo=False)
    async_session_factory = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    async with async_session_factory() as session:
        yield session
        await session.rollback()

    await engine.dispose()


# ---------------------------------------------------------------------------
# SAVEPOINT-based fixtures for repository / UoW / deps integration tests
# (Change 04 — §9.1)
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def async_engine(override_settings) -> AsyncGenerator[AsyncEngine, None]:  # type: ignore[return]
    """Function-scoped async engine connected to the test database.

    Uses TEST_DATABASE_URL from the environment. Disposed after each test.
    """
    test_url = os.environ["TEST_DATABASE_URL"]
    engine = create_async_engine(test_url, echo=False)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def async_connection(async_engine: AsyncEngine) -> AsyncGenerator[AsyncConnection, None]:  # type: ignore[return]
    """Function-scoped connection that wraps the test in a single transaction.

    Rolls back the transaction after each test — no data ever reaches the DB.
    Uses engine.begin() to start an outermost transaction; SAVEPOINT (begin_nested)
    runs inside it so that repository flush() calls work correctly.
    """
    async with async_engine.begin() as conn:
        yield conn
        await conn.rollback()


@pytest_asyncio.fixture
async def async_session(async_connection: AsyncConnection) -> AsyncGenerator[AsyncSession, None]:  # type: ignore[return]
    """Function-scoped AsyncSession that runs every test in a SAVEPOINT.

    The SAVEPOINT (begin_nested) allows repository flush() calls to succeed
    while keeping the data isolated — rolling back the SAVEPOINT at teardown
    undoes all changes within the test without affecting other tests.

    Use this session in integration tests:
        async def test_create_user(async_session):
            repo = UsuarioRepository(async_session)
            ...

    To override get_uow in endpoint tests, use make_uow_override from
    tests/fixtures/uow.py:
        app.dependency_overrides[get_uow] = make_uow_override(async_session)
    """
    session = AsyncSession(
        bind=async_connection,
        expire_on_commit=False,
    )
    await session.begin_nested()  # SAVEPOINT — rolls back at teardown

    yield session

    await session.rollback()  # Rolls back SAVEPOINT
    await session.close()


# ---------------------------------------------------------------------------
# Seeded session — async_session with catalog roles pre-loaded
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def seeded_session(async_session: AsyncSession) -> AsyncGenerator[AsyncSession, None]:  # type: ignore[return]
    """async_session with the 4 RBAC roles seeded (not committed — rolls back at teardown).

    Auth integration tests require the CLIENT role to exist so that
    AuthService.register_user() can assign it. This fixture seeds only the roles
    table (the minimum needed) using the same session/SAVEPOINT as async_session.

    Usage:
        async def test_register(seeded_session, async_client):
            app.dependency_overrides[get_uow] = make_uow_override(seeded_session)
    """
    from app.db.seed import seed_roles

    await seed_roles(async_session)
    yield async_session


# ---------------------------------------------------------------------------
# Type alias for generators (helps mypy)
# ---------------------------------------------------------------------------

from collections.abc import AsyncGenerator  # noqa: E402 — after conditional imports
