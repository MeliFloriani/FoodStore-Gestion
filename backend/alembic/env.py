"""
Alembic async env.py — D-24 + D-24 Addendum.

Key design decisions:
- D-24: Uses asyncio.run(run_async_migrations()) with create_async_engine.
- D-24 Addendum: Alembic creates its OWN engine — does NOT import app.main or get_engine().
  This avoids import cycles, side effects (middlewares, rate limiter), and event loop conflicts.
- D-05: URL is read from get_settings().DATABASE_URL (lazy, reads from .env).
- D-12/P-07: app.db.base MUST be imported first to apply naming_convention before models.
- D-25: app.models is imported to register all 16 tables into SQLModel.metadata.
"""

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine

# ── Naming convention + model registration ────────────────────────────────────
# Import order is critical (D-12/P-07):
# 1. app.db.base  → applies SQLModel.metadata.naming_convention
# 2. app.models   → registers all 16 tables into SQLModel.metadata
import app.db.base  # noqa: F401  # activates naming_convention
import app.models  # noqa: F401  # registers all domain tables

from app.core.config import get_settings
from sqlmodel import SQLModel

# ── Alembic config ─────────────────────────────────────────────────────────────
config = context.config

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# target_metadata is used by autogenerate to compare against the DB schema.
target_metadata = SQLModel.metadata


# ── Offline mode (generates SQL script without DB connection) ──────────────────
def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    Generates SQL without requiring an actual DB connection.
    URL is read from get_settings() — not from alembic.ini (D-05).
    """
    url = get_settings().DATABASE_URL
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


# ── Async online mode ─────────────────────────────────────────────────────────
def do_run_migrations(connection) -> None:  # type: ignore[type-arg]
    """Synchronous callback that Alembic uses to run migrations via run_sync()."""
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Create a fresh async engine and run migrations.

    D-24 Addendum: this engine is independent of get_engine() in app/db/session.py.
    - Does NOT import app.main (avoids FastAPI/middleware import side effects).
    - Does NOT call get_engine() (avoids event loop conflicts and lifecycle coupling).
    - Pool size = 1 is sufficient for migration runs.
    """
    connectable = create_async_engine(
        get_settings().DATABASE_URL,
        pool_size=1,
        max_overflow=0,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Entry point for online migrations — delegates to asyncio.run()."""
    asyncio.run(run_async_migrations())


# ── Dispatch ──────────────────────────────────────────────────────────────────
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
