"""
Generic base repository providing typed async CRUD operations for all domain entities.

Flush-only contract:
  All write methods (create, update, soft_delete, hard_delete) call session.flush()
  to stage changes within the current transaction. session.commit() is NEVER called
  here — that is the exclusive responsibility of UnitOfWork (core/uow.py).

Soft-delete two-step pattern:
  1. Call entity.soft_delete() to mutate deleted_at in memory (via Base.soft_delete()).
  2. Call await session.flush() to propagate the mutation to the DB within the
     current transaction — without committing.
  Any get_by_id / list_all / count call without include_deleted=True will apply
  a "deleted_at IS NULL" filter automatically.

Session injection invariant:
  Repositories receive AsyncSession via constructor from UnitOfWork.
  They MUST NOT create sessions, call Depends(get_session), or import from
  app.db.session.
"""

from __future__ import annotations

import uuid
from typing import Any, Generic, TypeVar

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from app.models.base import Base

T = TypeVar("T", bound=Base)

# Columns that are managed exclusively by the ORM / database hooks.
# These are silently ignored in update(data) and filters to prevent:
#   - Soft-delete resurrection via data={'deleted_at': None}
#   - PK reassignment via data={'id': ...}
#   - Timestamp tampering via data={'created_at': ...}
PROTECTED_COLUMNS: frozenset[str] = frozenset(
    {"id", "created_at", "updated_at", "deleted_at"}
)


