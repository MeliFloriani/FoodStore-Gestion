"""
Unit/integration tests for the auth domain repositories.

Tasks 4.2, 4.4, 4.6 — RefreshTokenRepository, RolRepository, UsuarioRepository.

These tests use the SAVEPOINT-based async_session fixture so that all DB
mutations are rolled back after each test without committing.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio

from app.models.user import RefreshToken, Rol, Usuario, UsuarioRol
from app.repositories.user import (
    RefreshTokenRepository,
    RolRepository,
    UsuarioRepository,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_usuario(suffix: str = "") -> Usuario:
    """Build an unsaved Usuario for testing.

    The password_hash is exactly 60 characters (CHAR(60) constraint in the DB)
    with a valid bcrypt format prefix for the field constraint.
    """
    return Usuario(
        email=f"test{suffix}@example.com",
        # Exactly 60 chars — bcrypt hashes are always 60 chars
        password_hash="$2b$12$AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
        nombre="Test",
        apellido="User",
    )


def _make_rol(codigo: str = "TESTROLE") -> Rol:
    """Build an unsaved Rol for testing."""
    return Rol(codigo=codigo, nombre=f"Role {codigo}")


def _make_refresh_token(usuario_id: uuid.UUID, hours: int = 24) -> RefreshToken:
    """Build an unsaved RefreshToken for testing.

    Updated in Change 07 (auth-refresh-logout-rbac-me): family_id is now
    required (NOT NULL). A new UUID is generated per call to simulate login
    seeding a fresh family.
    """
    return RefreshToken(
        token_hash="a" * 64,
        usuario_id=usuario_id,
        family_id=uuid.uuid4(),
        expires_at=datetime.now(timezone.utc) + timedelta(hours=hours),
    )


# ---------------------------------------------------------------------------
# Task 4.2 — RefreshTokenRepository.insert and revoke_by_hash
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_refresh_token_insert(async_session) -> None:
    """RefreshTokenRepository.insert persists the token within the transaction."""
    # Create a user first (FK constraint)
    usuario_repo = UsuarioRepository(async_session)
    usuario = await usuario_repo.create(_make_usuario("_rt_insert"))

    repo = RefreshTokenRepository(async_session)
    token = _make_refresh_token(usuario.id)
    saved = await repo.insert(token)

    assert saved.id is not None
    assert saved.token_hash == "a" * 64
    assert saved.usuario_id == usuario.id
    assert saved.revoked_at is None


@pytest.mark.asyncio
async def test_refresh_token_revoke_by_hash_found(async_session) -> None:
    """revoke_by_hash returns True and sets revoked_at when the token exists."""
    usuario_repo = UsuarioRepository(async_session)
    usuario = await usuario_repo.create(_make_usuario("_rt_revoke"))

    repo = RefreshTokenRepository(async_session)
    token = await repo.insert(_make_refresh_token(usuario.id))

    result = await repo.revoke_by_hash(token.token_hash)

    assert result is True
    assert token.revoked_at is not None
    assert isinstance(token.revoked_at, datetime)


@pytest.mark.asyncio
async def test_refresh_token_revoke_by_hash_not_found(async_session) -> None:
    """revoke_by_hash returns False when the token_hash does not exist."""
    repo = RefreshTokenRepository(async_session)
    result = await repo.revoke_by_hash("z" * 64)
    assert result is False


# ---------------------------------------------------------------------------
# Task 4.6 — UsuarioRepository.get_by_email
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_by_email_returns_usuario(async_session) -> None:
    """get_by_email returns the matching Usuario for an existing email."""
    repo = UsuarioRepository(async_session)
    usuario = await repo.create(_make_usuario("_email_found"))

    result = await repo.get_by_email(usuario.email)

    assert result is not None
    assert result.id == usuario.id
    assert result.email == usuario.email


@pytest.mark.asyncio
async def test_get_by_email_returns_none_unknown(async_session) -> None:
    """get_by_email returns None for an email that does not exist."""
    repo = UsuarioRepository(async_session)
    result = await repo.get_by_email("nobody@nowhere.example.com")
    assert result is None


@pytest.mark.asyncio
async def test_get_by_email_excludes_soft_deleted(async_session) -> None:
    """get_by_email returns None for a soft-deleted user."""
    repo = UsuarioRepository(async_session)
    usuario = await repo.create(_make_usuario("_email_deleted"))
    # Soft delete the user
    await repo.soft_delete(usuario.id)

    result = await repo.get_by_email(usuario.email)
    assert result is None


# ---------------------------------------------------------------------------
# Task 4.4 — RolRepository.get_by_codigo
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_by_codigo_returns_rol(async_session) -> None:
    """get_by_codigo returns the matching Rol for a valid code."""
    repo = RolRepository(async_session)
    rol = await repo.create(_make_rol("TESTCODE"))

    result = await repo.get_by_codigo("TESTCODE")

    assert result is not None
    assert result.id == rol.id
    assert result.codigo == "TESTCODE"


@pytest.mark.asyncio
async def test_get_by_codigo_returns_none_unknown(async_session) -> None:
    """get_by_codigo returns None for a code that does not exist."""
    repo = RolRepository(async_session)
    result = await repo.get_by_codigo("NONEXISTENT_ROLE")
    assert result is None


@pytest.mark.asyncio
async def test_get_by_codigo_excludes_soft_deleted(async_session) -> None:
    """get_by_codigo returns None for a soft-deleted role."""
    repo = RolRepository(async_session)
    rol = await repo.create(_make_rol("DELETED_ROLE"))
    await repo.soft_delete(rol.id)

    result = await repo.get_by_codigo("DELETED_ROLE")
    assert result is None
