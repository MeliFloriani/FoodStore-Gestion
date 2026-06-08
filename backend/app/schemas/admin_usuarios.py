"""
Pydantic schemas for the admin-usuarios feature (Change 21).

Schemas:
  - RolRead: compact role representation for admin responses.
  - UsuarioAdminRead: full user detail for admin panel. NEVER exposes password_hash.
  - UsuarioAdminUpdate: editable fields for PUT /admin/usuarios/{id}.
      email is NOT included (D-01: email is immutable). extra="ignore" silently
      drops any email field if sent by a misbehaving client.
  - UsuarioRolesUpdate: full role set replacement for PUT /admin/usuarios/{id}/roles.
      Validates role codes, deduplicates, enforces min_length=1.
  - UsuarioEstadoUpdate: activo flag for PATCH /admin/usuarios/{id}/estado.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class RolRead(BaseModel):
    """Compact role representation included in UsuarioAdminRead.roles."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    codigo: str
    nombre: str


class UsuarioAdminRead(BaseModel):
    """Full user detail returned by all admin endpoints.

    INVARIANTS:
    - password_hash is NEVER included (security: admin panel must not expose it).
    - roles is populated from usuario_roles relationship chain.
    - is_active is a computed property: deleted_at IS NULL.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    nombre: str
    apellido: str
    created_at: datetime
    deleted_at: datetime | None
    roles: list[RolRead] = Field(default_factory=list)

    @property
    def is_active(self) -> bool:
        """Return True if the user is active (not soft-deleted)."""
        return self.deleted_at is None

    @classmethod
    def from_usuario(cls, usuario: object) -> "UsuarioAdminRead":
        """Build UsuarioAdminRead from a Usuario ORM object with roles loaded.

        Converts UsuarioRol relationship chain to RolRead list.
        Requires usuario.usuario_roles to be eagerly loaded (selectinload).
        """
        usuario_roles = getattr(usuario, "usuario_roles", [])
        roles = [
            RolRead(
                id=ur.rol.id,
                codigo=ur.rol.codigo,
                nombre=ur.rol.nombre,
            )
            for ur in usuario_roles
            if ur.rol is not None
        ]
        return cls(
            id=getattr(usuario, "id"),
            email=getattr(usuario, "email"),
            nombre=getattr(usuario, "nombre"),
            apellido=getattr(usuario, "apellido"),
            created_at=getattr(usuario, "created_at"),
            deleted_at=getattr(usuario, "deleted_at", None),
            roles=roles,
        )


class UsuarioAdminUpdate(BaseModel):
    """Editable fields for PUT /admin/usuarios/{id}.

    D-01: email is NOT a field here. If a client sends email in the payload,
    extra="ignore" silently drops it — no error, no modification.

    Only nombre and apellido can be updated by ADMIN.
    """

    model_config = ConfigDict(extra="ignore")

    nombre: str | None = Field(default=None, max_length=80)
    apellido: str | None = Field(default=None, max_length=80)


class UsuarioRolesUpdate(BaseModel):
    """Full role set replacement payload for PUT /admin/usuarios/{id}/roles.

    Semantics (D-02): PUT replace — the payload contains the COMPLETE desired
    set of roles. The backend replaces all current roles with this set.

    Constraints:
    - min_length=1: at least one role must be provided.
    - validate_roles: each item must be one of the 4 valid role codes.
    - Deduplication: duplicate entries in the input are silently merged.
    """

    roles: list[str] = Field(
        min_length=1,
        description="Complete set of roles. Valid codes: ADMIN, STOCK, PEDIDOS, CLIENT.",
    )

    @field_validator("roles")
    @classmethod
    def validate_roles(cls, v: list[str]) -> list[str]:
        """Validate each role code and deduplicate the list."""
        valid = {"ADMIN", "STOCK", "PEDIDOS", "CLIENT"}
        invalid = set(v) - valid
        if invalid:
            raise ValueError(
                f"Roles inválidos: {invalid}. "
                f"Roles válidos: {valid}"
            )
        # Deduplicate while preserving order (using dict keys trick)
        seen: dict[str, None] = {}
        for code in v:
            seen[code] = None
        return list(seen.keys())


class UsuarioEstadoUpdate(BaseModel):
    """Activation/deactivation payload for PATCH /admin/usuarios/{id}/estado.

    activo=False → soft-delete (deactivate) the user.
    activo=True  → reactivate the user (D-05: backend supports it, frontend does NOT expose it).
    """

    activo: bool
