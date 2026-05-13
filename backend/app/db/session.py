"""
Async database session management.

Design decisions:
- D-05 / P-01: Engine and session factory are lazy — created via @lru_cache(maxsize=1).
  NEVER instantiated at module level. This allows tests to override settings before
  the engine is created.
- D-05: Engine must be disposed on shutdown (lifespan calls get_engine().dispose()).
- get_session(): FastAPI dependency that injects AsyncSession via Depends(get_session).

Timezone compatibility patch (Change 04 discovery):
  app/models/base.py uses datetime.now(UTC) (timezone-aware) in:
    - created_at / updated_at default_factory
    - updated_at onupdate hook
    - Base.soft_delete() -> sets deleted_at = datetime.now(UTC)
  The migration schema uses sa.DateTime() -> TIMESTAMP WITHOUT TIME ZONE, which
  requires naive datetimes. asyncpg raises DataError when receiving tz-aware datetimes
  for TIMESTAMP WITHOUT TIME ZONE columns.

  Workaround: monkey-patch AsyncpgDateTime.bind_processor to strip tzinfo before
  binding. This is applied at module import time (before any engine is created).
  Long-term fix: migrate timestamp columns to TIMESTAMPTZ (TIMESTAMP WITH TIME ZONE)
  in a future change.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator, Callable
from datetime import datetime
from functools import lru_cache
from typing import Any

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings


# ---------------------------------------------------------------------------
# Timezone compatibility patch
# ---------------------------------------------------------------------------

def _patch_asyncpg_datetime_tz() -> None:
    """Strip tzinfo from timezone-aware datetimes before binding to asyncpg.

    Context: Base.soft_delete() and the onupdate hook produce UTC-aware datetimes
    (datetime.now(UTC)), but the migration schema uses TIMESTAMP WITHOUT TIME ZONE.
    asyncpg rejects tz-aware datetimes for those columns.

    This patch intercepts bind processing at the SQLAlchemy dialect level and strips
    tzinfo, preserving the UTC timestamp value as a naive datetime.

    This patch is idempotent and safe to call multiple times.
    """
    try:
        from sqlalchemy.dialects.postgresql.asyncpg import AsyncpgDateTime

        _original_bind = AsyncpgDateTime.bind_processor

        def _tz_safe_bind_processor(self: Any, dialect: Any) -> Callable[[Any], Any]:
            proc: Callable[[Any], Any] | None = _original_bind(self, dialect)

            def process(value: Any) -> Any:
                if isinstance(value, datetime) and value.tzinfo is not None:
                    value = value.replace(tzinfo=None)
                if proc is not None:
                    return proc(value)
                return value

            return process

        # Only patch if not already patched (idempotency guard)
        if not getattr(AsyncpgDateTime, "_tz_patched", False):
            AsyncpgDateTime.bind_processor = _tz_safe_bind_processor  # type: ignore[assignment]
            AsyncpgDateTime._tz_patched = True  # type: ignore[attr-defined]
    except ImportError:
        pass  # asyncpg not installed — no-op


_patch_asyncpg_datetime_tz()


# ---------------------------------------------------------------------------
# Engine and session factory
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def get_engine() -> AsyncEngine:
    """Return the singleton async engine.

    Lazy: constructed on first call, cached thereafter.
    Called by get_session_factory() and disposed in lifespan shutdown.

    Correction P-01: engine is NOT instantiated at module level.
    """
    settings = get_settings()
    return create_async_engine(
        settings.DATABASE_URL,
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True,
        echo=settings.ENVIRONMENT == "development",
    )


@lru_cache(maxsize=1)
def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Return the singleton session factory.

    Lazy: constructed on first call using get_engine().
    Correction P-01: session factory is NOT instantiated at module level.
    """
    return async_sessionmaker(
        get_engine(),
        class_=AsyncSession,
        expire_on_commit=False,
    )


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields an AsyncSession.

    Usage:
        @router.get("/items")
        async def list_items(session: AsyncSession = Depends(get_session)):
            ...
    """
    async with get_session_factory()() as session:
        yield session
