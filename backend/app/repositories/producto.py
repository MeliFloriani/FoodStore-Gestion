"""
ProductoRepository — data-access layer for the Producto entity.

Extends BaseRepository[Producto] with product-specific methods:
  - list_paginated(): paginated listing with filters (disponible, search, categoria_id)
  - get_with_relations(): load product with M2M relationships (selectinload anti-N+1)
  - set_categorias(): replace-all category associations (atomic within UoW session)
  - add_ingrediente(): insert ProductoIngrediente pivot
  - remove_ingrediente(): hard-delete ProductoIngrediente pivot
  - get_ingredientes(): list ingredients for a product (with selectinload)
  - decrement_stock(): atomic UPDATE WHERE stock_cantidad >= delta RETURNING

Flush-only contract: inherited from BaseRepository.
All methods use session.execute() with SQLAlchemy select/update/delete expressions.
session.commit() is NEVER called here — UnitOfWork owns the transaction.

Loading strategy (anti-N+1):
  - Producto.producto_categorias uses lazy="noload" → MUST use explicit selectinload.
  - Producto.producto_ingredientes uses lazy="noload" → MUST use explicit selectinload.
  - Pivot back-refs (categoria, ingrediente) use lazy="selectin" — loaded automatically
    when the pivot is fetched, but explicit nested selectinload takes precedence.
"""

from __future__ import annotations

import math
import uuid
from typing import TYPE_CHECKING

from sqlalchemy import delete, exists, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.catalog import (
    Producto,
    ProductoCategoria,
    ProductoIngrediente,
)
from app.repositories.base import BaseRepository

if TYPE_CHECKING:
    from app.schemas.catalog_public import CatalogProductosQuery


