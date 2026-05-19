"""0006_add_catalog_public_indices

Revision ID: a2b3c4d5e6f7
Revises: f1e2d3c4b5a6
Create Date: 2026-05-19 00:00:00.000000

Migration 0006 — Add public catalog performance indices to the producto table.

Change 12 (catalog-public-browsing) introduces two new indices:

1. idx_productos_disponible_deleted_at (required):
   Partial index on producto(id) WHERE disponible=true AND deleted_at IS NULL.
   This is the primary visibility gate index for all public catalog queries.
   Dramatically reduces I/O by pre-filtering the eligible product set.
   Created CONCURRENTLY to avoid blocking writes on live databases.

2. idx_productos_nombre_lower (optional, documented trade-off):
   B-tree index on lower(nombre) for case-insensitive equality/prefix searches.
   Helps with: WHERE lower(nombre) = lower(:q) or prefix ILIKE 'q%'.
   Does NOT help with: WHERE nombre ILIKE '%q%' (leading wildcard).
   NOTE: For production-scale full-text search on nombre, replace with:
       CREATE INDEX USING GIN (nombre gin_trgm_ops)
   which requires the pg_trgm extension and supports leading-wildcard ILIKE.

CRITICAL — Alembic transaction requirement:
   CREATE INDEX CONCURRENTLY cannot run inside a PostgreSQL transaction block.
   Alembic wraps migrations in transactions by default.
   Both index creations are wrapped in op.get_context().autocommit_block()
   to execute outside the implicit transaction.

down_revision: 'f1e2d3c4b5a6' — hash of migration 0005_add_producto_indexes
"""

from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision = "a2b3c4d5e6f7"
down_revision = "f1e2d3c4b5a6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add two performance indices to the producto table.

    CONCURRENTLY requires running outside a transaction block — both index
    creations are wrapped in autocommit_block() as required by the spec.

    idx_productos_disponible_deleted_at:
        Partial index for all public catalog visibility queries.
        WHERE disponible=true AND deleted_at IS NULL.
        This is the primary filter applied to every public catalog query.

    idx_productos_nombre_lower:
        B-tree index on lower(nombre) for case-insensitive search.
        Limited utility for leading-wildcard ILIKE patterns.
        For production scale, use pg_trgm GIN index instead (see docstring).
    """
    # CONCURRENTLY requires running outside a transaction block
    with op.get_context().autocommit_block():
        op.execute("""
            CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_productos_disponible_deleted_at
            ON producto (id)
            WHERE disponible = true AND deleted_at IS NULL
        """)
        op.execute("""
            CREATE INDEX IF NOT EXISTS idx_productos_nombre_lower
            ON producto (lower(nombre))
        """)


def downgrade() -> None:
    """Drop both catalogue performance indices.

    Uses DROP INDEX IF EXISTS for safety — safe even if the upgrade was never
    run or was interrupted.

    NOTE: downgrade does not use autocommit_block() for DROP INDEX because
    DROP INDEX (non-CONCURRENTLY) can run inside a transaction block.
    """
    op.execute("DROP INDEX IF EXISTS idx_productos_disponible_deleted_at")
    op.execute("DROP INDEX IF EXISTS idx_productos_nombre_lower")
