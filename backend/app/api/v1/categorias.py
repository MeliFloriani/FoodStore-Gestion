"""
Categorias router — category management endpoints.

Routes:
  GET    /categorias/        — list all categories as tree (public, no auth)
  GET    /categorias/{id}    — get single category by ID (public, no auth)
  POST   /categorias/        — create a new category (ADMIN + STOCK)
  PUT    /categorias/{id}    — update a category (ADMIN + STOCK)
  DELETE /categorias/{id}    — soft-delete a category (ADMIN + STOCK)

Design decisions:
  - Read endpoints (GET) have NO auth dependency — they are fully public (D-01).
  - Write endpoints use require_role("ADMIN", "STOCK") (D-01 / §4.2).
  - PUT passes the CategoriaUpdate Pydantic model DIRECTLY to service (NOT
    model_dump()) — the service uses model_fields_set to implement the parent_id
    sentinel (D-09 / spec requirement).
  - session.commit() is NEVER called here — UnitOfWork handles it.
  - No prefix on the router — prefix "/categorias" is added in build_v1_router.
  - UoW is injected via Depends(get_uow) so tests can override it with
    make_uow_override(session) for transactional isolation.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.api.deps import require_role
from app.core.uow import UnitOfWork, get_uow
from app.schemas.categoria import CategoriaCreate, CategoriaRead, CategoriaTreeNode, CategoriaUpdate
from app.services.categoria import CategoriaService

categorias_router = APIRouter()


@categorias_router.get(
    "/",
    response_model=list[CategoriaTreeNode],
    status_code=status.HTTP_200_OK,
    summary="List all categories as a tree",
    description=(
        "Return all active categories as a nested tree structure. "
        "Root categories are at the top level. Each node contains its "
        "direct children in 'subcategorias'. Public endpoint — no auth required."
    ),
    tags=["categorias"],
)
async def list_categorias(uow: UnitOfWork = Depends(get_uow)) -> list[CategoriaTreeNode]:
    """Return the full category tree. No auth required."""
    return await CategoriaService.get_tree(uow)


@categorias_router.get(
    "/{category_id}",
    response_model=CategoriaRead,
    status_code=status.HTTP_200_OK,
    summary="Get a category by ID",
    description=(
        "Return a single active category by UUID. "
        "Returns 404 if the category does not exist or has been soft-deleted. "
        "Public endpoint — no auth required."
    ),
    tags=["categorias"],
)
async def get_categoria(
    category_id: UUID,
    uow: UnitOfWork = Depends(get_uow),
) -> CategoriaRead:
    """Return a single category by ID. No auth required."""
    return await CategoriaService.get_by_id(category_id, uow)


@categorias_router.post(
    "/",
    response_model=CategoriaRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new category",
    description=(
        "Create a new category. Requires ADMIN or STOCK role. "
        "Set parent_id to create a subcategory; omit for a root category. "
        "Returns 409 if nombre already exists at the same level. "
        "Returns 422 if parent_id doesn't exist or tree depth would exceed 5."
    ),
    tags=["categorias"],
    dependencies=[Depends(require_role("ADMIN", "STOCK"))],
)
async def create_categoria(
    data: CategoriaCreate,
    uow: UnitOfWork = Depends(get_uow),
) -> CategoriaRead:
    """Create a new category. Requires ADMIN or STOCK role."""
    return await CategoriaService.create_categoria(data, uow)


@categorias_router.put(
    "/{category_id}",
    response_model=CategoriaRead,
    status_code=status.HTTP_200_OK,
    summary="Update a category",
    description=(
        "Update an existing category. Requires ADMIN or STOCK role. "
        "All fields are optional (partial update). "
        "Set parent_id=null to promote to root; omit parent_id to leave unchanged. "
        "Returns 409 on duplicate nombre; 422 on self-parent, cycle, or depth violation."
    ),
    tags=["categorias"],
    dependencies=[Depends(require_role("ADMIN", "STOCK"))],
)
async def update_categoria(
    category_id: UUID,
    data: CategoriaUpdate,
    uow: UnitOfWork = Depends(get_uow),
) -> CategoriaRead:
    """Update a category. Requires ADMIN or STOCK role.

    IMPORTANT: 'data' is passed as-is (Pydantic model, NOT data.model_dump()).
    The service reads data.model_fields_set to implement the parent_id sentinel —
    distinguishing 'not sent' from 'explicitly set to None'.
    """
    return await CategoriaService.update_categoria(category_id, data, uow)


@categorias_router.delete(
    "/{category_id}",
    response_model=None,
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Soft-delete a category",
    description=(
        "Soft-delete a category. Requires ADMIN or STOCK role. "
        "Blocked if the category has active subcategories (409) or "
        "active linked products (409). Returns 204 No Content on success."
    ),
    tags=["categorias"],
    dependencies=[Depends(require_role("ADMIN", "STOCK"))],
)
async def delete_categoria(
    category_id: UUID,
    uow: UnitOfWork = Depends(get_uow),
) -> None:
    """Soft-delete a category. Requires ADMIN or STOCK role."""
    await CategoriaService.delete_categoria(category_id, uow)