class ProductoRepository(BaseRepository[Producto]):
    """Repository for the Producto entity with product-specific queries."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Producto, session)

    async def list_paginated(
        self,
        page: int,
        size: int,
        categoria_id: uuid.UUID | None = None,
        disponible: bool | None = None,
        search: str | None = None,
    ) -> tuple[list[Producto], int]:
        """Return (items, total) for paginated product listing.

        Filters applied:
          - deleted_at IS NULL (always — soft-delete exclusion)
          - categoria_id: INNER JOIN with producto_categoria if provided
          - disponible: exact match if not None
          - search: ILIKE '%search%' on nombre if provided

        Args:
            page: Page number (1-based).
            size: Number of items per page.
            categoria_id: Optional filter to only products in this category.
            disponible: Optional filter by availability flag.
            search: Optional ILIKE substring search on nombre.

        Returns:
            Tuple of (list of Producto, total count).
        """
        skip = (page - 1) * size

        # Base query — active products only
        stmt = select(Producto).where(self._active_filter())
        count_stmt = select(func.count()).select_from(Producto).where(self._active_filter())

        # Filter by categoria_id via JOIN
        if categoria_id is not None:
            stmt = stmt.join(
                ProductoCategoria,
                ProductoCategoria.producto_id == Producto.id,
            ).where(ProductoCategoria.categoria_id == categoria_id)
            count_stmt = count_stmt.join(
                ProductoCategoria,
                ProductoCategoria.producto_id == Producto.id,
            ).where(ProductoCategoria.categoria_id == categoria_id)

        # Filter by disponible
        if disponible is not None:
            stmt = stmt.where(Producto.disponible == disponible)
            count_stmt = count_stmt.where(Producto.disponible == disponible)

        # Filter by search (ILIKE '%search%' on nombre)
        if search is not None:
            pattern = f"%{search}%"
            stmt = stmt.where(Producto.nombre.ilike(pattern))  # type: ignore[union-attr]
            count_stmt = count_stmt.where(Producto.nombre.ilike(pattern))  # type: ignore[union-attr]

        # Execute count
        count_result = await self.session.execute(count_stmt)
        total = int(count_result.scalar() or 0)

        # Execute paginated query (no relations — listado is compact)
        stmt = stmt.offset(skip).limit(size)
        result = await self.session.execute(stmt)
        items = list(result.scalars().all())

        return items, total

    async def get_with_relations(self, producto_id: uuid.UUID) -> Producto | None:
        """Load product with M2M relationships using selectinload (anti-N+1).

        Loads:
          - producto_categorias → categoria (nested selectinload)
          - producto_ingredientes → ingrediente (nested selectinload)

        Both Producto.producto_categorias and Producto.producto_ingredientes have
        lazy="noload", so this explicit selectinload is REQUIRED. The nested
        selectinload on the pivot back-refs (categoria, ingrediente) takes precedence
        over the lazy="selectin" on those relationships, preventing redundant loads.

        Total query cost: up to 5 queries (1 product + 2 selectinloads for pivots +
        2 selectinloads for nested related entities). Does NOT grow with the number
        of categories or ingredients (anti-N+1 guarantee).

        Args:
            producto_id: UUID of the product to load.

        Returns:
            Producto with relations loaded, or None if not found / soft-deleted.
        """
        stmt = (
            select(Producto)
            .where(Producto.id == producto_id, self._active_filter())
            .options(
                selectinload(Producto.producto_categorias).selectinload(
                    ProductoCategoria.categoria
                ),
                selectinload(Producto.producto_ingredientes).selectinload(
                    ProductoIngrediente.ingrediente
                ),
            )
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def set_categorias(
        self,
        session: AsyncSession,
        producto: Producto,
        categoria_ids: list[uuid.UUID],
    ) -> None:
        """Replace all category associations for a product (replace-all semantics).

        ATOMICITY: This method MUST be called within the same UoW session that
        created/updated the product. The session is shared — any exception during
        INSERT causes rollback of both the DELETE and the INSERT, leaving the
        original categories intact.

        Hard-deletes all existing ProductoCategoria pivots for this product, then
        inserts new ones. The first categoria_id in the list gets es_principal=True;
        all others get es_principal=False.

        If categoria_ids is empty, only the DELETE executes (removes all categories).

        Args:
            session: The shared AsyncSession from the current UoW.
            producto: The Producto ORM instance (must be persisted — id is used).
            categoria_ids: List of Categoria UUIDs to associate. [] removes all.
        """
        # Hard delete all existing pivots for this product
        await session.execute(
            delete(ProductoCategoria).where(
                ProductoCategoria.producto_id == producto.id
            )
        )

        # Insert new pivots
        for i, cat_id in enumerate(categoria_ids):
            pivot = ProductoCategoria(
                producto_id=producto.id,
                categoria_id=cat_id,
                es_principal=(i == 0),  # First entry is the principal category
            )
            session.add(pivot)

        # Flush to propagate within the current transaction (no commit)
        await session.flush()

    async def add_ingrediente(
        self,
        producto_id: uuid.UUID,
        ingrediente_id: uuid.UUID,
        es_removible: bool,
    ) -> ProductoIngrediente:
        """Insert a ProductoIngrediente pivot record.

        Does NOT handle IntegrityError — the caller (service) is responsible for
        catching it and converting it to ConflictError(code="PRODUCT_INGREDIENT_DUPLICATE").

        Args:
            producto_id: UUID of the product.
            ingrediente_id: UUID of the ingredient to associate.
            es_removible: Whether the ingredient can be removed by the customer.

        Returns:
            The newly created ProductoIngrediente pivot instance.

        Raises:
            IntegrityError: If the association already exists (unique constraint violation).
        """
        pivot = ProductoIngrediente(
            producto_id=producto_id,
            ingrediente_id=ingrediente_id,
            es_removible=es_removible,
        )
        self.session.add(pivot)
        await self.session.flush()
        return pivot

    async def remove_ingrediente(
        self,
        producto_id: uuid.UUID,
        ingrediente_id: uuid.UUID,
    ) -> bool:
        """Hard-delete a ProductoIngrediente pivot record.

        Args:
            producto_id: UUID of the product.
            ingrediente_id: UUID of the ingredient to disassociate.

        Returns:
            True if a pivot was found and deleted, False if not found.
        """
        result = await self.session.execute(
            delete(ProductoIngrediente)
            .where(
                ProductoIngrediente.producto_id == producto_id,
                ProductoIngrediente.ingrediente_id == ingrediente_id,
            )
            .returning(ProductoIngrediente.id)
        )
        deleted_row = result.scalars().first()
        await self.session.flush()
        return deleted_row is not None

    async def get_ingredientes(
        self,
        producto_id: uuid.UUID,
    ) -> list[ProductoIngrediente]:
        """Return all ProductoIngrediente pivots for a product with ingrediente loaded.

        Uses selectinload on ProductoIngrediente.ingrediente to avoid N+1.
        Does NOT filter by producto.deleted_at — caller (service) must validate
        the product exists before calling this method.

        Args:
            producto_id: UUID of the product.

        Returns:
            List of ProductoIngrediente instances with .ingrediente relation loaded.
        """
        stmt = (
            select(ProductoIngrediente)
            .where(ProductoIngrediente.producto_id == producto_id)
            .options(selectinload(ProductoIngrediente.ingrediente))
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    # =========================================================================
    # Public catalog methods (Change 12 — catalog-public-browsing)
    # =========================================================================

    def _apply_public_visibility(self, stmt):  # type: ignore[return]
        """Append WHERE disponible=true AND deleted_at IS NULL to a select statement.

        This is the single gate between the full product set and what public
        users can see. Both list_public() and get_public_by_id() MUST call this.

        Args:
            stmt: A SQLAlchemy Select statement.

        Returns:
            The statement with the public visibility filter applied.
        """
        return stmt.where(
            Producto.disponible.is_(True),  # type: ignore[union-attr]
            Producto.deleted_at.is_(None),  # type: ignore[union-attr]
        )

    async def list_public(
        self,
        filters: "CatalogProductosQuery",
        parsed_alergenos: list[uuid.UUID] | None = None,
    ) -> tuple[list[Producto], int]:
        """Return (items, total) for public catalog listing.

        Applies public visibility rule (disponible=true AND deleted_at IS NULL)
        plus all composable filters. Fires exactly 2 SQL statements: 1 COUNT + 1 SELECT.
        Does NOT load categorias or ingredientes — ProductoPublicoRead list schema
        does not include relations.

        Args:
            filters: CatalogProductosQuery with page, size, categoria_id, q, ordenar.
            parsed_alergenos: Pre-parsed list of allergen ingredient UUIDs from the service.
                              If provided and non-empty, applies NOT EXISTS filter.

        Returns:
            Tuple of (list of Producto, total count).
        """
        # Base stmt — apply public visibility always
        stmt = self._apply_public_visibility(select(Producto))
        count_stmt = self._apply_public_visibility(
            select(func.count()).select_from(Producto)
        )

        # Filter by categoria_id via JOIN
        if filters.categoria_id is not None:
            stmt = stmt.join(
                ProductoCategoria,
                ProductoCategoria.producto_id == Producto.id,
            ).where(ProductoCategoria.categoria_id == filters.categoria_id)
            count_stmt = count_stmt.join(
                ProductoCategoria,
                ProductoCategoria.producto_id == Producto.id,
            ).where(ProductoCategoria.categoria_id == filters.categoria_id)

        # Filter by q (ILIKE '%q%' on nombre)
        if filters.q is not None:
            pattern = f"%{filters.q}%"
            stmt = stmt.where(Producto.nombre.ilike(pattern))  # type: ignore[union-attr]
            count_stmt = count_stmt.where(Producto.nombre.ilike(pattern))  # type: ignore[union-attr]

        # Filter by excluir_alergenos: NOT EXISTS sub-query
        if parsed_alergenos:
            not_exists_subq = ~exists().where(
                ProductoIngrediente.producto_id == Producto.id,
                ProductoIngrediente.ingrediente_id.in_(parsed_alergenos),  # type: ignore[union-attr]
            )
            stmt = stmt.where(not_exists_subq)
            count_stmt = count_stmt.where(not_exists_subq)

        # ORDER BY — default: nombre ASC (alphabetical, user-friendly for catalog)
        if filters.ordenar == "nombre":
            stmt = stmt.order_by(Producto.nombre.asc())  # type: ignore[union-attr]
        elif filters.ordenar == "-nombre":
            stmt = stmt.order_by(Producto.nombre.desc())  # type: ignore[union-attr]
        elif filters.ordenar == "precio":
            stmt = stmt.order_by(Producto.precio_base.asc())  # type: ignore[union-attr]
        elif filters.ordenar == "-precio":
            stmt = stmt.order_by(Producto.precio_base.desc())  # type: ignore[union-attr]
        else:
            stmt = stmt.order_by(Producto.nombre.asc())  # type: ignore[union-attr]

        # Execute count first
        count_result = await self.session.execute(count_stmt)
        total = int(count_result.scalar() or 0)

        # Execute paginated data query (no selectinloads — list schema has no relations)
        skip = (filters.page - 1) * filters.size
        stmt = stmt.offset(skip).limit(filters.size)
        result = await self.session.execute(stmt)
        items = list(result.scalars().all())

        return items, total

    async def get_public_by_id(self, producto_id: uuid.UUID) -> Producto | None:
        """Load a public product with M2M relationships.

        Applies public visibility rule: only returns if disponible=true AND deleted_at IS NULL.
        Loads categorias and ingredientes via selectinload (anti-N+1, max 3 queries).

        Args:
            producto_id: UUID of the product to load.

        Returns:
            Producto with relations loaded, or None if not found / hidden / soft-deleted.
        """
        stmt = (
            self._apply_public_visibility(
                select(Producto).where(Producto.id == producto_id)
            )
            .options(
                selectinload(Producto.producto_categorias).selectinload(
                    ProductoCategoria.categoria
                ),
                selectinload(Producto.producto_ingredientes).selectinload(
                    ProductoIngrediente.ingrediente
                ),
            )
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def decrement_stock(
        self,
        producto_id: uuid.UUID,
        delta: int,
    ) -> Producto | None:
        """Atomically decrement stock_cantidad using UPDATE WHERE.

        Uses UPDATE ... WHERE stock_cantidad >= :delta to implement optimistic
        concurrency control. If no row is updated (stock insufficient or product
        not found / soft-deleted), returns None.

        This is suitable for single-product stock adjustments from the admin panel.
        For checkout (Change 17), use SELECT ... FOR UPDATE instead to serialize
        access across multiple products in a single transaction.

        Args:
            producto_id: UUID of the product to decrement.
            delta: Amount to decrement from stock_cantidad (must be > 0).

        Returns:
            Updated Producto instance (with new stock_cantidad), or None if
            the decrement could not be applied (insufficient stock or not found).
        """
        stmt = (
            update(Producto)
            .where(
                Producto.id == producto_id,
                Producto.stock_cantidad >= delta,
                Producto.deleted_at.is_(None),  # type: ignore[union-attr]
            )
            .values(
                stock_cantidad=Producto.stock_cantidad - delta,
                updated_at=func.now(),
            )
            .returning(Producto)
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()
