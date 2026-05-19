"""
Ingredientes router — ingredient management endpoints.

Routes:
  GET    /ingredientes/           — list all active ingredients (ADMIN + STOCK)
  GET    /ingredientes/{id}       — get single ingredient by ID (ADMIN + STOCK)
  POST   /ingredientes/           — create a new ingredient (ADMIN + STOCK)
  PUT    /ingredientes/{id}       — update an ingredient (ADMIN + STOCK)
  DELETE /ingredientes/{id}       — soft-delete an ingredient (ADMIN + STOCK)

Design decisions:
  - D-01: ALL endpoints (including reads) require ADMIN or STOCK role.
    There are no public endpoints in this change — ingredients are an internal
    catalog resource. Public allergen display is deferred to Change 12.
  - D-05: PUT passes the IngredienteUpdate Pydantic model DIRECTLY to service
    (NOT model_dump()). The service uses model_fields_set to implement partial
    updates — only supplied fields are written to the DB.
  - session.commit() is NEVER called here — UnitOfWork handles it.
  - No prefix on the router — prefix "/ingredientes" is added in build_v1_router.
  - UoW is injected via Depends(get_uow) so tests can override it with
    make_uow_override(session) for transactional isolation.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import require_role
from app.core.uow import UnitOfWork, get_uow
from app.schemas.ingrediente import IngredienteCreate, IngredienteRead, IngredienteUpdate
from app.services.ingrediente import IngredienteService

ingredientes_router = APIRouter()


@ingredientes_router.get(
    "/",
    response_model=list[IngredienteRead],
    status_code=status.HTTP_200_OK,
    summary="List all active ingredients",
    description=(
        "Return all active ingredients. "
        "Optionally filter by es_alergeno query parameter. "
        "Results are ordered alphabetically by nombre. "
        "Requires ADMIN or STOCK role."
    ),
    tags=["ingredientes"],
    dependencies=[Depends(require_role("ADMIN", "STOCK"))],
)
async def list_ingredientes(
    es_alergeno: bool | None = Query(default=None, description="Filter by allergen flag"),
    uow: UnitOfWork = Depends(get_uow),
) -> list[IngredienteRead]:
    """Return all active ingredients, optionally filtered by es_alergeno.

    Requires ADMIN or STOCK role.
    """
    return await IngredienteService.list_ingredientes(es_alergeno, uow)


@ingredientes_router.get(
    "/{ingrediente_id}",
    response_model=IngredienteRead,
    status_code=status.HTTP_200_OK,
    summary="Get an ingredient by ID",
    description=(
        "Return a single active ingredient by UUID. "
        "Returns 404 if the ingredient does not exist or has been soft-deleted. "
        "Requires ADMIN or STOCK role."
    ),
    tags=["ingredientes"],
    dependencies=[Depends(require_role("ADMIN", "STOCK"))],
)
async def get_ingrediente(
    ingrediente_id: UUID,
    uow: UnitOfWork = Depends(get_uow),
) -> IngredienteRead:
    """Return a single ingredient by ID. Requires ADMIN or STOCK role."""
    return await IngredienteService.get_ingrediente(ingrediente_id, uow)


@ingredientes_router.post(
    "/",
    response_model=IngredienteRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new ingredient",
    description=(
        "Create a new ingredient. Requires ADMIN or STOCK role. "
        "Returns 409 if nombre already exists among active ingredients."
    ),
    tags=["ingredientes"],
    dependencies=[Depends(require_role("ADMIN", "STOCK"))],
)
async def create_ingrediente(
    data: IngredienteCreate,
    uow: UnitOfWork = Depends(get_uow),
) -> IngredienteRead:
    """Create a new ingredient. Requires ADMIN or STOCK role."""
    return await IngredienteService.create_ingrediente(data, uow)


@ingredientes_router.put(
    "/{ingrediente_id}",
    response_model=IngredienteRead,
    status_code=status.HTTP_200_OK,
    summary="Update an ingredient",
    description=(
        "Update an existing ingredient. Requires ADMIN or STOCK role. "
        "All fields are optional (partial update). "
        "Only supplied fields are updated; absent fields are preserved at current values. "
        "Returns 409 on duplicate nombre; 404 if not found or soft-deleted."
    ),
    tags=["ingredientes"],
    dependencies=[Depends(require_role("ADMIN", "STOCK"))],
)
async def update_ingrediente(
    ingrediente_id: UUID,
    data: IngredienteUpdate,
    uow: UnitOfWork = Depends(get_uow),
) -> IngredienteRead:
    """Update an ingredient. Requires ADMIN or STOCK role.

    IMPORTANT: 'data' is passed as-is (Pydantic model, NOT data.model_dump()).
    The service reads data.model_fields_set to implement partial updates —
    distinguishing 'not sent' from 'explicitly set to None' (D-05).
    """
    # CORRECT — pass Pydantic model directly, NOT data.model_dump()
    return await IngredienteService.update_ingrediente(ingrediente_id, data, uow)


@ingredientes_router.delete(
    "/{ingrediente_id}",
    response_model=None,
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Soft-delete an ingredient",
    description=(
        "Soft-delete an ingredient. Requires ADMIN or STOCK role. "
        "Returns 404 if the ingredient does not exist or is already deleted. "
        "Returns 204 No Content on success. "
        "The ingredient name becomes immediately available for reuse after soft-delete."
    ),
    tags=["ingredientes"],
    dependencies=[Depends(require_role("ADMIN", "STOCK"))],
)
async def delete_ingrediente(
    ingrediente_id: UUID,
    uow: UnitOfWork = Depends(get_uow),
) -> None:
    """Soft-delete an ingredient. Requires ADMIN or STOCK role."""
    await IngredienteService.delete_ingrediente(ingrediente_id, uow)
