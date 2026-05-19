"""
CatalogPublicService — stateless business logic for the public catalog API.

Architectural rules:
  - session.commit() is NEVER called here — UnitOfWork owns the transaction.
  - All DB access goes through UnitOfWork: uow.productos and uow.ingredientes.
  - NEVER uses model_validate(orm_obj) for ProductoPublicoRead or IngredientePublicoRead.
    Always uses _to_publico_read() and _to_publico_detalle() helper methods.
  - Raises NotFoundError (404) when a product is hidden or not found.
  - Raises AppValidationError (422) for invalid excluir_alergenos values.

Error codes raised:
  - PRODUCT_NOT_FOUND (404) — product not visible (hidden, soft-deleted, or non-existent)
  - INVALID_ALLERGEN_IDS (422) — excluir_alergenos contains non-UUID or > 20 IDs
"""

from __future__ import annotations

import math
import uuid
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID

from app.core.exceptions import AppValidationError, NotFoundError
from app.schemas.catalog_public import (
    CatalogProductosQuery,
    CategoriaPublicaRead,
    IngredienteAlergenicoListResponse,
    IngredientePublicoRead,
    PaginatedCatalogProductos,
    ProductoPublicoDetalleRead,
    ProductoPublicoRead,
)

if TYPE_CHECKING:
    from app.core.uow import UnitOfWork
    from app.models.catalog import Producto


