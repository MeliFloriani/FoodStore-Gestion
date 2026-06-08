"""
AdminUsuariosService — stateless admin user management business logic.

Change 21: admin-users-management.

Contains:
  - list_usuarios: paginated listing with search and filters.
  - get_usuario: fetch a single user by ID.
  - update_usuario_data: update editable fields (nombre, apellido only — D-01).
  - update_usuario_roles: replace full role set with last-admin guard (D-02, D-03).
  - deactivate_usuario: soft-delete or reactivate with last-admin guard (D-03, D-05).

Architectural rules:
  - session.commit() is NEVER called here — UnitOfWork owns the transaction.
  - HTTPException is NEVER raised here — AppError subclasses are used and
    converted by the global error handler (app/api/errors.py).
  - All methods are @staticmethod — no per-instance state.
  - The UnitOfWork lifecycle is owned by the router via get_uow() (same pattern
    as AuthService). Services receive the active UoW and use it directly — they
    do NOT call `async with uow:` themselves. Opening `async with uow:` inside a
    service creates a new session, bypassing the test session injection in
    integration tests.

Last-admin guard (D-03):
  - SELECT FOR UPDATE on the target user's rows via count_active_admins().
  - Serializes concurrent degradation attempts (race condition prevention).
  - Raises ConflictError(code="LAST_ADMIN_PROTECTED") when count == 0.
"""

from __future__ import annotations

import uuid

from app.core.exceptions import ConflictError, NotFoundError
from app.core.uow import UnitOfWork
from app.models.user import UsuarioRol
from app.schemas.admin_usuarios import (
    UsuarioAdminRead,
    UsuarioAdminUpdate,
)
from app.schemas.base import Page, create_pagination_meta


