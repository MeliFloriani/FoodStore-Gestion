# backend-catalog-public-browsing Specification

## Purpose
Public-facing catalog API: visibility rules, public Pydantic schemas, repository public methods, CatalogPublicService, catalog router, and performance indices. Introduced in Change 12 (catalog-public-browsing). NEVER exposes admin schemas or `stock_cantidad` exact value.

## ADDED Requirements

### Requirement: Public visibility rule — disponible AND not soft-deleted
The system SHALL enforce the rule `disponible = true AND deleted_at IS NULL` on ALL public catalog queries. This rule is the single gate between the full product set and what public users can see. No public endpoint SHALL ever return a product that fails this rule.

The rule SHALL be implemented as a private method `_apply_public_visibility(stmt)` on `ProductoRepository` in `backend/app/repositories/producto.py`. Both `list_public()` and `get_public_by_id()` MUST call this method.

#### Scenario: Soft-deleted product is invisible to public listing
- **GIVEN** a product with `disponible=true` and `deleted_at` set to a timestamp
- **WHEN** `GET /api/v1/catalog/productos` is called
- **THEN** that product does NOT appear in the response `items`
- **THEN** the `total` count does NOT include that product

#### Scenario: Unavailable product is invisible to public listing
- **GIVEN** a product with `disponible=false` and `deleted_at=null`
- **WHEN** `GET /api/v1/catalog/productos` is called
- **THEN** that product does NOT appear in the response `items`

#### Scenario: Soft-deleted product returns 404 on detail
- **GIVEN** a product with `deleted_at` set to a timestamp (regardless of `disponible` value)
- **WHEN** `GET /api/v1/catalog/productos/{id}` is called with that product's id
- **THEN** response is HTTP 404 with `code="PRODUCT_NOT_FOUND"`

#### Scenario: Unavailable product returns 404 on detail
- **GIVEN** a product with `disponible=false` and `deleted_at=null`
- **WHEN** `GET /api/v1/catalog/productos/{id}` is called with that product's id
- **THEN** response is HTTP 404 with `code="PRODUCT_NOT_FOUND"`

---

### Requirement: Public Pydantic schemas in catalog_public.py
The system SHALL provide Pydantic v2 schemas in `backend/app/schemas/catalog_public.py` for all public catalog API operations. These schemas are SEPARATE from the admin schemas in `backend/app/schemas/producto.py` and MUST NOT be imported from or inherited from admin schemas.

`CatalogProductosQuery(BaseModel)` SHALL enforce:
- `page: int = Field(default=1, ge=1)`
- `size: int = Field(default=20, ge=1, le=100)`
- `categoria_id: UUID | None = None`
- `q: str | None = Field(default=None, max_length=100)`
- `excluir_alergenos: str | None = Field(default=None)` — comma-separated positive integer ingredient IDs; validated in service
- `ordenar: str | None = Field(default=None, pattern="^-?(nombre|precio)$")`

`ProductoPublicoRead` SHALL include:
- `id: UUID`
- `nombre: str`
- `descripcion: str | None`
- `imagen_url: str | None`
- `precio_base: Decimal` — serialized as string via `@field_serializer`
- `disponible: bool`
- `tiene_stock: bool` — `True` if `stock_cantidad > 0`; NEVER exposes exact `stock_cantidad`
- `model_config = ConfigDict(from_attributes=True)`
- SHALL NOT include: `stock_cantidad`, `created_at`, `updated_at`, `deleted_at`

`CategoriaPublicaRead` SHALL include:
- `id: UUID`
- `nombre: str`
- `model_config = ConfigDict(from_attributes=True)`

`IngredientePublicoRead` SHALL include:
- `ingrediente_id: UUID`
- `nombre: str`
- `es_alergeno: bool`
- `model_config = ConfigDict(from_attributes=True)`
- SHALL NOT include: `es_removible` (operational/admin detail)

`ProductoPublicoDetalleRead(ProductoPublicoRead)` SHALL add:
- `categorias: list[CategoriaPublicaRead]`
- `ingredientes: list[IngredientePublicoRead]`

