"""
Pytest fixtures for the backend test suite.

Design decisions:
- D-16 / P-03: override_settings fixture clears ALL four lru_cache getters
  (get_settings, get_engine, get_session_factory, get_limiter) before AND after
  the override. Without this, cached instances from prior tests bleed through.
- P-05: async_client uses ASGITransport(app=app) — the deprecated AsyncClient(app=...)
  form is not used.
- test_db_session provides an isolated AsyncSession per test via rollback teardown.
"""

from __future__ import annotations

import os

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import Settings, get_settings
from app.core.rate_limit import get_limiter
from app.db.session import get_engine, get_session_factory
from app.main import app


# ---------------------------------------------------------------------------
# Settings override — clears all lazy caches before and after
# ---------------------------------------------------------------------------


@pytest.fixture
def override_settings():
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
async def async_client(override_settings):
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
# Isolated database session for unit-style DB tests
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def test_db_session(override_settings):
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
