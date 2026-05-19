"""
Pydantic v2 schemas for the Producto domain.

Strict separation of concerns:
  - ProductoBase: shared validation rules (nombre, precio_base, disponible)
  - ProductoCreate: create operation (inherits base + stock_cantidad + categoria_ids)
  - ProductoUpdate: partial update — all fields optional; service uses model_fields_set
  - ProductoRead: read response with ORM fields (from_attributes=True)
  - ProductoDetail: extends ProductoRead with categorias + ingredientes
  - ProductoIngredienteRead: M2M join result for ingredient associations
  - DisponibilidadUpdate: PATCH /disponibilidad payload
  - AsociarIngredienteRequest: POST /ingredientes payload
  - PaginatedProductos: paginated list response (backend-pagination-schema)

Key design decisions:
  - H-02: precio_base declared as Decimal in schemas (not float).
    The ORM model has precio_base: float (DECIMAL(10,2)), but asyncpg may return
    Decimal or float. Pydantic v2 with from_attributes=True handles float→Decimal
    conversion automatically. The @field_serializer ensures JSON output is a string.
  - model_fields_set pattern: ProductoUpdate uses model_fields_set so the service
    can distinguish "field not sent" from "field explicitly set to None/False/0".
    IMPORTANT: the router MUST pass the Pydantic model instance directly to the
    service — NOT data.model_dump(). Converting to dict loses model_fields_set.
  - categoria_ids in ProductoUpdate: if absent → unchanged; if [] → remove all.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator

from app.schemas.categoria import CategoriaRead


class ProductoBase(BaseModel):
    """Shared validation rules for all Producto schemas."""

    nombre: str = Field(min_length=1, max_length=200)
    descripcion: str | None = None
    imagen_url: str | None = Field(default=None, max_length=500)
    precio_base: Decimal = Field(ge=Decimal("0.00"))
    disponible: bool = True

    @field_validator("precio_base")
    @classmethod
    def validate_precio_decimal_places(cls, v: Decimal) -> Decimal:
        """Reject precio_base with more than 2 decimal places.

        Ensures the value stored in DECIMAL(10,2) is not silently truncated.
        Examples:
          - Decimal("19.99")  → accepted (2 decimal places)
          - Decimal("19.999") → rejected (3 decimal places)
          - Decimal("19")     → accepted (0 decimal places — no trailing zeros issue)
        """
        sign, digits, exponent = v.as_tuple()
        # exponent is negative for decimal places; e.g. -2 means 2 decimal places
        if isinstance(exponent, int) and exponent < -2:
            raise ValueError("precio_base cannot have more than 2 decimal places")
        return v


class ProductoCreate(ProductoBase):
    """Schema for POST /api/v1/productos — create a new product.

    Inherits all ProductoBase fields (nombre, descripcion, imagen_url,
    precio_base, disponible).

    Additional fields:
      - stock_cantidad: initial stock (0 by default, must be non-negative)
      - categoria_ids: optional list of category UUIDs to associate on creation
    """

    stock_cantidad: int = Field(ge=0, default=0)
    categoria_ids: list[UUID] | None = None


class ProductoUpdate(BaseModel):
    """Schema for PATCH /api/v1/productos/{id} — partial update.

    All fields are optional. The service uses model_fields_set to distinguish:
      - Field absent from payload → do NOT update that field
      - Field present with value  → update to that value

    Special sentinel for categoria_ids:
      - Not in model_fields_set → category associations unchanged
      - In model_fields_set with value [] → ALL category associations removed
      - In model_fields_set with UUIDs → associations replaced (replace-all)

    IMPORTANT: The router MUST pass this Pydantic model instance directly to
    the service (NOT data.model_dump()). Converting to dict loses model_fields_set,
    breaking the partial-update sentinel pattern.
    """

    nombre: str | None = Field(default=None, min_length=1, max_length=200)
    descripcion: str | None = None
    imagen_url: str | None = Field(default=None, max_length=500)
    precio_base: Decimal | None = Field(default=None, ge=Decimal("0.00"))
    stock_cantidad: int | None = Field(default=None, ge=0)  # ADMIN can set absolute stock
    disponible: bool | None = None
    # categoria_ids sentinel:
    # - absent → not in model_fields_set → no change to categories
    # - []     → in model_fields_set → remove all categories
    # - [uuid] → in model_fields_set → replace-all categories
    categoria_ids: list[UUID] | None = None


class ProductoRead(ProductoBase):
    """Schema for compact read responses (list endpoint).

    Includes all ProductoBase fields plus ORM-managed fields.
    from_attributes=True allows model_validate(orm_instance).
    deleted_at intentionally excluded — API consumers must not see soft-delete state.

    H-02: precio_base is declared as Decimal (not float). The @field_serializer
    ensures JSON output serializes it as a string, not a float — preventing float
    precision loss in JSON (e.g. 15.50 becoming 15.5).
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    stock_cantidad: int
    created_at: datetime
    updated_at: datetime

    @field_serializer("precio_base")
    def serialize_precio(self, v: Decimal) -> str:
        """Serialize precio_base as a string in JSON output.

        Prevents float precision loss: Decimal("15.50") → "15.50" (not 15.5).
        The backend stores DECIMAL(10,2); we serialize as string to preserve
        the exact representation through the HTTP API.
        """
        return str(Decimal(str(v)).quantize(Decimal("0.01")))


class ProductoIngredienteRead(BaseModel):
    """Schema for ingredient association read responses.

    Maps ProductoIngrediente pivot + nested Ingrediente data.
    from_attributes=True allows model_validate(orm_instance).

    Fields:
      - ingrediente_id: UUID of the associated ingredient
      - nombre: nombre field from the related Ingrediente
      - es_alergeno: allergen flag from the related Ingrediente
      - es_removible: removable flag from the ProductoIngrediente pivot
    """

    model_config = ConfigDict(from_attributes=True)

    ingrediente_id: UUID
    nombre: str
    es_alergeno: bool
    es_removible: bool


class ProductoDetail(ProductoRead):
    """Schema for full product detail (single product endpoint).

    Extends ProductoRead with M2M associations:
      - categorias: flat list of associated categories (CategoriaRead)
      - ingredientes: list of ingredient associations (ProductoIngredienteRead)

    Both lists may be empty if the product has no associations.
    """

    categorias: list[CategoriaRead] = []
    ingredientes: list[ProductoIngredienteRead] = []


class DisponibilidadUpdate(BaseModel):
    """Schema for PATCH /api/v1/productos/{id}/disponibilidad.

    Single required field — available to ADMIN and STOCK roles.
    """

    disponible: bool


class AsociarIngredienteRequest(BaseModel):
    """Schema for POST /api/v1/productos/{id}/ingredientes.

    es_removible is REQUIRED (no default) — must always be explicit because
    ProductoIngrediente.es_removible has no DB default (D-31 design decision).
    Pydantic will raise ValidationError if es_removible is absent from the payload.
    """

    ingrediente_id: UUID
    es_removible: bool  # Required — no default


class PaginatedProductos(BaseModel):
    """Paginated product list response following backend-pagination-schema.

    Shape: { items, total, page, size, pages }
    pages = ceil(total / size).
    """

    items: list[ProductoRead]
    total: int
    page: int
    size: int
    pages: int
