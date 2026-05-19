"""
Public catalog router — read-only public endpoints for the product catalog.

Routes (all prefixed with /catalog when registered in build_v1_router):
  GET /catalog/productos                — paginated public product listing (NO auth)
  GET /catalog/productos/{id}           — public product detail with relations (NO auth)
  GET /catalog/ingredientes-alergenos   — list of allergen ingredients (NO auth)

Design decisions:
  - NO auth dependency at router level or on any individual endpoint.
    These are fully public — no Authorization header required.
  - Separate from /productos (admin surface) to avoid mixing public/admin endpoints.
  - UoW injected via Depends(get_uow) so tests can override with make_uow_override.
  - Service raises NotFoundError (404) and AppValidationError (422) — the global
    error handlers in app/api/errors.py convert them to RFC 7807 responses.
  - Router does NOT catch or re-raise these exceptions — the global handler does.
  - session.commit() is NEVER called here — UnitOfWork handles it.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.core.uow import UnitOfWork, get_uow
from app.schemas.catalog_public import (
    CatalogProductosQuery,
    IngredienteAlergenicoListResponse,
    PaginatedCatalogProductos,
    ProductoPublicoDetalleRead,
)
from app.services.catalog_public import CatalogPublicService

catalog_router = APIRouter()


@catalog_router.get(
    "/productos",
    response_model=PaginatedCatalogProductos,
    status_code=status.HTTP_200_OK,
    summary="List public catalog products",
    description=(
        "Return a paginated list of publicly available products "
        "(disponible=true AND deleted_at IS NULL). "
        "Supports filtering by categoria_id, q (nombre ILIKE), excluir_alergenos "
        "(comma-separated ingredient IDs), and ordering. "
        "No authentication required."
    ),
)
async def list_catalog_productos(
    filters: CatalogProductosQuery = Depends(),
    uow: UnitOfWork = Depends(get_uow),
) -> PaginatedCatalogProductos:
    """List publicly visible products with composable filters.

    No auth dependency — fully public endpoint.
    Query params validated by CatalogProductosQuery (page, size, categoria_id, q,
    excluir_alergenos, ordenar). excluir_alergenos further validated by service.
    """
    return await CatalogPublicService.list_catalog(uow=uow, filters=filters)


@catalog_router.get(
    "/productos/{id}",
    response_model=ProductoPublicoDetalleRead,
    status_code=status.HTTP_200_OK,
    summary="Get public product detail",
    description=(
        "Return full product detail including categorias and ingredientes. "
        "Returns 404 if product is not found, soft-deleted, or disponible=false. "
        "Response includes tiene_stock (boolean) but NEVER stock_cantidad. "
        "No authentication required."
    ),
    responses={
        404: {"description": "Product not found or not publicly visible"},
        422: {"description": "Invalid UUID path parameter"},
    },
)
async def get_catalog_producto_detail(
    id: UUID,
    uow: UnitOfWork = Depends(get_uow),
) -> ProductoPublicoDetalleRead:
    """Get full product detail for the public catalog.

    No auth dependency — fully public endpoint.
    Returns 404 (code=PRODUCT_NOT_FOUND) if product is unavailable or not found.
    The global error handler converts NotFoundError → RFC 7807 response.
    """
    return await CatalogPublicService.get_catalog_detail(uow=uow, producto_id=id)


@catalog_router.get(
    "/ingredientes-alergenos",
    response_model=IngredienteAlergenicoListResponse,
    status_code=status.HTTP_200_OK,
    summary="List public allergen ingredients",
    description=(
        "Return all active allergen ingredients (es_alergeno=true AND deleted_at IS NULL). "
        "Used by the frontend AllergenosExclusion widget to populate filter options. "
        "This endpoint is public because GET /api/v1/ingredientes requires ADMIN/STOCK role. "
        "No authentication required."
    ),
)
async def list_ingredientes_alergenos(
    uow: UnitOfWork = Depends(get_uow),
) -> IngredienteAlergenicoListResponse:
    """List active allergen ingredients for public use.

    No auth dependency — fully public endpoint.
    Avoids requiring access to the admin-only GET /api/v1/ingredientes endpoint.
    """
    return await CatalogPublicService.list_alergenos(uow=uow)
