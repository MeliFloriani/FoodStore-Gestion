"""
Pydantic v2 schemas for the Categoria domain.

Strict separation of concerns:
  - CategoriaBase: shared validation rules (nombre length)
  - CategoriaCreate: create operation (inherits base + parent_id)
  - CategoriaUpdate: partial update — uses model_fields_set sentinel for parent_id
  - CategoriaRead: read response with ORM fields (from_attributes=True)
  - CategoriaTreeNode: recursive tree node for GET /categorias response

Sentinel pattern for CategoriaUpdate.parent_id:
  - If "parent_id" is NOT in model_fields_set → field was absent from payload
    → service does NOT touch the category's parent_id (no reparenting)
  - If "parent_id" IS in model_fields_set AND value is None → explicit null sent
    → service sets parent_id = NULL (promote to root)
  - If "parent_id" IS in model_fields_set AND value is UUID → reparent to that UUID
    → service validates and sets parent_id = new_parent_id

This approach avoids a custom UNSET sentinel type while being fully type-safe.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CategoriaBase(BaseModel):
    """Shared validation rules for all Categoria schemas."""

    nombre: str = Field(min_length=1, max_length=100)
    descripcion: str | None = None


class CategoriaCreate(CategoriaBase):
    """Schema for POST /api/v1/categorias — create a new category.

    Inherits nombre + descripcion from CategoriaBase.
    parent_id=None creates a root category.
    parent_id=<UUID> creates a subcategory under the given parent.
    """

    parent_id: UUID | None = None


class CategoriaUpdate(BaseModel):
    """Schema for PUT /api/v1/categorias/{id} — partial update.

    All fields are optional. The service uses model_fields_set to distinguish:
      - Field absent from payload → do NOT update that field
      - Field present as None → set to NULL (for parent_id: promote to root)
      - Field present as value → update to that value

    IMPORTANT: The router MUST pass this Pydantic model instance directly to
    the service (NOT data.model_dump()). Converting to dict loses model_fields_set
    information, breaking the sentinel pattern for parent_id.
    """

    nombre: str | None = Field(default=None, min_length=1, max_length=100)
    descripcion: str | None = None
    # parent_id sentinel:
    # - absent → not in model_fields_set → no reparenting
    # - None   → in model_fields_set → promote to root
    # - UUID   → in model_fields_set → reparent to that category
    parent_id: UUID | None = None


class CategoriaRead(CategoriaBase):
    """Schema for read responses — includes ORM fields.

    from_attributes=True allows model_validate(orm_instance).
    deleted_at intentionally excluded — public endpoint MUST NOT
    expose soft-delete status to API consumers.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    parent_id: UUID | None
    created_at: datetime
    updated_at: datetime


class CategoriaTreeNode(BaseModel):
    """Recursive tree node for GET /api/v1/categorias response.

    Represents one node in the category tree. subcategorias contains
    the direct children, each of which may have their own subcategorias.

    model_rebuild() is called at MODULE LEVEL immediately after the class
    definition to resolve the forward reference "CategoriaTreeNode" in
    subcategorias. This MUST occur at module import time — not inside a
    function or conditional — otherwise Pydantic fails to serialize nested trees.
    """

    id: UUID
    nombre: str
    descripcion: str | None = None
    subcategorias: list["CategoriaTreeNode"] = []


# Resolve the forward reference at module import time (mandatory — see docstring above)
CategoriaTreeNode.model_rebuild()
