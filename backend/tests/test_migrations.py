"""
Tests de migración Alembic — ciclo upgrade/downgrade/upgrade.

Estrategia (task 9.0, Opción B):
  - Usa alembic upgrade head + alembic downgrade base via subprocess.
  - Opera sobre foodstore_test (TEST_DATABASE_URL).
  - Fixture session-scoped garantiza la DB queda limpia al inicio de la suite.

Design:
  - Usa subprocess para invocar alembic CLI (evita conflictos de event loop).
  - TEST_DATABASE_URL se inyecta como variable de entorno DATABASE_URL
    para que get_settings() en env.py lo use.
"""

from __future__ import annotations

import asyncio
import os
import subprocess
import sys

import asyncpg
import pytest
from dotenv import load_dotenv

# Load .env so TEST_DATABASE_URL is available in os.environ
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))


BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _alembic(args: list[str]) -> subprocess.CompletedProcess:
    """Corre un comando alembic apuntando a foodstore_test."""
    test_url = os.environ["TEST_DATABASE_URL"]
    env = {**os.environ, "DATABASE_URL": test_url}
    result = subprocess.run(
        [sys.executable, "-m", "alembic"] + args,
        cwd=BACKEND_DIR,
        env=env,
        capture_output=True,
        text=True,
    )
    return result


@pytest.fixture(scope="session", autouse=True)
def clean_test_db_at_start():
    """Fixture session-scoped: garantiza la BD de test queda en estado limpio al inicio.

    Si la BD quedó sucia de una ejecución anterior (downgrade falló a mitad),
    este fixture ejecuta downgrade base antes de que empiecen los tests.
    Ignora errores (puede que ya esté limpia).

    Al finalizar: deja la BD en head para que test_seed.py pueda correr sin
    necesitar hacer upgrade separado.
    """
    _alembic(["downgrade", "base"])  # ignore errors — cleanup anterior run
    yield
    # Teardown: restaurar a head para que otros tests (test_seed) puedan funcionar
    _alembic(["upgrade", "head"])


