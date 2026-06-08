"""pago_add_mp_preference_id

Revision ID: c0d1e2f3a4b5
Revises: b1c2d3e4f5a6
Create Date: 2026-05-28 00:00:00.000000

Migration 0011 — Change 19 (payments-mercadopago-integration, Checkout Pro migration).

Adds mp_preference_id column to the pago table to support MercadoPago Checkout Pro.
In Checkout Pro flow, the preference is created first (mp_preference_id is set),
and mp_payment_id stays NULL until the webhook fires after the user pays.

Design decisions:
  - mp_preference_id VARCHAR(100) UNIQUE NULL: MercadoPago preference IDs are globally
    unique. UNIQUE constraint allows efficient lookup and prevents duplicate rows.
  - INDEX ix_pagos_mp_preference_id: supports fast lookup by preference_id if needed.
  - mp_payment_id already nullable (from previous migration); no change needed.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "c0d1e2f3a4b5"
down_revision: str = "b1c2d3e4f5a6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add mp_preference_id column with UNIQUE constraint and index."""

    # Add mp_preference_id column (nullable — existing rows have NULL)
    op.add_column(
        "pago",
        sa.Column(
            "mp_preference_id",
            sa.String(length=100),
            nullable=True,
        ),
    )

    # Create unique constraint on mp_preference_id
    op.create_unique_constraint(
        "uq_pago_mp_preference_id",
        "pago",
        ["mp_preference_id"],
    )

    # Create index for fast lookups
    op.create_index(
        "ix_pago_mp_preference_id",
        "pago",
        ["mp_preference_id"],
    )


def downgrade() -> None:
    """Remove mp_preference_id column, constraint, and index."""

    # Drop index first
    op.drop_index("ix_pago_mp_preference_id", table_name="pago")

    # Drop unique constraint
    op.drop_constraint("uq_pago_mp_preference_id", "pago", type_="unique")

    # Drop column
    op.drop_column("pago", "mp_preference_id")
