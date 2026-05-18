"""0003_categoria_nombre_per_parent

Replace the global UNIQUE(nombre) constraint on categoria with two partial
unique indexes (per-parent scope) and one performance index for CTE joins.

Revision ID: c9d8e7f6a5b4
Revises: a1b2c3d4e5f6
Create Date: 2026-05-18 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c9d8e7f6a5b4"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Replace global unique on categoria.nombre with two partial unique indexes.

    1. Drop global unique constraint on categoria.nombre (created by 0001_initial_schema).
    2. Create partial unique index for non-root categories (same nombre under same parent).
    3. Create partial unique index for root categories (parent_id IS NULL).
       NOTE: PostgreSQL treats NULL != NULL in standard unique indexes, so two rows
       with parent_id=NULL and the same nombre would NOT conflict without this index.
    4. Create performance index for CTE JOIN on parent_id.

    All indexes use WHERE deleted_at IS NULL so soft-deleted names are reclaimable.
    """
    # Drop global unique constraint on nombre
    op.drop_constraint("uq_categoria_nombre", "categoria", type_="unique")

    # Partial unique index: non-root categories (same nombre under same parent)
    op.execute("""
        CREATE UNIQUE INDEX uq_categoria_nombre_parent
        ON categoria (parent_id, nombre)
        WHERE deleted_at IS NULL
    """)

    # Partial unique index: root categories (parent_id IS NULL)
    op.execute("""
        CREATE UNIQUE INDEX uq_categoria_nombre_root
        ON categoria (nombre)
        WHERE parent_id IS NULL AND deleted_at IS NULL
    """)

    # Performance index for CTE JOIN on parent_id
    # EXPLAIN ANALYZE: used by get_tree() and would_create_cycle() CTEs
    op.execute("""
        CREATE INDEX ix_categoria_parent_id
        ON categoria (parent_id)
        WHERE deleted_at IS NULL
    """)


def downgrade() -> None:
    """Restore global unique constraint on categoria.nombre.

    IMPORTANT: This downgrade assumes no duplicate names exist at the same
    parent level (which is the same assumption as the initial schema).
    If duplicates were introduced while migration 0003 was active, downgrade
    will fail with a unique constraint violation.
    """
    op.execute("DROP INDEX IF EXISTS ix_categoria_parent_id")
    op.execute("DROP INDEX IF EXISTS uq_categoria_nombre_root")
    op.execute("DROP INDEX IF EXISTS uq_categoria_nombre_parent")
    op.create_unique_constraint("uq_categoria_nombre", "categoria", ["nombre"])
