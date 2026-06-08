"""
AdminUsuariosRepository — data-access layer for the admin user management feature.

Change 21: admin-users-management.

Extends BaseRepository[Usuario] with:
  - list_paginated: paginated listing with ILIKE search + rol/activo filters.
  - count_active_admins: count active ADMINs excluding a specific user.
    Uses SELECT FOR UPDATE on the target user row to prevent TOCTOU race
    conditions in the last-admin guard (D-03).

All methods use flush-only contract inherited from BaseRepository.
No session.commit() is ever called here.
"""

from __future__ import annotations

import uuid

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.user import Rol, Usuario, UsuarioRol
from app.repositories.base import BaseRepository


class AdminUsuariosRepository(BaseRepository[Usuario]):
    """Repository for admin user management operations."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Usuario, session)

    async def list_paginated(
        self,
        *,
        page: int,
        size: int,
        q: str | None,
        rol: str | None,
        activo: bool | None,
    ) -> tuple[list[Usuario], int]:
        """Return paginated users with optional search and filter.

        Args:
            page: 1-based page number.
            size: Items per page (max 100).
            q: Search string for ILIKE on nombre, apellido, or email.
            rol: Filter by role code (e.g. "ADMIN", "CLIENT").
            activo: True = active only, False = inactive only, None = all.

        Returns:
            Tuple of (items, total) where items is the page slice and total
            is the count matching all filters (for pagination metadata).
        """
        # --- Base query with eager loading of roles ---
        base_stmt = (
            select(Usuario)
            .options(
                selectinload(Usuario.usuario_roles).selectinload(UsuarioRol.rol)
            )
        )

        count_stmt = select(func.count()).select_from(Usuario)

        # --- Filter: activo ---
        if activo is True:
            base_stmt = base_stmt.where(Usuario.deleted_at.is_(None))
            count_stmt = count_stmt.where(Usuario.deleted_at.is_(None))
        elif activo is False:
            base_stmt = base_stmt.where(Usuario.deleted_at.is_not(None))
            count_stmt = count_stmt.where(Usuario.deleted_at.is_not(None))
        # activo is None → no filter (include all)

        # --- Filter: search query (ILIKE on nombre, apellido, email) ---
        if q:
            search_pattern = f"%{q}%"
            ilike_filter = or_(
                Usuario.nombre.ilike(search_pattern),
                Usuario.apellido.ilike(search_pattern),
                Usuario.email.ilike(search_pattern),
            )
            base_stmt = base_stmt.where(ilike_filter)
            count_stmt = count_stmt.where(ilike_filter)

        # --- Filter: rol (join to UsuarioRol + Rol) ---
        if rol:
            rol_filter = and_(
                UsuarioRol.usuario_id == Usuario.id,
                UsuarioRol.deleted_at.is_(None),
                Rol.id == UsuarioRol.rol_id,
                Rol.codigo == rol,
                Rol.deleted_at.is_(None),
            )
            base_stmt = base_stmt.join(UsuarioRol, UsuarioRol.usuario_id == Usuario.id).join(
                Rol, Rol.id == UsuarioRol.rol_id
            ).where(
                UsuarioRol.deleted_at.is_(None),
                Rol.codigo == rol,
                Rol.deleted_at.is_(None),
            ).distinct()
            count_stmt = count_stmt.join(UsuarioRol, UsuarioRol.usuario_id == Usuario.id).join(
                Rol, Rol.id == UsuarioRol.rol_id
            ).where(
                UsuarioRol.deleted_at.is_(None),
                Rol.codigo == rol,
                Rol.deleted_at.is_(None),
            )

        # --- ORDER BY: newest first ---
        base_stmt = base_stmt.order_by(Usuario.created_at.desc())

        # --- Pagination ---
        offset = (page - 1) * size
        paginated_stmt = base_stmt.offset(offset).limit(size)

        # Execute both queries
        items_result = await self.session.execute(paginated_stmt)
        items = list(items_result.scalars().all())

        count_result = await self.session.execute(count_stmt)
        total = int(count_result.scalar() or 0)

        return items, total

    async def count_active_admins(self, *, exclude_user_id: uuid.UUID) -> int:
        """Count active ADMIN users excluding a specific user.

        Used in the last-admin guard before removing ADMIN role or deactivating
        a user. Uses SELECT FOR UPDATE on the usuario rows to prevent TOCTOU
        race conditions when two concurrent transactions both check the guard
        simultaneously (D-03).

        The lock serializes concurrent degradation attempts: the first
        transaction to acquire the lock sees the current count; the second
        sees the count AFTER the first has already modified the role assignments.

        PostgreSQL does not allow FOR UPDATE with aggregate functions (COUNT),
        so we SELECT the actual usuario.id rows with FOR UPDATE and count them
        in Python. This achieves the same row-level locking semantics.

        Args:
            exclude_user_id: UUID of the user being modified (excluded from count).

        Returns:
            Count of active ADMIN users (excluding the target user).
        """
        stmt = (
            select(Usuario.id)
            .join(UsuarioRol, UsuarioRol.usuario_id == Usuario.id)
            .join(Rol, Rol.id == UsuarioRol.rol_id)
            .where(
                Rol.codigo == "ADMIN",
                Usuario.deleted_at.is_(None),
                UsuarioRol.deleted_at.is_(None),
                Rol.deleted_at.is_(None),
                Usuario.id != exclude_user_id,
            )
            .with_for_update(of=Usuario)
        )
        result = await self.session.execute(stmt)
        return len(result.all())
