"""detalle_pedido_personalizacion_uuid

Revision ID: e5f6a7b8c9d0
Revises: d423a69b21a0
Create Date: 2026-05-20 00:00:00.000000

Migration 0008 — Change detalle_pedido.personalizacion from INTEGER[] to UUID[].

Design decision (Change 17 — order-creation-with-snapshots, D-09 / Nota R-01):
  DetallePedido.personalizacion stores UUIDs of excluded ingredients.
  The original model (Change 03) declared ARRAY(Integer) based on the original
  BIGSERIAL PK convention. The project migrated to UUID-first PKs before Change 17.
  This migration corrects the column type to uuid[] to be consistent with:
    - Ingrediente.id: UUID (inherited from Base)
    - ProductoIngrediente.ingrediente_id: UUID
    - CartItem.personalizacion: string[] (UUID strings) in the frontend cartStore

Conversion strategy:
  - Existing rows with personalizacion IS NULL are unaffected.
  - Existing rows with INTEGER[] values cannot be automatically converted to UUID[]
    without a mapping table. Since Change 03 seeded no orders and Change 17 is the
    first endpoint that creates orders, there should be no existing data.
  - The USING clause attempts text[]::uuid[] conversion. If any non-UUID integer
    values exist, the migration will fail with a cast error — this is intentional
    (fail loudly rather than silently drop data).

down_revision: 'd423a69b21a0' — hash of migration create_direccion_entrega (Change 14)
"""

from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e5f6a7b8c9d0"
down_revision: str = "d423a69b21a0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Change detalle_pedido.personalizacion from integer[] to uuid[].

    Uses op.execute() with ALTER TABLE ... ALTER COLUMN ... TYPE uuid[] USING
    because Alembic's alter_column does not support PostgreSQL ARRAY type changes
    natively.

    The USING clause:
      personalizacion::text[]::uuid[]
    First casts the integer array to text[], then to uuid[]. For NULL values,
    this is a no-op. For any integer values that exist, the cast to uuid[] will
    fail — this is the desired behavior (fail loudly).
    """
    op.execute(
        """
        ALTER TABLE detalle_pedido
        ALTER COLUMN personalizacion
        TYPE uuid[]
        USING personalizacion::text[]::uuid[]
        """
    )


def downgrade() -> None:
    """Revert detalle_pedido.personalizacion from uuid[] back to integer[].

    Uses the same ALTER TABLE pattern. UUIDs cannot be safely cast back to integers
    — if any UUID rows exist, this will fail. In practice, downgrade should only be
    run in development environments before any order data exists.
    """
    op.execute(
        """
        ALTER TABLE detalle_pedido
        ALTER COLUMN personalizacion
        TYPE integer[]
        USING personalizacion::text[]::integer[]
        """
    )
