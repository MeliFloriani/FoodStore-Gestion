# backend-products-management Specification

## Purpose
Backend product management capability: Pydantic schemas, repository, service, and REST endpoints for the `producto` domain including M2M associations to `categoria` and `ingrediente`. Introduced in Change 11 (catalog-products-management).

## ADDED Requirements

### Requirement: Pydantic schemas for Producto
The system SHALL provide Pydantic v2 schemas in `backend/app/schemas/producto.py` for all product API operations.

`ProductoBase` SHALL enforce:
- `nombre: str` — `Field(min_length=1, max_length=200)`
- `descripcion: str | None = None`
- `imagen_url: str | None = Field(default=None, max_length=500)`
- `precio_base: Decimal = Field(ge=Decimal("0.00"))` — with a `@field_validator` ensuring exactly 2 decimal places and non-negative value
- `disponible: bool = True`

`ProductoCreate(ProductoBase)` SHALL add:
- `stock_cantidad: int = Field(ge=0, default=0)`
- `categoria_ids: list[UUID] | None = None`

`ProductoUpdate` SHALL be a flat `BaseModel` (no inheritance) with all fields optional. The service SHALL use `model_fields_set` to distinguish "field not sent" from "field sent as None/False/0". `categoria_ids: list[UUID] | None = None` — if in `model_fields_set` with value `[]`, removes all category associations; if not in `model_fields_set`, category associations are unchanged. The router MUST pass the Pydantic model instance directly to the service — NOT a dict from `model_dump()`.

`ProductoRead` SHALL include `id: UUID`, all `ProductoBase` fields, `stock_cantidad: int`, `created_at: datetime`, `updated_at: datetime`. `model_config = ConfigDict(from_attributes=True)`. SHALL NOT expose `deleted_at`. `precio_base` SHALL be serialized as string in JSON output.

`ProductoDetail(ProductoRead)` SHALL add:
- `categorias: list[CategoriaRead]` — flat list of associated categories
- `ingredientes: list[ProductoIngredienteRead]` — list of ingredient associations

`ProductoIngredienteRead` SHALL include:
- `ingrediente_id: UUID`
- `nombre: str` — from the related `Ingrediente`
- `es_alergeno: bool` — from the related `Ingrediente`
- `es_removible: bool` — from `ProductoIngrediente.es_removible`
- `model_config = ConfigDict(from_attributes=True)`

`DisponibilidadUpdate` SHALL include `disponible: bool` only.

`AsociarIngredienteRequest` SHALL include `ingrediente_id: UUID` and `es_removible: bool` (required — no default).

`PaginatedProductos` SHALL follow the `backend-pagination-schema` contract: `{ items: list[ProductoRead], total: int, page: int, size: int, pages: int }`.

#### Scenario: ProductoCreate validates precio_base is non-negative
- **WHEN** a `ProductoCreate` payload has `precio_base = -1`
- **THEN** Pydantic raises `ValidationError` with a field error on `precio_base`

#### Scenario: ProductoCreate rejects float precio_base in favor of Decimal
- **WHEN** a `ProductoCreate` payload has `precio_base = Decimal("19.99")`
- **THEN** the validated value is `Decimal("19.99")` with exact precision

#### Scenario: ProductoCreate validates stock_cantidad is non-negative
- **WHEN** a `ProductoCreate` payload has `stock_cantidad = -5`
- **THEN** Pydantic raises `ValidationError` with a field error on `stock_cantidad`

#### Scenario: ProductoUpdate with absent categoria_ids does not modify categories
- **WHEN** `PATCH /api/v1/productos/{id}` is called with body `{"nombre": "Nuevo"}` (no `categoria_ids`)
- **THEN** the service reads `"categoria_ids" not in data.model_fields_set` as `True`
- **THEN** category associations remain unchanged

#### Scenario: ProductoUpdate with empty categoria_ids list removes all categories
- **WHEN** `PATCH /api/v1/productos/{id}` is called with body `{"categoria_ids": []}`
- **THEN** the service reads `"categoria_ids" in data.model_fields_set` as `True` with value `[]`
- **THEN** all `ProductoCategoria` pivot records for this product are hard-deleted

#### Scenario: ProductoRead serializes precio_base as string
- **WHEN** a `ProductoRead` instance with `precio_base = Decimal("15.50")` is serialized to JSON
- **THEN** the JSON value for `precio_base` is the string `"15.50"` (not the float `15.5`)

