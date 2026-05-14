"""
Unit tests for AuthService.register_user and AuthService.login_user.

Tasks 5.3, 6.2, 6.3, 6.4 — uses MagicMock to isolate the service from the DB.

These tests mock the UnitOfWork and its repositories to test service logic only.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.exceptions import ConflictError, UnauthorizedError
from app.models.user import Rol, Usuario
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse
from app.services.auth import AuthService


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_mock_uow() -> MagicMock:
    """Build a fully mocked UnitOfWork with async repo methods."""
    uow = MagicMock()
    uow.usuarios = MagicMock()
    uow.roles = MagicMock()
    uow.usuario_roles = MagicMock()
    uow.refresh_tokens = MagicMock()

    # All repo methods return coroutines
    uow.usuarios.get_by_email = AsyncMock(return_value=None)
    uow.usuarios.create = AsyncMock()
    uow.roles.get_by_codigo = AsyncMock(return_value=None)
    uow.usuario_roles.create = AsyncMock()
    uow.refresh_tokens.insert = AsyncMock()

    return uow


def _make_usuario(email: str = "juan@example.com") -> Usuario:
    """Build a mock Usuario with a preset bcrypt hash."""
    usuario = MagicMock(spec=Usuario)
    usuario.id = uuid.uuid4()
    usuario.email = email
    usuario.nombre = "Juan"
    usuario.apellido = "Pérez"
    # Pre-computed bcrypt hash for password "Secur3Pass!"
    # This hash is intentionally not real for speed — tests verify the logic, not bcrypt.
    usuario.password_hash = "$2b$12$KIXAjkl7EYvs4j3JaWmg7OX7RFT1jCjN6jY6uaVl9b9gfXoKRpAo"
    usuario.usuario_roles = []
    return usuario


def _make_rol(codigo: str = "CLIENT") -> Rol:
    """Build a mock Rol."""
    rol = MagicMock(spec=Rol)
    rol.id = uuid.uuid4()
    rol.codigo = codigo
    return rol


def _make_register_data() -> RegisterRequest:
    return RegisterRequest(
        nombre="Juan",
        apellido="Pérez",
        email="juan@example.com",
        password="Secur3Pass!",
    )


def _make_login_data(email: str = "juan@example.com", password: str = "Secur3Pass!") -> LoginRequest:
    return LoginRequest(email=email, password=password)


# ---------------------------------------------------------------------------
# Task 5.3 — AuthService.register_user
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_register_user_success(override_settings) -> None:
    """Successful registration returns a Usuario instance."""
    uow = _make_mock_uow()
    # Email does not exist
    uow.usuarios.get_by_email = AsyncMock(return_value=None)
    # create() returns a fake usuario
    saved_usuario = _make_usuario()
    uow.usuarios.create = AsyncMock(return_value=saved_usuario)
    # CLIENT role exists
    uow.roles.get_by_codigo = AsyncMock(return_value=_make_rol("CLIENT"))
    # UsuarioRol create returns anything
    uow.usuario_roles.create = AsyncMock(return_value=MagicMock())

    data = _make_register_data()
    result = await AuthService.register_user(uow, data)

    assert result is saved_usuario
    uow.usuarios.get_by_email.assert_called_once_with(data.email)
    uow.usuarios.create.assert_called_once()
    uow.roles.get_by_codigo.assert_called_once_with("CLIENT")
    uow.usuario_roles.create.assert_called_once()


@pytest.mark.asyncio
async def test_register_user_409_on_duplicate_email(override_settings) -> None:
    """Registration raises ConflictError when the email is already taken."""
    uow = _make_mock_uow()
    # Email already exists
    uow.usuarios.get_by_email = AsyncMock(return_value=_make_usuario())

    data = _make_register_data()
    with pytest.raises(ConflictError) as exc_info:
        await AuthService.register_user(uow, data)

    assert exc_info.value.code == "email_conflict"
    assert exc_info.value.status_code == 409
    # Should not proceed to create user
    uow.usuarios.create.assert_not_called()


@pytest.mark.asyncio
async def test_register_user_500_when_client_role_missing(override_settings) -> None:
    """Registration raises RuntimeError when the CLIENT role is not seeded."""
    uow = _make_mock_uow()
    uow.usuarios.get_by_email = AsyncMock(return_value=None)
    uow.usuarios.create = AsyncMock(return_value=_make_usuario())
    # CLIENT role not in DB
    uow.roles.get_by_codigo = AsyncMock(return_value=None)

    data = _make_register_data()
    with pytest.raises(RuntimeError, match="CLIENT role not seeded"):
        await AuthService.register_user(uow, data)


# ---------------------------------------------------------------------------
# Task 6.2 — AuthService.login_user happy path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_login_user_happy_path(override_settings) -> None:
    """Successful login returns a TokenResponse with the correct structure."""
    from app.core.security import hash_password

    uow = _make_mock_uow()
    password = "Secur3Pass!"
    usuario = _make_usuario()
    usuario.password_hash = hash_password(password)

    uow.usuarios.get_by_email = AsyncMock(return_value=usuario)
    uow.refresh_tokens.insert = AsyncMock(return_value=MagicMock())

    data = _make_login_data(password=password)
    request = MagicMock()

    result = await AuthService.login_user(uow, data, request)

    assert isinstance(result, TokenResponse)
    assert result.token_type == "bearer"
    assert result.expires_in == 1800
    assert result.access_token
    assert result.refresh_token
    # Refresh token must have been persisted
    uow.refresh_tokens.insert.assert_called_once()


# ---------------------------------------------------------------------------
# Task 6.3 — wrong password raises UnauthorizedError
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_login_user_wrong_password(override_settings) -> None:
    """login_user raises UnauthorizedError with code 'invalid_credentials' for wrong password."""
    from app.core.security import hash_password

    uow = _make_mock_uow()
    usuario = _make_usuario()
    usuario.password_hash = hash_password("CorrectPassword!")

    uow.usuarios.get_by_email = AsyncMock(return_value=usuario)

    data = _make_login_data(password="WrongPassword!")
    request = MagicMock()

    with pytest.raises(UnauthorizedError) as exc_info:
        await AuthService.login_user(uow, data, request)

    assert exc_info.value.code == "invalid_credentials"
    assert exc_info.value.status_code == 401


# ---------------------------------------------------------------------------
# Task 6.4 — enumeration prevention: unknown email returns same error shape
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_login_user_unknown_email_same_error_shape(override_settings) -> None:
    """login_user raises the same UnauthorizedError for unknown email as for wrong password."""
    uow = _make_mock_uow()
    # Email does not exist
    uow.usuarios.get_by_email = AsyncMock(return_value=None)

    data = _make_login_data(email="nobody@example.com", password="AnyPassword!")
    request = MagicMock()

    with pytest.raises(UnauthorizedError) as exc_info:
        await AuthService.login_user(uow, data, request)

    error = exc_info.value
    assert error.code == "invalid_credentials"
    assert error.status_code == 401
    # The detail must be the same as the wrong-password path
    assert error.detail == "Invalid credentials"


@pytest.mark.asyncio
async def test_login_user_unknown_email_does_not_expose_email(override_settings) -> None:
    """The error raised for unknown email must not reveal that the email was not found."""
    uow = _make_mock_uow()
    uow.usuarios.get_by_email = AsyncMock(return_value=None)

    data = _make_login_data(email="mystery@example.com")
    request = MagicMock()

    with pytest.raises(UnauthorizedError) as exc_info:
        await AuthService.login_user(uow, data, request)

    # The detail should not mention "email", "user", "not found", etc.
    detail_lower = exc_info.value.detail.lower()
    assert "email" not in detail_lower
    assert "not found" not in detail_lower
    assert "user" not in detail_lower
