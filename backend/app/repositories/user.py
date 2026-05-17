"""
Concrete repository implementations for the auth / identity domain.

Change auth-register-login extends each repository with domain-specific query methods:
  - UsuarioRepository.get_by_email (task 4.5)
  - RolRepository.get_by_codigo (task 4.3)
  - RefreshTokenRepository.insert / revoke_by_hash (task 4.1)

Change auth-refresh-logout-rbac-me adds to RefreshTokenRepository:
  - find_by_hash (task 3.1) — lookup by hash without active filter
  - find_active_by_hash (task 3.2) — lookup only if not revoked and not expired
  - create_with_family (task 3.3) — delegates to BaseRepository.create()
  - revoke_family (task 3.4) — bulk UPDATE all tokens of same family_id

All mutations use session.flush() only — session.commit() is the exclusive
responsibility of UnitOfWork (see core/uow.py).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.user import RefreshToken, Rol, Usuario, UsuarioRol
from app.repositories.base import BaseRepository


class UsuarioRepository(BaseRepository[Usuario]):
    """Repository for the Usuario entity (auth path)."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Usuario, session)

    async def get_by_email(self, email: str) -> Usuario | None:
        """Return the active Usuario with the given email, or None if not found.

        Applies the soft-delete filter (deleted_at IS NULL) automatically.

        NOTE: The returned object has usuario_roles loaded via the model's
        lazy="selectin" strategy (fires during the SELECT). Safe to use with
        UserRead.model_validate() as long as this method is the load path.

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

    async def get_with_roles(self, user_id: uuid.UUID) -> Usuario | None:
        """Return an active Usuario with usuario_roles and each rol fully loaded.

        Uses explicit selectinload() options to guarantee that both levels of the
        relationship chain are populated in Python memory before returning:
            Usuario.usuario_roles  →  selectinload
            UsuarioRol.rol         →  selectinload (chained)

        This method MUST be used whenever the caller intends to serialize the
        result into UserRead (or any schema that accesses ur.rol.codigo), because
        SQLAlchemy 2.x async sessions cannot satisfy lazy loads in synchronous
        code (e.g. Pydantic's model_validate). Using a newly-created object
        (add + flush) directly would trigger MissingGreenlet.

        Design note: This is an intentional post-insert re-query pattern for
        SQLAlchemy async. The cost is two extra SELECTs (selectin strategy issues
        one query for usuario_roles + one for rol objects). Acceptable for an
        auth endpoint that runs once per registration.

        Args:
            user_id: UUID primary key of the Usuario to load.

        Returns:
            The Usuario instance with usuario_roles and rol fully loaded,
            or None if not found / soft-deleted.
        """
        result = await self.session.execute(
            select(Usuario)
            .where(
                Usuario.id == user_id,
                Usuario.deleted_at.is_(None),
            )
            .options(
                selectinload(Usuario.usuario_roles).selectinload(UsuarioRol.rol)
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
    Extended in Change auth-refresh-logout-rbac-me with find_by_hash(),
    find_active_by_hash(), create_with_family(), and revoke_family().

    NOTE: Callers MUST supply family_id when constructing RefreshToken instances
    for insert/create_with_family. The field is NOT NULL — omitting it raises a
    database error.
    """

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(RefreshToken, session)

    async def insert(self, token: RefreshToken) -> RefreshToken:
        """Persist a new RefreshToken by delegating to BaseRepository.create().

        NOTE: Callers must supply token.family_id — the field is NOT NULL.

        Args:
            token: The RefreshToken instance to persist.

        Returns:
            The persisted RefreshToken (with server-side defaults populated after flush).
        """
        return await self.create(token)

    async def find_by_hash(self, token_hash: str) -> RefreshToken | None:
        """Return the RefreshToken with the given hash, regardless of revocation state.

        No active filter — returns both active and revoked tokens. Used for
        replay detection: if find_active_by_hash returns None, this method
        determines whether the token was revoked (replay) or simply unknown.

        Args:
            token_hash: The SHA-256 hex digest of the refresh JWT.

        Returns:
            The RefreshToken instance, or None if not found.
        """
        result = await self.session.execute(
            select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        )
        return result.scalar_one_or_none()

    async def find_active_by_hash(self, token_hash: str) -> RefreshToken | None:
        """Return the RefreshToken only if it is not revoked and not expired.

        Args:
            token_hash: The SHA-256 hex digest of the refresh JWT.

        Returns:
            The RefreshToken instance if active (revoked_at IS NULL AND expires_at > now),
            or None if not found, revoked, or expired.
        """
        now_utc = datetime.now(timezone.utc)
        result = await self.session.execute(
            select(RefreshToken).where(
                RefreshToken.token_hash == token_hash,
                RefreshToken.revoked_at.is_(None),
                RefreshToken.expires_at > now_utc,
            )
        )
        return result.scalar_one_or_none()

    async def create_with_family(self, token: RefreshToken) -> RefreshToken:
        """Persist a new RefreshToken with family_id already set by the caller.

        Delegates to BaseRepository.create(). The caller is responsible for
        populating token.family_id (inheriting the parent token's family_id
        in a rotation scenario).

        Args:
            token: The RefreshToken instance with family_id already set.

        Returns:
            The persisted RefreshToken after flush.
        """
        return await self.create(token)

    async def revoke_family(self, family_id: uuid.UUID) -> int:
        """Revoke all active RefreshTokens with the given family_id.

        Sets revoked_at = now() on ALL rows with family_id == family_id WHERE
        revoked_at IS NULL. Idempotent — already-revoked rows are not affected.

        Used by the router in the second UoW after detecting a replay attack
        (D-07-C Opción A). The entire token family is revoked synchronously
        before the 401 response is returned to the client.

        Args:
            family_id: The UUID family group identifier shared by related tokens.

        Returns:
            The count of rows that were revoked (0 if all were already revoked).
        """
        now_utc = datetime.now(timezone.utc)
        result = await self.session.execute(
            update(RefreshToken)
            .where(
                RefreshToken.family_id == family_id,
                RefreshToken.revoked_at.is_(None),
            )
            .values(revoked_at=now_utc)
            .execution_options(synchronize_session="fetch")
        )
        await self.session.flush()
        return result.rowcount  # type: ignore[return-value]

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