`PaginatedCatalogProductos` SHALL follow the `backend-pagination-schema` contract: `{ items: list[ProductoPublicoRead], total: int, page: int, size: int, pages: int }`.

#### Scenario: ProductoPublicoRead never includes stock_cantidad
- **WHEN** a `ProductoPublicoRead` instance is serialized to JSON
- **THEN** the resulting JSON object does NOT have a key `"stock_cantidad"`
- **THEN** the resulting JSON object HAS a key `"tiene_stock"` of type boolean

#### Scenario: tiene_stock is True when stock_cantidad > 0
- **GIVEN** a `Producto` with `stock_cantidad = 5`
- **WHEN** `ProductoPublicoRead` is constructed from that product
- **THEN** `tiene_stock` is `True`

#### Scenario: tiene_stock is False when stock_cantidad is 0
- **GIVEN** a `Producto` with `stock_cantidad = 0`
- **WHEN** `ProductoPublicoRead` is constructed from that product
- **THEN** `tiene_stock` is `False`

#### Constraint: ORM direct instantiation is prohibited for ProductoPublicoRead and IngredientePublicoRead
The schemas `ProductoPublicoRead` and `IngredientePublicoRead` SHALL NOT be instantiated via `model_validate(orm_object)` directly because:
- `tiene_stock` is not an attribute of the `Producto` ORM model (it is derived from `stock_cantidad > 0`).
- `ingrediente_id` in `IngredientePublicoRead` must be explicitly mapped from the `Ingrediente.id` attribute during DTO construction.

The `CatalogPublicService` SHALL ALWAYS use `_to_publico_read()` and `_to_publico_detalle()` as the sole mapping path from ORM objects to public schemas.

**Scenario: model_validate is not used for public schemas**
- **GIVEN** a `Producto` ORM instance with `stock_cantidad=5`
- **WHEN** the service maps it to a public DTO
- **THEN** `_to_publico_read(product)` is called — NOT `ProductoPublicoRead.model_validate(product)`
- **THEN** `tiene_stock` is set to `True` (5 > 0) in the returned DTO

#### Scenario: precio_base serialized as string in public schema
- **GIVEN** a `Producto` with `precio_base = Decimal("12.50")`
- **WHEN** `ProductoPublicoRead` is serialized to JSON
- **THEN** `"precio_base"` is the string `"12.50"` (not float `12.5`)

#### Scenario: CatalogProductosQuery rejects size > 100
- **WHEN** `CatalogProductosQuery(size=200)` is instantiated
- **THEN** Pydantic raises `ValidationError` with a field error on `size`

#### Scenario: CatalogProductosQuery rejects q longer than 100 chars
- **WHEN** `CatalogProductosQuery(q="x" * 101)` is instantiated
- **THEN** Pydantic raises `ValidationError` with a field error on `q`

#### Scenario: CatalogProductosQuery rejects invalid ordenar pattern
- **WHEN** `CatalogProductosQuery(ordenar="stock")` is instantiated
- **THEN** Pydantic raises `ValidationError` with a field error on `ordenar`

---

### Requirement: ProductoRepository public listing method
The system SHALL add `list_public(filters: CatalogProductosQuery) -> tuple[list[Producto], int]` to `ProductoRepository` in `backend/app/repositories/producto.py`.

The method SHALL:
- Apply `_apply_public_visibility()` to base query (always).
- If `filters.categoria_id` is not None: inner join `producto_categoria WHERE categoria_id = :id`.
- If `filters.q` is not None: `WHERE nombre ILIKE '%' || :q || '%'`.
- If `filters.excluir_alergenos` is not None (after service parsing to a list of ints): `NOT EXISTS (SELECT 1 FROM producto_ingrediente pi WHERE pi.producto_id = p.id AND pi.ingrediente_id IN (:ids))`.
- If `filters.ordenar` is not None: apply ORDER BY clause; default to `ORDER BY nombre ASC` (alphabetical, user-friendly for public catalog browsing).
- Execute a count query (`SELECT COUNT(*)`) with the same WHERE conditions but no LIMIT/OFFSET.
- Execute a data query with `OFFSET (page - 1) * size LIMIT size`.
- NOT load categorias or ingredientes via selectinload — ProductoPublicoRead does not include relations. The list query fires exactly 2 SQL statements: 1 COUNT + 1 SELECT with OFFSET/LIMIT.
- Return `(items, total)`.

