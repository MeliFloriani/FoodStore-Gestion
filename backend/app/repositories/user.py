"""
Concrete repository implementations for the auth / identity domain.

These repositories are needed by UnitOfWork typed accessors in this change (Change 04).
They intentionally have no extra methods — all CRUD is inherited from BaseRepository[T].
Domain-specific query methods (e.g. get_by_email) will be added in Change 06.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import RefreshToken, Rol, Usuario, UsuarioRol
from app.repositories.base import BaseRepository


class UsuarioRepository(BaseRepository[Usuario]):
    """Repository for the Usuario entity (auth path)."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Usuario, session)


class RolRepository(BaseRepository[Rol]):
    """Repository for the Rol entity (RBAC path)."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Rol, session)


class UsuarioRolRepository(BaseRepository[UsuarioRol]):
    """Repository for the UsuarioRol pivot entity (role assignment path)."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(UsuarioRol, session)


class RefreshTokenRepository(BaseRepository[RefreshToken]):
    """Repository for the RefreshToken entity.

    No methods are called on this repository in Change 04 — it is included
    so that uow.refresh_tokens type-checks correctly.
    Token issuance and verification logic is deferred to Change 06.
    """

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(RefreshToken, session)
