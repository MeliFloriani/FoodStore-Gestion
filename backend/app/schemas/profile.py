"""
Pydantic v2 schemas for the profile domain (Change 13: customer-profile-management).

Schemas:
  - ProfileUpdate: editable fields only (nombre, apellido). Email is immutable —
    if it appears in the request body it is silently ignored (extra='ignore').
  - PasswordChangeRequest: current + new password. password_confirm is a
    frontend-only UX field and MUST NOT be sent to the backend (extra='forbid').
  - UserRead: re-exported from schemas/auth.py (single source of truth).

Design decisions:
  - UserRead is NOT re-declared here — imported from schemas.auth to guarantee
    that PATCH /profile/me and GET /auth/me share the exact same response shape.
  - validate_password() from core.validators is the single source of truth for
    the minimum-8-chars rule (D-07).
  - ProfileUpdate uses extra='ignore' (D-02): silent email drop prevents
    leaking which fields are immutable.
  - PasswordChangeRequest uses extra='forbid': password_confirm from a
    misconfigured client should surface as a 422, not be silently accepted.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.validators import validate_password

# Re-export UserRead from auth schemas — do NOT re-declare.
# This guarantees identical response shape for /auth/me and /profile/me.
from app.schemas.auth import UserRead  # noqa: F401


class ProfileUpdate(BaseModel):
    """Request body for PATCH /api/v1/profile/me.

    Only nombre and apellido are editable. The email field is intentionally
    absent — if a client sends it, Pydantic's extra='ignore' silently drops it
    before the service processes the update (D-02).
    """

    model_config = ConfigDict(extra="ignore")

    nombre: str | None = Field(default=None, max_length=80)
    apellido: str | None = Field(default=None, max_length=80)


class PasswordChangeRequest(BaseModel):
    """Request body for POST /api/v1/profile/me/password.

    password_confirm MUST NOT exist on this schema — it is a frontend-only
    UX field. If a client sends it, extra='forbid' returns HTTP 422, making
    the frontend implementation error visible rather than silently ignoring it.
    """

    model_config = ConfigDict(extra="forbid")

    current_password: str
    new_password: str = Field(min_length=8)

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, v: str) -> str:
        """Reuse canonical password validator from core.validators (D-07)."""
        return validate_password(v)
