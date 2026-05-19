"""
Productos router — product management endpoints.

Routes:
  GET    /productos/                          — list paginated products (public)
  GET    /productos/{id}                      — get product detail with relations (public)
  POST   /productos/                          — create a new product (ADMIN)
  PATCH  /productos/{id}                      — partial update (ADMIN)
  DELETE /productos/{id}                      — soft-delete (ADMIN)
  PATCH  /productos/{id}/disponibilidad       — toggle availability (ADMIN, STOCK)
  GET    /productos/{id}/ingredientes         — list product ingredients (public)
  POST   /productos/{id}/ingredientes         — associate ingredient (ADMIN)
  DELETE /productos/{id}/ingredientes/{ing_id} — remove ingredient association (ADMIN)

Design decisions:
  - D-01: RBAC per endpoint per Integrador §5.2 (overrides US-015 through US-022
    where STOCK was named — see design.md Decision Log).
  - PATCH vs PUT (H-01): using PATCH for partial updates via model_fields_set.
    See design.md §API Contracts for rationale.
  - No prefix on the router — prefix "/productos" added in build_v1_router.
  - UoW injected via Depends(get_uow) so tests can override with make_uow_override.
  - session.commit() is NEVER called here — UnitOfWork handles it.
  - D-05: PATCH /{id} passes the ProductoUpdate Pydantic model DIRECTLY to the
    service (NOT data.model_dump()) to preserve model_fields_set for partial updates.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import require_role
from app.core.uow import UnitOfWork, get_uow
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
from app.services.producto import ProductoService

productos_router = APIRouter()


@productos_router.get(
    "/",
    response_model=PaginatedProductos,
    status_code=status.HTTP_200_OK,
    summary="List paginated products",
    description=(
        "Return a paginated list of active products. "
        "Optionally filter by categoria_id, disponible flag, or nombre search (ILIKE). "
        "Public endpoint — no authentication required."
    ),
    tags=["productos"],
)
async def list_productos(
    page: int = Query(default=1, ge=1, description="Page number (1-based)"),
    size: int = Query(default=20, ge=1, le=100, description="Items per page (1–100)"),
    categoria_id: UUID | None = Query(default=None, description="Filter by category UUID"),
    disponible: bool | None = Query(default=None, description="Filter by availability flag"),
    search: str | None = Query(default=None, description="ILIKE substring search on nombre"),
    uow: UnitOfWork = Depends(get_uow),
) -> PaginatedProductos:
    """Return a paginated list of active products.

    Public — no authentication required.
    """
    return await ProductoService.list_productos(
        uow=uow,
        page=page,
        size=size,
        categoria_id=categoria_id,
        disponible=disponible,
        search=search,
    )


@productos_router.get(
    "/{producto_id}",
    response_model=ProductoDetail,
    status_code=status.HTTP_200_OK,
    summary="Get product detail",
    description=(
        "Return full product detail including category and ingredient associations. "
        "Returns 404 if the product does not exist or has been soft-deleted. "
        "Public endpoint — no authentication required."
    ),
    tags=["productos"],
)
async def get_producto_detail(
    producto_id: UUID,
    uow: UnitOfWork = Depends(get_uow),
) -> ProductoDetail:
    """Return full product detail with categorias and ingredientes loaded.

    Public — no authentication required.
    """
    return await ProductoService.get_producto_detail(uow=uow, producto_id=producto_id)


@productos_router.post(
    "/",
    response_model=ProductoRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new product",
    description=(
        "Create a new product in the catalog. Requires ADMIN role. "
        "Optionally associates the product with one or more categories via categoria_ids. "
        "Returns 404 if any categoria_id does not exist or is soft-deleted."
    ),
    tags=["productos"],
    dependencies=[Depends(require_role("ADMIN"))],
)
async def create_producto(
    data: ProductoCreate,
    uow: UnitOfWork = Depends(get_uow),
) -> ProductoRead:
    """Create a new product. Requires ADMIN role."""
    return await ProductoService.create_producto(uow=uow, data=data)


@productos_router.patch(
    "/{producto_id}",
    response_model=ProductoRead,
    status_code=status.HTTP_200_OK,
    summary="Update a product (partial)",
    description=(
        "Partially update a product. Requires ADMIN role. "
        "Only supplied fields are updated — absent fields preserve their current values. "
        "If categoria_ids is provided (even as []), category associations are replaced. "
        "Returns 404 if product or any categoria_id is not found."
    ),
    tags=["productos"],
    dependencies=[Depends(require_role("ADMIN"))],
)
async def update_producto(
    producto_id: UUID,
    data: ProductoUpdate,
    uow: UnitOfWork = Depends(get_uow),
) -> ProductoRead:
    """Partially update a product. Requires ADMIN role.

    IMPORTANT: 'data' is passed as-is (Pydantic model, NOT data.model_dump()).
    The service reads data.model_fields_set to implement partial updates —
    distinguishing 'not sent' from 'explicitly set to None' (D-05).
    """
    # CORRECT — pass Pydantic model directly, NOT data.model_dump()
    return await ProductoService.update_producto(uow=uow, producto_id=producto_id, data=data)


@productos_router.delete(
    "/{producto_id}",
    response_model=None,
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Soft-delete a product",
    description=(
        "Soft-delete a product from the catalog. Requires ADMIN role. "
        "Returns 404 if the product does not exist or is already soft-deleted. "
        "Returns 204 No Content on success. "
        "Pivot records (categories, ingredients) are preserved (D-31)."
    ),
    tags=["productos"],
    dependencies=[Depends(require_role("ADMIN"))],
)
async def delete_producto(
    producto_id: UUID,
    uow: UnitOfWork = Depends(get_uow),
) -> None:
    """Soft-delete a product. Requires ADMIN role."""
    await ProductoService.delete_producto(uow=uow, producto_id=producto_id)


@productos_router.patch(
    "/{producto_id}/disponibilidad",
    response_model=ProductoRead,
    status_code=status.HTTP_200_OK,
    summary="Update product availability",
    description=(
        "Toggle the disponible flag of a product. "
        "Requires ADMIN or STOCK role (STOCK manages daily availability without full CRUD access). "
        "Returns 401 if no token provided; 403 if role is insufficient. "
        "Returns 404 if product not found."
    ),
    tags=["productos"],
    dependencies=[Depends(require_role("ADMIN", "STOCK"))],
)
async def set_disponibilidad(
    producto_id: UUID,
    data: DisponibilidadUpdate,
    uow: UnitOfWork = Depends(get_uow),
) -> ProductoRead:
    """Update product availability. Requires ADMIN or STOCK role."""
    return await ProductoService.set_disponibilidad(
        uow=uow, producto_id=producto_id, data=data
    )


@productos_router.get(
    "/{producto_id}/ingredientes",
    response_model=list[ProductoIngredienteRead],
    status_code=status.HTTP_200_OK,
    summary="Get product ingredients",
    description=(
        "Return all active ingredient associations for a product. "
        "Returns 404 if the product does not exist or is soft-deleted. "
        "Returns an empty list if the product has no ingredient associations. "
        "Public endpoint — no authentication required."
    ),
    tags=["productos"],
)
async def get_producto_ingredientes(
    producto_id: UUID,
    uow: UnitOfWork = Depends(get_uow),
) -> list[ProductoIngredienteRead]:
    """Return ingredient associations for a product.

    Public — no authentication required.
    NOTE: Returns 404 (not empty list) if product does not exist (H-03).
    """
    return await ProductoService.get_producto_ingredientes(
        uow=uow, producto_id=producto_id
    )


@productos_router.post(
    "/{producto_id}/ingredientes",
    response_model=ProductoIngredienteRead,
    status_code=status.HTTP_201_CREATED,
    summary="Associate an ingredient with a product",
    description=(
        "Associate an ingredient with a product. Requires ADMIN role. "
        "Returns 404 if product or ingredient not found. "
        "Returns 409 if the association already exists (PRODUCT_INGREDIENT_DUPLICATE)."
    ),
    tags=["productos"],
    dependencies=[Depends(require_role("ADMIN"))],
)
async def add_ingrediente(
    producto_id: UUID,
    data: AsociarIngredienteRequest,
    uow: UnitOfWork = Depends(get_uow),
) -> ProductoIngredienteRead:
    """Associate an ingredient with a product. Requires ADMIN role."""
    return await ProductoService.add_ingrediente(
        uow=uow, producto_id=producto_id, data=data
    )


@productos_router.delete(
    "/{producto_id}/ingredientes/{ing_id}",
    response_model=None,
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove an ingredient association from a product",
    description=(
        "Remove (hard-delete) the association between a product and an ingredient. "
        "Requires ADMIN role. "
        "Returns 404 if the product or the association does not exist. "
        "Returns 204 No Content on success."
    ),
    tags=["productos"],
    dependencies=[Depends(require_role("ADMIN"))],
)
async def remove_ingrediente(
    producto_id: UUID,
    ing_id: UUID,
    uow: UnitOfWork = Depends(get_uow),
) -> None:
    """Remove ingredient association from product. Requires ADMIN role."""
    await ProductoService.remove_ingrediente(
        uow=uow, producto_id=producto_id, ingrediente_id=ing_id
    )
