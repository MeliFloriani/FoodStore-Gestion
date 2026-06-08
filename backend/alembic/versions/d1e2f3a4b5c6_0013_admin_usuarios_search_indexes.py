"""admin_usuarios_search_indexes

Revision ID: d1e2f3a4b5c6
Revises: c0d1e2f3a4b5
Create Date: 2026-06-02 00:00:00.000000

Migration 0013 — Change 21 (admin-users-management).

Adds pg_trgm GIN indexes on usuario.nombre, usuario.apellido, and usuario.email
to support case-insensitive ILIKE substring search (`%query%`) efficiently.

Design decisions (D-07):
  - GIN pg_trgm indexes support arbitrary substring matching (`%query%`).
  - Pure lower() functional indexes only optimize prefix `LIKE 'query%'` queries.
  - pg_trgm is required for the expected search UX (substring match).
  - CREATE EXTENSION IF NOT EXISTS: idempotent; safe to run on fresh DB.
  - CREATE INDEX IF NOT EXISTS: idempotent; safe to re-run on existing DB.
"""

from __future__ import annotations

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "d1e2f3a4b5c6"
down_revision: str = "c0d1e2f3a4b5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create pg_trgm extension and GIN trigram indexes on usuario columns."""

    # Enable pg_trgm extension (required for gin_trgm_ops operator class)
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    # Trigram index on email for ILIKE substring search
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_usuario_email_trgm "
        "ON usuario USING gin (email gin_trgm_ops)"
    )

    # Trigram index on nombre for ILIKE substring search
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_usuario_nombre_trgm "
        "ON usuario USING gin (nombre gin_trgm_ops)"
    )

    # Trigram index on apellido for ILIKE substring search
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_usuario_apellido_trgm "
        "ON usuario USING gin (apellido gin_trgm_ops)"
    )


def downgrade() -> None:
    """Drop the three GIN trigram indexes (conditionally)."""

    op.execute("DROP INDEX IF EXISTS ix_usuario_apellido_trgm")
    op.execute("DROP INDEX IF EXISTS ix_usuario_nombre_trgm")
    op.execute("DROP INDEX IF EXISTS ix_usuario_email_trgm")

    # Note: we do NOT drop the pg_trgm extension because other indexes or
    # queries may depend on it (e.g. future migrations). The extension is safe
    # to leave installed; it adds no overhead when unused.