#### Scenario: list_public returns only visible products
- **GIVEN** 5 products: 3 visible (disponible=true, deleted_at=null), 1 with disponible=false, 1 soft-deleted
- **WHEN** `list_public(CatalogProductosQuery())` is called
- **THEN** the returned list has 3 items and total is 3

#### Scenario: list_public filters by categoria_id
- **GIVEN** products P1 (category A), P2 (category B), P3 (category A) — all visible
- **WHEN** `list_public(CatalogProductosQuery(categoria_id=<category_A_id>))` is called
- **THEN** the returned items are [P1, P3] and total is 2

#### Scenario: list_public filters by q ILIKE
- **GIVEN** products "Pizza Margherita", "Hamburguesa Clásica", "Pizza Napolitana" — all visible
- **WHEN** `list_public(CatalogProductosQuery(q="pizza"))` is called
- **THEN** the returned items are ["Pizza Margherita", "Pizza Napolitana"] and total is 2
- **THEN** the ILIKE match is case-insensitive

#### Scenario: list_public excludes products with specified allergen ingredients
- **GIVEN** product P1 with ingredients [gluten (id=1, es_alergeno=true), tomate (id=2)]
- **GIVEN** product P2 with ingredients [tomate (id=2)] only
- **WHEN** `list_public` is called with `excluir_alergenos` parsed to [1]
- **THEN** P1 does NOT appear in results (contains ingredient 1)
- **THEN** P2 DOES appear in results (does not contain ingredient 1)

#### Scenario: list_public respects page and size
- **GIVEN** 25 visible products
- **WHEN** `list_public(CatalogProductosQuery(page=2, size=10))` is called
- **THEN** returns 10 items starting from item 11
- **THEN** total is 25

#### Scenario: list_public fires exactly 2 SQL queries
- **GIVEN** 20 visible products
- **WHEN** `list_public(CatalogProductosQuery(page=1, size=20))` is called
- **THEN** exactly 2 SQL queries are fired: one COUNT and one SELECT
- **THEN** no selectinload queries for categorias or ingredientes are fired

---

### Requirement: ProductoRepository public detail method
The system SHALL add `get_public_by_id(producto_id: UUID) -> Producto | None` to `ProductoRepository` in `backend/app/repositories/producto.py`.

The method SHALL:
- Apply `_apply_public_visibility()` (disponible=true AND deleted_at IS NULL).
- Load with `selectinload(Producto.producto_categorias).selectinload(ProductoCategoria.categoria)` and `selectinload(Producto.producto_ingredientes).selectinload(ProductoIngrediente.ingrediente)`.
- Return the `Producto` instance if found, `None` otherwise.

#### Scenario: get_public_by_id returns product with relations
- **GIVEN** a visible product with 2 categories and 3 ingredients
- **WHEN** `get_public_by_id(product_id)` is called
- **THEN** returns the product with `producto_categorias` list of length 2 and `producto_ingredientes` list of length 3
- **THEN** total SQL queries fired is at most 3

#### Scenario: get_public_by_id returns None for hidden product
- **GIVEN** a product with `disponible=false`
- **WHEN** `get_public_by_id(product_id)` is called
- **THEN** returns `None`

---

### Requirement: CatalogPublicService
The system SHALL provide `CatalogPublicService` in `backend/app/services/catalog_public.py` with two public methods:

**`list_catalog(uow: UnitOfWork, filters: CatalogProductosQuery) -> PaginatedCatalogProductos`**:
1. Validates `excluir_alergenos`: parses comma-separated string to `list[int]`, rejects non-integer or non-positive values with `AppValidationError(code="INVALID_ALLERGEN_IDS", status_code=422)`, deduplicates, caps at 20 items (raises 422 if exceeded).
2. Calls `await uow.productos.list_public(filters)`.
3. Assembles `PaginatedCatalogProductos` with `pages = ceil(total / filters.size)`.
4. Maps each `Producto` to `ProductoPublicoRead` via `_to_publico_read()`.

