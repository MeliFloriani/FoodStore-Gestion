"""
ProductoService — stateless business logic for the Producto domain.

Architectural rules:
  - session.commit() is NEVER called here — UnitOfWork owns the transaction.
  - All DB access goes through UnitOfWork typed repos: uow.productos, uow.categorias,
    uow.ingredientes.
  - Domain errors raised here are caught by global handlers in app/api/errors.py.
  - The router MUST pass ProductoUpdate Pydantic model instance directly to
    update_producto — NOT model_dump() — to preserve model_fields_set for the
    partial-update sentinel.

Error codes raised:
  - PRODUCT_NOT_FOUND (404)
  - CATEGORY_NOT_FOUND (404)
  - INGREDIENT_NOT_FOUND (404)
  - PRODUCT_INGREDIENT_NOT_FOUND (404)
  - PRODUCT_INGREDIENT_DUPLICATE (409)
  - INSUFFICIENT_STOCK (422) — from decrement_stock
"""

from __future__ import annotations

import math
import uuid

from sqlalchemy.exc import IntegrityError

from app.core.exceptions import AppValidationError, ConflictError, NotFoundError
from app.schemas.categoria import CategoriaRead
from app.schemas.producto import (
    AsociarIngredienteRequest,
    DisponibilidadUpdate,
    PaginatedProductos,
    ProductoCreate,
    ProductoDetail,
    ProductoIngredienteRead,
    ProductoRead,
    ProductoUpdate,
)


