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


# ---------------------------------------------------------------------------
# Migration 0004 — ingrediente table partial indexes tests
# Tasks 1.1–1.8
# ---------------------------------------------------------------------------


class TestMigration0004:
    """Tests for migration 0004 — ingrediente table alterations.

    All tests require a live database. Mark as skipped if no DB is available.
    # requires live DB
    """

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

    def test_0004_upgrade_alters_ingrediente_table(self):
        """After upgrading to 0004, ingrediente table exists with no uq_ingrediente_nombre.

        Tasks 1.1 + 1.8: table still exists; no global uq_ingrediente_nombre constraint.
        # requires live DB
        """

        async def check():
            rows = await _query("""
                SELECT indexname FROM pg_indexes
                WHERE tablename = 'ingrediente'
                  AND indexname = 'uq_ingrediente_nombre'
            """)
            return rows

        rows = asyncio.run(check())
        # After migration 0004, uq_ingrediente_nombre constraint must be GONE
        assert len(rows) == 0, (
            "uq_ingrediente_nombre still exists after migration 0004 — DROP CONSTRAINT not applied"
        )

    def test_0004_upgrade_creates_ix_ingrediente_nombre_activo(self):
        """After upgrading to 0004, ix_ingrediente_nombre_activo partial index exists.

        Task 1.2: partial unique index on ingrediente(nombre) WHERE deleted_at IS NULL.
        # requires live DB
        """

        async def check():
            rows = await _query("""
                SELECT indexname, indexdef FROM pg_indexes
                WHERE tablename = 'ingrediente'
                  AND indexname = 'ix_ingrediente_nombre_activo'
            """)
            return rows

        rows = asyncio.run(check())
        assert len(rows) == 1, "ix_ingrediente_nombre_activo index not found after migration 0004"
        # Verify partial condition appears in definition
        index_def = rows[0]["indexdef"].lower()
        assert "deleted_at is null" in index_def, (
            f"ix_ingrediente_nombre_activo missing WHERE deleted_at IS NULL: {index_def}"
        )

    def test_0004_upgrade_creates_ix_ingrediente_es_alergeno(self):
        """After upgrading to 0004, ix_ingrediente_es_alergeno partial index exists.

        Task 1.3: partial index on ingrediente(es_alergeno) WHERE deleted_at IS NULL.
        # requires live DB
        """

        async def check():
            rows = await _query("""
                SELECT indexname, indexdef FROM pg_indexes
                WHERE tablename = 'ingrediente'
                  AND indexname = 'ix_ingrediente_es_alergeno'
            """)
            return rows

        rows = asyncio.run(check())
        assert len(rows) == 1, "ix_ingrediente_es_alergeno index not found after migration 0004"
        index_def = rows[0]["indexdef"].lower()
        assert "deleted_at is null" in index_def, (
            f"ix_ingrediente_es_alergeno missing WHERE deleted_at IS NULL: {index_def}"
        )

    def test_0004_blocks_duplicate_active_nombre(self):
        """Two active ingredients with the same nombre must fail with a unique violation.

        Task 1.4: partial unique index enforces uniqueness among active records.
        # requires live DB
        """
        import uuid

        async def run():
            conn = await asyncpg.connect(_get_asyncpg_url())
            i1 = str(uuid.uuid4())
            i2 = str(uuid.uuid4())
            now = "2026-05-18 00:00:00"
            try:
                await conn.execute(
                    f"INSERT INTO ingrediente (id, created_at, updated_at, deleted_at, nombre, es_alergeno) "
                    f"VALUES ('{i1}', '{now}', '{now}', NULL, 'Sal', false)"
                )
                raised = False
                try:
                    await conn.execute(
                        f"INSERT INTO ingrediente (id, created_at, updated_at, deleted_at, nombre, es_alergeno) "
                        f"VALUES ('{i2}', '{now}', '{now}', NULL, 'Sal', false)"
                    )
                except Exception as exc:
                    raised = True
                    err = str(exc).lower()
                    assert (
                        "unique" in err or "duplicate" in err or "ix_ingrediente_nombre_activo" in err
                    ), f"Unexpected error type: {exc}"
                assert raised, "Expected uniqueness violation for two active ingredients with same nombre"
            finally:
                await conn.execute(f"DELETE FROM ingrediente WHERE id IN ('{i1}', '{i2}')")
                await conn.close()

        asyncio.run(run())

    def test_0004_reclaims_soft_deleted_nombre(self):
        """A soft-deleted ingredient's nombre can be reused by a new active row.

        Task 1.5: partial unique index allows name reuse after soft delete.
        # requires live DB
        """
        import uuid

        async def run():
            conn = await asyncpg.connect(_get_asyncpg_url())
            i1 = str(uuid.uuid4())
            i2 = str(uuid.uuid4())
            now = "2026-05-18 00:00:00"
            try:
                # Insert soft-deleted ingredient
                await conn.execute(
                    f"INSERT INTO ingrediente (id, created_at, updated_at, deleted_at, nombre, es_alergeno) "
                    f"VALUES ('{i1}', '{now}', '{now}', '{now}', 'Azucar', false)"
                )
                # Insert new active ingredient with same nombre — should succeed
                await conn.execute(
                    f"INSERT INTO ingrediente (id, created_at, updated_at, deleted_at, nombre, es_alergeno) "
                    f"VALUES ('{i2}', '{now}', '{now}', NULL, 'Azucar', false)"
                )
            finally:
                await conn.execute(f"DELETE FROM ingrediente WHERE id IN ('{i1}', '{i2}')")
                await conn.close()

        asyncio.run(run())  # should not raise

    def test_0004_downgrade_drops_indexes_and_restores_constraint(self):
        """Downgrade removes both partial indexes and restores uq_ingrediente_nombre.

        Task 1.6: downgrade is reversible and correct.
        # requires live DB
        """
        result = _alembic(["downgrade", "c9d8e7f6a5b4"])
        assert result.returncode == 0, f"downgrade to c9d8e7f6a5b4 failed: {result.stderr}"

        async def check():
            partial_indexes = await _query("""
                SELECT indexname FROM pg_indexes
                WHERE tablename = 'ingrediente'
                  AND indexname IN ('ix_ingrediente_nombre_activo', 'ix_ingrediente_es_alergeno')
            """)
            global_constraint = await _query("""
                SELECT indexname FROM pg_indexes
                WHERE tablename = 'ingrediente'
                  AND indexname = 'uq_ingrediente_nombre'
            """)
            return partial_indexes, global_constraint

        partial_indexes, global_constraint = asyncio.run(check())
        assert len(partial_indexes) == 0, (
            f"Partial indexes should be gone after downgrade: {[r['indexname'] for r in partial_indexes]}"
        )
        assert len(global_constraint) == 1, (
            "uq_ingrediente_nombre constraint should be restored after downgrade"
        )

        # Re-upgrade to head
        result = _alembic(["upgrade", "head"])
        assert result.returncode == 0, f"re-upgrade after downgrade test failed: {result.stderr}"

    def test_0004_round_trip_reproducible(self):
        """upgrade + downgrade + upgrade completes without errors.

        Task 1.7: migration is idempotent and reproducible.
        # requires live DB
        """
        r1 = _alembic(["downgrade", "c9d8e7f6a5b4"])
        assert r1.returncode == 0, f"downgrade failed: {r1.stderr}"

        r2 = _alembic(["upgrade", "8212a24ee1b0"])
        assert r2.returncode == 0, f"second upgrade failed: {r2.stderr}"

    def test_0004_no_spurious_constraint_after_upgrade(self):
        """uq_ingrediente_nombre is NOT present after upgrading to head.

        Task 1.8: no stale unique constraint detected on ingrediente.nombre.
        Migration 0004 replaces the global unique constraint with two partial
        indexes.  After upgrade the old constraint must be gone.
        # requires live DB
        """
        # Ensure we are at head (handles the case where a prior test left the
        # DB below head, e.g. test_0004_round_trip_reproducible only goes to 0004)
        upgrade_result = _alembic(["upgrade", "head"])
        assert upgrade_result.returncode == 0, (
            f"upgrade to head failed:\n{upgrade_result.stderr}"
        )

        async def check():
            return await _query("""
                SELECT indexname FROM pg_indexes
                WHERE tablename = 'ingrediente'
                  AND indexname = 'uq_ingrediente_nombre'
            """)

        rows = asyncio.run(check())
        assert len(rows) == 0, (
            "Spurious constraint uq_ingrediente_nombre still present after "
            f"upgrade to head: {[r['indexname'] for r in rows]}"
        )


