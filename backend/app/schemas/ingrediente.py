"""
Pydantic v2 schemas for the Ingrediente domain.

Strict separation of concerns:
  - IngredienteBase: shared validation rules (nombre length + strip whitespace)
  - IngredienteCreate: create operation (inherits base, no extra fields)
  - IngredienteUpdate: partial update — all fields optional; service uses
    model_fields_set to only update supplied fields (D-05 from design.md)
  - IngredienteRead: read response with ORM fields (from_attributes=True)

model_fields_set pattern for IngredienteUpdate:
  - If "nombre" is NOT in model_fields_set → field was absent from payload
    → service does NOT touch nombre
  - If "es_alergeno" is NOT in model_fields_set → field was absent from payload
    → service does NOT touch es_alergeno

IMPORTANT: The router MUST pass the IngredienteUpdate Pydantic model instance
directly to the service (NOT data.model_dump()). Converting to dict loses
model_fields_set information, breaking the partial-update sentinel (D-05).
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class IngredienteBase(BaseModel):
    """Shared validation rules for all Ingrediente schemas."""

    nombre: str = Field(min_length=1, max_length=100)
    es_alergeno: bool = False

    @field_validator("nombre")
    @classmethod
    def strip_and_validate_nombre(cls, v: str) -> str:
        """Strip whitespace from nombre and reject whitespace-only strings.

        Two-step validation:
          1. Strip leading/trailing whitespace.
          2. Reject empty string (min_length=1 enforces this after strip).
        """
        stripped = v.strip()
        if not stripped:
            raise ValueError("nombre must not be blank or whitespace-only")
        return stripped


class IngredienteCreate(IngredienteBase):
    """Schema for POST /api/v1/ingredientes — create a new ingredient.

    Inherits nombre + es_alergeno from IngredienteBase.
    es_alergeno defaults to False if not supplied.
    """


class IngredienteUpdate(BaseModel):
    """Schema for PUT /api/v1/ingredientes/{id} — partial update.

    All fields are optional. The service uses model_fields_set to distinguish:
      - Field absent from payload → do NOT update that field
      - Field present with value   → update to that value

    IMPORTANT: The router MUST pass this Pydantic model instance directly to
    the service (NOT data.model_dump()). Converting to dict loses model_fields_set
    information, breaking the partial-update sentinel pattern (D-05).
    """

    # None means "not supplied by caller" — absent from model_fields_set
    nombre: str | None = None
    es_alergeno: bool | None = None


class IngredienteRead(IngredienteBase):
    """Schema for read responses — includes ORM fields.

    from_attributes=True allows model_validate(orm_instance).
    deleted_at intentionally excluded — API consumers must not see soft-delete state.

    Field names match Base class exactly:
      - id: uuid.UUID  (not int — D-18: UUID PK)
      - created_at: datetime
      - updated_at: datetime
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime
    updated_at: datetime
