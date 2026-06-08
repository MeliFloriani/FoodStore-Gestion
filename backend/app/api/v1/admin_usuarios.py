"""
Admin usuarios router — Change 21: admin-users-management.

Endpoints (mounted at /api/v1/admin/usuarios):
  GET  /               list_usuarios        — paginated list with search/filters
  GET  /{id}           get_usuario          — single user detail
  PUT  /{id}/roles     update_usuario_roles — replace full role set (D-02)
  PATCH /{id}/estado   update_usuario_estado — activate/deactivate (D-05)
  PUT  /{id}           update_usuario_data  — update nombre/apellido (D-01)

Route ordering matters: /{id}/roles and /{id}/estado MUST be declared BEFORE
/{id} to prevent path matching ambiguity (FastAPI matches top-to-bottom).

Conventions:
  - All endpoints require `Depends(require_role("ADMIN"))` for RBAC.
  - No HTTPException is raised directly — services raise AppError subclasses.
  - Router owns UoW lifecycle via `Depends(get_uow)`; services receive the active UoW directly (no `async with uow` inside the service).
  - response_model is explicit on every endpoint (P-02).
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query

from app.api.deps import require_role
from app.core.uow import UnitOfWork, get_uow
from app.models.user import Usuario
from app.schemas.admin_usuarios import (
    UsuarioAdminRead,
    UsuarioAdminUpdate,
    UsuarioEstadoUpdate,
    UsuarioRolesUpdate,
)
from app.schemas.base import Page
from app.services.admin_usuarios import AdminUsuariosService

admin_usuarios_router = APIRouter(tags=["admin-usuarios"])


@admin_usuarios_router.get("", response_model=Page[UsuarioAdminRead])
async def list_usuarios(
    page: int = Query(1, ge=1, description="Número de página (1-based)"),
    size: int = Query(20, ge=1, le=100, description="Items por página"),
    q: str | None = Query(None, max_length=100, description="Búsqueda por nombre, apellido o email"),
    rol: str | None = Query(None, description="Filtrar por código de rol"),
    activo: bool | None = Query(None, description="true=solo activos, false=solo inactivos"),
    _admin: Usuario = Depends(require_role("ADMIN")),
    uow: UnitOfWork = Depends(get_uow),
) -> Page[UsuarioAdminRead]:
    """List all users with pagination, search, and filters.

    Query params:
      - page: 1-based page number (default: 1)
      - size: items per page (default: 20, max: 100)
      - q: ILIKE search on nombre, apellido, email
      - rol: filter by role code (ADMIN, STOCK, PEDIDOS, CLIENT)
      - activo: true=active only, false=inactive only, null=all
    """
    return await AdminUsuariosService.list_usuarios(
        uow,
        page=page,
        size=size,
        q=q,
        rol=rol,
        activo=activo,
    )


@admin_usuarios_router.get("/{id}", response_model=UsuarioAdminRead)
async def get_usuario(
    id: uuid.UUID,
    _admin: Usuario = Depends(require_role("ADMIN")),
    uow: UnitOfWork = Depends(get_uow),
) -> UsuarioAdminRead:
    """Get a single user by UUID."""
    return await AdminUsuariosService.get_usuario(uow, id)


@admin_usuarios_router.put("/{id}/roles", response_model=UsuarioAdminRead)
async def update_usuario_roles(
    id: uuid.UUID,
    body: UsuarioRolesUpdate,
    admin: Usuario = Depends(require_role("ADMIN")),
    uow: UnitOfWork = Depends(get_uow),
) -> UsuarioAdminRead:
    """Replace the full role set for a user (PUT replace semantics — D-02).

    The payload must contain the COMPLETE desired set of roles.
    Validates last-admin guard: cannot remove ADMIN from the last active ADMIN.
    Revokes all refresh tokens on success (forces re-login with new roles).
    """
    return await AdminUsuariosService.update_usuario_roles(
        uow,
        user_id=id,
        new_roles=body.roles,
        admin_id=admin.id,
    )


@admin_usuarios_router.patch("/{id}/estado", response_model=UsuarioAdminRead)
async def update_usuario_estado(
    id: uuid.UUID,
    body: UsuarioEstadoUpdate,
    _admin: Usuario = Depends(require_role("ADMIN")),
    uow: UnitOfWork = Depends(get_uow),
) -> UsuarioAdminRead:
    """Activate or deactivate a user.

    activo=false: soft-delete the user + revoke all refresh tokens.
    activo=true: reactivate the user (D-05: backend supports it, frontend
    does NOT expose this in Change 21).

    Validates last-admin guard when deactivating an ADMIN user.
    """
    return await AdminUsuariosService.deactivate_usuario(
        uow,
        user_id=id,
        activo=body.activo,
    )


@admin_usuarios_router.put("/{id}", response_model=UsuarioAdminRead)
async def update_usuario_data(
    id: uuid.UUID,
    body: UsuarioAdminUpdate,
    _admin: Usuario = Depends(require_role("ADMIN")),
    uow: UnitOfWork = Depends(get_uow),
) -> UsuarioAdminRead:
    """Update editable user data (nombre and/or apellido only).

    D-01: email is immutable. Any email in the request body is silently ignored.
    """
    return await AdminUsuariosService.update_usuario_data(uow, id, body)
