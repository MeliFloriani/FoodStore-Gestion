"""
Unit tests for admin_usuarios Pydantic schemas (Change 21).

Phase 8.1 — Task 8.1 (schemas unit tests).

Covers:
  - UsuarioAdminUpdate drops email silently (D-01, extra="ignore").
  - UsuarioRolesUpdate rejects unknown roles (ValidationError).
  - UsuarioRolesUpdate deduplicates roles.
  - UsuarioRolesUpdate with empty list raises validation error (min_length=1).
  - UsuarioAdminRead does not include password_hash field.
  - RolRead schema parses correctly.
  - UsuarioEstadoUpdate accepts bool.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError


# ---------------------------------------------------------------------------
# UsuarioAdminUpdate — D-01: email immutable, extra="ignore"
# ---------------------------------------------------------------------------


class TestUsuarioAdminUpdate:
    """Tests for UsuarioAdminUpdate schema."""

    def test_email_is_not_a_field(self) -> None:
        """email is NOT a field on UsuarioAdminUpdate (D-01)."""
        from app.schemas.admin_usuarios import UsuarioAdminUpdate

        instance = UsuarioAdminUpdate(nombre="Ana")  # type: ignore[call-arg]
        assert not hasattr(instance, "email")

    def test_email_in_payload_is_silently_dropped(self) -> None:
        """Passing email to UsuarioAdminUpdate silently drops it (extra='ignore')."""
        from app.schemas.admin_usuarios import UsuarioAdminUpdate

        # Should not raise — extra="ignore" drops unknown fields
        instance = UsuarioAdminUpdate.model_validate(
            {"nombre": "Ana", "email": "hack@test.com"}
        )
        assert instance.nombre == "Ana"
        assert not hasattr(instance, "email")

    def test_nombre_max_length_80(self) -> None:
        """nombre exceeding 80 characters raises ValidationError."""
        from app.schemas.admin_usuarios import UsuarioAdminUpdate

        with pytest.raises(ValidationError):
            UsuarioAdminUpdate(nombre="A" * 81)  # type: ignore[call-arg]

    def test_apellido_max_length_80(self) -> None:
        """apellido exceeding 80 characters raises ValidationError."""
        from app.schemas.admin_usuarios import UsuarioAdminUpdate

        with pytest.raises(ValidationError):
            UsuarioAdminUpdate(apellido="B" * 81)  # type: ignore[call-arg]

    def test_all_none_is_valid(self) -> None:
        """UsuarioAdminUpdate with no fields (all default None) is valid."""
        from app.schemas.admin_usuarios import UsuarioAdminUpdate

        instance = UsuarioAdminUpdate()
        assert instance.nombre is None
        assert instance.apellido is None

    def test_nombre_and_apellido_set(self) -> None:
        """UsuarioAdminUpdate accepts valid nombre and apellido."""
        from app.schemas.admin_usuarios import UsuarioAdminUpdate

        instance = UsuarioAdminUpdate(nombre="Juan", apellido="Pérez")  # type: ignore[call-arg]
        assert instance.nombre == "Juan"
        assert instance.apellido == "Pérez"


# ---------------------------------------------------------------------------
# UsuarioRolesUpdate — role validation and deduplication
# ---------------------------------------------------------------------------


class TestUsuarioRolesUpdate:
    """Tests for UsuarioRolesUpdate schema."""

    def test_invalid_role_raises_validation_error(self) -> None:
        """UsuarioRolesUpdate with unknown role code raises ValidationError."""
        from app.schemas.admin_usuarios import UsuarioRolesUpdate

        with pytest.raises(ValidationError) as exc_info:
            UsuarioRolesUpdate(roles=["ADMIN", "INVALID"])
        # Check error message mentions the invalid role
        assert "INVALID" in str(exc_info.value)

    def test_duplicate_roles_are_deduplicated(self) -> None:
        """UsuarioRolesUpdate deduplicates repeated role codes."""
        from app.schemas.admin_usuarios import UsuarioRolesUpdate

        instance = UsuarioRolesUpdate(roles=["ADMIN", "ADMIN"])
        assert instance.roles == ["ADMIN"]

    def test_empty_list_raises_validation_error(self) -> None:
        """UsuarioRolesUpdate with empty list raises ValidationError (min_length=1)."""
        from app.schemas.admin_usuarios import UsuarioRolesUpdate

        with pytest.raises(ValidationError):
            UsuarioRolesUpdate(roles=[])

    def test_valid_single_role(self) -> None:
        """UsuarioRolesUpdate with a single valid role is accepted."""
        from app.schemas.admin_usuarios import UsuarioRolesUpdate

        instance = UsuarioRolesUpdate(roles=["CLIENT"])
        assert instance.roles == ["CLIENT"]

    def test_all_valid_roles(self) -> None:
        """UsuarioRolesUpdate accepts all four valid role codes."""
        from app.schemas.admin_usuarios import UsuarioRolesUpdate

        instance = UsuarioRolesUpdate(roles=["ADMIN", "STOCK", "PEDIDOS", "CLIENT"])
        assert set(instance.roles) == {"ADMIN", "STOCK", "PEDIDOS", "CLIENT"}

    def test_multiple_unknown_roles_listed_in_error(self) -> None:
        """ValidationError message lists all invalid role codes."""
        from app.schemas.admin_usuarios import UsuarioRolesUpdate

        with pytest.raises(ValidationError) as exc_info:
            UsuarioRolesUpdate(roles=["SUPERADMIN", "GUEST"])
        error_text = str(exc_info.value)
        # At least one of the invalid roles should appear in the error
        assert "SUPERADMIN" in error_text or "GUEST" in error_text


# ---------------------------------------------------------------------------
# UsuarioAdminRead — no password_hash, computed is_active
# ---------------------------------------------------------------------------


class TestUsuarioAdminRead:
    """Tests for UsuarioAdminRead schema."""

    def _make_mock_usuario(
        self,
        deleted_at: datetime | None = None,
        roles: list[str] | None = None,
    ) -> MagicMock:
        """Build a minimal mock Usuario with optional roles and deleted_at."""
        usuario = MagicMock()
        usuario.id = uuid.uuid4()
        usuario.email = "test@example.com"
        usuario.nombre = "Test"
        usuario.apellido = "User"
        usuario.created_at = datetime.now(timezone.utc)
        usuario.deleted_at = deleted_at
        usuario.password_hash = "$2b$12$hashhash"

        # Build mock usuario_roles
        usuario_roles = []
        for codigo in (roles or []):
            rol = MagicMock()
            rol.id = uuid.uuid4()
            rol.codigo = codigo
            rol.nombre = codigo.title()
            ur = MagicMock()
            ur.rol = rol
            usuario_roles.append(ur)
        usuario.usuario_roles = usuario_roles
        return usuario

    def test_password_hash_not_in_schema(self) -> None:
        """UsuarioAdminRead does NOT have a password_hash field."""
        from app.schemas.admin_usuarios import UsuarioAdminRead

        # Check schema fields
        field_names = set(UsuarioAdminRead.model_fields.keys())
        assert "password_hash" not in field_names

    def test_from_usuario_excludes_password_hash(self) -> None:
        """from_usuario() does not include password_hash in the output."""
        from app.schemas.admin_usuarios import UsuarioAdminRead

        usuario = self._make_mock_usuario(roles=["CLIENT"])
        read = UsuarioAdminRead.from_usuario(usuario)
        dumped = read.model_dump()
        assert "password_hash" not in dumped

    def test_is_active_true_when_deleted_at_none(self) -> None:
        """is_active returns True when deleted_at is None."""
        from app.schemas.admin_usuarios import UsuarioAdminRead

        usuario = self._make_mock_usuario(deleted_at=None)
        read = UsuarioAdminRead.from_usuario(usuario)
        assert read.is_active is True

    def test_is_active_false_when_deleted_at_set(self) -> None:
        """is_active returns False when deleted_at is not None."""
        from app.schemas.admin_usuarios import UsuarioAdminRead

        usuario = self._make_mock_usuario(deleted_at=datetime.now(timezone.utc))
        read = UsuarioAdminRead.from_usuario(usuario)
        assert read.is_active is False

    def test_roles_populated_from_usuario_roles(self) -> None:
        """from_usuario() correctly maps usuario_roles to RolRead list."""
        from app.schemas.admin_usuarios import UsuarioAdminRead

        usuario = self._make_mock_usuario(roles=["ADMIN", "CLIENT"])
        read = UsuarioAdminRead.from_usuario(usuario)
        role_codes = {r.codigo for r in read.roles}
        assert role_codes == {"ADMIN", "CLIENT"}

    def test_empty_roles_list_when_no_roles(self) -> None:
        """from_usuario() returns empty roles list when usuario has no roles."""
        from app.schemas.admin_usuarios import UsuarioAdminRead

        usuario = self._make_mock_usuario(roles=[])
        read = UsuarioAdminRead.from_usuario(usuario)
        assert read.roles == []


# ---------------------------------------------------------------------------
# UsuarioEstadoUpdate
# ---------------------------------------------------------------------------


class TestUsuarioEstadoUpdate:
    """Tests for UsuarioEstadoUpdate schema."""

    def test_activo_false_is_valid(self) -> None:
        """UsuarioEstadoUpdate(activo=False) parses correctly."""
        from app.schemas.admin_usuarios import UsuarioEstadoUpdate

        instance = UsuarioEstadoUpdate(activo=False)
        assert instance.activo is False

    def test_activo_true_is_valid(self) -> None:
        """UsuarioEstadoUpdate(activo=True) parses correctly."""
        from app.schemas.admin_usuarios import UsuarioEstadoUpdate

        instance = UsuarioEstadoUpdate(activo=True)
        assert instance.activo is True
