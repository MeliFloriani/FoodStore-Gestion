"""
Unit tests for AdminUsuariosService (Change 21).

Phase 8.2 — Task 8.2 (service unit tests with mock repos).

Covers:
  - list_usuarios: returns Page with correct pagination metadata.
  - update_usuario_roles: last ADMIN → ConflictError(LAST_ADMIN_PROTECTED).
  - update_usuario_roles: 2+ ADMINs → succeeds + revokes tokens.
  - deactivate_usuario(activo=False) → sets deleted_at + revokes tokens.
  - deactivate_usuario(activo=False) when already inactive → idempotent.
  - deactivate_usuario(activo=False) for last ADMIN → ConflictError(LAST_ADMIN_PROTECTED).
  - deactivate_usuario(activo=True) → clears deleted_at.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.exceptions import ConflictError, NotFoundError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_uow() -> MagicMock:
    """Build a fully mocked UnitOfWork with async repo methods."""
    uow = MagicMock()
    uow.__aenter__ = AsyncMock(return_value=uow)
    uow.__aexit__ = AsyncMock(return_value=False)

    uow.usuarios = MagicMock()
    uow.roles = MagicMock()
    uow.refresh_tokens = MagicMock()
    uow.admin_usuarios = MagicMock()

    uow.usuarios.get_with_roles = AsyncMock(return_value=None)
    uow.usuarios.get_by_id = AsyncMock(return_value=None)
    uow.roles.get_by_codigo = AsyncMock(return_value=None)
    uow.refresh_tokens.revoke_all_for_user = AsyncMock(return_value=0)
    uow.admin_usuarios.list_paginated = AsyncMock(return_value=([], 0))
    uow.admin_usuarios.count_active_admins = AsyncMock(return_value=0)

    # Mock session methods used by service
    uow.session = MagicMock()
    uow.session.add = MagicMock()
    uow.session.delete = AsyncMock()
    uow.session.flush = AsyncMock()

    return uow


def _make_mock_rol(codigo: str = "CLIENT") -> MagicMock:
    """Build a mock Rol with given codigo."""
    rol = MagicMock()
    rol.id = uuid.uuid4()
    rol.codigo = codigo
    rol.nombre = codigo.title()
    return rol


def _make_mock_usuario_rol(codigo: str = "CLIENT") -> MagicMock:
    """Build a mock UsuarioRol with given rol codigo."""
    ur = MagicMock()
    ur.id = uuid.uuid4()
    ur.rol = _make_mock_rol(codigo)
    return ur


def _make_mock_usuario(
    *,
    roles: list[str] | None = None,
    deleted_at: datetime | None = None,
) -> MagicMock:
    """Build a mock Usuario with optional roles and deleted_at."""
    usuario = MagicMock()
    usuario.id = uuid.uuid4()
    usuario.email = "test@example.com"
    usuario.nombre = "Test"
    usuario.apellido = "User"
    usuario.created_at = datetime.now(timezone.utc)
    usuario.deleted_at = deleted_at
    usuario.password_hash = "$2b$12$dummy"

    ur_list = [_make_mock_usuario_rol(r) for r in (roles or [])]
    usuario.usuario_roles = ur_list
    return usuario


# ---------------------------------------------------------------------------
# list_usuarios
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_usuarios_returns_page_with_correct_metadata() -> None:
    """list_usuarios returns Page with correct total, pages, items."""
    from app.services.admin_usuarios import AdminUsuariosService

    # Setup: 3 users total, page 1, size 2 → pages=2
    users = [_make_mock_usuario(roles=["CLIENT"]) for _ in range(2)]
    uow = _make_mock_uow()
    uow.admin_usuarios.list_paginated = AsyncMock(return_value=(users, 3))

    result = await AdminUsuariosService.list_usuarios(
        uow, page=1, size=2, q=None, rol=None, activo=None
    )

    assert result.total == 3
    assert result.page == 1
    assert result.size == 2
    assert result.pages == 2
    assert len(result.items) == 2


@pytest.mark.asyncio
async def test_list_usuarios_empty_result() -> None:
    """list_usuarios with no users returns empty Page."""
    from app.services.admin_usuarios import AdminUsuariosService

    uow = _make_mock_uow()
    uow.admin_usuarios.list_paginated = AsyncMock(return_value=([], 0))

    result = await AdminUsuariosService.list_usuarios(
        uow, page=1, size=20, q=None, rol=None, activo=None
    )

    assert result.total == 0
    assert result.pages == 0
    assert result.items == []


# ---------------------------------------------------------------------------
# update_usuario_roles
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_usuario_roles_last_admin_raises_conflict() -> None:
    """update_usuario_roles when only ADMIN → raises ConflictError(LAST_ADMIN_PROTECTED)."""
    from app.services.admin_usuarios import AdminUsuariosService

    admin_user = _make_mock_usuario(roles=["ADMIN"])
    uow = _make_mock_uow()
    uow.usuarios.get_with_roles = AsyncMock(return_value=admin_user)
    uow.admin_usuarios.count_active_admins = AsyncMock(return_value=0)  # no other admins

    with pytest.raises(ConflictError) as exc_info:
        await AdminUsuariosService.update_usuario_roles(
            uow,
            user_id=admin_user.id,
            new_roles=["CLIENT"],  # removing ADMIN role
            admin_id=uuid.uuid4(),
        )

    assert exc_info.value.code == "LAST_ADMIN_PROTECTED"
    assert exc_info.value.status_code == 409


@pytest.mark.asyncio
async def test_update_usuario_roles_two_admins_succeeds_and_revokes_tokens() -> None:
    """update_usuario_roles with 2+ ADMINs → succeeds + revokes tokens."""
    from app.services.admin_usuarios import AdminUsuariosService

    admin_user = _make_mock_usuario(roles=["ADMIN"])
    updated_user = _make_mock_usuario(roles=["CLIENT"])

    uow = _make_mock_uow()
    # First call returns admin_user, second call (reload) returns updated_user
    uow.usuarios.get_with_roles = AsyncMock(
        side_effect=[admin_user, updated_user]
    )
    uow.admin_usuarios.count_active_admins = AsyncMock(return_value=1)  # 1 other ADMIN

    # Mock the CLIENT role lookup
    client_rol = _make_mock_rol("CLIENT")
    uow.roles.get_by_codigo = AsyncMock(return_value=client_rol)

    result = await AdminUsuariosService.update_usuario_roles(
        uow,
        user_id=admin_user.id,
        new_roles=["CLIENT"],
        admin_id=uuid.uuid4(),
    )

    # Tokens were revoked
    uow.refresh_tokens.revoke_all_for_user.assert_called_once_with(admin_user.id)
    # Returned the updated user
    assert result is not None


@pytest.mark.asyncio
async def test_update_usuario_roles_not_removing_admin_skips_guard() -> None:
    """update_usuario_roles when ADMIN stays in role set → skips last-admin check."""
    from app.services.admin_usuarios import AdminUsuariosService

    admin_user = _make_mock_usuario(roles=["ADMIN"])
    updated_user = _make_mock_usuario(roles=["ADMIN", "CLIENT"])

    uow = _make_mock_uow()
    uow.usuarios.get_with_roles = AsyncMock(
        side_effect=[admin_user, updated_user]
    )

    admin_rol = _make_mock_rol("ADMIN")
    client_rol = _make_mock_rol("CLIENT")
    uow.roles.get_by_codigo = AsyncMock(side_effect=lambda c: admin_rol if c == "ADMIN" else client_rol)

    result = await AdminUsuariosService.update_usuario_roles(
        uow,
        user_id=admin_user.id,
        new_roles=["ADMIN", "CLIENT"],  # keeping ADMIN
        admin_id=uuid.uuid4(),
    )

    # count_active_admins should NOT have been called
    uow.admin_usuarios.count_active_admins.assert_not_called()
    assert result is not None


@pytest.mark.asyncio
async def test_update_usuario_roles_user_not_found_raises_404() -> None:
    """update_usuario_roles with non-existent user → raises NotFoundError."""
    from app.services.admin_usuarios import AdminUsuariosService

    uow = _make_mock_uow()
    uow.usuarios.get_with_roles = AsyncMock(return_value=None)

    with pytest.raises(NotFoundError) as exc_info:
        await AdminUsuariosService.update_usuario_roles(
            uow,
            user_id=uuid.uuid4(),
            new_roles=["CLIENT"],
            admin_id=uuid.uuid4(),
        )

    assert exc_info.value.code == "USER_NOT_FOUND"
    assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# deactivate_usuario
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_deactivate_usuario_sets_deleted_at_and_revokes_tokens() -> None:
    """deactivate_usuario(activo=False) → sets deleted_at and revokes tokens."""
    from app.services.admin_usuarios import AdminUsuariosService

    client_user = _make_mock_usuario(roles=["CLIENT"])
    reloaded_user = _make_mock_usuario(
        roles=["CLIENT"],
        deleted_at=datetime.now(timezone.utc),
    )

    uow = _make_mock_uow()
    uow.usuarios.get_with_roles = AsyncMock(
        side_effect=[client_user, reloaded_user]
    )

    result = await AdminUsuariosService.deactivate_usuario(
        uow, user_id=client_user.id, activo=False
    )

    # soft_delete() was called on the user
    client_user.soft_delete.assert_called_once()
    # Tokens were revoked
    uow.refresh_tokens.revoke_all_for_user.assert_called_once_with(client_user.id)
    assert result is not None


@pytest.mark.asyncio
async def test_deactivate_usuario_idempotent_when_already_inactive() -> None:
    """deactivate_usuario(activo=False) when already inactive → idempotent (no error)."""
    from app.services.admin_usuarios import AdminUsuariosService

    already_deleted = _make_mock_usuario(
        roles=["CLIENT"],
        deleted_at=datetime.now(timezone.utc),
    )

    uow = _make_mock_uow()
    uow.usuarios.get_with_roles = AsyncMock(return_value=already_deleted)

    result = await AdminUsuariosService.deactivate_usuario(
        uow, user_id=already_deleted.id, activo=False
    )

    # soft_delete() should NOT be called (already inactive)
    already_deleted.soft_delete.assert_not_called()
    # Tokens should NOT be revoked (already inactive)
    uow.refresh_tokens.revoke_all_for_user.assert_not_called()
    assert result is not None


@pytest.mark.asyncio
async def test_deactivate_usuario_last_admin_raises_conflict() -> None:
    """deactivate_usuario(activo=False) for last ADMIN → ConflictError(LAST_ADMIN_PROTECTED)."""
    from app.services.admin_usuarios import AdminUsuariosService

    admin_user = _make_mock_usuario(roles=["ADMIN"])

    uow = _make_mock_uow()
    uow.usuarios.get_with_roles = AsyncMock(return_value=admin_user)
    uow.admin_usuarios.count_active_admins = AsyncMock(return_value=0)  # no other ADMINs

    with pytest.raises(ConflictError) as exc_info:
        await AdminUsuariosService.deactivate_usuario(
            uow, user_id=admin_user.id, activo=False
        )

    assert exc_info.value.code == "LAST_ADMIN_PROTECTED"
    assert exc_info.value.status_code == 409

    # soft_delete() should NOT have been called
    admin_user.soft_delete.assert_not_called()


@pytest.mark.asyncio
async def test_deactivate_usuario_reactivate_clears_deleted_at() -> None:
    """deactivate_usuario(activo=True) → clears deleted_at (reactivation)."""
    from app.services.admin_usuarios import AdminUsuariosService

    inactive_user = _make_mock_usuario(
        roles=["CLIENT"],
        deleted_at=datetime.now(timezone.utc),
    )
    reloaded_user = _make_mock_usuario(roles=["CLIENT"], deleted_at=None)

    uow = _make_mock_uow()
    uow.usuarios.get_by_id = AsyncMock(return_value=inactive_user)
    uow.usuarios.get_with_roles = AsyncMock(return_value=reloaded_user)

    result = await AdminUsuariosService.deactivate_usuario(
        uow, user_id=inactive_user.id, activo=True
    )

    # deleted_at should have been cleared
    assert inactive_user.deleted_at is None
    # Tokens should NOT be revoked on reactivation
    uow.refresh_tokens.revoke_all_for_user.assert_not_called()
    assert result is not None


@pytest.mark.asyncio
async def test_deactivate_usuario_reactivate_idempotent_when_already_active() -> None:
    """deactivate_usuario(activo=True) when already active → idempotent."""
    from app.services.admin_usuarios import AdminUsuariosService

    active_user = _make_mock_usuario(roles=["CLIENT"], deleted_at=None)

    uow = _make_mock_uow()
    uow.usuarios.get_by_id = AsyncMock(return_value=active_user)
    uow.usuarios.get_with_roles = AsyncMock(return_value=active_user)

    result = await AdminUsuariosService.deactivate_usuario(
        uow, user_id=active_user.id, activo=True
    )

    # No changes to deleted_at (already None)
    assert active_user.deleted_at is None
    assert result is not None


@pytest.mark.asyncio
async def test_deactivate_usuario_not_found_raises_404() -> None:
    """deactivate_usuario with non-existent user → raises NotFoundError."""
    from app.services.admin_usuarios import AdminUsuariosService

    uow = _make_mock_uow()
    uow.usuarios.get_with_roles = AsyncMock(return_value=None)
    uow.usuarios.get_by_id = AsyncMock(return_value=None)

    with pytest.raises(NotFoundError) as exc_info:
        await AdminUsuariosService.deactivate_usuario(
            uow, user_id=uuid.uuid4(), activo=False
        )

    assert exc_info.value.code == "USER_NOT_FOUND"


@pytest.mark.asyncio
async def test_deactivate_admin_user_with_other_admins_succeeds() -> None:
    """deactivate_usuario(activo=False) for ADMIN when other ADMINs exist → succeeds."""
    from app.services.admin_usuarios import AdminUsuariosService

    admin_user = _make_mock_usuario(roles=["ADMIN"])
    reloaded_user = _make_mock_usuario(
        roles=["ADMIN"],
        deleted_at=datetime.now(timezone.utc),
    )

    uow = _make_mock_uow()
    uow.usuarios.get_with_roles = AsyncMock(
        side_effect=[admin_user, reloaded_user]
    )
    uow.admin_usuarios.count_active_admins = AsyncMock(return_value=1)  # 1 other ADMIN

    result = await AdminUsuariosService.deactivate_usuario(
        uow, user_id=admin_user.id, activo=False
    )

    admin_user.soft_delete.assert_called_once()
    uow.refresh_tokens.revoke_all_for_user.assert_called_once_with(admin_user.id)
    assert result is not None