class BaseRepository(Generic[T]):
    """Typed generic data-access layer for all SQLModel entities.

    Usage:
        class UsuarioRepository(BaseRepository[Usuario]):
            def __init__(self, session: AsyncSession) -> None:
                super().__init__(Usuario, session)

    All methods that modify data call session.flush() only — never session.commit().
    Commit authority belongs exclusively to UnitOfWork.
    """

    def __init__(self, model: type[T], session: AsyncSession) -> None:
        """Initialise the repository with a model class and an injected session.

        Args:
            model: The SQLModel entity class (e.g. Usuario, Rol).
            session: AsyncSession provided by UnitOfWork.__aenter__.
                     The repository holds a reference to this session but never
                     creates or closes it.
        """
        self.model = model
        self.session = session

    # -------------------------------------------------------------------------
    # Helper
    # -------------------------------------------------------------------------

    def _active_filter(self) -> ColumnElement[bool]:
        """Return the SQLAlchemy column expression for 'deleted_at IS NULL'.

        Reusable in custom queries on concrete repositories to prevent R-04
        (soft-delete filter forgotten on custom queries).

        Example:
            stmt = select(Producto).where(
                self._active_filter(),
                Producto.categoria_id == categoria_id,
            )
        """
        col: ColumnElement[Any] = self.model.deleted_at  # type: ignore[assignment]
        return col.is_(None)

    # -------------------------------------------------------------------------
    # Read
    # -------------------------------------------------------------------------

    async def get_by_id(
        self,
        id: uuid.UUID,
        include_deleted: bool = False,
    ) -> T | None:
        """Return the entity with the given UUID, or None if not found.

        By default, soft-deleted entities (deleted_at IS NOT NULL) are treated
        as non-existent and return None. Pass include_deleted=True to retrieve them.

        Args:
            id: Primary key UUID to look up.
            include_deleted: If True, return the entity even if soft-deleted.

        Returns:
            The entity instance, or None if not found / soft-deleted.
        """
        stmt = select(self.model).where(self.model.id == id)  # type: ignore[arg-type]
        if not include_deleted:
            stmt = stmt.where(self._active_filter())
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def list_all(
        self,
        skip: int = 0,
        limit: int = 100,
        filters: dict[str, Any] | None = None,
        include_deleted: bool = False,
    ) -> list[T]:
        """Return a paginated list of entities matching the given filters.

        Soft-deleted records are excluded by default. Use include_deleted=True
        to include them.

        Filter contract:
          - filters supports only equality comparisons: {column_name: exact_value}
          - PROTECTED_COLUMNS keys are silently ignored
          - Unknown columns raise ValueError

        Args:
            skip: Number of records to skip (offset).
            limit: Maximum number of records to return.
            filters: Optional dict of {column_name: exact_value} equality filters.
            include_deleted: If True, include soft-deleted records in results.

        Returns:
            List of matching entity instances.

        Raises:
            ValueError: If filters contains a column not present on the model.
        """
        stmt = select(self.model)
        if not include_deleted:
            stmt = stmt.where(self._active_filter())
        if filters:
            stmt = self._apply_filters(stmt, filters)
        stmt = stmt.offset(skip).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count(
        self,
        filters: dict[str, Any] | None = None,
        include_deleted: bool = False,
    ) -> int:
        """Return the count of entities matching the given filters.

        Args:
            filters: Optional dict of {column_name: exact_value} equality filters.
            include_deleted: If True, count includes soft-deleted records.

        Returns:
            Integer count of matching rows.

        Raises:
            ValueError: If filters contains a column not present on the model.
        """
        stmt = select(func.count()).select_from(self.model)
        if not include_deleted:
            stmt = stmt.where(self._active_filter())
        if filters:
            stmt = self._apply_filters(stmt, filters)
        result = await self.session.execute(stmt)
        return int(result.scalar() or 0)

    # -------------------------------------------------------------------------
    # Write
    # -------------------------------------------------------------------------

    async def create(self, obj: T) -> T:
        """Persist a new entity by adding it to the session and flushing.

        session.flush() is called to obtain any server-side defaults (e.g. timestamps
        generated by the DB) without committing the transaction.
        session.commit() is NOT called — that is the UoW's responsibility.

        Args:
            obj: A new entity instance (not yet in the session).

        Returns:
            The same entity after flush (with server-side defaults populated).
        """
        self.session.add(obj)
        await self.session.flush()
        return obj

    async def update(
        self,
        id: uuid.UUID,
        data: dict[str, Any],
    ) -> T | None:
        """Apply the given dict of field updates to an active entity.

        PROTECTED_COLUMNS (id, created_at, updated_at, deleted_at) are silently
        skipped to prevent:
          - Soft-delete resurrection via {'deleted_at': None}
          - PK reassignment via {'id': new_uuid}
          - Timestamp tampering via {'created_at': ...}

        updated_at is refreshed automatically by the SQLAlchemy onupdate hook
        defined in Base — never via user data.

        Args:
            id: UUID of the entity to update.
            data: Dict of {field_name: value} pairs to apply.
                Protected keys are ignored.

        Returns:
            The updated entity after flush, or None if not found / soft-deleted.
        """
        entity = await self.get_by_id(id)
        if entity is None:
            return None
        for key, value in data.items():
            if key in PROTECTED_COLUMNS:
                continue
            setattr(entity, key, value)
        await self.session.flush()
        return entity

    async def soft_delete(self, id: uuid.UUID) -> bool:
        """Mark the entity as deleted by setting deleted_at = now(UTC).

        Two-step pattern:
          1. Call entity.soft_delete() to mutate deleted_at in memory.
          2. Call session.flush() to stage the mutation within the transaction.

        session.commit() is NOT called.

        This method fetches the entity bypassing the soft-delete filter
        (include_deleted=True) to allow soft-deleting an already-soft-deleted
        entity if needed, and to correctly return False for non-existent entities.

        Args:
            id: UUID of the entity to soft-delete.

        Returns:
            True if the entity was found and soft-deleted, False if not found.
        """
        entity = await self.get_by_id(id, include_deleted=True)
        if entity is None:
            return False
        entity.soft_delete()
        await self.session.flush()
        return True

    async def hard_delete(self, id: uuid.UUID) -> bool:
        """Remove the entity row from the database entirely.

        Reserved for admin operations and test cleanup. In production business
        logic, soft_delete should be preferred.

        Args:
            id: UUID of the entity to permanently delete (active or soft-deleted).

        Returns:
            True if the entity was found and deleted, False if not found.
        """
        entity = await self.get_by_id(id, include_deleted=True)
        if entity is None:
            return False
        await self.session.delete(entity)
        await self.session.flush()
        return True

    # -------------------------------------------------------------------------
    # Internal helpers
    # -------------------------------------------------------------------------

    def _apply_filters(self, stmt: Select[Any], filters: dict[str, Any]) -> Select[Any]:
        """Apply equality filters from a dict to a SQLAlchemy select statement.

        PROTECTED_COLUMNS are silently ignored.
        Columns not present on the model raise ValueError.

        Args:
            stmt: SQLAlchemy select statement to augment.
            filters: Dict of {column_name: exact_value} equality filters.

        Returns:
            The modified statement with WHERE clauses applied.

        Raises:
            ValueError: If filters contains a column not present on the model.
        """
        for column_name, value in filters.items():
            if column_name in PROTECTED_COLUMNS:
                continue
            col = getattr(self.model, column_name, None)
            if col is None:
                raise ValueError(f"unknown filter column: {column_name}")
            stmt = stmt.where(col == value)
        return stmt