class TestMigrationCycle:
    """Tests del ciclo completo upgrade/downgrade/upgrade sobre foodstore_test."""

    def test_upgrade_head(self):
        """upgrade head debe completar sin errores."""
        result = _alembic(["upgrade", "head"])
        assert result.returncode == 0, (
            f"alembic upgrade head falló:\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )

    def test_downgrade_base(self):
        """downgrade base debe completar sin errores de FK."""
        result = _alembic(["downgrade", "base"])
        assert result.returncode == 0, (
            f"alembic downgrade base falló:\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )

    def test_upgrade_after_downgrade(self):
        """upgrade head después de downgrade base debe completar (schema reproducible)."""
        result = _alembic(["upgrade", "head"])
        assert result.returncode == 0, (
            f"alembic upgrade head (post-downgrade) falló:\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )

    def test_upgrade_downgrade_upgrade_cycle(self):
        """Ciclo completo: upgrade → downgrade → upgrade debe completar sin errores."""
        # Downgrade
        r1 = _alembic(["downgrade", "base"])
        assert r1.returncode == 0, f"downgrade falló: {r1.stderr}"

        # Upgrade
        r2 = _alembic(["upgrade", "head"])
        assert r2.returncode == 0, f"upgrade (2do) falló: {r2.stderr}"


# ---------------------------------------------------------------------------
# Migration 0003 — per-parent uniqueness constraint tests
# ---------------------------------------------------------------------------


def _get_asyncpg_url() -> str:
    """Return a raw asyncpg DSN from TEST_DATABASE_URL, stripping SQLAlchemy prefix."""
    url = os.environ["TEST_DATABASE_URL"]
    url = url.replace("postgresql+asyncpg://", "postgresql://")
    url = url.replace("asyncpg+postgresql://", "postgresql://")
    return url


async def _query(sql: str, *params):
    """Run a SELECT and return all rows as asyncpg Record objects."""
    conn = await asyncpg.connect(_get_asyncpg_url())
    try:
        return await conn.fetch(sql, *params)
    finally:
        await conn.close()


async def _execute(sql: str, *params):
    """Run a non-SELECT statement and return the status string."""
    conn = await asyncpg.connect(_get_asyncpg_url())
    try:
        return await conn.execute(sql, *params)
    finally:
        await conn.close()


class TestMigration0003:
    """Tests for migration 0003 — categoria_nombre_per_parent partial indexes."""

    @pytest.fixture(scope="class", autouse=True)
    def ensure_head_after_class(self):
        """Always ensure DB is at head after this class runs."""
        yield
        _alembic(["upgrade", "head"])

    @pytest.fixture(autouse=True)
    def ensure_at_head(self):
        """Ensure DB is at head before each test, and restore after."""
        _alembic(["upgrade", "head"])
        yield
        _alembic(["upgrade", "head"])

    def test_0003_upgrade_creates_partial_indexes(self):
        """After upgrading to head, the three partial indexes must exist."""

        async def check_indexes():
            rows = await _query("""
                SELECT indexname FROM pg_indexes
                WHERE tablename = 'categoria'
                  AND indexname IN (
                    'uq_categoria_nombre_parent',
                    'uq_categoria_nombre_root',
                    'ix_categoria_parent_id'
                  )
                ORDER BY indexname
            """)
            return [r["indexname"] for r in rows]

        index_names = asyncio.run(check_indexes())
        assert "uq_categoria_nombre_parent" in index_names, "uq_categoria_nombre_parent index missing"
        assert "uq_categoria_nombre_root" in index_names, "uq_categoria_nombre_root index missing"
        assert "ix_categoria_parent_id" in index_names, "ix_categoria_parent_id index missing"

    def test_0003_allows_same_name_different_parent(self):
        """Two categories with same nombre but different parents should be allowed."""
        import uuid

        async def run():
            conn = await asyncpg.connect(_get_asyncpg_url())
            try:
                now = "2026-05-18 00:00:00"
                pid1 = str(uuid.uuid4())
                pid2 = str(uuid.uuid4())
                c1 = str(uuid.uuid4())
                c2 = str(uuid.uuid4())
                # Create two root parents
                await conn.execute(f"""
                    INSERT INTO categoria (id, created_at, updated_at, deleted_at, nombre, descripcion, parent_id)
                    VALUES ('{pid1}', '{now}', '{now}', NULL, 'Parent1', NULL, NULL),
                           ('{pid2}', '{now}', '{now}', NULL, 'Parent2', NULL, NULL)
                """)
                # Create child with same nombre under each parent — must not raise
                await conn.execute(f"""
                    INSERT INTO categoria (id, created_at, updated_at, deleted_at, nombre, descripcion, parent_id)
                    VALUES ('{c1}', '{now}', '{now}', NULL, 'Child', NULL, '{pid1}'),
                           ('{c2}', '{now}', '{now}', NULL, 'Child', NULL, '{pid2}')
                """)
                # Cleanup
                await conn.execute(
                    f"DELETE FROM categoria WHERE id IN ('{c1}', '{c2}', '{pid1}', '{pid2}')"
                )
            finally:
                await conn.close()

        asyncio.run(run())  # should not raise

    def test_0003_blocks_same_name_same_root(self):
        """Two root categories with same nombre must fail with a unique violation."""
        import uuid

        async def run():
            conn = await asyncpg.connect(_get_asyncpg_url())
            r1 = str(uuid.uuid4())
            r2 = str(uuid.uuid4())
            now = "2026-05-18 00:00:00"
            try:
                await conn.execute(
                    f"INSERT INTO categoria (id, created_at, updated_at, deleted_at, nombre, descripcion, parent_id) "
                    f"VALUES ('{r1}', '{now}', '{now}', NULL, 'UniqueRoot', NULL, NULL)"
                )
                raised = False
                try:
                    await conn.execute(
                        f"INSERT INTO categoria (id, created_at, updated_at, deleted_at, nombre, descripcion, parent_id) "
                        f"VALUES ('{r2}', '{now}', '{now}', NULL, 'UniqueRoot', NULL, NULL)"
                    )
                except Exception as exc:
                    raised = True
                    err = str(exc).lower()
                    assert (
                        "unique" in err or "duplicate" in err or "uq_categoria_nombre_root" in err
                    ), f"Unexpected error type: {exc}"
                assert raised, "Expected uniqueness violation for two root categories with same nombre"
            finally:
                await conn.execute(
                    f"DELETE FROM categoria WHERE id IN ('{r1}', '{r2}')"
                )
                await conn.close()

        asyncio.run(run())

    def test_0003_reclaims_soft_deleted_name(self):
        """After soft-deleting a root category, its nombre can be reused."""
        import uuid

        async def run():
            conn = await asyncpg.connect(_get_asyncpg_url())
            r1 = str(uuid.uuid4())
            r2 = str(uuid.uuid4())
            now = "2026-05-18 00:00:00"
            try:
                # Insert soft-deleted root category
                await conn.execute(
                    f"INSERT INTO categoria (id, created_at, updated_at, deleted_at, nombre, descripcion, parent_id) "
                    f"VALUES ('{r1}', '{now}', '{now}', '{now}', 'Reclaimable', NULL, NULL)"
                )
                # Insert new active root category with same nombre — should succeed
                await conn.execute(
                    f"INSERT INTO categoria (id, created_at, updated_at, deleted_at, nombre, descripcion, parent_id) "
                    f"VALUES ('{r2}', '{now}', '{now}', NULL, 'Reclaimable', NULL, NULL)"
                )
            finally:
                await conn.execute(
                    f"DELETE FROM categoria WHERE id IN ('{r1}', '{r2}')"
                )
                await conn.close()

        asyncio.run(run())  # should not raise

    def test_0003_downgrade_restores_global_unique(self):
        """After downgrade, two root categories with same nombre must fail."""
        import uuid

        result = _alembic(["downgrade", "a1b2c3d4e5f6"])
        assert result.returncode == 0, f"downgrade to a1b2c3d4e5f6 failed: {result.stderr}"

        async def run():
            conn = await asyncpg.connect(_get_asyncpg_url())
            r1 = str(uuid.uuid4())
            r2 = str(uuid.uuid4())
            now = "2026-05-18 00:00:00"
            try:
                await conn.execute(
                    f"INSERT INTO categoria (id, created_at, updated_at, deleted_at, nombre, descripcion, parent_id) "
                    f"VALUES ('{r1}', '{now}', '{now}', NULL, 'GlobalUnique', NULL, NULL)"
                )
                raised = False
                try:
                    await conn.execute(
                        f"INSERT INTO categoria (id, created_at, updated_at, deleted_at, nombre, descripcion, parent_id) "
                        f"VALUES ('{r2}', '{now}', '{now}', NULL, 'GlobalUnique', NULL, NULL)"
                    )
                except Exception:
                    raised = True
                assert raised, "Expected global unique violation after downgrade"
            finally:
                await conn.execute(
                    f"DELETE FROM categoria WHERE id IN ('{r1}', '{r2}')"
                )
                await conn.close()

        asyncio.run(run())

        # Re-upgrade to head to leave DB in clean state for other tests
        result = _alembic(["upgrade", "head"])
        assert result.returncode == 0, f"re-upgrade after downgrade test failed: {result.stderr}"