---

### Requirement: Producto SQLModel (already exists — no new file)
The system SHALL use the `Producto`, `ProductoCategoria`, and `ProductoIngrediente` SQLModel classes that ALREADY EXIST in `backend/app/models/catalog.py` (Change 03 convention D-17). There is NO `app/models/producto.py` file — do NOT create one.

The existing model has:
- `Producto.__tablename__ = "producto"` (SINGULAR)
- `precio_base: float` mapped to `DECIMAL(10, 2)` via `sa_column`
- `stock_cantidad: int` with `CHECK stock_cantidad >= 0`
- `disponible: bool` with `default=True`
- `deleted_at: datetime | None` — soft delete sentinel
- `Producto.producto_categorias` and `Producto.producto_ingredientes` use `lazy="noload"` — **explicit `selectinload` required in every query that needs these relations**
- Back-refs and nested relations within pivots (`ProductoCategoria.categoria`, `ProductoCategoria.producto`, `ProductoIngrediente.ingrediente`, `ProductoIngrediente.producto`) use `lazy="selectin"` — loaded automatically when the pivot is fetched, but explicit `selectinload` options in a query take precedence and avoid redundant loads

`ProductoCategoria` has `es_principal: bool = False` and `UniqueConstraint(producto_id, categoria_id)`.
`ProductoIngrediente` has `es_removible: bool` (no default — always explicit) and `UniqueConstraint(producto_id, ingrediente_id)`.

#### Scenario: Producto model maps to producto table (singular)
- **WHEN** `SQLModel.metadata` is inspected after importing `app.models.catalog`
- **THEN** a table named `producto` (singular) exists in the metadata
- **THEN** the table has columns `id` (UUID), `nombre`, `descripcion`, `imagen_url`, `precio_base` (DECIMAL), `stock_cantidad` (INTEGER), `disponible` (BOOLEAN), `created_at`, `updated_at`, `deleted_at`
- **THEN** CHECK constraints `ck_producto_precio_base` and `ck_producto_stock_cantidad` exist

#### Scenario: ProductoIngrediente es_removible has no default
- **WHEN** an `AsociarIngredienteRequest` without `es_removible` is submitted
- **THEN** Pydantic raises `ValidationError` (field is required)

---

### Requirement: ProductoRepository with paginated listing and atomic stock
The system SHALL provide `ProductoRepository(BaseRepository[Producto])` at `backend/app/repositories/producto.py` with these methods beyond `BaseRepository`:

- `list_paginated(page, size, categoria_id, disponible, search) -> tuple[list[Producto], int]`: Returns `(items, total)`. Filters `deleted_at IS NULL`. If `categoria_id`: inner join with `producto_categoria`. If `disponible` is not None: filters `disponible = :val`. If `search`: `ILIKE '%' || :search || '%'` on `nombre`. Offset = `(page - 1) * size`.
- `get_with_relations(producto_id: UUID) -> Producto | None`: Loads product with `selectinload(Producto.producto_categorias).selectinload(ProductoCategoria.categoria)` and `selectinload(Producto.producto_ingredientes).selectinload(ProductoIngrediente.ingrediente)`. Filters `deleted_at IS NULL`.
- `set_categorias(session, producto: Producto, categoria_ids: list[UUID]) -> None`: Hard-deletes all existing `ProductoCategoria` records for this product, then inserts new ones. First `categoria_id` in the list gets `es_principal=True`; others get `es_principal=False`. If `categoria_ids` is empty, only deletes.
- `add_ingrediente(producto_id: UUID, ingrediente_id: UUID, es_removible: bool) -> ProductoIngrediente`: Inserts new `ProductoIngrediente`. Raises `IntegrityError` if the association already exists.
- `remove_ingrediente(producto_id: UUID, ingrediente_id: UUID) -> bool`: Hard-deletes the `ProductoIngrediente` pivot. Returns `True` if a row was deleted, `False` if not found.
- `get_ingredientes(producto_id: UUID) -> list[ProductoIngrediente]`: Returns `ProductoIngrediente` list with `selectinload(ProductoIngrediente.ingrediente)` filtered by `producto_id` and `producto.deleted_at IS NULL`.
- `decrement_stock(producto_id: UUID, delta: int) -> Producto | None`: Executes `UPDATE producto SET stock_cantidad = stock_cantidad - :delta, updated_at = NOW() WHERE id = :producto_id AND stock_cantidad >= :delta AND deleted_at IS NULL RETURNING *`. Returns the updated `Producto` if successful, `None` if no row was updated (insufficient stock or not found).