class AdminUsuariosService:
    """Stateless service for admin user management operations.

    All methods are @staticmethod — no per-instance state.
    Receives UnitOfWork as a parameter for every operation.
    """

    @staticmethod
    async def list_usuarios(
        uow: UnitOfWork,
        *,
        page: int,
        size: int,
        q: str | None,
        rol: str | None,
        activo: bool | None,
    ) -> Page[UsuarioAdminRead]:
        """Return a paginated list of users with optional search and filters.

        Args:
            uow: Active UnitOfWork (lifecycle managed by get_uow in the router).
            page: 1-based page number.
            size: Items per page.
            q: Search string (ILIKE on nombre/apellido/email).
            rol: Role code filter.
            activo: True=active only, False=inactive only, None=all.

        Returns:
            Page[UsuarioAdminRead] with items, total, page, size, pages.
        """
        items, total = await uow.admin_usuarios.list_paginated(
            page=page,
            size=size,
            q=q,
            rol=rol,
            activo=activo,
        )
        meta = create_pagination_meta(total=total, page=page, size=size)
        read_items = [UsuarioAdminRead.from_usuario(u) for u in items]
        return Page[UsuarioAdminRead](items=read_items, **meta)

    @staticmethod
    async def get_usuario(
        uow: UnitOfWork,
        user_id: uuid.UUID,
    ) -> UsuarioAdminRead:
        """Return a single user by ID.

        Args:
            uow: Active UnitOfWork (lifecycle managed by get_uow in the router).
            user_id: UUID of the user to fetch.

        Returns:
            UsuarioAdminRead for the user.

        Raises:
            NotFoundError: If the user does not exist (code="USER_NOT_FOUND").
        """
        user = await uow.usuarios.get_with_roles(user_id)
        if user is None:
            raise NotFoundError(
                f"Usuario con id={user_id} no encontrado",
                code="USER_NOT_FOUND",
            )
        return UsuarioAdminRead.from_usuario(user)

    @staticmethod
    async def update_usuario_data(
        uow: UnitOfWork,
        user_id: uuid.UUID,
        data: UsuarioAdminUpdate,
    ) -> UsuarioAdminRead:
        """Update editable profile fields for a user (nombre and/or apellido only).

        D-01: email is NOT editable — UsuarioAdminUpdate schema does not include
        the email field. extra="ignore" silently drops any email in the payload.

        Logic:
        1. Fetch user with roles. Raise NotFoundError if not found.
        2. Build update dict from non-None fields only.
        3. If empty (all-None), return current UsuarioAdminRead without DB write.
        4. Apply fields via setattr, flush via session.add + flush.
        5. Re-query with get_with_roles to reload relationships.
        6. Return UsuarioAdminRead.

        Args:
            uow: Active UnitOfWork (lifecycle managed by get_uow in the router).
            user_id: UUID of the user to update.
            data: UsuarioAdminUpdate with optional nombre/apellido.

        Returns:
            UsuarioAdminRead of the updated (or unchanged) user.

        Raises:
            NotFoundError: If the user does not exist (code="USER_NOT_FOUND").
        """
        user = await uow.usuarios.get_with_roles(user_id)
        if user is None:
            raise NotFoundError(
                f"Usuario con id={user_id} no encontrado",
                code="USER_NOT_FOUND",
            )

        update_data = data.model_dump(exclude_none=True)

        if not update_data:
            return UsuarioAdminRead.from_usuario(user)

        for field, value in update_data.items():
            setattr(user, field, value)

        uow.session.add(user)
        await uow.session.flush()

        # Re-query to get fresh relationships
        reloaded = await uow.usuarios.get_with_roles(user_id)
        if reloaded is None:
            raise NotFoundError(
                f"Usuario con id={user_id} no encontrado después de actualizar",
                code="USER_NOT_FOUND",
            )
        return UsuarioAdminRead.from_usuario(reloaded)

    @staticmethod
    async def update_usuario_roles(
        uow: UnitOfWork,
        user_id: uuid.UUID,
        new_roles: list[str],
        admin_id: uuid.UUID,
    ) -> UsuarioAdminRead:
        """Replace the full role set for a user (PUT replace semantics — D-02).

        Algorithm (D-03 last-admin guard):
        1. Load target user with roles (404 if not found).
        2. Extract current role codes.
        3. IF 'ADMIN' is in current roles AND 'ADMIN' is NOT in new_roles:
           a. Call count_active_admins(exclude=user_id) — SELECT FOR UPDATE.
           b. IF count == 0 → raise ConflictError(LAST_ADMIN_PROTECTED).
        4. Hard-delete all current UsuarioRol records.
        5. Insert new UsuarioRol records (asignado_por_id = admin_id).
        6. Revoke all refresh tokens for the user (US-054: force re-login).
        7. Re-query and return UsuarioAdminRead.

        Args:
            uow: Active UnitOfWork (lifecycle managed by get_uow in the router).
            user_id: UUID of the user whose roles to replace.
            new_roles: Complete desired set of role codes (already validated/deduped).
            admin_id: UUID of the admin performing the operation (for audit trail).

        Returns:
            UsuarioAdminRead of the user with updated roles.

        Raises:
            NotFoundError: If user not found (code="USER_NOT_FOUND").
            ConflictError: If removing ADMIN from last admin (code="LAST_ADMIN_PROTECTED").
        """
        user = await uow.usuarios.get_with_roles(user_id)
        if user is None:
            raise NotFoundError(
                f"Usuario con id={user_id} no encontrado",
                code="USER_NOT_FOUND",
            )

        # Extract current role codes
        current_codes = {
            ur.rol.codigo
            for ur in user.usuario_roles
            if ur.rol is not None
        }

        # Last-admin guard: check if ADMIN is being removed
        if "ADMIN" in current_codes and "ADMIN" not in new_roles:
            count = await uow.admin_usuarios.count_active_admins(
                exclude_user_id=user_id
            )
            if count == 0:
                raise ConflictError(
                    "No se puede quitar el rol ADMIN al último administrador del sistema",
                    code="LAST_ADMIN_PROTECTED",
                )

        # Hard-delete all current UsuarioRol records
        for ur in list(user.usuario_roles):
            await uow.session.delete(ur)
        await uow.session.flush()

        # Insert new UsuarioRol records
        for codigo in new_roles:
            rol = await uow.roles.get_by_codigo(codigo)
            if rol is None:
                raise NotFoundError(
                    f"Rol '{codigo}' no encontrado",
                    code="ROLE_NOT_FOUND",
                )
            new_ur = UsuarioRol(
                usuario_id=user_id,
                rol_id=rol.id,
                asignado_por_id=admin_id,
            )
            uow.session.add(new_ur)

        await uow.session.flush()

        # Revoke all refresh tokens (US-054: force re-login with new roles)
        await uow.refresh_tokens.revoke_all_for_user(user_id)

        # Re-query with eager-loaded roles
        reloaded = await uow.usuarios.get_with_roles(user_id)
        if reloaded is None:
            raise NotFoundError(
                f"Usuario con id={user_id} no encontrado después de actualizar roles",
                code="USER_NOT_FOUND",
            )
        return UsuarioAdminRead.from_usuario(reloaded)

    @staticmethod
    async def deactivate_usuario(
        uow: UnitOfWork,
        user_id: uuid.UUID,
        activo: bool,
    ) -> UsuarioAdminRead:
        """Soft-delete (deactivate) or reactivate a user.

        Deactivation (activo=False):
        1. Load user with roles (404 if not found).
        2. IF user has ADMIN role AND user is currently active:
           a. count_active_admins(exclude=user_id) — SELECT FOR UPDATE.
           b. IF count == 0 → raise ConflictError(LAST_ADMIN_PROTECTED).
        3. IF user is already inactive (deleted_at IS NOT NULL) → idempotent, skip.
        4. user.soft_delete() — sets deleted_at = now().
        5. revoke_all_for_user(user_id) — US-055 requirement.

        Reactivation (activo=True — D-05):
        1. Load user with include_deleted=True (404 if not found at all).
        2. IF user is already active (deleted_at IS NULL) → idempotent, skip.
        3. user.deleted_at = None.

        Args:
            uow: Active UnitOfWork (lifecycle managed by get_uow in the router).
            user_id: UUID of the user to activate/deactivate.
            activo: False to deactivate, True to reactivate.

        Returns:
            UsuarioAdminRead of the user after the operation.

        Raises:
            NotFoundError: If user not found (code="USER_NOT_FOUND").
            ConflictError: If deactivating the last ADMIN (code="LAST_ADMIN_PROTECTED").
        """
        if not activo:
            # Deactivation path
            user = await uow.usuarios.get_with_roles(user_id)
            if user is None:
                raise NotFoundError(
                    f"Usuario con id={user_id} no encontrado",
                    code="USER_NOT_FOUND",
                )

            # Check if user has ADMIN role
            has_admin_role = any(
                ur.rol is not None and ur.rol.codigo == "ADMIN"
                for ur in user.usuario_roles
            )

            if has_admin_role:
                count = await uow.admin_usuarios.count_active_admins(
                    exclude_user_id=user_id
                )
                if count == 0:
                    raise ConflictError(
                        "No se puede desactivar al último administrador del sistema",
                        code="LAST_ADMIN_PROTECTED",
                    )

            # Idempotent: if already inactive, return current state
            if user.deleted_at is not None:
                return UsuarioAdminRead.from_usuario(user)

            # Soft-delete and revoke tokens
            user.soft_delete()
            await uow.session.flush()
            await uow.refresh_tokens.revoke_all_for_user(user_id)

        else:
            # Reactivation path (D-05)
            # Use get_by_id with include_deleted=True to fetch even soft-deleted users
            user = await uow.usuarios.get_by_id(user_id, include_deleted=True)
            if user is None:
                raise NotFoundError(
                    f"Usuario con id={user_id} no encontrado",
                    code="USER_NOT_FOUND",
                )

            # Idempotent: if already active, return current state
            if user.deleted_at is None:
                # Re-query with roles for proper response
                user_with_roles = await uow.usuarios.get_with_roles(user_id)
                if user_with_roles is None:
                    return UsuarioAdminRead.from_usuario(user)
                return UsuarioAdminRead.from_usuario(user_with_roles)

            user.deleted_at = None
            await uow.session.flush()

        # Re-query with roles for proper response
        # For reactivated users, need to search including soft-deleted state now cleared
        reloaded = await uow.usuarios.get_with_roles(user_id)
        if reloaded is None:
            # User was just reactivated - fetch with include_deleted won't be needed now
            # but as fallback use the in-memory object
            return UsuarioAdminRead.from_usuario(user)
        return UsuarioAdminRead.from_usuario(reloaded)
