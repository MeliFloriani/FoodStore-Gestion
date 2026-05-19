"""
Unit tests for ProfileService.

Tasks 3.1, 3.2 — TDD red phase.

Covers:
  - update_profile: updates nombre, returns UserRead
  - update_profile: all-None no-op, returns current UserRead
  - update_profile: raises 404 for non-existent user_id
  - change_password: correct current_password → hash updated + tokens revoked
  - change_password: wrong current_password → 409
  - change_password: rollback if revoke_all_for_user raises
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.exceptions import ConflictError, NotFoundError


def _make_mock_uow() -> MagicMock:
    """Build a fully mocked UnitOfWork with async repo methods."""
    uow = MagicMock()
    uow.__aenter__ = AsyncMock(return_value=uow)
    uow.__aexit__ = AsyncMock(return_value=False)

    uow.usuarios = MagicMock()
    uow.refresh_tokens = MagicMock()

    uow.usuarios.get = AsyncMock(return_value=None)
    uow.usuarios.add = AsyncMock()
    uow.refresh_tokens.revoke_all_for_user = AsyncMock(return_value=0)

    return uow


def _make_mock_usuario(
    nombre: str = "Juan",
    apellido: str = "Pérez",
    email: str = "juan@example.com",
) -> MagicMock:
    """Build a mock Usuario with preset attributes."""
    usuario = MagicMock()
    usuario.id = uuid.uuid4()
    usuario.nombre = nombre
    usuario.apellido = apellido
    usuario.email = email
    usuario.created_at = datetime.now(timezone.utc)
    usuario.password_hash = "$2b$12$KIXAjkl7EYvs4j3JaWmg7OX7RFT1jCjN6jY6uaVl9b9gfXoKRpAo"
    usuario.usuario_roles = []
    return usuario


# ---------------------------------------------------------------------------
# Task 3.1 — ProfileService.update_profile
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_profile_updates_nombre_returns_user_read() -> None:
    """update_profile with ProfileUpdate(nombre='New') → updates nombre, returns UserRead."""
    from app.schemas.profile import ProfileUpdate
    from app.services.profile import ProfileService

    usuario = _make_mock_usuario()
    uow = _make_mock_uow()
    uow.usuarios.get = AsyncMock(return_value=usuario)

    data = ProfileUpdate(nombre="Nuevo Nombre")
    result = await ProfileService.update_profile(uow, usuario.id, data)

    assert result.nombre == "Nuevo Nombre"
    uow.usuarios.add.assert_called_once_with(usuario)


@pytest.mark.asyncio
async def test_update_profile_all_none_is_noop() -> None:
    """update_profile with all-None payload → no-op, returns current UserRead."""
    from app.schemas.profile import ProfileUpdate
    from app.services.profile import ProfileService

    usuario = _make_mock_usuario(nombre="Original")
    uow = _make_mock_uow()
    uow.usuarios.get = AsyncMock(return_value=usuario)

    data = ProfileUpdate()  # all None
    result = await ProfileService.update_profile(uow, usuario.id, data)

    # Should return current data without DB write
    assert result.nombre == "Original"
    uow.usuarios.add.assert_not_called()


@pytest.mark.asyncio
async def test_update_profile_raises_404_for_nonexistent_user() -> None:
    """update_profile with non-existent user_id → raises NotFoundError (HTTP 404)."""
    from app.schemas.profile import ProfileUpdate
    from app.services.profile import ProfileService

    uow = _make_mock_uow()
    uow.usuarios.get = AsyncMock(return_value=None)  # User not found

    data = ProfileUpdate(nombre="X")
    with pytest.raises(NotFoundError) as exc_info:
        await ProfileService.update_profile(uow, uuid.uuid4(), data)

    assert exc_info.value.code == "USER_NOT_FOUND"
    assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# Task 3.2 — ProfileService.change_password
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_change_password_updates_hash_and_revokes_tokens() -> None:
    """change_password with correct current_password → hash updated + tokens revoked."""
    from app.schemas.profile import PasswordChangeRequest
    from app.services.profile import ProfileService

    # Create a user with a real bcrypt hash of "OldPass1!"
    from app.core.security import hash_password

    usuario = _make_mock_usuario()
    usuario.password_hash = hash_password("OldPass1!")
    original_hash = usuario.password_hash

    uow = _make_mock_uow()
    uow.usuarios.get = AsyncMock(return_value=usuario)
    uow.refresh_tokens.revoke_all_for_user = AsyncMock(return_value=2)

    data = PasswordChangeRequest(
        current_password="OldPass1!", new_password="NewPass1!"
    )
    result = await ProfileService.change_password(uow, usuario.id, data)

    # Returns None (204)
    assert result is None
    # Hash was updated to new password
    assert usuario.password_hash != original_hash
    from app.core.security import verify_password
    assert verify_password("NewPass1!", usuario.password_hash)
    # Tokens were revoked
    uow.refresh_tokens.revoke_all_for_user.assert_called_once_with(usuario.id)


@pytest.mark.asyncio
async def test_change_password_raises_409_on_wrong_current_password() -> None:
    """change_password with wrong current_password → raises ConflictError (HTTP 409)."""
    from app.core.security import hash_password
    from app.schemas.profile import PasswordChangeRequest
    from app.services.profile import ProfileService

    usuario = _make_mock_usuario()
    usuario.password_hash = hash_password("CorrectPass!")

    uow = _make_mock_uow()
    uow.usuarios.get = AsyncMock(return_value=usuario)

    data = PasswordChangeRequest(
        current_password="WrongPass!", new_password="NewPass1!"
    )

    with pytest.raises(ConflictError) as exc_info:
        await ProfileService.change_password(uow, usuario.id, data)

    assert exc_info.value.code == "CURRENT_PASSWORD_MISMATCH"
    assert exc_info.value.status_code == 409
    # No DB writes should have happened
    uow.usuarios.add.assert_not_called()
    uow.refresh_tokens.revoke_all_for_user.assert_not_called()


@pytest.mark.asyncio
async def test_change_password_rolls_back_if_revoke_all_raises() -> None:
    """If revoke_all_for_user raises, the exception propagates (UoW rolls back)."""
    from app.core.security import hash_password
    from app.schemas.profile import PasswordChangeRequest
    from app.services.profile import ProfileService

    usuario = _make_mock_usuario()
    usuario.password_hash = hash_password("OldPass1!")

    uow = _make_mock_uow()
    uow.usuarios.get = AsyncMock(return_value=usuario)
    # Simulate a DB error during token revocation
    uow.refresh_tokens.revoke_all_for_user = AsyncMock(
        side_effect=RuntimeError("DB error during revocation")
    )
    # UoW __aexit__ should propagate the exception (return_value=False means reraise)
    uow.__aexit__ = AsyncMock(side_effect=RuntimeError("DB error during revocation"))

    data = PasswordChangeRequest(
        current_password="OldPass1!", new_password="NewPass1!"
    )

    with pytest.raises(RuntimeError, match="DB error"):
        await ProfileService.change_password(uow, usuario.id, data)


@pytest.mark.asyncio
async def test_change_password_raises_404_for_nonexistent_user() -> None:
    """change_password with non-existent user_id → raises NotFoundError (HTTP 404)."""
    from app.schemas.profile import PasswordChangeRequest
    from app.services.profile import ProfileService

    uow = _make_mock_uow()
    uow.usuarios.get = AsyncMock(return_value=None)

    data = PasswordChangeRequest(
        current_password="OldPass1!", new_password="NewPass1!"
    )

    with pytest.raises(NotFoundError) as exc_info:
        await ProfileService.change_password(uow, uuid.uuid4(), data)

    assert exc_info.value.code == "USER_NOT_FOUND"