#### Scenario: list_paginated returns correct page and total
- **WHEN** there are 25 active products and `page=2, size=10` is requested
- **THEN** `list_paginated` returns `(10 items, 25)` where items are the second page
- **THEN** no soft-deleted products appear in the result

#### Scenario: list_paginated filters by categoria_id
- **WHEN** `categoria_id` is provided
- **THEN** only products linked to that category via `producto_categoria` appear in the result

#### Scenario: list_paginated filters by disponible=True
- **WHEN** `disponible=True` is requested
- **THEN** only products with `disponible=True AND deleted_at IS NULL` appear

#### Scenario: list_paginated filters by search ILIKE
- **WHEN** `search="pizza"` is requested
- **THEN** only products with `nombre ILIKE '%pizza%'` appear (case-insensitive)

#### Scenario: get_with_relations loads categorias and ingredientes without N+1
- **WHEN** `get_with_relations(product_id)` is called on a product with 3 categories and 5 ingredients
- **THEN** the result has `producto_categorias` list of length 3 and `producto_ingredientes` list of length 5
- **THEN** the total number of SQL queries is at most 5: 1 product SELECT + 1 selectinload for `producto_categorias` + 1 selectinload for `categorias` (nested) + 1 selectinload for `producto_ingredientes` + 1 selectinload for `ingredientes` (nested). No per-record queries are fired regardless of category or ingredient count.
- **NOTE** `Producto.producto_categorias` has `lazy="noload"` so the explicit `selectinload` is required. Pivot back-refs have `lazy="selectin"` but the explicit nested `selectinload` option takes precedence, preventing redundant automatic loads.

#### Scenario: set_categorias replaces all category associations
- **GIVEN** a product linked to categories [A, B, C]
- **WHEN** `set_categorias(producto, [D, E])` is called
- **THEN** the pivot records for A, B, C are hard-deleted
- **THEN** new pivot records for D and E are inserted
- **THEN** the pivot for D has `es_principal=True`, the pivot for E has `es_principal=False`

#### Scenario: set_categorias is atomic within UoW — rollback on failure reverts both delete and insert
- **GIVEN** a product linked to categories [A, B]
- **WHEN** `set_categorias(producto, [C, <invalid_uuid>])` is called inside a UoW and the insert of `<invalid_uuid>` raises an error (e.g., FK violation)
- **THEN** the entire UoW rolls back
- **THEN** the product remains linked to categories [A, B] (original state preserved)
- **THEN** no partial state (product with 0 categories) is ever committed to the database
- **NOTE** atomicity is guaranteed by sharing the same `AsyncSession` within the UoW. `set_categorias` MUST NOT open its own session or call `session.commit()` directly.

#### Scenario: add_ingrediente raises IntegrityError on duplicate
- **WHEN** `add_ingrediente(producto_id, ingrediente_id, es_removible)` is called for an existing association
- **THEN** SQLAlchemy raises `IntegrityError` (unique constraint violation)

#### Scenario: remove_ingrediente returns False when association does not exist
- **WHEN** `remove_ingrediente(producto_id, non_existent_ingrediente_id)` is called
- **THEN** the method returns `False` without raising an exception

#### Scenario: decrement_stock returns None when stock is insufficient
- **GIVEN** a product with `stock_cantidad = 3`
- **WHEN** `decrement_stock(producto_id, delta=5)` is called
- **THEN** the method returns `None` (no row updated — `5 > 3`)
- **THEN** the product's `stock_cantidad` remains 3 (no partial update)

#### Scenario: decrement_stock returns updated product on success
- **GIVEN** a product with `stock_cantidad = 10`
- **WHEN** `decrement_stock(producto_id, delta=3)` is called
- **THEN** the method returns a `Producto` with `stock_cantidad = 7`
- **THEN** the database row shows `stock_cantidad = 7`

---

### Requirement: ProductoService with full business rule enforcement
The system SHALL provide `ProductoService` at `backend/app/services/producto.py` orchestrating all business rules. The router SHALL pass `UnitOfWork` to the service via dependency injection.

**`list_productos(uow, page, size, categoria_id, disponible, search) -> PaginatedProductos`**: Calls `uow.productos.list_paginated(...)`. Assembles `PaginatedProductos` with `pages = ceil(total / size)`.

