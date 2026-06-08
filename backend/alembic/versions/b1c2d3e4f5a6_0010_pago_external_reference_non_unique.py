"""pago_external_reference_non_unique

Revision ID: b1c2d3e4f5a6
Revises: e5f6a7b8c9d0
Create Date: 2026-05-26 00:00:00.000000

Migration 0010 — Change 19 (payments-mercadopago-integration).

Drops the UNIQUE constraint on pago.external_reference to allow 1:N Pago per Pedido
(payment retry support — US-048 / D-01). Adds mp_status_detail column and a
composite index for query performance.

Design decisions (D-01):
  - Drop uq_pago_external_reference: allows multiple Pago rows with the same
    external_reference (the pedido UUID), enabling payment retries.
  - idempotency_key UNIQUE is preserved — each payment attempt has a unique key.
  - mp_payment_id UNIQUE is preserved — MP payment IDs are globally unique.
  - mp_status_detail VARCHAR(100) NULL added — stores MP rejection reason codes
    for frontend display (e.g. "cc_rejected_insufficient_amount").
  - ix_pago_pedido_id_created_at: composite index for fast latest-payment queries.

Downgrade strategy:
  - Before re-adding the constraint, check for duplicate external_reference values.
    If duplicates exist, downgrade raises an Exception requiring manual cleanup.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision: str = "b1c2d3e4f5a6"
down_revision: str = "e5f6a7b8c9d0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Drop external_reference UNIQUE constraint; add mp_status_detail; create index."""

    # Drop the UNIQUE constraint on external_reference
    # Naming convention: uq_pago_external_reference
    op.drop_constraint(
        "uq_pago_external_reference",
        "pago",
        type_="unique",
    )

    # Add mp_status_detail column (nullable VARCHAR(100))
    op.add_column(
        "pago",
        sa.Column(
            "mp_status_detail",
            sa.String(length=100),
            nullable=True,
        ),
    )

    # Create composite index on (pedido_id, created_at DESC) for latest-payment queries
    op.create_index(
        "ix_pago_pedido_id_created_at",
        "pago",
        ["pedido_id", sa.text("created_at DESC")],
    )


def downgrade() -> None:
    """Revert: drop index, drop mp_status_detail, re-add UNIQUE constraint.

    Pre-check: if duplicate external_reference rows exist, raise an error.
    Manual cleanup of duplicates is required before downgrade can proceed.
    """
    # Pre-check: ensure no duplicate external_reference rows exist
    result = op.get_bind().execute(
        text(
            "SELECT external_reference, count(*) FROM pago "
            "GROUP BY external_reference HAVING count(*) > 1"
        )
    )
    if result.fetchall():
        raise Exception(
            "Cannot downgrade: duplicate external_references exist. "
            "Manual cleanup required before re-adding the UNIQUE constraint. "
            "Run: SELECT external_reference, count(*) FROM pago "
            "GROUP BY external_reference HAVING count(*) > 1;"
        )

    # Drop the composite index
    op.drop_index("ix_pago_pedido_id_created_at", table_name="pago")

    # Drop mp_status_detail column
    op.drop_column("pago", "mp_status_detail")

    # Re-add the UNIQUE constraint on external_reference
    op.create_unique_constraint(
        "uq_pago_external_reference",
        "pago",
        ["external_reference"],
    )
