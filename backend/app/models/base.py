"""
Abstract base model shared by all domain entities.

IMPORTANT: Import order matters.
  app.db.base must be imported BEFORE declaring any SQLModel class
  to ensure SQLModel.metadata.naming_convention is applied globally
  before Alembic or SQLAlchemy inspects the metadata.
  Correction P-07 / D-12.

Design decisions:
- D-04 / P-06: updated_at uses sa_column_kwargs={"onupdate": ...}.
  Without the onupdate hook, updated_at stays equal to created_at forever.
- Soft delete is implemented via deleted_at + is_deleted property.
  The actual persistence (flush/commit) is the repository's responsibility (Change 04).
- Base is table=False: it's an abstract template, not a database table itself.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlmodel import Field, SQLModel

import app.db.base  # noqa: F401  # must import to apply naming_convention before model declaration


class Base(SQLModel, table=False):
    """Abstract base for all persisted domain entities.

    Provides:
    - UUID primary key (client-generated, avoids sequential ID exposure).
    - created_at: set on INSERT via server_default=func.now() and client default.
    - updated_at: refreshed on every UPDATE via onupdate hook (P-06).
    - deleted_at: None means active; set by soft_delete() to mark as deleted.
    - is_deleted property: convenience accessor for soft-delete state.
    - soft_delete(): mutates deleted_at in memory; caller persists the change.
    """

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        primary_key=True,
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_column_kwargs={"server_default": "now()"},
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        # onupdate is REQUIRED (P-06): without it, updated_at never refreshes on UPDATE.
        sa_column_kwargs={"onupdate": lambda: datetime.now(UTC)},
    )
    deleted_at: datetime | None = Field(default=None)

    @property
    def is_deleted(self) -> bool:
        """Return True if this entity has been soft-deleted."""
        return self.deleted_at is not None

    def soft_delete(self) -> None:
        """Mark this entity as deleted by setting deleted_at to now (UTC).

        This method only mutates the in-memory attribute.
        Persistence (session.flush() / commit) is the caller's responsibility.
        """
        self.deleted_at = datetime.now(UTC)