**`get_catalog_detail(uow: UnitOfWork, producto_id: UUID) -> ProductoPublicoDetalleRead`**:
1. Calls `await uow.productos.get_public_by_id(producto_id)`.
2. If `None`: raises `NotFoundError(code="PRODUCT_NOT_FOUND")`.
3. Maps to `ProductoPublicoDetalleRead` via `_to_publico_detalle()`.

Private helpers:
- `_to_publico_read(p: Producto) -> ProductoPublicoRead` — sets `tiene_stock = p.stock_cantidad > 0`.
- `_to_publico_detalle(p: Producto) -> ProductoPublicoDetalleRead` — maps relations to `CategoriaPublicaRead` and `IngredientePublicoRead`.

#### Scenario: list_catalog returns paginated public products
- **WHEN** `list_catalog(uow, CatalogProductosQuery(page=1, size=20))` is called with 5 visible products
- **THEN** returns `PaginatedCatalogProductos` with 5 items, total=5, pages=1
- **THEN** no item has a `stock_cantidad` field

#### Scenario: list_catalog raises 422 on invalid excluir_alergenos
- **WHEN** `list_catalog` is called with `excluir_alergenos="abc,1"` (non-integer)
- **THEN** service raises `AppValidationError(code="INVALID_ALLERGEN_IDS", status_code=422)`

#### Scenario: list_catalog raises 422 when excluir_alergenos exceeds 20 items
- **WHEN** `list_catalog` is called with `excluir_alergenos` containing 21 comma-separated IDs
- **THEN** service raises `AppValidationError(code="INVALID_ALLERGEN_IDS", status_code=422)`

#### Scenario: get_catalog_detail raises 404 for hidden product
- **WHEN** `get_catalog_detail(uow, product_id)` is called for a product with `disponible=false`
- **THEN** service raises `NotFoundError(code="PRODUCT_NOT_FOUND")`

---

### Requirement: Public catalog REST endpoints (2 endpoints)
The system SHALL expose 2 REST endpoints in `backend/app/api/v1/catalog.py` registered via `catalog_router`. The router SHALL have NO dependency on any auth function — endpoints are fully public.

**`GET /api/v1/catalog/productos`**:
- Query params: `CatalogProductosQuery` via `Depends`.
- Response model: `PaginatedCatalogProductos`.
- HTTP 200 on success; HTTP 422 on invalid query params.
- No Authorization header required.

**`GET /api/v1/catalog/productos/{id}`**:
- Path param: `id: UUID`.
- Response model: `ProductoPublicoDetalleRead`.
- HTTP 200 on success; HTTP 404 with `code="PRODUCT_NOT_FOUND"` when product is hidden or not found; HTTP 422 if `id` is not a valid UUID.
- No Authorization header required.

#### Scenario: GET /api/v1/catalog/productos returns 200 with no auth
- **WHEN** `GET /api/v1/catalog/productos` is called without Authorization header
- **THEN** response is HTTP 200
- **THEN** body matches `PaginatedCatalogProductos` shape
- **THEN** no item in `items` has a `stock_cantidad` key
- **THEN** every item in `items` has `tiene_stock` as a boolean

#### Scenario: GET /api/v1/catalog/productos supports all filters
- **WHEN** `GET /api/v1/catalog/productos?page=1&size=10&q=pizza&categoria_id=<uuid>&excluir_alergenos=1,2&ordenar=-precio` is called
- **THEN** response is HTTP 200
- **THEN** items are filtered by all provided params with AND semantics

#### Scenario: GET /api/v1/catalog/productos/{id} returns full detail
- **WHEN** `GET /api/v1/catalog/productos/{id}` is called for a visible product
- **THEN** response is HTTP 200 with `ProductoPublicoDetalleRead`
- **THEN** response includes `categorias` list and `ingredientes` list
- **THEN** each ingredient has `es_alergeno` field
- **THEN** response does NOT include `stock_cantidad`