**`get_producto_detail(uow, producto_id: UUID) -> ProductoDetail`**: Calls `uow.productos.get_with_relations(producto_id)`. Raises `NotFoundError(code="PRODUCT_NOT_FOUND")` if `None`. Assembles `ProductoDetail` with nested `categorias` and `ingredientes`.

**`create_producto(uow, data: ProductoCreate) -> ProductoRead`**: Validates each UUID in `data.categoria_ids` (raises `NotFoundError(code="CATEGORY_NOT_FOUND")` if any are missing). Calls `uow.productos.create(...)`. If `data.categoria_ids` is not None, calls `uow.productos.set_categorias(...)`.

**`update_producto(uow, producto_id: UUID, data: ProductoUpdate) -> ProductoRead`**: Loads entity (raises `NotFoundError`). Applies only fields present in `data.model_fields_set`. If `categoria_ids` in `model_fields_set`: validates all IDs exist, calls `set_categorias`. If `precio_base` or `stock_cantidad` in `model_fields_set`: validates non-negative. Calls `uow.productos.update(...)`.

**`delete_producto(uow, producto_id: UUID) -> None`**: Loads entity (raises `NotFoundError`). Calls `uow.productos.soft_delete(producto_id)`.

**`set_disponibilidad(uow, producto_id: UUID, data: DisponibilidadUpdate) -> ProductoRead`**: Loads entity (raises `NotFoundError`). Sets `disponible = data.disponible`. Calls `uow.productos.update(...)`.

**`get_producto_ingredientes(uow, producto_id: UUID) -> list[ProductoIngredienteRead]`**: Validates product exists (raises `NotFoundError`). Calls `uow.productos.get_ingredientes(...)`. Maps to `ProductoIngredienteRead`.

**`add_ingrediente(uow, producto_id: UUID, data: AsociarIngredienteRequest) -> ProductoIngredienteRead`**: Validates product exists (404). Validates `ingrediente_id` exists and is active (404). Calls `uow.productos.add_ingrediente(...)`. Catches `IntegrityError` → raises `ConflictError(code="PRODUCT_INGREDIENT_DUPLICATE")`.

**`remove_ingrediente(uow, producto_id: UUID, ingrediente_id: UUID) -> None`**: Validates product exists (404). Calls `uow.productos.remove_ingrediente(...)`. If returns `False` → raises `NotFoundError(code="PRODUCT_INGREDIENT_NOT_FOUND")`.

#### Scenario: create_producto with invalid categoria_id raises 404
- **WHEN** `POST /api/v1/productos` includes a `categoria_ids` entry that does not exist
- **THEN** service raises `NotFoundError(code="CATEGORY_NOT_FOUND")`
- **THEN** response is HTTP 404 RFC 7807

#### Scenario: create_producto with valid data returns ProductoRead
- **WHEN** `POST /api/v1/productos` is called with valid body and ADMIN JWT
- **THEN** service creates the product with all fields
- **THEN** response is `ProductoRead` with HTTP 201 including the assigned UUID

#### Scenario: update_producto with partial body preserves untouched fields
- **WHEN** `PATCH /api/v1/productos/{id}` is called with only `{"disponible": false}`
- **THEN** only `disponible` is updated
- **THEN** `nombre`, `precio_base`, `stock_cantidad`, category associations remain unchanged

#### Scenario: set_disponibilidad changes disponible for STOCK role
- **WHEN** `PATCH /api/v1/productos/{id}/disponibilidad` is called with STOCK JWT and `{"disponible": false}`
- **THEN** service sets `disponible = False` on the product
- **THEN** response is updated `ProductoRead` with `disponible: false`

#### Scenario: add_ingrediente with duplicate association raises 409
- **WHEN** `POST /api/v1/productos/{id}/ingredientes` is called with an `ingrediente_id` already associated
- **THEN** `IntegrityError` from the repo is caught
- **THEN** service raises `ConflictError(code="PRODUCT_INGREDIENT_DUPLICATE")`
- **THEN** response is HTTP 409 RFC 7807

#### Scenario: remove_ingrediente with non-existent association raises 404
- **WHEN** `DELETE /api/v1/productos/{id}/ingredientes/{ing_id}` is called for an association that does not exist
- **THEN** `remove_ingrediente` repo returns `False`
- **THEN** service raises `NotFoundError(code="PRODUCT_INGREDIENT_NOT_FOUND")`
- **THEN** response is HTTP 404 RFC 7807

