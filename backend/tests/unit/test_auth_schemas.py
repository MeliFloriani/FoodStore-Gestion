"""
Unit tests for auth Pydantic schemas.

Tasks 1.1, 1.2, 1.3 — TDD red phase. These tests import from app.schemas.auth
which does not exist yet, so they will fail until §2 is implemented.
"""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock

import pytest


# ---------------------------------------------------------------------------
# Task 1.1 — RegisterRequest and LoginRequest validation
# ---------------------------------------------------------------------------


class TestRegisterRequest:
    """Validation tests for RegisterRequest schema."""

    def test_valid_register_request(self) -> None:
        """A fully valid RegisterRequest should parse without error."""
        from app.schemas.auth import RegisterRequest

        req = RegisterRequest(
            nombre="Juan",
            apellido="Pérez",
            email="juan@example.com",
            password="Secur3Pass!",
        )
        assert req.nombre == "Juan"
        assert req.apellido == "Pérez"
        assert req.email == "juan@example.com"
        assert req.password == "Secur3Pass!"

    def test_register_request_email_coercion(self) -> None:
        """EmailStr should normalise the email to lowercase."""
        from app.schemas.auth import RegisterRequest

        req = RegisterRequest(
            nombre="Juan",
            apellido="Pérez",
            email="JUAN@EXAMPLE.COM",
            password="Secur3Pass!",
        )
        assert "@" in req.email

    def test_register_request_password_min_length(self) -> None:
        """Password shorter than 8 characters should raise ValidationError."""
        from pydantic import ValidationError

        from app.schemas.auth import RegisterRequest

        with pytest.raises(ValidationError) as exc_info:
            RegisterRequest(
                nombre="Juan",
                apellido="Pérez",
                email="juan@example.com",
                password="short",
            )
        errors = exc_info.value.errors()
        assert any("password" in str(e["loc"]) for e in errors)

    def test_register_request_invalid_email(self) -> None:
        """An invalid email address should raise ValidationError."""
        from pydantic import ValidationError

        from app.schemas.auth import RegisterRequest

        with pytest.raises(ValidationError):
            RegisterRequest(
                nombre="Juan",
                apellido="Pérez",
                email="not-an-email",
                password="Secur3Pass!",
            )

    def test_register_request_missing_nombre(self) -> None:
        """Missing required field nombre should raise ValidationError."""
        from pydantic import ValidationError

        from app.schemas.auth import RegisterRequest

        with pytest.raises(ValidationError):
            RegisterRequest(  # type: ignore[call-arg]
                apellido="Pérez",
                email="juan@example.com",
                password="Secur3Pass!",
            )


class TestLoginRequest:
    """Validation tests for LoginRequest schema."""

    def test_valid_login_request(self) -> None:
        """A fully valid LoginRequest should parse without error."""
        from app.schemas.auth import LoginRequest

        req = LoginRequest(email="juan@example.com", password="anypassword")
        assert req.email == "juan@example.com"
        assert req.password == "anypassword"

    def test_login_request_invalid_email(self) -> None:
        """An invalid email address should raise ValidationError."""
        from pydantic import ValidationError

        from app.schemas.auth import LoginRequest

        with pytest.raises(ValidationError):
            LoginRequest(email="not-an-email", password="anypassword")

    def test_login_request_missing_password(self) -> None:
        """Missing password field should raise ValidationError."""
        from pydantic import ValidationError

        from app.schemas.auth import LoginRequest

        with pytest.raises(ValidationError):
            LoginRequest(email="juan@example.com")  # type: ignore[call-arg]


# ---------------------------------------------------------------------------
# Task 1.2 — UserRead serialization
# ---------------------------------------------------------------------------


class TestUserRead:
    """UserRead serialisation tests."""

    def _make_mock_usuario(self) -> MagicMock:
        """Build a minimal mock Usuario object with relationships loaded."""
        usuario = MagicMock()
        usuario.id = uuid.uuid4()
        usuario.nombre = "Juan"
        usuario.apellido = "Pérez"
        usuario.email = "juan@example.com"

        # Build mock usuario_roles → rol chain
        rol = MagicMock()
        rol.codigo = "CLIENT"
        ur = MagicMock()
        ur.rol = rol
        usuario.usuario_roles = [ur]
        return usuario

    def test_user_read_id_is_str(self) -> None:
        """UserRead.id should be serialised as a string (UUID → str)."""
        from app.schemas.auth import UserRead

        usuario = self._make_mock_usuario()
        read = UserRead.model_validate(usuario)
        dumped = read.model_dump()
        assert isinstance(dumped["id"], str)

    def test_user_read_roles_flat_list(self) -> None:
        """UserRead.roles should be a flat list of codigo strings."""
        from app.schemas.auth import UserRead

        usuario = self._make_mock_usuario()
        read = UserRead.model_validate(usuario)
        assert read.roles == ["CLIENT"]

    def test_user_read_apellido_present(self) -> None:
        """UserRead should expose the apellido field."""
        from app.schemas.auth import UserRead

        usuario = self._make_mock_usuario()
        read = UserRead.model_validate(usuario)
        assert read.apellido == "Pérez"

    def test_user_read_multiple_roles(self) -> None:
        """UserRead.roles should list all roles when a user has multiple."""
        from app.schemas.auth import UserRead

        usuario = MagicMock()
        usuario.id = uuid.uuid4()
        usuario.nombre = "Admin"
        usuario.apellido = "User"
        usuario.email = "admin@example.com"

        roles_data = [("CLIENT", MagicMock()), ("ADMIN", MagicMock())]
        urs = []
        for codigo, rol_mock in roles_data:
            rol_mock.codigo = codigo
            ur = MagicMock()
            ur.rol = rol_mock
            urs.append(ur)
        usuario.usuario_roles = urs

        read = UserRead.model_validate(usuario)
        assert set(read.roles) == {"CLIENT", "ADMIN"}


# ---------------------------------------------------------------------------
# Task 1.3 — TokenResponse schema defaults
# ---------------------------------------------------------------------------


class TestTokenResponse:
    """TokenResponse schema defaults and structure."""

    def test_token_type_default_bearer(self) -> None:
        """token_type should default to 'bearer'."""
        from app.schemas.auth import TokenResponse

        resp = TokenResponse(access_token="aaa", refresh_token="bbb")
        assert resp.token_type == "bearer"

    def test_expires_in_default_1800(self) -> None:
        """expires_in should default to 1800 seconds."""
        from app.schemas.auth import TokenResponse

        resp = TokenResponse(access_token="aaa", refresh_token="bbb")
        assert resp.expires_in == 1800

    def test_token_response_custom_values(self) -> None:
        """TokenResponse should accept custom token_type and expires_in."""
        from app.schemas.auth import TokenResponse

        resp = TokenResponse(
            access_token="aaa",
            refresh_token="bbb",
            token_type="custom",
            expires_in=3600,
        )
        assert resp.token_type == "custom"
        assert resp.expires_in == 3600
