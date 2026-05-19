"""0004_ingredientes_table

ALTER ingrediente table: drop global unique constraint on nombre,
add partial unique index on nombre WHERE deleted_at IS NULL,
and add partial index on es_alergeno WHERE deleted_at IS NULL.

Revision ID: 8212a24ee1b0
Revises: c9d8e7f6a5b4
Create Date: 2026-05-18 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "8212a24ee1b0"
down_revision: Union[str, None] = "c9d8e7f6a5b4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """ALTER the existing ingrediente table (created by migration 0001).

    Steps (ORDER IS CRITICAL — D-02):
    1. Drop global unique constraint uq_ingrediente_nombre (from 0001_initial_schema).
       This MUST come FIRST — a partial index does not supersede an existing UNIQUE
       constraint. If both coexist, the global constraint would still block name reuse
       after soft delete, defeating the purpose of the partial index.
    2. Create partial unique index on nombre WHERE deleted_at IS NULL.
       Active ingredients cannot share names; soft-deleted names are immediately reusable.
    3. Create partial index on es_alergeno WHERE deleted_at IS NULL.
       Optimises GET /ingredientes?es_alergeno=true (Change 12 hot path).
    """
    # 1. Drop global unique constraint from migration 0001 — MUST come first
    op.drop_constraint("uq_ingrediente_nombre", "ingrediente", type_="unique")
    # 2. Create partial unique index (nombre among active records only)
    op.execute(
        "CREATE UNIQUE INDEX ix_ingrediente_nombre_activo"
        " ON ingrediente (nombre) WHERE deleted_at IS NULL"
    )
    # 3. Create allergen filter index
    op.execute(
        "CREATE INDEX ix_ingrediente_es_alergeno"
        " ON ingrediente (es_alergeno) WHERE deleted_at IS NULL"
    )


def downgrade() -> None:
    """Restore the global uq_ingrediente_nombre constraint and drop both partial indexes."""
    op.execute("DROP INDEX IF EXISTS ix_ingrediente_es_alergeno")
    op.execute("DROP INDEX IF EXISTS ix_ingrediente_nombre_activo")
    op.create_unique_constraint("uq_ingrediente_nombre", "ingrediente", ["nombre"])