---

### Requirement: Producto REST endpoints (9 endpoints)
The system SHALL expose 9 REST endpoints under `/api/v1/productos` registered via `productos_router` in `backend/app/api/v1/productos.py`. The router SHALL be included in `build_v1_router` with prefix `/productos` and tag `"productos"`.

#### Scenario: GET /api/v1/productos returns paginated list (public, no auth)
- **WHEN** `GET /api/v1/productos` is called without any Authorization header
- **THEN** response is HTTP 200 with body `PaginatedProductos`
- **THEN** only active products (`deleted_at IS NULL`) appear
- **THEN** response includes `items`, `total`, `page`, `size`, `pages`

#### Scenario: GET /api/v1/productos/{id} returns ProductoDetail (public)
- **WHEN** `GET /api/v1/productos/{id}` is called for an existing active product
- **THEN** response is HTTP 200 with body `ProductoDetail` including `categorias` and `ingredientes`
- **WHEN** the product does not exist or is soft-deleted
- **THEN** response is HTTP 404 RFC 7807 with `code="PRODUCT_NOT_FOUND"`

#### Scenario: POST /api/v1/productos requires ADMIN role only
- **WHEN** `POST /api/v1/productos` is called without a JWT token
- **THEN** response is HTTP 401
- **WHEN** called with STOCK JWT
- **THEN** response is HTTP 403
- **WHEN** called with CLIENT JWT
- **THEN** response is HTTP 403
- **WHEN** called with valid ADMIN JWT and valid body
- **THEN** response is HTTP 201 with `ProductoRead`

#### Scenario: PATCH /api/v1/productos/{id} requires ADMIN role only
- **WHEN** `PATCH /api/v1/productos/{id}` is called with valid ADMIN JWT and partial body
- **THEN** response is HTTP 200 with updated `ProductoRead`
- **WHEN** called with STOCK JWT
- **THEN** response is HTTP 403

#### Scenario: DELETE /api/v1/productos/{id} requires ADMIN role and returns 204
- **WHEN** `DELETE /api/v1/productos/{id}` is called with valid ADMIN JWT
- **THEN** response is HTTP 204 No Content
- **THEN** product `deleted_at` is set to current timestamp
- **WHEN** called with STOCK JWT
- **THEN** response is HTTP 403

#### Scenario: PATCH /api/v1/productos/{id}/disponibilidad accepts ADMIN or STOCK
- **WHEN** called with valid STOCK JWT and `{"disponible": false}`
- **THEN** response is HTTP 200 with `ProductoRead` having `disponible: false`
- **WHEN** called with valid ADMIN JWT and `{"disponible": true}`
- **THEN** response is HTTP 200 with `ProductoRead` having `disponible: true`
- **WHEN** called without JWT (no Authorization header)
- **THEN** response is HTTP **401** (missing_token) — evaluated BEFORE role check
- **WHEN** called with CLIENT JWT (valid token, wrong role)
- **THEN** response is HTTP **403** (forbidden) — 401 has priority over 403 in auth middleware

#### Scenario: GET /api/v1/productos/{id}/ingredientes returns ingredients (public)
- **WHEN** called without Authorization header for a product with 3 ingredients
- **THEN** response is HTTP 200 with `list[ProductoIngredienteRead]` of length 3
- **THEN** each item includes `ingrediente_id`, `nombre`, `es_alergeno`, `es_removible`
- **WHEN** the product does not exist or is soft-deleted
- **THEN** response is HTTP 404 with `code="PRODUCT_NOT_FOUND"`
- **NOTE** the service MUST call `uow.productos.get_by_id(producto_id)` before calling `get_ingredientes()`. If only `get_ingredientes()` is called on a non-existent product, it returns `[]` (empty list with HTTP 200) — which would be incorrect. The 404 guard is mandatory in `get_producto_ingredientes`.

#### Scenario: POST /api/v1/productos/{id}/ingredientes requires ADMIN
- **WHEN** called with valid ADMIN JWT and valid `AsociarIngredienteRequest`
- **THEN** response is HTTP 201 with `ProductoIngredienteRead`
- **WHEN** called with STOCK JWT
- **THEN** response is HTTP 403