#### Scenario: GET /api/v1/catalog/productos/{id} returns 404 for hidden product
- **WHEN** `GET /api/v1/catalog/productos/{id}` is called for a product with `disponible=false`
- **THEN** response is HTTP 404 with body `{"status": 404, "code": "PRODUCT_NOT_FOUND", "detail": "..."}`

#### Scenario: GET /api/v1/catalog/productos/{id} returns 422 for non-UUID id
- **WHEN** `GET /api/v1/catalog/productos/not-a-uuid` is called
- **THEN** response is HTTP 422 (FastAPI path param validation)

---

### Requirement: Performance index for public catalog queries
The system SHALL provide an Alembic migration in `backend/alembic/versions/` adding:

1. **Required**: `idx_productos_disponible_deleted_at` — partial index on `producto(id) WHERE disponible=true AND deleted_at IS NULL`. This index is required and MUST be present for acceptable query performance on the public listing endpoint.

2. **Optional (documented trade-off)**: `idx_productos_nombre_lower` — btree index on `lower(nombre)`. Helps with equality and prefix searches but NOT with `'%q%'` leading-wildcard ILIKE. Document in migration comment: "For production-scale full-text search on nombre, replace with `CREATE INDEX USING GIN (nombre gin_trgm_ops)` (requires pg_trgm extension)."

**CRITICAL — Alembic transaction requirement**: `CREATE INDEX CONCURRENTLY` cannot run inside a PostgreSQL transaction block. Alembic wraps migrations in transactions by default. The migration MUST use `autocommit_block()`:

```python
def upgrade():
    # CONCURRENTLY requires running outside a transaction block
    with op.get_context().autocommit_block():
        op.execute("""
            CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_productos_disponible_deleted_at
            ON producto (id)
            WHERE disponible = true AND deleted_at IS NULL
        """)
        op.execute("""
            CREATE INDEX IF NOT EXISTS idx_productos_nombre_lower
            ON producto (lower(nombre))
        """)

def downgrade():
    op.execute("DROP INDEX IF EXISTS idx_productos_disponible_deleted_at")
    op.execute("DROP INDEX IF EXISTS idx_productos_nombre_lower")
```

The migration SHALL be reversible (downgrade drops both indices).

#### Scenario: Migration runs successfully (CONCURRENTLY outside transaction)
- **WHEN** `alembic upgrade head` is run
- **THEN** the migration uses `autocommit_block()` to execute `CREATE INDEX CONCURRENTLY`
- **THEN** the migration does NOT fail with "CREATE INDEX CONCURRENTLY cannot run inside a transaction block"
- **THEN** `idx_productos_disponible_deleted_at` exists in the `producto` table after the migration

#### Scenario: Partial index exists after migration
- **WHEN** `alembic upgrade head` is run against a fresh schema
- **THEN** `idx_productos_disponible_deleted_at` exists in the `producto` table
- **THEN** the index has `WHERE disponible = true AND deleted_at IS NULL` as its predicate

#### Scenario: Migration is reversible
- **WHEN** `alembic downgrade -1` is run after the migration was applied
- **THEN** `idx_productos_disponible_deleted_at` is dropped
- **THEN** no other indices or table columns are affected

---

### Requirement: RFC 7807 error codes for public catalog
The system SHALL return RFC 7807-compliant error responses for all public catalog business rule violations.

| HTTP Status | `code` | Trigger |
|---|---|---|
| 404 | `PRODUCT_NOT_FOUND` | Product `id` does not exist, has `deleted_at` set, or has `disponible=false` |
| 422 | (Pydantic / FastAPI) | Invalid `page`, `size`, `q` too long, invalid `ordenar` pattern, invalid UUID path param |
| 422 | `INVALID_ALLERGEN_IDS` | `excluir_alergenos` contains non-integer, non-positive, or more than 20 IDs |

#### Scenario: 404 PRODUCT_NOT_FOUND matches RFC 7807 shape
- **WHEN** `GET /api/v1/catalog/productos/{non_existent_id}` is called
- **THEN** body contains `{"status": 404, "code": "PRODUCT_NOT_FOUND", "detail": "..."}`

