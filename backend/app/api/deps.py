"""
FastAPI dependency functions for authentication and role-based access control.

Dependency chain (D-06):
    require_role("ADMIN", "PEDIDOS")
            │
            ▼ Depends(get_current_user)
    get_current_user(token, uow)
            │
            ├── security.decode_access_token(token)  → dict | UnauthorizedError
            └── uow.usuarios.get_by_id(sub)          → Usuario | UnauthorizedError

Why deps.py lives in api/ (not core/):
    FastAPI-specific concepts (Depends, OAuth2PasswordBearer) belong to the API layer.
    core/ contains framework-agnostic infrastructure (config, uow, security,
    exceptions).

IMPORTANT: get_uow is used via Depends(get_uow) directly — never wrapped or aliased.
    Wrappers break FastAPI's identity-based Depends deduplication, causing two
    AsyncSession instances per request (D-06 / R-01).
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import Any

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer

from app.core.exceptions import ForbiddenError, UnauthorizedError
from app.core.logging import get_logger
from app.core.uow import UnitOfWork, get_uow
from app.models.user import Usuario

logger = get_logger(__name__)

# Placeholder oauth2_scheme — the /api/v1/auth/login endpoint is built in Change 06.
# auto_error=False: the scheme returns None instead of raising 401 for missing tokens.
# This gives get_current_user full control over error formatting (RFC 7807 compliance).
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/api/v1/auth/login",
    auto_error=False,
)


async def get_current_user(
    token: str | None = Depends(oauth2_scheme),
    uow: UnitOfWork = Depends(get_uow),
) -> Usuario:
    """Resolve and return the authenticated Usuario for the current request.

    Steps:
      1. Raise UnauthorizedError if token is None or empty.
      2. Decode the JWT via security.decode_access_token (raises
         UnauthorizedError on failure).
      3. Extract 'sub' claim (user UUID string).
      4. Look up Usuario via uow.usuarios.get_by_id — returns None if not found
         or soft-deleted.
      5. Raise UnauthorizedError if user not found / soft-deleted.
      6. Return the Usuario instance.

    All 401 errors use the same generic message to prevent information leakage
    about the specific failure mode (expired vs invalid signature vs user not found).

    Args:
        token: Bearer token from the Authorization header (None if header absent).
        uow: Unit of Work dependency — provides the usuarios repository.

    Returns:
        The authenticated Usuario instance.

    Raises:
        UnauthorizedError: If token is missing, invalid, expired, or user is not found.
    """
    if not token:
        logger.warning("auth.missing_token")
        raise UnauthorizedError("Token requerido", code="missing_token")

    # Import security here to avoid circular imports at module level.
    from app.core import security

    # decode_access_token raises UnauthorizedError on any JWT failure.
    payload = security.decode_access_token(token)

    sub: str | None = payload.get("sub")
    if not sub:
        logger.warning("auth.missing_sub_claim")
        raise UnauthorizedError("Token inválido o expirado", code="invalid_token")

    try:
        user_uuid = uuid.UUID(sub)
    except (ValueError, AttributeError):
        logger.warning("auth.invalid_sub_format", sub=sub[:20] if sub else None)
        raise UnauthorizedError("Token inválido o expirado", code="invalid_token")

    # get_by_id applies deleted_at IS NULL filter by default.
    # Returns None for both non-existent users and soft-deleted users.
    user = await uow.usuarios.get_by_id(user_uuid)
    if user is None:
        logger.warning("auth.user_not_found", user_id=str(user_uuid))
        raise UnauthorizedError(
            "Usuario no encontrado o inactivo",
            code="user_not_found",
        )

    return user


def require_role(*roles: str) -> Callable[..., Any]:
    """Return a FastAPI dependency that enforces role-based access control.

    The returned dependency calls get_current_user (authentication) first,
    then checks that the user has at least one of the required roles via
    UsuarioRol. HTTP 401 takes precedence over HTTP 403 — if authentication
    fails, the 401 from get_current_user propagates before role checking.

    Usage:
        @router.get("/admin/users")
        async def list_users(
            usuario: Usuario = Depends(require_role("ADMIN")),
        ):
            ...

    Args:
        *roles: One or more role codes (e.g. "ADMIN", "PEDIDOS", "STOCK").
                At least one must match the user's active roles.

    Returns:
        A FastAPI-compatible dependency callable.

    Raises:
        UnauthorizedError: If authentication fails (propagated from get_current_user).
        ForbiddenError: If the user is authenticated but lacks all required roles.
    """

    async def _check(
        usuario: Usuario = Depends(get_current_user),
        uow: UnitOfWork = Depends(get_uow),
    ) -> Usuario:
        """Inner dependency: verify role membership for the authenticated user.

        Queries active UsuarioRol records for the user and checks if any role
        code is in the required roles set. Only active (non-soft-deleted) role
        assignments are counted.
        """
        # Query active UsuarioRol records for this user.
        # UsuarioRol with deleted_at IS NOT NULL are excluded via list_all default.
        usuario_roles = await uow.usuario_roles.list_all(
            filters={"usuario_id": usuario.id}
        )

        # For each active role assignment, load the Rol and check codigo.
        user_role_codes: set[str] = set()
        for ur in usuario_roles:
            if ur.rol is not None:
                user_role_codes.add(ur.rol.codigo)

        required_set = set(roles)
        if not user_role_codes.intersection(required_set):
            logger.warning(
                "auth.insufficient_permissions",
                user_id=str(usuario.id),
                required_roles=list(required_set),
                user_roles=list(user_role_codes),
            )
            raise ForbiddenError("Permisos insuficientes", code="forbidden")

        return usuario

    return _check
