"""
Unit tests for profile Pydantic schemas.

Tasks 1.1, 1.3 — TDD red phase.

Covers:
  - ProfileUpdate: ignores extra fields (email), accepts partial updates,
    rejects nombre/apellido > 80 chars
  - PasswordChangeRequest: rejects new_password < 8 chars, accepts valid
    payloads, has no password_confirm field, forbids extra fields
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError


# ---------------------------------------------------------------------------
# Task 1.1 — ProfileUpdate schema
# ---------------------------------------------------------------------------


class TestProfileUpdate:
    """Validation tests for ProfileUpdate schema."""

    def test_profile_update_drops_email_silently(self) -> None:
        """ProfileUpdate with email field → email is silently ignored (extra='ignore')."""
        from app.schemas.profile import ProfileUpdate

        update = ProfileUpdate(nombre="Ana", email="hack@test.com")  # type: ignore[call-arg]
        assert update.nombre == "Ana"
        assert not hasattr(update, "email")

    def test_profile_update_rejects_nombre_over_80_chars(self) -> None:
        """ProfileUpdate with nombre > 80 chars → ValidationError."""
        from app.schemas.profile import ProfileUpdate

        with pytest.raises(ValidationError) as exc_info:
            ProfileUpdate(nombre="A" * 81)
        errors = exc_info.value.errors()
        assert any("nombre" in str(e["loc"]) for e in errors)

    def test_profile_update_accepts_only_nombre(self) -> None:
        """ProfileUpdate with only nombre set → valid, apellido is None."""
        from app.schemas.profile import ProfileUpdate

        update = ProfileUpdate(nombre="Ana")
        assert update.nombre == "Ana"
        assert update.apellido is None

    def test_profile_update_accepts_only_apellido(self) -> None:
        """ProfileUpdate with only apellido set → valid, nombre is None."""
        from app.schemas.profile import ProfileUpdate

        update = ProfileUpdate(apellido="García")
        assert update.apellido == "García"
        assert update.nombre is None

    def test_profile_update_all_none_is_valid(self) -> None:
        """ProfileUpdate with no fields → valid (all-None no-op)."""
        from app.schemas.profile import ProfileUpdate

        update = ProfileUpdate()
        assert update.nombre is None
        assert update.apellido is None

    def test_profile_update_rejects_apellido_over_80_chars(self) -> None:
        """ProfileUpdate with apellido > 80 chars → ValidationError."""
        from app.schemas.profile import ProfileUpdate

        with pytest.raises(ValidationError) as exc_info:
            ProfileUpdate(apellido="B" * 81)
        errors = exc_info.value.errors()
        assert any("apellido" in str(e["loc"]) for e in errors)

    def test_profile_update_accepts_max_length_values(self) -> None:
        """ProfileUpdate with nombre/apellido exactly 80 chars → valid."""
        from app.schemas.profile import ProfileUpdate

        update = ProfileUpdate(nombre="A" * 80, apellido="B" * 80)
        assert len(update.nombre) == 80  # type: ignore[arg-type]
        assert len(update.apellido) == 80  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Task 1.3 — PasswordChangeRequest schema
# ---------------------------------------------------------------------------


class TestPasswordChangeRequest:
    """Validation tests for PasswordChangeRequest schema."""

    def test_password_change_request_rejects_short_new_password(self) -> None:
        """PasswordChangeRequest with new_password < 8 chars → ValidationError."""
        from app.schemas.profile import PasswordChangeRequest

        with pytest.raises(ValidationError) as exc_info:
            PasswordChangeRequest(current_password="OldPass1", new_password="short")
        errors = exc_info.value.errors()
        assert any("new_password" in str(e["loc"]) for e in errors)

    def test_password_change_request_accepts_valid_payload(self) -> None:
        """PasswordChangeRequest with valid payload → passes without error."""
        from app.schemas.profile import PasswordChangeRequest

        req = PasswordChangeRequest(
            current_password="OldPass1", new_password="NewPass1!"
        )
        assert req.current_password == "OldPass1"
        assert req.new_password == "NewPass1!"

    def test_password_change_request_has_no_password_confirm_field(self) -> None:
        """PasswordChangeRequest should NOT have a password_confirm field."""
        from app.schemas.profile import PasswordChangeRequest

        req = PasswordChangeRequest(
            current_password="OldPass1", new_password="NewPass1!"
        )
        assert not hasattr(req, "password_confirm")

    def test_password_change_request_forbids_extra_fields(self) -> None:
        """PasswordChangeRequest with extra field → ValidationError (extra='forbid')."""
        from app.schemas.profile import PasswordChangeRequest

        with pytest.raises(ValidationError):
            PasswordChangeRequest(  # type: ignore[call-arg]
                current_password="OldPass1",
                new_password="NewPass1!",
                password_confirm="NewPass1!",
            )

    def test_password_change_request_new_password_exactly_8_chars(self) -> None:
        """new_password with exactly 8 chars should be valid."""
        from app.schemas.profile import PasswordChangeRequest

        req = PasswordChangeRequest(
            current_password="OldPass1", new_password="Exactly8"
        )
        assert req.new_password == "Exactly8"

    def test_password_change_request_7_chars_rejected(self) -> None:
        """new_password with 7 chars → ValidationError."""
        from app.schemas.profile import PasswordChangeRequest

        with pytest.raises(ValidationError):
            PasswordChangeRequest(current_password="OldPass1", new_password="short7c")
