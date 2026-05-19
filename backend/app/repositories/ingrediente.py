"""
IngredienteRepository — data-access layer for the Ingrediente entity.

Extends BaseRepository[Ingrediente] with ingredient-specific methods:
  - get_by_nombre_active(): SELECT by nombre WHERE deleted_at IS NULL
  - list_active(): list active ingredients with optional es_alergeno filter, ordered by nombre

Flush-only contract: inherited from BaseRepository.
All methods use session.execute() with SQLAlchemy select() expressions.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.catalog import Ingrediente
from app.repositories.base import BaseRepository


class IngredienteRepository(BaseRepository[Ingrediente]):
    """Repository for the Ingrediente entity with ingredient-specific queries."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Ingrediente, session)

    async def get_by_nombre_active(self, nombre: str) -> Ingrediente | None:
        """Return an active ingredient matching the given nombre, or None.

        Filters deleted_at IS NULL to exclude soft-deleted records.
        Used by the service for duplicate-detection (not relied on for
        uniqueness enforcement — the DB partial index is authoritative).

        Args:
            nombre: Exact nombre to look up (case-sensitive).

        Returns:
            The active Ingrediente instance, or None if not found / soft-deleted.
        """
        stmt = (
            select(Ingrediente)
            .where(Ingrediente.nombre == nombre)
            .where(self._active_filter())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def list_active(
        self,
        es_alergeno: bool | None = None,
    ) -> list[Ingrediente]:
        """Return all active ingredients, optionally filtered by es_alergeno.

        Active means deleted_at IS NULL. Results are ordered by nombre ASC.

        Args:
            es_alergeno: If not None, filter to only return ingredients where
                es_alergeno matches this value. If None, return all active.

        Returns:
            List of Ingrediente instances ordered by nombre ASC.
        """
        stmt = select(Ingrediente).where(self._active_filter())

        if es_alergeno is not None:
            stmt = stmt.where(Ingrediente.es_alergeno == es_alergeno)

        stmt = stmt.order_by(Ingrediente.nombre.asc())  # type: ignore[union-attr]

        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_public_alergenos(self) -> list[Ingrediente]:
        """Return all active allergen ingredients ordered by nombre ASC.

        Used by the public catalog endpoint GET /api/v1/catalog/ingredientes-alergenos.
        Filters: es_alergeno=true AND deleted_at IS NULL. Ordered by nombre ASC.

        Returns:
            List of active Ingrediente instances where es_alergeno=true.
        """
        stmt = (
            select(Ingrediente)
            .where(self._active_filter())
            .where(Ingrediente.es_alergeno.is_(True))  # type: ignore[union-attr]
            .order_by(Ingrediente.nombre.asc())  # type: ignore[union-attr]
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
