"""
DireccionEntregaRepository — data-access layer for the DireccionEntrega entity.

Change 14: delivery-addresses-management.

Extends BaseRepository[DireccionEntrega] with address-specific methods:
  - get_activos_por_usuario(): list active addresses for a user
  - get_by_id_and_usuario(): get address by id + ownership check
  - count_activos_por_usuario(): count active addresses for a user
  - limpiar_principal(): clear es_principal=True for all active user addresses
  - set_principal(): set es_principal=True for a specific address
  - get_mas_reciente_activa(): get most recently created active address (for auto-promote)

All methods use ORM-based queries via session.execute() + select().
Flush-only contract: inherited from BaseRepository.
No business logic — no HTTP exceptions — no commit/rollback.

UPDATE operations use ORM (setattr + flush) so that the onupdate=now() hook
on Base.updated_at fires automatically, as per spec requirement.
"""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.address import DireccionEntrega
from app.repositories.base import BaseRepository


class DireccionEntregaRepository(BaseRepository[DireccionEntrega]):
    """Repository for the DireccionEntrega entity with ownership-scoped methods."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(DireccionEntrega, session)

    # -------------------------------------------------------------------------
    # Read queries
    # -------------------------------------------------------------------------

    async def get_activos_por_usuario(
        self, usuario_id: uuid.UUID
    ) -> list[DireccionEntrega]:
        """Return all active (non-soft-deleted) addresses for a user.

        Args:
            usuario_id: UUID of the user to query.

        Returns:
            List of active DireccionEntrega instances for the user.
        """
        stmt = select(DireccionEntrega).where(
            DireccionEntrega.usuario_id == usuario_id,
            self._active_filter(),
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_id_and_usuario(
        self, id: uuid.UUID, usuario_id: uuid.UUID
    ) -> DireccionEntrega | None:
        """Return address by id + ownership, or None if not found / not owned.

        Does NOT raise an exception — returns None if:
          - The address doesn't exist.
          - The address belongs to a different user.
          - The address is soft-deleted.

        Args:
            id: UUID of the address to look up.
            usuario_id: UUID of the user that must own the address.

        Returns:
            DireccionEntrega instance if found and owned by usuario_id, else None.
        """
        stmt = select(DireccionEntrega).where(
            DireccionEntrega.id == id,
            DireccionEntrega.usuario_id == usuario_id,
            self._active_filter(),
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def count_activos_por_usuario(self, usuario_id: uuid.UUID) -> int:
        """Return the count of active addresses for a user.

        Args:
            usuario_id: UUID of the user to count for.

        Returns:
            Integer count of active (non-soft-deleted) addresses.
        """
        stmt = (
            select(func.count())
            .select_from(DireccionEntrega)
            .where(
                DireccionEntrega.usuario_id == usuario_id,
                self._active_filter(),
            )
        )
        result = await self.session.execute(stmt)
        return int(result.scalar() or 0)

    async def get_mas_reciente_activa(
        self, usuario_id: uuid.UUID
    ) -> DireccionEntrega | None:
        """Return the most recently created active address for a user.

        Used by the service to auto-promote a new principal after the current
        principal is soft-deleted.

        Args:
            usuario_id: UUID of the user.

        Returns:
            The active DireccionEntrega with the most recent created_at, or None.
        """
        stmt = (
            select(DireccionEntrega)
            .where(
                DireccionEntrega.usuario_id == usuario_id,
                self._active_filter(),
            )
            .order_by(DireccionEntrega.created_at.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    # -------------------------------------------------------------------------
    # Write queries (ORM-based to trigger updated_at onupdate hook)
    # -------------------------------------------------------------------------

    async def limpiar_principal(self, usuario_id: uuid.UUID) -> None:
        """Set es_principal=False for all active addresses of a user.

        Iterates over all active addresses with es_principal=True and sets them
        to False via ORM (not raw SQL) so that the onupdate hook on updated_at
        fires automatically (Base.updated_at sa_column_kwargs onupdate).

        This is a defensive operation — called before setting a new principal
        to ensure the partial unique index constraint is satisfied.

        Args:
            usuario_id: UUID of the user whose principal flag should be cleared.
        """
        stmt = select(DireccionEntrega).where(
            DireccionEntrega.usuario_id == usuario_id,
            DireccionEntrega.es_principal.is_(True),  # type: ignore[union-attr]
            self._active_filter(),
        )
        result = await self.session.execute(stmt)
        addresses = result.scalars().all()
        for addr in addresses:
            addr.es_principal = False
        if addresses:
            await self.session.flush()

    async def set_principal(self, id: uuid.UUID) -> None:
        """Set es_principal=True for the address with the given id.

        Uses ORM (not raw SQL) so the onupdate hook on updated_at fires.

        Args:
            id: UUID of the address to mark as principal.
        """
        stmt = select(DireccionEntrega).where(DireccionEntrega.id == id)
        result = await self.session.execute(stmt)
        addr = result.scalars().first()
        if addr is not None:
            addr.es_principal = True
            await self.session.flush()
