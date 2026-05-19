"""
Pydantic v2 schemas for the public catalog API.

These schemas are COMPLETELY SEPARATE from admin schemas (backend/app/schemas/producto.py).
They MUST NOT inherit from or import admin schemas.

Key design decisions:
  - ProductoPublicoRead: NEVER includes stock_cantidad; exposes tiene_stock: bool instead.
  - IngredientePublicoRead: uses ingrediente_id (not id) to avoid ambiguity in nested context.
  - ORM direct instantiation PROHIBITED for ProductoPublicoRead and IngredientePublicoRead.
    Always use CatalogPublicService._to_publico_read() and _to_publico_detalle().
  - precio_base: Decimal in schema → string in JSON via @field_serializer (H-02 pattern).
  - CatalogProductosQuery: used as FastAPI Depends() — all fields have defaults.
  - excluir_alergenos: comma-separated UUID strings, validated in service (not schema).
"""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_serializer


class CatalogProductosQuery(BaseModel):
    """Query params for GET /api/v1/catalog/productos.

    Used as a FastAPI Depends() dependency — all fields have defaults.

    Fields:
      - page: 1-based page number (ge=1)
      - size: items per page (1–100)
      - categoria_id: optional category UUID filter
      - q: optional ILIKE search on nombre (max 100 chars)
      - excluir_alergenos: comma-separated UUID ingredient IDs (validated in service)
      - ordenar: optional sort direction; pattern ^-?(nombre|precio)$
    """

    page: int = Field(default=1, ge=1)
    size: int = Field(default=20, ge=1, le=100)
    categoria_id: UUID | None = None
    q: str | None = Field(default=None, max_length=100)
    excluir_alergenos: str | None = Field(
        default=None,
        description="Comma-separated UUID ingredient IDs to exclude",
    )
    ordenar: str | None = Field(
        default=None,
        pattern=r"^-?(nombre|precio)$",
        description="Sort order: nombre, -nombre, precio, -precio",
    )


class CategoriaPublicaRead(BaseModel):
    """Public-safe schema for product category.

    Includes only id and nombre — admin fields like parent_id, descripcion are omitted.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    nombre: str


class IngredientePublicoRead(BaseModel):
    """Public-safe schema for an ingredient in a product detail response.

    Uses ingrediente_id (not id) to avoid ambiguity when nested inside
    ProductoPublicoDetalleRead (where id refers to the product).

    IMPORTANT: CANNOT be instantiated via model_validate(orm_obj) directly.
    ingrediente_id must be explicitly set from Ingrediente.id via service helper.
    """

    model_config = ConfigDict(from_attributes=True)

    ingrediente_id: UUID
    nombre: str
    es_alergeno: bool
    # es_removible intentionally omitted — operational/admin detail not needed publicly


class ProductoPublicoRead(BaseModel):
    """Public-safe schema for a product in catalog listing.

    CRITICAL: NEVER includes stock_cantidad. Uses tiene_stock: bool instead.
    NEVER includes created_at, updated_at, deleted_at.

    IMPORTANT: CANNOT be instantiated via model_validate(orm_obj) directly because:
    - tiene_stock is derived from stock_cantidad > 0 and does not exist on the ORM model.
    Always use CatalogPublicService._to_publico_read() to construct this schema.

    H-02: precio_base declared as Decimal; @field_serializer ensures string JSON output.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    nombre: str
    descripcion: str | None
    imagen_url: str | None
    precio_base: Decimal
    disponible: bool
    tiene_stock: bool  # True if stock_cantidad > 0; NEVER exposes exact stock_cantidad

    @field_serializer("precio_base")
    def serialize_precio(self, v: Decimal) -> str:
        """Serialize precio_base as a string in JSON output.

        Prevents float precision loss: Decimal("15.50") → "15.50" (not 15.5).
        Same pattern as ProductoRead in backend/app/schemas/producto.py.
        """
        return str(Decimal(str(v)).quantize(Decimal("0.01")))


class ProductoPublicoDetalleRead(ProductoPublicoRead):
    """Public-safe full product detail schema (extends list schema with relations).

    Adds categorias and ingredientes lists for the detail endpoint.
    Both lists may be empty if the product has no associations.
    """

    categorias: list[CategoriaPublicaRead] = []
    ingredientes: list[IngredientePublicoRead] = []


class PaginatedCatalogProductos(BaseModel):
    """Paginated catalog product list response.

    Follows the backend-pagination-schema contract: { items, total, page, size, pages }.
    pages = ceil(total / size).
    """

    items: list[ProductoPublicoRead]
    total: int
    page: int
    size: int
    pages: int


class IngredienteAlergenicoListResponse(BaseModel):
    """Response schema for GET /api/v1/catalog/ingredientes-alergenos.

    Returns all active allergen ingredients for public display.
    Used by the frontend AllergenosExclusion widget to populate filter options.
    """

    items: list[IngredientePublicoRead]
    total: int