# ---------------------------------------------------------------------------
# Migration 0005 — producto performance indexes tests
# Tasks 1.1–1.5
# ---------------------------------------------------------------------------


class TestMigration0005:
    """Tests for migration 0005 — producto performance indexes.

    All tests require a live database.
    # requires live DB
    """

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

    def test_0005_upgrade_creates_ix_producto_disponible(self):
        """After upgrading to head, ix_producto_disponible partial index must exist.

        Task 1.1: index on producto(disponible) WHERE deleted_at IS NULL.
        # requires live DB
        """

        async def check():
            rows = await _query("""
                SELECT indexname, indexdef FROM pg_indexes
                WHERE tablename = 'producto'
                  AND indexname = 'ix_producto_disponible'
            """)
            return rows

        rows = asyncio.run(check())
        assert len(rows) == 1, "ix_producto_disponible index not found after migration 0005"
        index_def = rows[0]["indexdef"].lower()
        assert "deleted_at is null" in index_def, (
            f"ix_producto_disponible missing WHERE deleted_at IS NULL: {index_def}"
        )

    def test_0005_upgrade_creates_ix_producto_nombre_search(self):
        """After upgrading to head, ix_producto_nombre_search index must exist.

        Task 1.2: index on producto(nombre text_pattern_ops) WHERE deleted_at IS NULL.
        # requires live DB
        """

        async def check():
            rows = await _query("""
                SELECT indexname, indexdef FROM pg_indexes
                WHERE tablename = 'producto'
                  AND indexname = 'ix_producto_nombre_search'
            """)
            return rows

        rows = asyncio.run(check())
        assert len(rows) == 1, "ix_producto_nombre_search index not found after migration 0005"
        index_def = rows[0]["indexdef"].lower()
        assert "deleted_at is null" in index_def, (
            f"ix_producto_nombre_search missing WHERE deleted_at IS NULL: {index_def}"
        )

    def test_0005_producto_columns_unchanged(self):
        """After migration 0005, all original producto columns and constraints remain.

        Task 1.3: no columns dropped or altered; CHECK constraints still present.
        # requires live DB
        """

        async def check():
            columns = await _query("""
                SELECT column_name FROM information_schema.columns
                WHERE table_name = 'producto'
                ORDER BY column_name
            """)
            constraints = await _query("""
                SELECT constraint_name FROM information_schema.table_constraints
                WHERE table_name = 'producto'
                  AND constraint_type = 'CHECK'
                ORDER BY constraint_name
            """)
            return [r["column_name"] for r in columns], [r["constraint_name"] for r in constraints]

        column_names, constraint_names = asyncio.run(check())

        expected_cols = {"id", "nombre", "descripcion", "imagen_url", "precio_base",
                         "stock_cantidad", "disponible", "created_at", "updated_at", "deleted_at"}
        for col in expected_cols:
            assert col in column_names, f"Column '{col}' missing from producto table after migration 0005"

        # Both CHECK constraints from migration 0001 must remain
        ck_constraints = [c for c in constraint_names if "precio_base" in c or "stock_cantidad" in c]
        assert len(ck_constraints) >= 2, (
            f"Expected at least 2 CHECK constraints on producto, found: {constraint_names}"
        )

    def test_0005_downgrade_drops_indexes(self):
        """After downgrade -1, both producto indexes are absent.

        Task 1.4: downgrade removes ix_producto_disponible and ix_producto_nombre_search.
        # requires live DB
        """
        result = _alembic(["downgrade", "-1"])
        assert result.returncode == 0, f"downgrade -1 failed: {result.stderr}"

        async def check():
            rows = await _query("""
                SELECT indexname FROM pg_indexes
                WHERE tablename = 'producto'
                  AND indexname IN ('ix_producto_disponible', 'ix_producto_nombre_search')
            """)
            return rows

        rows = asyncio.run(check())
        assert len(rows) == 0, (
            f"Indexes should be gone after downgrade: {[r['indexname'] for r in rows]}"
        )

        # Re-upgrade to head to leave DB clean
        result = _alembic(["upgrade", "head"])
        assert result.returncode == 0, f"re-upgrade after downgrade test failed: {result.stderr}"

    def test_0005_round_trip_reproducible(self):
        """upgrade + downgrade + upgrade completes without errors.

        Task 1.5: migration is idempotent and reproducible.
        # requires live DB
        """
        r1 = _alembic(["downgrade", "-1"])
        assert r1.returncode == 0, f"downgrade failed: {r1.stderr}"

        r2 = _alembic(["upgrade", "head"])
        assert r2.returncode == 0, f"second upgrade failed: {r2.stderr}"