class CatalogPublicService:
    """Stateless service for public catalog read operations.

    All methods are @staticmethod — no per-instance state.
    Receives UnitOfWork as a parameter for every operation.

    This service is intentionally minimal and has NO mutation methods.
    It enforces the public visibility rule through repository methods.
    """

    @staticmethod
    async def list_catalog(
        uow: "UnitOfWork",
        filters: CatalogProductosQuery,
    ) -> PaginatedCatalogProductos:
        """Return a paginated list of publicly visible products.

        Validates and parses excluir_alergenos before calling the repository.
        Applies public visibility rule (disponible=true AND deleted_at IS NULL).

        Args:
            uow: UnitOfWork providing uow.productos.list_public().
            filters: CatalogProductosQuery with pagination and filter params.

        Returns:
            PaginatedCatalogProductos with items, total, page, size, pages.

        Raises:
            AppValidationError(code="INVALID_ALLERGEN_IDS"):
                if excluir_alergenos contains non-UUID values or > 20 IDs.
        """
        parsed_alergenos = CatalogPublicService._parse_excluir_alergenos(
            filters.excluir_alergenos
        )

        items, total = await uow.productos.list_public(
            filters=filters,
            parsed_alergenos=parsed_alergenos,
        )

        pages = math.ceil(total / filters.size) if filters.size > 0 else 0

        return PaginatedCatalogProductos(
            items=[CatalogPublicService._to_publico_read(p) for p in items],
            total=total,
            page=filters.page,
            size=filters.size,
            pages=pages,
        )

    @staticmethod
    async def get_catalog_detail(
        uow: "UnitOfWork",
        producto_id: uuid.UUID,
    ) -> ProductoPublicoDetalleRead:
        """Return full product detail with relations for the public detail endpoint.

        Args:
            uow: UnitOfWork providing uow.productos.get_public_by_id().
            producto_id: UUID of the product to retrieve.

        Returns:
            ProductoPublicoDetalleRead with categorias and ingredientes.

        Raises:
            NotFoundError(code="PRODUCT_NOT_FOUND"):
                if product is not found, soft-deleted, or disponible=false.
        """
        product = await uow.productos.get_public_by_id(producto_id)
        if product is None:
            raise NotFoundError(
                f"Producto {producto_id} no encontrado o no disponible",
                code="PRODUCT_NOT_FOUND",
            )
        return CatalogPublicService._to_publico_detalle(product)

    @staticmethod
    async def list_alergenos(
        uow: "UnitOfWork",
    ) -> IngredienteAlergenicoListResponse:
        """Return all active allergen ingredients for public display.

        Used by GET /api/v1/catalog/ingredientes-alergenos (no auth required).
        Delegates to uow.ingredientes.list_public_alergenos().

        Args:
            uow: UnitOfWork providing uow.ingredientes.list_public_alergenos().

        Returns:
            IngredienteAlergenicoListResponse with items and total.
        """
        ingredients = await uow.ingredientes.list_public_alergenos()
        items = [
            IngredientePublicoRead(
                ingrediente_id=i.id,
                nombre=i.nombre,
                es_alergeno=True,  # guaranteed by list_public_alergenos query
            )
            for i in ingredients
        ]
        return IngredienteAlergenicoListResponse(items=items, total=len(items))

    @staticmethod
    def _to_publico_read(p: "Producto") -> ProductoPublicoRead:
        """Map a Producto ORM instance to ProductoPublicoRead.

        NEVER uses model_validate(p) — tiene_stock does not exist on the ORM model.
        Manually sets tiene_stock = p.stock_cantidad > 0.

        Args:
            p: Producto ORM instance.

        Returns:
            ProductoPublicoRead with tiene_stock derived from stock_cantidad.
        """
        return ProductoPublicoRead(
            id=p.id,
            nombre=p.nombre,
            descripcion=p.descripcion,
            imagen_url=p.imagen_url,
            precio_base=Decimal(str(p.precio_base)),
            disponible=p.disponible,
            tiene_stock=p.stock_cantidad > 0,
        )

    @staticmethod
    def _to_publico_detalle(p: "Producto") -> ProductoPublicoDetalleRead:
        """Map a Producto ORM instance (with loaded relations) to ProductoPublicoDetalleRead.

        Relations must be pre-loaded via selectinload (done by get_public_by_id).
        Maps ProductoCategoria pivots to CategoriaPublicaRead.
        Maps ProductoIngrediente pivots to IngredientePublicoRead, explicitly setting
        ingrediente_id=pivot.ingrediente.id to avoid any ORM auto-resolution issues.

        Filters out pivots with soft-deleted related entities.

        Args:
            p: Producto ORM instance with producto_categorias and producto_ingredientes loaded.

        Returns:
            ProductoPublicoDetalleRead with mapped categorias and ingredientes.
        """
        categorias = [
            CategoriaPublicaRead(
                id=pc.categoria.id,
                nombre=pc.categoria.nombre,
            )
            for pc in p.producto_categorias
            if pc.categoria is not None and pc.categoria.deleted_at is None
        ]

        ingredientes = [
            IngredientePublicoRead(
                ingrediente_id=pi.ingrediente.id,
                nombre=pi.ingrediente.nombre,
                es_alergeno=pi.ingrediente.es_alergeno,
            )
            for pi in p.producto_ingredientes
            if pi.ingrediente is not None and pi.ingrediente.deleted_at is None
        ]

        return ProductoPublicoDetalleRead(
            id=p.id,
            nombre=p.nombre,
            descripcion=p.descripcion,
            imagen_url=p.imagen_url,
            precio_base=Decimal(str(p.precio_base)),
            disponible=p.disponible,
            tiene_stock=p.stock_cantidad > 0,
            categorias=categorias,
            ingredientes=ingredientes,
        )

    @staticmethod
    def _parse_excluir_alergenos(excluir_alergenos: str | None) -> list[UUID] | None:
        """Parse and validate the excluir_alergenos query parameter.

        Rules:
        - None or empty/whitespace-only string → return None (no filter applied)
        - Non-empty string → split on comma, strip whitespace
        - Each part must be a valid UUID string (raises AppValidationError if not)
        - Deduplicate IDs preserving order
        - Cap at 20 IDs (raises AppValidationError if exceeded)

        Args:
            excluir_alergenos: Raw comma-separated UUID string from query params.

        Returns:
            Deduplicated list of UUID ingredient IDs, or None if no filter.

        Raises:
            AppValidationError(code="INVALID_ALLERGEN_IDS"):
                if any value is not a valid UUID, or if > 20 unique IDs provided.
        """
        if excluir_alergenos is None:
            return None

        stripped = excluir_alergenos.strip()
        if not stripped:
            return None

        parts = [part.strip() for part in stripped.split(",")]
        ids: list[UUID] = []

        for part in parts:
            if not part:
                # Empty part from trailing comma — skip
                continue
            try:
                ids.append(UUID(part))
            except ValueError:
                raise AppValidationError(
                    f"'{part}' is not a valid UUID ingredient ID",
                    code="INVALID_ALLERGEN_IDS",
                    status_code=422,
                )

        # Deduplicate while preserving order
        seen: set[UUID] = set()
        unique_ids = [x for x in ids if not (x in seen or seen.add(x))]  # type: ignore[func-returns-value]

        if len(unique_ids) > 20:
            raise AppValidationError(
                f"excluir_alergenos accepts at most 20 ingredient IDs (got {len(unique_ids)})",
                code="INVALID_ALLERGEN_IDS",
                status_code=422,
            )

        return unique_ids if unique_ids else None
