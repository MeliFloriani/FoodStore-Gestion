"""
Pydantic v2 schemas for the auth domain.

Covers RegisterRequest, LoginRequest, UserRead, TokenResponse,
RefreshRequest, and LogoutRequest.

Design decisions:
- UserRead uses model_config = ConfigDict(from_attributes=True) to work with
  SQLModel/SQLAlchemy ORM objects directly.
- UserRead.id is a UUID field with a @field_serializer that converts to str for JSON.
- UserRead.usuario_roles is declared as a regular field (read from ORM via from_attributes)
  but excluded from serialization output via Field(exclude=True).
- UserRead.roles is a @computed_field that reads the usuario_roles relationship.
- UserRead.created_at is required per Integrador §6.1 (UserResponse includes created_at).
- TokenResponse.expires_in defaults to 1800 (30 minutes), matching ACCESS_TOKEN_EXPIRE_MINUTES.
- RefreshRequest: body for POST /auth/refresh (Change 07).
- LogoutRequest: body for POST /auth/logout (Change 07).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, computed_field, field_serializer


class RegisterRequest(BaseModel):
    """Request body for POST /api/v1/auth/register."""

    nombre: str
    apellido: str
    email: EmailStr
    password: str = Field(min_length=8)


class LoginRequest(BaseModel):
    """Request body for POST /api/v1/auth/login."""

    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    """Request body for POST /api/v1/auth/refresh.

    Added in Change 07 (auth-refresh-logout-rbac-me).
    """

    refresh_token: str


class LogoutRequest(BaseModel):
    """Request body for POST /api/v1/auth/logout.

    Added in Change 07 (auth-refresh-logout-rbac-me).
    Bearer access token is NOT required — the logout is keyed on refresh_token.
    """

    refresh_token: str


class UserRead(BaseModel):
    """Response body for a registered/authenticated user.

    Reads ORM attributes from a Usuario instance via from_attributes=True.
    usuario_roles is read from the ORM relationship but excluded from the output;
    the roles @computed_field produces the flat list of role codes instead.
    created_at is included per Integrador §6.1 (UserResponse shape).
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    nombre: str
    apellido: str
    email: str
    created_at: datetime
    # Read the relationship from ORM but exclude from JSON output.
    # The @computed_field 'roles' derives from this.
    usuario_roles: list[Any] = Field(default=[], exclude=True)

    @field_serializer("id")
    def serialize_id(self, v: UUID) -> str:
        """Serialize UUID primary key as a string for JSON output."""
        return str(v)

    @computed_field  # type: ignore[misc]
    @property
    def roles(self) -> list[str]:
        """Extract role codes from the usuario_roles relationship.

        Reads self.usuario_roles (populated by from_attributes + selectin loading)
        and extracts ur.rol.codigo for each role assignment.
        """
        return [ur.rol.codigo for ur in (self.usuario_roles or [])]


class TokenResponse(BaseModel):
    """Response body for POST /api/v1/auth/login and POST /api/v1/auth/refresh."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = 1800
