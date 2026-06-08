"""
Pydantic v2 schemas for the DireccionEntrega domain.

Change 14: delivery-addresses-management.

Strict separation of concerns:
  - DireccionEntregaCreate: fields for creating a new address (linea1 required).
    es_principal is intentionally EXCLUDED — logic is handled by the service.
  - DireccionEntregaUpdate: partial update — all fields optional, es_principal excluded.
    The field es_principal is not editable via PATCH general; use PATCH /{id}/principal.
  - DireccionEntregaRead: response schema — includes ORM fields, excludes deleted_at
    (internal audit field, never exposed to client).

Validation rules per spec:
  - linea1: required, min_length=3, max_length=255
  - alias: optional, max_length=50
  - linea2, ciudad, provincia, referencia: optional strings
  - codigo_postal: optional, max_length=10
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class DireccionEntregaCreate(BaseModel):
    """Schema for POST /api/v1/direcciones — create a new delivery address.

    linea1 is the only required field. All others are optional.
    es_principal is intentionally excluded — the service determines it based
    on whether the user already has active addresses.
    """

    linea1: str = Field(min_length=3, max_length=255)
    alias: str | None = Field(default=None, max_length=50)
    linea2: str | None = Field(default=None, max_length=255)
    ciudad: str | None = Field(default=None, max_length=100)
    provincia: str | None = Field(default=None, max_length=100)
    codigo_postal: str | None = Field(default=None, max_length=10)
    referencia: str | None = Field(default=None, max_length=255)


class DireccionEntregaUpdate(BaseModel):
    """Schema for PATCH /api/v1/direcciones/{id} — partial update.

    All fields are optional. Only fields present in the request body are updated.
    es_principal is intentionally excluded — use PATCH /{id}/principal instead.
    """

    linea1: str | None = Field(default=None, min_length=3, max_length=255)
    alias: str | None = Field(default=None, max_length=50)
    linea2: str | None = Field(default=None, max_length=255)
    ciudad: str | None = Field(default=None, max_length=100)
    provincia: str | None = Field(default=None, max_length=100)
    codigo_postal: str | None = Field(default=None, max_length=10)
    referencia: str | None = Field(default=None, max_length=255)


class DireccionEntregaRead(BaseModel):
    """Schema for read responses — includes ORM fields.

    from_attributes=True allows model_validate(orm_instance).
    deleted_at is intentionally excluded — it is an internal audit field
    and MUST NOT be exposed to API consumers.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    usuario_id: uuid.UUID
    alias: str | None
    linea1: str
    linea2: str | None
    ciudad: str | None
    provincia: str | None
    codigo_postal: str | None
    referencia: str | None
    es_principal: bool
    created_at: datetime
    updated_at: datetime
