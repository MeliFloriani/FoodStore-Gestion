"""
Concrete repository implementations for the auth / identity domain.

Change auth-register-login extends each repository with domain-specific query methods:
  - UsuarioRepository.get_by_email (task 4.5)
  - RolRepository.get_by_codigo (task 4.3)
  - RefreshTokenRepository.insert / revoke_by_hash (task 4.1)

All mutations use session.flush() only — session.commit() is the exclusive
responsibility of UnitOfWork (see core/uow.py).
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import RefreshToken, Rol, Usuario, UsuarioRol
from app.repositories.base import BaseRepository


class UsuarioRepository(BaseRepository[Usuario]):
    """Repository for the Usuario entity (auth path)."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Usuario, session)

    async def get_by_email(self, email: str) -> Usuario | None:
        """Return the active Usuario with the given email, or None if not found.

        Applies the soft-delete filter (deleted_at IS NULL) automatically.

        Args:
            email: The email address to look up.

        Returns:
            The Usuario instance, or None if not found / soft-deleted.
        """
        result = await self.session.execute(
            select(Usuario).where(
                Usuario.email == email,
                Usuario.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()


class RolRepository(BaseRepository[Rol]):
    """Repository for the Rol entity (RBAC path)."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Rol, session)

    async def get_by_codigo(self, codigo: str) -> Rol | None:
        """Return the active Rol with the given semantic code, or None if not found.

        Args:
            codigo: The role code (e.g. "CLIENT", "ADMIN").

        Returns:
            The Rol instance, or None if not found / soft-deleted.
        """
        result = await self.session.execute(
            select(Rol).where(
                Rol.codigo == codigo,
                Rol.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()


class UsuarioRolRepository(BaseRepository[UsuarioRol]):
    """Repository for the UsuarioRol pivot entity (role assignment path)."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(UsuarioRol, session)


class RefreshTokenRepository(BaseRepository[RefreshToken]):
    """Repository for the RefreshToken entity.

    Extended in Change auth-register-login with insert() and revoke_by_hash().
    """

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(RefreshToken, session)

    async def insert(self, token: RefreshToken) -> RefreshToken:
        """Persist a new RefreshToken by delegating to BaseRepository.create().

        Args:
            token: The RefreshToken instance to persist.

        Returns:
            The persisted RefreshToken (with server-side defaults populated after flush).
        """
        return await self.create(token)

    async def revoke_by_hash(self, token_hash: str) -> bool:
        """Set revoked_at on the RefreshToken identified by token_hash.

        Args:
            token_hash: The SHA-256 hex digest of the refresh JWT.

        Returns:
            True if the token was found and revoked, False if not found.
        """
        result = await self.session.execute(
            select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        )
        token = result.scalar_one_or_none()
        if token is None:
            return False
        token.revoked_at = datetime.now(timezone.utc)
        await self.session.flush()
        return True