#### Scenario: 422 INVALID_ALLERGEN_IDS matches RFC 7807 shape
- **WHEN** `GET /api/v1/catalog/productos?excluir_alergenos=abc` is called
- **THEN** body contains `{"status": 422, "code": "INVALID_ALLERGEN_IDS"}`

---

### Requirement: Public exposure security restrictions
The system SHALL NEVER include the following fields in ANY public catalog response:

- `stock_cantidad` — exact stock quantity is operational data and MUST NOT be disclosed
- `deleted_at` — internal soft delete sentinel
- `created_at` — internal audit timestamp
- `updated_at` — internal audit timestamp

The public schemas (`ProductoPublicoRead`, `ProductoPublicoDetalleRead`) are the enforcement mechanism. No response_model override, `exclude` directive, or runtime filtering shall be relied upon as the sole protection — the schemas themselves MUST NOT define those fields.

#### Scenario: Public list response body never contains stock_cantidad
- **WHEN** `GET /api/v1/catalog/productos` response body is inspected at the JSON level
- **THEN** no object in `items` has the key `"stock_cantidad"`
- **THEN** no object in `items` has the key `"deleted_at"`, `"created_at"`, or `"updated_at"`

#### Scenario: Public detail response body never contains stock_cantidad
- **WHEN** `GET /api/v1/catalog/productos/{id}` response body is inspected at the JSON level
- **THEN** the root object does NOT have the key `"stock_cantidad"`
- **THEN** the root object DOES have the key `"tiene_stock"` as a boolean

---

### Requirement: Public allergen ingredient list endpoint
**Motivation**: `GET /api/v1/ingredientes` requires ADMIN/STOCK role (defined in `backend-ingredientes-management` spec). The frontend `AllergenosExclusion` widget needs a list of allergen ingredients for public, unauthenticated users. This change adds a dedicated public endpoint to avoid modifying the admin ingredients surface.

The system SHALL expose `GET /api/v1/catalog/ingredientes-alergenos` in `catalog_router` with NO auth dependency.

`CatalogPublicService.list_alergenos(uow)` SHALL:
1. Query `SELECT * FROM ingrediente WHERE es_alergeno=true AND deleted_at IS NULL ORDER BY nombre ASC`.
2. Return `IngredienteAlergenicoListResponse(items=list[IngredientePublicoRead], total=int)`.

`IngredienteAlergenicoListResponse` SHALL be added to `backend/app/schemas/catalog_public.py`:
```python
class IngredienteAlergenicoListResponse(BaseModel):
    items: list[IngredientePublicoRead]
    total: int
```

#### Scenario: GET /api/v1/catalog/ingredientes-alergenos returns all active allergens
- **GIVEN** 3 active allergen ingredients and 2 non-allergen ingredients in the DB
- **WHEN** `GET /api/v1/catalog/ingredientes-alergenos` is called without Authorization header
- **THEN** response is HTTP 200
- **THEN** `items` has 3 entries, all with `es_alergeno=true`
- **THEN** non-allergen ingredients are NOT in the response

#### Scenario: GET /api/v1/catalog/ingredientes-alergenos excludes soft-deleted ingredients
- **GIVEN** an allergen ingredient with `deleted_at` set
- **WHEN** `GET /api/v1/catalog/ingredientes-alergenos` is called
- **THEN** the soft-deleted ingredient does NOT appear in `items`

#### Scenario: GET /api/v1/catalog/ingredientes-alergenos requires no auth
- **WHEN** `GET /api/v1/catalog/ingredientes-alergenos` is called without Authorization header
- **THEN** response is HTTP 200 (not 401 or 403)

#### Scenario: GET /api/v1/catalog/ingredientes-alergenos returns empty list when no allergens exist
- **GIVEN** no allergen ingredients in the DB
- **WHEN** `GET /api/v1/catalog/ingredientes-alergenos` is called
- **THEN** response is HTTP 200 with `{ "items": [], "total": 0 }`