#### Scenario: DELETE /api/v1/productos/{id}/ingredientes/{ing_id} requires ADMIN
- **WHEN** called with valid ADMIN JWT for an existing association
- **THEN** response is HTTP 204 No Content
- **THEN** the `ProductoIngrediente` pivot record is hard-deleted
- **WHEN** called with STOCK JWT
- **THEN** response is HTTP 403

---

### Requirement: Business rules RN-CA04 through RN-CA09 applied to Producto
The system SHALL enforce the following business rules for products:

- **RN-CA04** — `precio_base` SHALL be stored as `DECIMAL(10,2)`. Pydantic schema uses `Decimal` type. JSON serialization as string. `precio_base < 0` is rejected.
- **RN-CA05** — `stock_cantidad` SHALL be an integer `>= 0`. Rejected at Pydantic level and enforced by `CHECK` constraint.
- **RN-CA06** — A product CAN belong to multiple categories (M2M via `producto_categoria`).
- **RN-CA07** — A product CAN have multiple ingredients (M2M via `producto_ingrediente`); each ingredient has `es_alergeno` flag.
- **RN-CA09** — Soft delete SHALL set `deleted_at = NOW()`. Product SHALL NEVER be physically deleted. Pivot records are preserved (D-31).

#### Scenario: RN-CA04 — precio_base stored as DECIMAL, serialized as string
- **WHEN** `POST /api/v1/productos` creates a product with `precio_base = "19.99"` (as Decimal)
- **THEN** `GET /api/v1/productos/{id}` returns `"precio_base": "19.99"` as a JSON string
- **THEN** no float precision loss occurs

#### Scenario: RN-CA05 — stock_cantidad cannot be negative
- **WHEN** `POST /api/v1/productos` is called with `stock_cantidad = -1`
- **THEN** response is HTTP 422 (Pydantic validation error)

#### Scenario: RN-CA09 — deleted product does not appear in listing
- **WHEN** `DELETE /api/v1/productos/{id}` soft-deletes a product
- **THEN** `GET /api/v1/productos` does not include that product in `items`
- **THEN** `GET /api/v1/productos/{id}` returns HTTP 404

---

### Requirement: RFC 7807 error codes for Producto
The system SHALL return RFC 7807-compliant error responses for all product business rule violations.

| HTTP Status | `code` | Trigger |
|---|---|---|
| 401 | `missing_token` | Token ausente en endpoint protegido |
| 403 | `forbidden` | Rol insuficiente para la operación |
| 404 | `PRODUCT_NOT_FOUND` | `producto_id` no existe o está soft-deleted |
| 404 | `CATEGORY_NOT_FOUND` | UUID en `categoria_ids` no existe o está soft-deleted |
| 404 | `INGREDIENT_NOT_FOUND` | `ingrediente_id` en `AsociarIngredienteRequest` no existe |
| 404 | `PRODUCT_INGREDIENT_NOT_FOUND` | Asociación producto↔ingrediente no existe al intentar eliminarla |
| 409 | `PRODUCT_INGREDIENT_DUPLICATE` | La asociación producto↔ingrediente ya existe |
| 422 | (Pydantic) | `precio_base < 0` o `stock_cantidad < 0` |
| 422 | `INSUFFICIENT_STOCK` | `decrement_stock` devuelve None — stock insuficiente. `AppValidationError(code="INSUFFICIENT_STOCK", status_code=422)`. El request es válido; es una violación de regla de negocio (no HTTP 400 que implica request malformado). |

#### Scenario: 404 PRODUCT_NOT_FOUND matches RFC 7807 shape
- **WHEN** `GET /api/v1/productos/{non_existent_id}` is called
- **THEN** body contains `{"status": 404, "code": "PRODUCT_NOT_FOUND", "detail": "..."}`

#### Scenario: 409 PRODUCT_INGREDIENT_DUPLICATE matches RFC 7807 shape
- **WHEN** duplicate ingredient association is submitted
- **THEN** body contains `{"status": 409, "code": "PRODUCT_INGREDIENT_DUPLICATE"}`

---

### Requirement: UnitOfWork gains productos repository accessor
The system SHALL add `uow.productos: ProductoRepository` as a lazy property in `backend/app/core/uow.py`, sharing the same `AsyncSession` as all other repositories.

#### Scenario: uow.productos returns ProductoRepository instance
- **WHEN** `uow.productos` is accessed inside an `async with UnitOfWork() as uow:` block
- **THEN** the returned object is an instance of `ProductoRepository`
- **THEN** `uow.productos.session is uow.session` evaluates to `True`
