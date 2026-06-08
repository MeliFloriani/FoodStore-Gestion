"""Migration 0014 — admin_metrics_indexes.

Creates two net-new B-tree indexes supporting the admin analytics API
introduced in Change 23 (admin-metrics-dashboard).

Verification performed against migrations 0001–0013:
  - ix_pedido_created_at_estado_codigo: NOT found in any prior migration.
    This is a net-new composite index on pedido(created_at, estado_codigo).
  - ix_detalle_pedido_producto_id: NOT found in any prior migration.
    Migration 0001 created ix_detalle_pedido_pedido_id (on pedido_id column),
    but ix_detalle_pedido_producto_id (on producto_id column) does NOT exist.

Why these indexes exist:
  1. ix_pedido_created_at_estado_codigo — composite index on pedido(created_at,
     estado_codigo). created_at is the first column (range scan), estado_codigo
     is the second (equality/IN filter). Without this, all four analytics
     endpoints perform a sequential scan on the full pedido table for every
     date-range filter. This is the hottest analytics path.

  2. ix_detalle_pedido_producto_id — single-column index on
     detalle_pedido(producto_id). Enables the hash join / index scan in the
     top-products GROUP BY query (GET /api/v1/admin/metricas/productos-top).
     Without this, the join from detalle_pedido → pedido via producto_id
     requires a seq scan on a potentially large table.

Coexistence note: ix_pedido_estado_codigo (created in migration 0001) is
preserved — it covers single-column estado_codigo queries (e.g. order
management panel filters). The new composite index adds the created_at
dimension for analytics. Both indexes serve distinct query shapes.

Revision chain: 0014 → 0013 (d1e2f3a4b5c6) → 0012 (c0d1e2f3a4b5) → ...
"""

from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e1f2a3b4c5d6"
down_revision: str = "d1e2f3a4b5c6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Composite index: created_at first (supports range scans), estado_codigo
    # second (equality/IN filter). Drives all four admin analytics endpoints.
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_pedido_created_at_estado_codigo
        ON pedido (created_at, estado_codigo)
    """)

    # Single-column index: enables efficient GROUP BY join in top-products query.
    # Migration 0001 created ix_detalle_pedido_pedido_id but NOT this one.
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_detalle_pedido_producto_id
        ON detalle_pedido (producto_id)
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_detalle_pedido_producto_id")
    op.execute("DROP INDEX IF EXISTS ix_pedido_created_at_estado_codigo")
