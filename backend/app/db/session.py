"""
Async database session management.

Design decisions:
- D-05 / P-01: Engine and session factory are lazy — created via @lru_cache(maxsize=1).
  NEVER instantiated at module level. This allows tests to override settings before
  the engine is created.
- D-05: Engine must be disposed on shutdown (lifespan calls get_engine().dispose()).
- get_session(): FastAPI dependency that injects AsyncSession via Depends(get_session).
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from functools import lru_cache

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings


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