class ProductoService:
    """Stateless service for Producto CRUD operations and business rules.

    All methods are @staticmethod — no per-instance state.
    Receives UnitOfWork as a parameter for every operation.
    Mirrors the IngredienteService / CategoriaService pattern exactly.
    """

    @staticmethod
    async def list_productos(
        uow,
        page: int,
        size: int,
        categoria_id: uuid.UUID | None,
        disponible: bool | None,
        search: str | None,
    ) -> PaginatedProductos:
        """Return a paginated list of active products with optional filters.

        Args:
            uow: UnitOfWork providing uow.productos.list_paginated().
            page: 1-based page number.
            size: Items per page.
            categoria_id: Optional category UUID to filter by.
            disponible: Optional availability flag filter.
            search: Optional ILIKE substring search on nombre.

        Returns:
            PaginatedProductos with items, total, page, size, pages.
        """
        items, total = await uow.productos.list_paginated(
            page=page,
            size=size,
            categoria_id=categoria_id,
            disponible=disponible,
            search=search,
        )
        pages = math.ceil(total / size) if size > 0 else 0
        return PaginatedProductos(
            items=[ProductoRead.model_validate(p) for p in items],
            total=total,
            page=page,
            size=size,
            pages=pages,
        )

    @staticmethod
    async def get_producto_detail(
        uow,
        producto_id: uuid.UUID,
    ) -> ProductoDetail:
        """Return full ProductoDetail with categorias and ingredientes loaded.

        Args:
            uow: UnitOfWork providing uow.productos.get_with_relations().
            producto_id: UUID of the product to retrieve.

        Returns:
            ProductoDetail with nested categorias and ingredientes.

        Raises:
            NotFoundError(code="PRODUCT_NOT_FOUND"): if not found or soft-deleted.
        """
        product = await uow.productos.get_with_relations(producto_id)
        if product is None:
            raise NotFoundError(
                f"Producto {producto_id} no encontrado",
                code="PRODUCT_NOT_FOUND",
            )

        # Map M2M relations to read schemas
        categorias = [
            CategoriaRead.model_validate(pc.categoria)
            for pc in product.producto_categorias
            if pc.categoria is not None and pc.categoria.deleted_at is None
        ]
        ingredientes = [
            ProductoIngredienteRead(
                ingrediente_id=pi.ingrediente_id,
                nombre=pi.ingrediente.nombre,
                es_alergeno=pi.ingrediente.es_alergeno,
                es_removible=pi.es_removible,
            )
            for pi in product.producto_ingredientes
            if pi.ingrediente is not None and pi.ingrediente.deleted_at is None
        ]

        return ProductoDetail(
            id=product.id,
            nombre=product.nombre,
            descripcion=product.descripcion,
            imagen_url=product.imagen_url,
            precio_base=product.precio_base,
            stock_cantidad=product.stock_cantidad,
            disponible=product.disponible,
            created_at=product.created_at,
            updated_at=product.updated_at,
            categorias=categorias,
            ingredientes=ingredientes,
        )

    @staticmethod
    async def create_producto(
        uow,
        data: ProductoCreate,
    ) -> ProductoRead:
        """Create a new product with optional category associations.

        Validates all categoria_ids exist before creating the product. If any
        categoria_id does not exist or is soft-deleted, raises NotFoundError
        before any write operation.

        Args:
            uow: UnitOfWork providing uow.productos and uow.categorias.
            data: ProductoCreate schema with product fields and optional categoria_ids.

        Returns:
            ProductoRead for the newly created product.

        Raises:
            NotFoundError(code="CATEGORY_NOT_FOUND"): if any categoria_id is invalid.
        """
        from app.models.catalog import Producto

        # Validate all categoria_ids exist before any write
        if data.categoria_ids:
            for cat_id in data.categoria_ids:
                cat = await uow.categorias.get_by_id(cat_id)
                if cat is None:
                    raise NotFoundError(
                        f"Categoria {cat_id} no encontrada",
                        code="CATEGORY_NOT_FOUND",
                    )

        # Create the product entity
        product = await uow.productos.create(
            Producto(
                nombre=data.nombre,
                descripcion=data.descripcion,
                imagen_url=data.imagen_url,
                precio_base=float(data.precio_base),
                stock_cantidad=data.stock_cantidad,
                disponible=data.disponible,
            )
        )

        # Associate categories if provided
        if data.categoria_ids is not None:
            await uow.productos.set_categorias(uow.session, product, data.categoria_ids)

        return ProductoRead.model_validate(product)

    @staticmethod
    async def update_producto(
        uow,
        producto_id: uuid.UUID,
        data: ProductoUpdate,
    ) -> ProductoRead:
        """Partially update a product using model_fields_set sentinel.

        Only fields present in data.model_fields_set are applied. Fields absent
        from the payload are left at their current DB values.

        IMPORTANT: The router MUST pass the ProductoUpdate Pydantic model instance
        directly — NOT data.model_dump() — to preserve model_fields_set.

        Args:
            uow: UnitOfWork providing uow.productos and uow.categorias.
            producto_id: UUID of the product to update.
            data: ProductoUpdate with model_fields_set sentinel.

        Returns:
            ProductoRead for the updated product.

        Raises:
            NotFoundError(code="PRODUCT_NOT_FOUND"): if product not found.
            NotFoundError(code="CATEGORY_NOT_FOUND"): if any categoria_id is invalid.
        """
        product = await uow.productos.get_by_id(producto_id)
        if product is None:
            raise NotFoundError(
                f"Producto {producto_id} no encontrado",
                code="PRODUCT_NOT_FOUND",
            )

        # Build update dict from model_fields_set (only supplied fields)
        update_data: dict = {}
        for field in data.model_fields_set:
            if field == "categoria_ids":
                continue  # handled separately below
            value = getattr(data, field)
            if field == "precio_base" and value is not None:
                update_data[field] = float(value)
            else:
                update_data[field] = value

        # Apply updates to the entity
        if update_data:
            updated = await uow.productos.update(producto_id, update_data)
        else:
            updated = product

        # Handle categoria_ids if in model_fields_set (sentinel: None → no change; [] → remove all)
        if "categoria_ids" in data.model_fields_set:
            categoria_ids = data.categoria_ids or []
            # Validate all provided categoria_ids exist
            for cat_id in categoria_ids:
                cat = await uow.categorias.get_by_id(cat_id)
                if cat is None:
                    raise NotFoundError(
                        f"Categoria {cat_id} no encontrada",
                        code="CATEGORY_NOT_FOUND",
                    )
            await uow.productos.set_categorias(uow.session, product, categoria_ids)

        return ProductoRead.model_validate(updated or product)

    @staticmethod
    async def delete_producto(
        uow,
        producto_id: uuid.UUID,
    ) -> None:
        """Soft-delete a product.

        Validates existence before soft-deleting (404 on missing product).

        Args:
            uow: UnitOfWork providing uow.productos.
            producto_id: UUID of the product to soft-delete.

        Raises:
            NotFoundError(code="PRODUCT_NOT_FOUND"): if not found or already deleted.
        """
        product = await uow.productos.get_by_id(producto_id)
        if product is None:
            raise NotFoundError(
                f"Producto {producto_id} no encontrado",
                code="PRODUCT_NOT_FOUND",
            )
        await uow.productos.soft_delete(producto_id)

    @staticmethod
    async def set_disponibilidad(
        uow,
        producto_id: uuid.UUID,
        data: DisponibilidadUpdate,
    ) -> ProductoRead:
        """Update only the disponible flag of a product.

        Available to ADMIN and STOCK roles (STOCK cannot change other fields).

        Args:
            uow: UnitOfWork providing uow.productos.
            producto_id: UUID of the product to update.
            data: DisponibilidadUpdate with the new disponible value.

        Returns:
            ProductoRead for the updated product.

        Raises:
            NotFoundError(code="PRODUCT_NOT_FOUND"): if not found.
        """
        product = await uow.productos.get_by_id(producto_id)
        if product is None:
            raise NotFoundError(
                f"Producto {producto_id} no encontrado",
                code="PRODUCT_NOT_FOUND",
            )
        updated = await uow.productos.update(producto_id, {"disponible": data.disponible})
        return ProductoRead.model_validate(updated or product)

    @staticmethod
    async def get_producto_ingredientes(
        uow,
        producto_id: uuid.UUID,
    ) -> list[ProductoIngredienteRead]:
        """Return the ingredient associations for a product.

        MANDATORY: validates product exists BEFORE calling get_ingredientes().
        If only get_ingredientes() were called on a non-existent product, it would
        return [] with HTTP 200 — which would be incorrect (H-03 spec requirement).

        Args:
            uow: UnitOfWork providing uow.productos.
            producto_id: UUID of the product.

        Returns:
            List of ProductoIngredienteRead for all active ingredient associations.

        Raises:
            NotFoundError(code="PRODUCT_NOT_FOUND"): if not found or soft-deleted.
        """
        product = await uow.productos.get_by_id(producto_id)
        if product is None:
            raise NotFoundError(
                f"Producto {producto_id} no encontrado",
                code="PRODUCT_NOT_FOUND",
            )

        pivots = await uow.productos.get_ingredientes(producto_id)
        return [
            ProductoIngredienteRead(
                ingrediente_id=pi.ingrediente_id,
                nombre=pi.ingrediente.nombre,
                es_alergeno=pi.ingrediente.es_alergeno,
                es_removible=pi.es_removible,
            )
            for pi in pivots
            if pi.ingrediente is not None and pi.ingrediente.deleted_at is None
        ]

    @staticmethod
    async def add_ingrediente(
        uow,
        producto_id: uuid.UUID,
        data: AsociarIngredienteRequest,
    ) -> ProductoIngredienteRead:
        """Associate an ingredient with a product.

        Validates both product and ingredient exist before inserting the pivot.
        Catches IntegrityError from duplicate association and converts to ConflictError.

        Args:
            uow: UnitOfWork providing uow.productos and uow.ingredientes.
            producto_id: UUID of the product.
            data: AsociarIngredienteRequest with ingrediente_id and es_removible.

        Returns:
            ProductoIngredienteRead for the newly created association.

        Raises:
            NotFoundError(code="PRODUCT_NOT_FOUND"): if product not found.
            NotFoundError(code="INGREDIENT_NOT_FOUND"): if ingredient not found.
            ConflictError(code="PRODUCT_INGREDIENT_DUPLICATE"): if already associated.
        """
        product = await uow.productos.get_by_id(producto_id)
        if product is None:
            raise NotFoundError(
                f"Producto {producto_id} no encontrado",
                code="PRODUCT_NOT_FOUND",
            )

        ingrediente = await uow.ingredientes.get_by_id(data.ingrediente_id)
        if ingrediente is None:
            raise NotFoundError(
                f"Ingrediente {data.ingrediente_id} no encontrado",
                code="INGREDIENT_NOT_FOUND",
            )

        try:
            pivot = await uow.productos.add_ingrediente(
                producto_id=producto_id,
                ingrediente_id=data.ingrediente_id,
                es_removible=data.es_removible,
            )
        except IntegrityError:
            raise ConflictError(
                "La asociación producto↔ingrediente ya existe",
                code="PRODUCT_INGREDIENT_DUPLICATE",
            )

        return ProductoIngredienteRead(
            ingrediente_id=pivot.ingrediente_id,
            nombre=ingrediente.nombre,
            es_alergeno=ingrediente.es_alergeno,
            es_removible=pivot.es_removible,
        )

    @staticmethod
    async def remove_ingrediente(
        uow,
        producto_id: uuid.UUID,
        ingrediente_id: uuid.UUID,
    ) -> None:
        """Remove an ingredient association from a product.

        Validates product exists before attempting removal.
        Raises NotFoundError if the association does not exist.

        Args:
            uow: UnitOfWork providing uow.productos.
            producto_id: UUID of the product.
            ingrediente_id: UUID of the ingredient to disassociate.

        Raises:
            NotFoundError(code="PRODUCT_NOT_FOUND"): if product not found.
            NotFoundError(code="PRODUCT_INGREDIENT_NOT_FOUND"): if association not found.
        """
        product = await uow.productos.get_by_id(producto_id)
        if product is None:
            raise NotFoundError(
                f"Producto {producto_id} no encontrado",
                code="PRODUCT_NOT_FOUND",
            )

        removed = await uow.productos.remove_ingrediente(producto_id, ingrediente_id)
        if not removed:
            raise NotFoundError(
                f"Asociación producto {producto_id} ↔ ingrediente {ingrediente_id} no encontrada",
                code="PRODUCT_INGREDIENT_NOT_FOUND",
            )
