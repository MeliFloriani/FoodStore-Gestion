"""
ProfileService — stateless profile management business logic.

Change 13: customer-profile-management.

Contains:
  - update_profile: update editable user fields (nombre, apellido). Email is
    immutable — ProfileUpdate schema enforces this via extra='ignore'.
  - change_password: verify current password, hash new password, revoke all
    refresh tokens for the user, all within a single UnitOfWork transaction.

Architectural rules:
  - session.commit() is NEVER called here — UnitOfWork owns the transaction.
  - All DB access goes through UnitOfWork typed repos (uow.usuarios, uow.refresh_tokens).
  - HTTPException is NEVER raised here — AppError subclasses (NotFoundError,
    ConflictError) are used and converted by the global error handler in
    app/api/errors.py.
  - All methods are @staticmethod — no per-instance state.
"""

from __future__ import annotations

import uuid

from app.core.exceptions import ConflictError, NotFoundError
from app.core.security import hash_password, verify_password
from app.core.uow import UnitOfWork
from app.schemas.profile import PasswordChangeRequest, ProfileUpdate, UserRead


class ProfileService:
    """Stateless service for user profile management operations.

    All methods are @staticmethod — no per-instance state.
    Receives UnitOfWork as a parameter for every operation.
    """

    @staticmethod
    async def update_profile(
        uow: UnitOfWork, user_id: uuid.UUID, data: ProfileUpdate
    ) -> UserRead:
        """Update editable profile fields for the authenticated user.

        Logic:
        1. Fetch user by user_id. Raise NotFoundError if not found.
        2. Build update dict of non-None fields only.
        3. If no fields to update (all-None), return current UserRead without DB write.
        4. Apply fields to the model, persist via add(), return updated UserRead.

        Args:
            uow: UnitOfWork context (provides transactional access to repos).
            user_id: UUID of the authenticated user (from JWT via get_current_user).
            data: ProfileUpdate with optional nombre/apellido. Email ignored by schema.

        Returns:
            UserRead of the updated (or unchanged) user.

        Raises:
            NotFoundError: If the user does not exist (code="USER_NOT_FOUND").
        """
        async with uow:
            user = await uow.usuarios.get(user_id)
            if not user:
                raise NotFoundError(
                    f"Usuario con id={user_id} no encontrado",
                    code="USER_NOT_FOUND",
                )

            update_data = data.model_dump(exclude_none=True)

            if not update_data:
                # All-None payload → idempotent no-op
                return UserRead.model_validate(user)

            for field, value in update_data.items():
                setattr(user, field, value)

            await uow.usuarios.add(user)
            return UserRead.model_validate(user)

    @staticmethod
    async def change_password(
        uow: UnitOfWork, user_id: uuid.UUID, data: PasswordChangeRequest
    ) -> None:
        """Change user password and revoke all active refresh tokens atomically.

        Transactional constraint: password hash update AND token revocation occur
        within the SAME UnitOfWork context. If either fails, both roll back.

        Logic:
        1. Fetch user by user_id. Raise NotFoundError if not found.
        2. Verify current_password against stored hash. Raise ConflictError (409) if wrong.
        3. Hash new_password with bcrypt (cost from settings).
        4. Update user.password_hash via add().
        5. Revoke ALL active refresh tokens for user via revoke_all_for_user().
        6. Return None (caller → 204 No Content).

        Args:
            uow: UnitOfWork context (provides transactional access to repos).
            user_id: UUID of the authenticated user (from JWT via get_current_user).
            data: PasswordChangeRequest with current_password and new_password.

        Returns:
            None (HTTP 204 No Content).

        Raises:
            NotFoundError: If the user does not exist (code="USER_NOT_FOUND").
            ConflictError: If current_password does not match (code="CURRENT_PASSWORD_MISMATCH").
        """
        async with uow:
            user = await uow.usuarios.get(user_id)
            if not user:
                raise NotFoundError(
                    f"Usuario con id={user_id} no encontrado",
                    code="USER_NOT_FOUND",
                )

            if not verify_password(data.current_password, user.password_hash):
                raise ConflictError(
                    "La contraseña actual no coincide",
                    code="CURRENT_PASSWORD_MISMATCH",
                )

            user.password_hash = hash_password(data.new_password)
            await uow.usuarios.add(user)
            await uow.refresh_tokens.revoke_all_for_user(user_id)
            # UoW commits on __aexit__ — no session.commit() here
            return None
