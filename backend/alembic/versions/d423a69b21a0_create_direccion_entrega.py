"""create_direccion_entrega

Revision ID: d423a69b21a0
Revises: a2b3c4d5e6f7
Create Date: 2026-05-20 00:00:00.000000

Migration 0007 — Correct and complete the direccion_entrega table.

Change 14 (delivery-addresses-management) corrections to the table that was
partially created by a prior migration:
  - ciudad and provincia changed to nullable (spec defines them as NULL).
  - codigo_postal type changed from VARCHAR(20) to VARCHAR(10) (spec: max 10).
  - referencia field added as TEXT NULL.
  - FK constraint changed from ON DELETE CASCADE to ON DELETE RESTRICT.
  - Existing lat/lon/etiqueta columns dropped (not in spec).

Indexes added (as required by spec backend-migrations/spec.md):
  - ix_direccion_entrega_usuario_id: standard index for join performance.
  - ix_direccion_entrega_principal_unico: partial unique index guaranteeing
    only one active principal per user (WHERE es_principal AND deleted_at IS NULL).
    Created via op.execute() — Alembic has no native API for partial indexes.

down_revision: 'a2b3c4d5e6f7' — hash of migration 0006_add_catalog_public_indices
"""

from __future__ import annotations

import sqlalchemy as sa
import sqlmodel.sql.sqltypes
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d423a69b21a0"
down_revision: str = "a2b3c4d5e6f7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Correct direccion_entrega table structure per Change 14 spec.

    Steps:
    1. Add referencia column (TEXT NULL).
    2. Make ciudad and provincia nullable.
    3. Change codigo_postal length from 20 to 10.
    4. Drop old FK (CASCADE) and recreate with RESTRICT.
    5. Drop stale columns (latitud, longitud, etiqueta) not in spec.
    6. Add standard index ix_direccion_entrega_usuario_id.
    7. Add partial unique index ix_direccion_entrega_principal_unico.
    """
    # 1. Add referencia column
    op.add_column(
        "direccion_entrega",
        sa.Column("referencia", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    )

    # 2. Make ciudad and provincia nullable
    op.alter_column(
        "direccion_entrega",
        "ciudad",
        existing_type=sa.VARCHAR(length=100),
        nullable=True,
    )
    op.alter_column(
        "direccion_entrega",
        "provincia",
        existing_type=sa.VARCHAR(length=100),
        nullable=True,
    )

    # 3. Change codigo_postal from VARCHAR(20) to VARCHAR(10)
    op.alter_column(
        "direccion_entrega",
        "codigo_postal",
        existing_type=sa.VARCHAR(length=20),
        type_=sqlmodel.sql.sqltypes.AutoString(length=10),
        existing_nullable=True,
    )

    # 4. Drop old CASCADE FK and recreate with RESTRICT
    op.drop_constraint(
        op.f("fk_direccion_entrega_usuario_id_usuario"),
        "direccion_entrega",
        type_="foreignkey",
    )
    op.create_foreign_key(
        op.f("fk_direccion_entrega_usuario_id_usuario"),
        "direccion_entrega",
        "usuario",
        ["usuario_id"],
        ["id"],
        ondelete="RESTRICT",
    )

    # 5. Drop stale columns not in spec (latitud, longitud, etiqueta)
    # Use raw SQL with DO $$ block to conditionally drop — avoids aborting the
    # transaction in envs where these columns don't exist (e.g. test DB).
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'direccion_entrega' AND column_name = 'longitud'
            ) THEN
                ALTER TABLE direccion_entrega DROP COLUMN longitud;
            END IF;
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'direccion_entrega' AND column_name = 'etiqueta'
            ) THEN
                ALTER TABLE direccion_entrega DROP COLUMN etiqueta;
            END IF;
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'direccion_entrega' AND column_name = 'latitud'
            ) THEN
                ALTER TABLE direccion_entrega DROP COLUMN latitud;
            END IF;
        END $$;
    """)

    # 6. Standard index for JOIN performance on usuario_id
    op.create_index(
        "ix_direccion_entrega_usuario_id",
        "direccion_entrega",
        ["usuario_id"],
    )

    # 7. Partial unique index — one active principal per user
    # op.execute() is required; Alembic has no native API for partial indexes.
    op.execute(
        "CREATE UNIQUE INDEX ix_direccion_entrega_principal_unico "
        "ON direccion_entrega (usuario_id) "
        "WHERE es_principal AND deleted_at IS NULL"
    )


def downgrade() -> None:
    """Revert Change 14 corrections to direccion_entrega table.

    Drops indexes first, then reverts column changes.
    """
    # Drop partial unique index first (explicit for clarity — also dropped by DROP TABLE)
    op.execute("DROP INDEX IF EXISTS ix_direccion_entrega_principal_unico")

    # Drop standard index
    op.drop_index("ix_direccion_entrega_usuario_id", table_name="direccion_entrega")

    # Restore stale columns (reverse of upgrade step 5)
    op.add_column(
        "direccion_entrega",
        sa.Column("latitud", sa.NUMERIC(precision=9, scale=6), autoincrement=False, nullable=True),
    )
    op.add_column(
        "direccion_entrega",
        sa.Column("etiqueta", sa.VARCHAR(length=80), autoincrement=False, nullable=True),
    )
    op.add_column(
        "direccion_entrega",
        sa.Column("longitud", sa.NUMERIC(precision=9, scale=6), autoincrement=False, nullable=True),
    )

    # Restore FK to CASCADE
    op.drop_constraint(
        op.f("fk_direccion_entrega_usuario_id_usuario"),
        "direccion_entrega",
        type_="foreignkey",
    )
    op.create_foreign_key(
        op.f("fk_direccion_entrega_usuario_id_usuario"),
        "direccion_entrega",
        "usuario",
        ["usuario_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # Restore codigo_postal to VARCHAR(20)
    op.alter_column(
        "direccion_entrega",
        "codigo_postal",
        existing_type=sqlmodel.sql.sqltypes.AutoString(length=10),
        type_=sa.VARCHAR(length=20),
        existing_nullable=True,
    )

    # Restore provincia and ciudad as NOT NULL
    op.alter_column(
        "direccion_entrega",
        "provincia",
        existing_type=sa.VARCHAR(length=100),
        nullable=False,
    )
    op.alter_column(
        "direccion_entrega",
        "ciudad",
        existing_type=sa.VARCHAR(length=100),
        nullable=False,
    )

    # Drop referencia column
    op.drop_column("direccion_entrega", "referencia")
