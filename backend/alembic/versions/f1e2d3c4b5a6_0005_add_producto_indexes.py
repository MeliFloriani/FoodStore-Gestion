"""0005_add_producto_indexes

Revision ID: f1e2d3c4b5a6
Revises: 8212a24ee1b0
Create Date: 2026-05-18 00:00:00.000000

Migration 0005 — Add performance indexes to the producto table.

This migration ONLY adds indexes — it does NOT create new tables or modify
existing columns. The producto, producto_categoria, and producto_ingrediente
tables already exist from migration 0001.

Indexes added:
  - ix_producto_disponible: filters catalog by availability (Change 12)
  - ix_producto_nombre_search: prefix ILIKE search on nombre (Change 12)

Both indexes are partial (WHERE deleted_at IS NULL) to avoid including
soft-deleted products in the index and reduce index bloat.

down_revision: '8212a24ee1b0' — hash of migration 0004_ingredientes_table
(verified with alembic history — do NOT use the string '0004_ingredientes_table').
"""

from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision = "f1e2d3c4b5a6"
down_revision = "8212a24ee1b0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add two partial performance indexes to the producto table.

    Both indexes filter WHERE deleted_at IS NULL so they only cover
    active products. This avoids indexing soft-deleted rows and keeps
    the indexes lean.

    ix_producto_disponible:
        Supports filtering catalog queries by disponible=True/False (Change 12).
        Partial — only active products are filtered by disponibility.

    ix_producto_nombre_search:
        Supports prefix ILIKE searches using text_pattern_ops operator class.
        text_pattern_ops enables B-tree index usage for LIKE 'prefix%' patterns
        (case-sensitive prefix). For case-insensitive ILIKE, the optimizer may
        fall back to a sequential scan unless pg_trgm is enabled (future Change 12).
    """
    # Filtro de catálogo público (Change 12)
    op.execute(
        "CREATE INDEX ix_producto_disponible "
        "ON producto (disponible) WHERE deleted_at IS NULL"
    )
    # Búsqueda ILIKE con prefijo (Change 12)
    op.execute(
        "CREATE INDEX ix_producto_nombre_search "
        "ON producto (nombre text_pattern_ops) WHERE deleted_at IS NULL"
    )


def downgrade() -> None:
    """Drop the two partial performance indexes added in upgrade().

    Uses IF EXISTS for safety in case indexes were never created
    (e.g., partial upgrade/downgrade cycle interrupted).
    """
    op.execute("DROP INDEX IF EXISTS ix_producto_nombre_search")
    op.execute("DROP INDEX IF EXISTS ix_producto_disponible")
