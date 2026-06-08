"""
Direcciones router — delivery address management endpoints.

Change 14: delivery-addresses-management.

Routes (all require CLIENT role):
  POST   /                    — create a new address (201)
  GET    /                    — list all active addresses for the user (200)
  GET    /{id}                — get single address by ID (200)
  PATCH  /{id}/principal      — mark address as principal (200) — DECLARED BEFORE /{id}
  PATCH  /{id}                — partial update address (200)
  DELETE /{id}                — soft-delete address (204)

Design decisions:
  - All endpoints use require_role("CLIENT") for access control (RBAC per spec).
  - usuario_id is ALWAYS extracted from JWT via require_role dependency (current_user.id).
    It is NEVER taken from the body or query params.
  - PATCH /{id}/principal is declared BEFORE PATCH /{id} to avoid FastAPI path
    ambiguity — FastAPI evaluates routes in declaration order.
  - No prefix on the router — prefix "/direcciones" is added in build_v1_router.
  - UoW is injected via Depends(get_uow) so tests can override it.
  - session.commit() is NEVER called here — UnitOfWork handles it.
  - HTTPException is NEVER raised here — raised by DireccionEntregaService.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Response, status

from app.api.deps import require_role
from app.core.uow import UnitOfWork, get_uow
from app.models.user import Usuario
from app.schemas.direccion_entrega import (
    DireccionEntregaCreate,
    DireccionEntregaRead,
    DireccionEntregaUpdate,
)
from app.services.direccion_entrega import DireccionEntregaService

direcciones_router = APIRouter()


@direcciones_router.post(
    "/",
    response_model=DireccionEntregaRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new delivery address",
    description=(
        "Create a new delivery address for the authenticated user. "
        "The first address is automatically set as principal. "
        "Maximum 20 active addresses per user. "
        "Requires CLIENT role."
    ),
    tags=["Direcciones"],
)
async def crear_direccion(
    data: DireccionEntregaCreate,
    current_user: Usuario = Depends(require_role("CLIENT")),
    uow: UnitOfWork = Depends(get_uow),
) -> DireccionEntregaRead:
    """Create a new delivery address. Requires CLIENT role."""
    return await DireccionEntregaService.crear_direccion(uow, current_user.id, data)


@direcciones_router.get(
    "/",
    response_model=list[DireccionEntregaRead],
    status_code=status.HTTP_200_OK,
    summary="List delivery addresses",
    description=(
        "Return all active delivery addresses for the authenticated user. "
        "Soft-deleted addresses are excluded. Requires CLIENT role."
    ),
    tags=["Direcciones"],
)
async def listar_direcciones(
    current_user: Usuario = Depends(require_role("CLIENT")),
    uow: UnitOfWork = Depends(get_uow),
) -> list[DireccionEntregaRead]:
    """List all active delivery addresses for the authenticated user. Requires CLIENT role."""
    return await DireccionEntregaService.listar_direcciones(uow, current_user.id)


@direcciones_router.get(
    "/{direccion_id}",
    response_model=DireccionEntregaRead,
    status_code=status.HTTP_200_OK,
    summary="Get a delivery address by ID",
    description=(
        "Return a single active delivery address by ID. "
        "Returns 404 if not found, soft-deleted, or owned by another user. "
        "Requires CLIENT role."
    ),
    tags=["Direcciones"],
)
async def obtener_direccion(
    direccion_id: uuid.UUID,
    current_user: Usuario = Depends(require_role("CLIENT")),
    uow: UnitOfWork = Depends(get_uow),
) -> DireccionEntregaRead:
    """Get a delivery address by ID. Requires CLIENT role."""
    return await DireccionEntregaService.obtener_direccion(uow, current_user.id, direccion_id)


# IMPORTANT: PATCH /{id}/principal MUST be declared BEFORE PATCH /{id} to avoid
# FastAPI path matching ambiguity. FastAPI evaluates routes in declaration order;
# if /{id} comes first, requests to /{id}/principal would match /{id} with
# id="some-uuid/principal" — resulting in a 422 validation error.
@direcciones_router.patch(
    "/{direccion_id}/principal",
    response_model=DireccionEntregaRead,
    status_code=status.HTTP_200_OK,
    summary="Mark address as principal",
    description=(
        "Mark the specified delivery address as the user's principal address. "
        "The previous principal address loses the principal flag. "
        "Idempotent: if already principal, returns HTTP 200 without modifying the DB. "
        "No body required. Requires CLIENT role."
    ),
    tags=["Direcciones"],
)
async def marcar_principal(
    direccion_id: uuid.UUID,
    current_user: Usuario = Depends(require_role("CLIENT")),
    uow: UnitOfWork = Depends(get_uow),
) -> DireccionEntregaRead:
    """Mark a delivery address as principal. Requires CLIENT role."""
    return await DireccionEntregaService.marcar_principal(uow, current_user.id, direccion_id)


@direcciones_router.patch(
    "/{direccion_id}",
    response_model=DireccionEntregaRead,
    status_code=status.HTTP_200_OK,
    summary="Partially update a delivery address",
    description=(
        "Apply a partial update to an existing delivery address. "
        "Only the fields present in the request body are updated. "
        "es_principal cannot be changed via this endpoint — use PATCH /{id}/principal. "
        "Returns 404 if not found or owned by another user. "
        "Requires CLIENT role."
    ),
    tags=["Direcciones"],
)
async def actualizar_direccion(
    direccion_id: uuid.UUID,
    data: DireccionEntregaUpdate,
    current_user: Usuario = Depends(require_role("CLIENT")),
    uow: UnitOfWork = Depends(get_uow),
) -> DireccionEntregaRead:
    """Partially update a delivery address. Requires CLIENT role."""
    return await DireccionEntregaService.actualizar_direccion(
        uow, current_user.id, direccion_id, data
    )


@direcciones_router.delete(
    "/{direccion_id}",
    response_model=None,
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Soft-delete a delivery address",
    description=(
        "Soft-delete a delivery address. "
        "If the deleted address was the principal and others exist, "
        "the most recently created active address is auto-promoted as principal. "
        "Returns 204 No Content on success. "
        "Returns 404 if not found or owned by another user. "
        "Requires CLIENT role."
    ),
    tags=["Direcciones"],
)
async def eliminar_direccion(
    direccion_id: uuid.UUID,
    current_user: Usuario = Depends(require_role("CLIENT")),
    uow: UnitOfWork = Depends(get_uow),
) -> Response:
    """Soft-delete a delivery address. Requires CLIENT role."""
    await DireccionEntregaService.eliminar_direccion(uow, current_user.id, direccion_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
