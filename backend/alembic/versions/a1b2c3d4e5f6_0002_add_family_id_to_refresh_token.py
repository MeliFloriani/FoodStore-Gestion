"""0002_add_family_id_to_refresh_token

auth-refresh-logout-rbac-me: Adds family_id UUID NOT NULL to refresh_token table.
This column groups refresh tokens by family lineage to enable replay-attack detection
and family-scoped revocation (D-07-A, D-07-C).

server_default=gen_random_uuid() backfills existing rows in dev/test environments.
PostgreSQL >= 13 required (gen_random_uuid() is built-in since PG 13).

Revision ID: a1b2c3d4e5f6
Revises: 6ebe5e787bdd
Create Date: 2026-05-16 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "6ebe5e787bdd"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add family_id UUID NOT NULL column to refresh_token table.

    Uses server_default=gen_random_uuid() to backfill any existing rows
    in dev/test environments. PostgreSQL >= 13 is required.
    """
    op.add_column(
        "refresh_token",
        sa.Column(
            "family_id",
            sa.UUID(),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
    )
    op.create_index(
        op.f("ix_refresh_token_family_id"),
        "refresh_token",
        ["family_id"],
        unique=False,
    )


def downgrade() -> None:
    """Remove family_id column and its index from refresh_token table."""
    op.drop_index(
        op.f("ix_refresh_token_family_id"),
        table_name="refresh_token",
    )
    op.drop_column("refresh_token", "family_id")
