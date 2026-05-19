## Context

Change 11 (`catalog-products-management`) delivered full admin CRUD for products through `GET/POST/PATCH/DELETE /api/v1/productos`. Those endpoints were intentionally not hardened for public use — they expose `stock_cantidad`, `created_at`, `updated_at`, and are mixed with protected (ADMIN/STOCK) mutation endpoints.

This change adds a dedicated **public read surface** at `/api/v1/catalog/productos` that:
- Enforces the visibility rule `disponible=true AND deleted_at IS NULL` at every query.
- Returns public-safe DTOs that deliberately omit `stock_cantidad` (returns `tiene_stock: bool` instead).
- Requires no authentication whatsoever.
- Supports paginated listing with composable filters (category, name search, allergen exclusion).

The frontend `/catalog` route was wired as a placeholder in Change 08 (`frontend-navigation-route-guards`) inside `PublicLayout`. This change delivers the actual pages, widgets, and hooks.

---

## Goals / Non-Goals

**Goals:**
- Deliver US-018, US-019, US-023 in a single atomic change.
- Define a clean public API surface separated from the admin `/productos` prefix.
- Protect exact `stock_cantidad` from public disclosure; return only `tiene_stock: bool`.
- Provide a performant, testable, fully-typed frontend with URL-synced filters and TanStack Query caching.
- Establish the filter composition pattern for future catalog changes (price range, ordering, etc.).
- Provide a public allergen ingredient list endpoint to support the frontend AllergenosExclusion widget without requiring authentication.

**Non-Goals:**
- Admin CRUD for products (Change 11).
- Cart, checkout, or order placement (future changes).
- Authenticated user features (favorites, purchase history).
- Price filtering, advanced sorting (deferred to Change 16+).
- Rate limiting on public endpoints (deferred to security hardening change).

---

## Decisions

### Decision 1: Separate URL prefix `/catalog/productos` instead of reusing `/productos`

**Choice**: New router at `backend/app/api/v1/catalog.py` with prefix `/catalog`, resulting in `/api/v1/catalog/productos`.

**Rationale**: The existing `/api/v1/productos` prefix is owned by the admin router (Change 11). Mixing public and admin endpoints under the same prefix would:
1. Force the public listing endpoint to share the router with protected mutation routes.
2. Create confusion about which endpoints require auth.
3. Complicate the OpenAPI schema (public vs. admin tag grouping).

Separating into `/catalog/productos` gives a clear, stable public surface that can be cached, CDN-fronted, or rate-limited independently in future changes.

**Impact on spec**: `backend-api-v1-router` spec must be modified to include `catalog_router` mounted at prefix `/catalog`.

---

### Decision 2: Completely separate public Pydantic schemas (no reuse of `ProductoRead`/`ProductoDetail`)

**Choice**: New file `backend/app/schemas/catalog_public.py` with `ProductoPublicoRead`, `ProductoPublicoDetalleRead`, `CategoriaPublicaRead`, `IngredientePublicoRead`.

**Rationale**: Reusing `ProductoRead` from Change 11 would expose `stock_cantidad`. Even with `exclude` in `model_dump()`, the field would still appear in OpenAPI schema documentation, creating confusion and a potential future leakage surface. New schemas guarantee by type-system enforcement that `stock_cantidad` is never present in a public response.

**Field mapping**:

```
ProductoPublicoRead:
  id: UUID
  nombre: str
  descripcion: str | None
  imagen_url: str | None
  precio_base: Decimal → serialized as string (@field_serializer)
  disponible: bool
  tiene_stock: bool          ← replaces stock_cantidad
  model_config = ConfigDict(from_attributes=True)
  # NOT included: stock_cantidad, created_at, updated_at, deleted_at

ProductoPublicoDetalleRead(ProductoPublicoRead):
  categorias: list[CategoriaPublicaRead]
  ingredientes: list[IngredientePublicoRead]

CategoriaPublicaRead:
  id: UUID
  nombre: str
  model_config = ConfigDict(from_attributes=True)

IngredientePublicoRead:
  ingrediente_id: UUID
  nombre: str
  es_alergeno: bool
  # NOT included: es_removible (internal operational detail)
  model_config = ConfigDict(from_attributes=True)
```

Note: `IngredientePublicoRead` omits `es_removible` (operational/admin detail). If a future US requires showing removable ingredients in public view, this can be added via a delta spec.

Note: `ingrediente_id` (not `id`) is used deliberately to avoid ambiguity when this schema appears nested inside `ProductoPublicoDetalleRead` — where `id` could be confused with the product's `id`. The mapping in `_to_publico_detalle()` must explicitly set `ingrediente_id=pivot.ingrediente.id` (i.e., the PK of the `Ingrediente` entity, accessed through the pivot's loaded relation).

> **⚠️ ORM Instantiation Restriction**
> `ProductoPublicoRead` and `IngredientePublicoRead` CANNOT be instantiated via `model_validate(orm_object)` directly.
> Reasons:
> - `tiene_stock: bool` is derived from `stock_cantidad > 0` — the field `tiene_stock` does NOT exist on the `Producto` ORM model.
> - `ingrediente_id` in `IngredientePublicoRead` must be mapped from the joined `Ingrediente.id` (not auto-resolved via `from_attributes`).
>
> **ALWAYS use the service helper methods:**
> - `_to_publico_read(producto: Producto) -> ProductoPublicoRead`
> - `_to_publico_detalle(producto: Producto) -> ProductoPublicoDetalleRead`
>
> `ConfigDict(from_attributes=True)` is kept for compatibility with other field mappings — it does NOT mean the schema can be used as a drop-in ORM serializer.

---

### Decision 3: `excluir_alergenos` as comma-separated string query param (single param)

**Choice**: `excluir_alergenos: str | None = Query(default=None)` — comma-separated ingredient IDs (integers), parsed and validated in the service layer.

**Rationale vs. repeated param**: FastAPI supports both `?excluir_alergenos=1&excluir_alergenos=2` (list param) and `?excluir_alergenos=1,2` (comma-separated string). The comma-separated string is chosen because:
1. It maps cleanly to URL search params in React (`URLSearchParams.set('excluir_alergenos', ids.join(','))`).
2. It produces a single, stable query key fragment for TanStack Query caching (e.g., `"1,2"` vs `[1, 2]`).
3. It is easier to share/copy as a URL.

Validation: the service splits on `,`, strips whitespace, rejects non-integer and non-positive values (422), deduplicates, and caps at 20 items max.

Edge case: if `excluir_alergenos` is an empty string (e.g., `?excluir_alergenos=`), it SHALL be treated as `None` (no filter applied). Validation: `if not value or not value.strip(): return early with no filter`.

---

### Decision 4: Query params model as `CatalogProductosQuery` Pydantic model

**Choice**: Define a `CatalogProductosQuery(BaseModel)` in `backend/app/schemas/catalog_public.py` for use with FastAPI's dependency injection (`Depends(CatalogProductosQuery)`).

```python
class CatalogProductosQuery(BaseModel):
    page: int = Field(default=1, ge=1)
    size: int = Field(default=20, ge=1, le=100)
    categoria_id: UUID | None = None
    q: str | None = Field(default=None, max_length=100)
    excluir_alergenos: str | None = Field(default=None, description="Comma-separated ingrediente IDs")
    ordenar: str | None = Field(default=None, pattern="^-?(nombre|precio)$")
```

This approach centralizes validation, produces a clean OpenAPI schema, and lets the router stay thin.

---

### Decision 5: `_apply_public_visibility(query)` private method on repository

**Choice**: Add private method `_apply_public_visibility(stmt)` to `ProductoRepository` that appends `WHERE disponible=true AND deleted_at IS NULL`. Both `list_public()` and `get_public_by_id()` call this.

**Rationale**: Centralizes the visibility rule in one place. If the rule ever changes (e.g., adding a `publicado_en` datetime column), only this one method needs to be updated.

---

### Decision 6: `CatalogPublicService` as a new, separate service

**Choice**: New file `backend/app/services/catalog_public.py` with `CatalogPublicService`.

**Rationale**: The existing `ProductoService` (Change 11) contains admin logic (create, update, delete, stock decrement, etc.). Mixing public read logic into it would couple two very different concerns. `CatalogPublicService` is intentionally minimal and has no mutation methods.

---

### Decision 7: TanStack Query cache strategy for catalog

**Choice**:
- `staleTime: 30_000` (30 s) — product data changes infrequently for public users.
- `gcTime: 300_000` (5 min) — keep data in memory for fast back-navigation.
- `placeholderData: keepPreviousData` — show previous page data while next page is loading (TQ5 idiom for pagination).
- `queryKey: ['catalog', 'products', filters]` for list; `['catalog', 'products', id]` for detail.
- No automatic invalidation within public browsing — this is a read-only surface.
- Document hook for future Change 16 (cart/checkout): invalidate `['catalog', 'products']` when cart checkout completes to ensure stock status is fresh.

---

### Decision 8: Filter-to-URL sync with `useCatalogFilters()`

**Choice**: A single `useCatalogFilters()` hook in `features/catalog/filters/` that reads/writes to `useSearchParams`. Changing a filter always resets `page` to 1. The `q` field is debounced 300 ms inside the hook using `useDebounce(value, 300)` from `shared/hooks/useDebounce.ts`.

**Rationale**: URL-synced filters enable bookmark, share, and browser-back support for free. Debouncing prevents a query on every keystroke.

---

## API Contracts

### `GET /api/v1/catalog/productos`

No authentication required.

**Query parameters** (validated via `CatalogProductosQuery`):

| Param | Type | Default | Constraint |
|---|---|---|---|
| `page` | int | 1 | ≥ 1 |
| `size` | int | 20 | 1–100 |
| `categoria_id` | UUID | null | must exist (otherwise 0 results, not 422) |
| `q` | string | null | max 100 chars |
| `excluir_alergenos` | string | null | comma-sep ints, max 20, each ≥ 1 |
| `ordenar` | string | null | pattern `^-?(nombre\|precio)$` |

**Response** `HTTP 200 PaginatedCatalogResponse`:
```json
{
  "items": [ProductoPublicoRead, ...],
  "total": 42,
  "page": 1,
  "size": 20,
  "pages": 3
}
```

Filter composition is AND semantics:
- `disponible=true AND deleted_at IS NULL` — always applied (base visibility).
- `categoria_id` — inner join with `producto_categoria` WHERE `categoria_id = :id`.
- `q` — `nombre ILIKE '%' || :q || '%'`.
- `excluir_alergenos` — `NOT EXISTS (SELECT 1 FROM producto_ingrediente pi WHERE pi.producto_id = p.id AND pi.ingrediente_id IN (:ids))`.
- `ordenar` — maps `nombre`→`ASC nombre`, `-nombre`→`DESC nombre`, `precio`→`ASC precio_base`, `-precio`→`DESC precio_base`. Default ordering is `nombre ASC` — alphabetical, user-friendly, predictable for catalog browsing. Pagination drift on new insertions is acceptable at MVP scale.

---

### `GET /api/v1/catalog/productos/{id}`

No authentication required.

**Response** `HTTP 200 ProductoPublicoDetalleRead`:
```json
{
  "id": "uuid",
  "nombre": "Pizza Margherita",
  "descripcion": "...",
  "imagen_url": "https://...",
  "precio_base": "12.50",
  "disponible": true,
  "tiene_stock": true,
  "categorias": [{"id": "uuid", "nombre": "Pizzas"}],
  "ingredientes": [
    {"ingrediente_id": "uuid", "nombre": "Gluten", "es_alergeno": true},
    {"ingrediente_id": "uuid", "nombre": "Tomate", "es_alergeno": false}
  ]
}
```

**Error cases**:
- Product not found OR `deleted_at IS NOT NULL` OR `disponible=false` → `HTTP 404` `code="PRODUCT_NOT_FOUND"`.
- `id` is not a valid UUID → `HTTP 422` (FastAPI path param validation).

---

### `GET /api/v1/catalog/ingredientes-alergenos`

No authentication required.

**Response** `HTTP 200 IngredienteAlergenicoListResponse`:
```json
{
  "items": [
    {"ingrediente_id": "uuid", "nombre": "Gluten", "es_alergeno": true},
    {"ingrediente_id": "uuid", "nombre": "Lactosa", "es_alergeno": true}
  ],
  "total": 2
}
```

Returns all active ingredients where `es_alergeno=true AND deleted_at IS NULL`, ordered by `nombre ASC`. Used exclusively by the frontend `AllergenosExclusion` widget to populate the allergen filter panel for public users.

This endpoint is introduced in this change because `GET /api/v1/ingredientes` requires ADMIN/STOCK role (Change 10, `backend-ingredientes-management` spec). A dedicated public read endpoint avoids modifying the admin ingredients surface.

---

## Repository Layer

New methods added to `ProductoRepository` in `backend/app/repositories/producto.py`:

```python
def _apply_public_visibility(self, stmt: Select) -> Select:
    """Appends WHERE disponible=true AND deleted_at IS NULL."""

async def list_public(
    self,
    filters: CatalogProductosQuery,
) -> tuple[list[Producto], int]:
    """Returns (items, total) applying public visibility + all composable filters."""

async def get_public_by_id(self, producto_id: UUID) -> Producto | None:
    """Returns product with selectinload for categorias+ingredientes,
       or None if not found / disponible=false / soft-deleted."""
```

`list_public` does NOT eager-load categorias or ingredientes — `ProductoPublicoRead` (the list response schema) does not include relations. The method fires exactly 2 queries: 1 COUNT with the same WHERE conditions, and 1 SELECT with OFFSET/LIMIT. Relations are only loaded in `get_public_by_id()` for the detail response.

**New method added to `IngredienteRepository`** (or directly via raw query in `CatalogPublicService` using existing UoW session):

```python
async def list_public_alergenos(self) -> list[Ingrediente]:
    """Returns active allergen ingredients ordered by nombre ASC."""
```

Query: `SELECT * FROM ingrediente WHERE es_alergeno=true AND deleted_at IS NULL ORDER BY nombre ASC`.

---

## Service Layer

`CatalogPublicService` in `backend/app/services/catalog_public.py`:

```python
async def list_catalog(
    self, uow: UnitOfWork, filters: CatalogProductosQuery
) -> Page[ProductoPublicoRead]:
    items, total = await uow.productos.list_public(filters)
    pages = ceil(total / filters.size)
    public_items = [self._to_publico_read(p) for p in items]
    return Page(items=public_items, total=total, page=filters.page, size=filters.size, pages=pages)

async def get_catalog_detail(
    self, uow: UnitOfWork, producto_id: UUID
) -> ProductoPublicoDetalleRead:
    product = await uow.productos.get_public_by_id(producto_id)
    if product is None:
        raise NotFoundError(code="PRODUCT_NOT_FOUND")
    return self._to_publico_detalle(product)

def _to_publico_read(self, p: Producto) -> ProductoPublicoRead:
    """Maps Producto to ProductoPublicoRead. tiene_stock = p.stock_cantidad > 0."""

def _to_publico_detalle(self, p: Producto) -> ProductoPublicoDetalleRead:
    """Maps Producto (with loaded relations) to ProductoPublicoDetalleRead."""

async def list_alergenos(self, uow: UnitOfWork) -> IngredienteAlergenicoListResponse:
    """Returns all active allergen ingredients for public display."""
    items = await uow.ingredientes.list_public_alergenos()
    return IngredienteAlergenicoListResponse(
        items=[IngredientePublicoRead(ingrediente_id=i.id, nombre=i.nombre, es_alergeno=True) for i in items],
        total=len(items)
    )
```

---

## Performance

**Existing indices (from Change 11 migrations — verify presence)**:
- `idx_producto_nombre` (btree on `nombre`) — may exist; ILIKE on leading wildcard `'%q%'` does NOT use a btree index. Trade-off: acceptable for datasets < 10 000 products; GIN/trigram is the right solution for scale.

**New indices (via Alembic migration in this change)**:

1. `idx_productos_disponible_deleted_at` — partial index (required):
   Dramatically reduces I/O for all public catalog queries by pre-filtering the eligible set.

2. `idx_productos_nombre_lower` (optional, documented trade-off):
   Helps with case-insensitive equality/prefix searches but NOT leading-wildcard ILIKE. Document: "For production scale, replace with `pg_trgm` GIN index on `nombre`."

**Implementation note — Alembic transaction requirement**:
`CREATE INDEX CONCURRENTLY` cannot run inside a PostgreSQL transaction block. Alembic wraps migrations in transactions by default. The migration MUST use `autocommit_block()`:

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

Note: `idx_productos_nombre_lower` (the optional btree index) does NOT require `CONCURRENTLY` — it is included in the same `autocommit_block` for convenience.

**Eager-load strategy for detail**:
- 3 queries max: 1 SELECT producto + 1 selectinload producto_categorias (+ pivot back-ref categoria auto-selectin) + 1 selectinload producto_ingredientes (+ pivot back-ref ingrediente auto-selectin).
- `lazy="noload"` on `Producto.producto_categorias/producto_ingredientes` forces explicit `selectinload` — no accidental N+1.

---

## Frontend Architecture

### Entity Layer (FSD: `entities/products/`)

**File**: `frontend/src/entities/products/api/productoFetchers.ts` — extend with:
```typescript
// GET /api/v1/catalog/productos
export function fetchCatalogProductos(filters: CatalogFilters): Promise<PaginatedCatalogProductos>
// GET /api/v1/catalog/productos/{id}
export function fetchCatalogProductoDetalle(id: string): Promise<ProductoPublicoDetalleRead>
```

**File**: `frontend/src/entities/products/model/types.ts` — extend with:
```typescript
export interface ProductoPublicoRead {
  id: string
  nombre: string
  descripcion: string | null
  imagen_url: string | null
  precio_base: string         // Decimal as string
  disponible: boolean
  tiene_stock: boolean        // NEVER stock_cantidad
}

export interface IngredientePublicoRead {
  ingrediente_id: string
  nombre: string
  es_alergeno: boolean
}

export interface ProductoPublicoDetalleRead extends ProductoPublicoRead {
  categorias: CategoriaPublicaRead[]
  ingredientes: IngredientePublicoRead[]
}

export interface CategoriaPublicaRead {
  id: string
  nombre: string
}

export interface CatalogFilters {
  page?: number
  size?: number
  categoria_id?: string | null
  q?: string | null
  excluir_alergenos?: string | null  // comma-separated IDs
  ordenar?: string | null
}

export interface PaginatedCatalogProductos {
  items: ProductoPublicoRead[]
  total: number
  page: number
  size: number
  pages: number
}
```

**File**: `frontend/src/entities/products/model/useCatalogProducts.ts` — new hooks:
```typescript
export function useCatalogProducts(filters: CatalogFilters): UseQueryResult<PaginatedCatalogProductos>
export function useCatalogProduct(id: string): UseQueryResult<ProductoPublicoDetalleRead>
```
Query key factory extension:
```typescript
catalogLists: () => ['catalog', 'products', 'list'] as const,
catalogList:  (f: CatalogFilters) => ['catalog', 'products', 'list', f] as const,
catalogDetail:(id: string) => ['catalog', 'products', 'detail', id] as const,
```
Cache config: `staleTime: 30_000`, `gcTime: 300_000`, `placeholderData: keepPreviousData`.

Endpoint constant: `CATALOG_PRODUCTOS = '/api/v1/catalog/productos'` added to `shared/api/endpoints.ts`.

---

### Features Layer (FSD: `features/catalog/`)

**`features/catalog/filters/`**
- `useCatalogFilters.ts` — reads/writes `useSearchParams`; exposes `filters: CatalogFilters`, `setFilter(key, value)`, `resetFilters()`. Any filter change resets `page` to 1.
- Debounce: `q` value is debounced 300 ms before being written to `filters.q` (uses `useDebounce` from `shared/hooks`).

**`features/catalog/product-list/`**
- `ProductGrid.tsx` — renders `ProductoPublicoRead[]` as responsive grid. Accepts `isLoading` prop to render skeleton cards.
- `ProductCard.tsx` — card component: image, nombre, precio_base, disponible badge, `tiene_stock` indicator (green dot / "Agotado" label).
- `EmptyState.tsx` — displayed when `items.length === 0` and not loading.
- `ErrorState.tsx` — displayed on network error.

**`features/catalog/product-detail/`**
- `ProductDetailView.tsx` — two-column layout (md+); left: image; right: nombre, precio, descripcion, categorias tags, ingredientes list with allergen badges.
- `AllergenBadge.tsx` — visual indicator for allergen ingredients.

---

### Widgets Layer (FSD: `widgets/catalog/`)

**`CatalogFilters/`**
- `CategoriaSelect.tsx` — uses existing `useCategorias` hook (from `entities/categories`) to populate a `<select>`.
- `SearchInput.tsx` — text input with `aria-label="Buscar productos"`, controlled by `useCatalogFilters` debounced `q`.
- `AllergenosExclusion.tsx` — multi-select toggle using `useCatalogAlergenos()` hook (from `entities/products/`) which calls `GET /api/v1/catalog/ingredientes-alergenos`. This avoids using the admin-only `GET /api/v1/ingredientes` endpoint for public users. Serializes selected IDs to comma-separated string for `excluir_alergenos` param.
- `CatalogFilters/index.tsx` — composes the three above.

---

### Pages Layer (FSD: `pages/catalog/`)

**`CatalogPage.tsx`**
- Consumes `useCatalogFilters()` + `useCatalogProducts(filters)`.
- Renders: `CatalogFilters` widget + `ProductGrid` feature + `PaginationControls` shared component.
- Route: `/catalog` (public, under `PublicLayout` from Change 08).

Edge case: when `total=0`, `pages=ceil(0/size)=0`. `PaginationControls` MUST NOT be rendered when `pages <= 1` (not just `pages > 1`) — consistent with: no pagination needed when there's only one page or no pages at all.

**`ProductDetailPage.tsx`**
- Reads `:id` from route params.
- Consumes `useCatalogProduct(id)`.
- Renders: `ProductDetailView` feature.
- On 404 error → renders `ErrorPage` (or inline not-found component from `shared`). To check for 404, use `error?.response?.status === 404` (AxiosError pattern from Change 05 interceptor) — NOT `error.status` directly.
- Route: `/catalog/:id` (public, under `PublicLayout`).

---

### Shared

**`shared/hooks/useDebounce.ts`** — create if absent:
```typescript
export function useDebounce<T>(value: T, delayMs: number): T
```

**`shared/ui/PaginationControls.tsx`** — create if absent:
- Props: `page`, `pages`, `onPageChange`.
- Renders: prev button, numeric page buttons (up to 7, with ellipsis), next button.
- Accessibility: `aria-label="Paginación"` on nav, `aria-current="page"` on active page button, keyboard-navigable.

---

### Responsive Layout

| Breakpoint | Grid columns |
|---|---|
| Default (mobile) | 1 column |
| sm (640 px+) | 2 columns |
| md (768 px+) | 3 columns |
| lg (1024 px+) | 4 columns |

Tailwind classes: `grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4`.

Product detail page: single column on mobile, `md:grid md:grid-cols-2` on medium+.

---

### Accessibility (A11y)

- Product images: `alt={producto.nombre}` — never empty `alt=""` (images are content, not decorative).
- Search input: `aria-label="Buscar productos por nombre"`.
- Category select: `aria-label="Filtrar por categoría"`.
- Allergen exclusion: `role="group"` with `aria-labelledby` pointing to "Excluir alérgenos" heading.
- Pagination nav: `<nav aria-label="Paginación del catálogo">`, active page button `aria-current="page"`.
- Skeleton loaders: `aria-busy="true"` on the loading container; `role="status"` with visually-hidden "Cargando..." text.
- On filter change, focus management: focus stays on the filter control that triggered the change (no unwanted focus jumps).
- Semantic landmarks: `<main>` wrapping catalog content, `<aside>` or `<section>` for filters.

---

## Risks / Trade-offs

| Risk | Mitigation |
|---|---|
| **N+1 on catalog list** — if selectinloads are missed, listing 20 products could fire 40+ queries | Enforced by `lazy="noload"` on `Producto.producto_categorias/ingredientes` + explicit `selectinload` in `list_public()`. Covered by integration test asserting query count. |
| **ILIKE on large datasets** — `'%q%'` leading-wildcard prevents btree index use | Add `idx_productos_nombre_lower` as a btree hint; document `pg_trgm` GIN as the production-scale solution. Acceptable for MVP scale (< 10 k products). |
| **Admin/public schema drift** — `ProductoRead` (Change 11) gains a new field; public schema silently lags | Spec note: any change to `backend-products-management` schemas MUST be reviewed against `backend-catalog-public-browsing` schemas. Mitigated by separate schema file and separate spec. |
| **URL-state desync** — filter in component state diverges from URL | `useCatalogFilters()` is the single source of truth for filters; URL is the authoritative store. No local useState for filters. |
| **Debounce + pagination interaction** — user types in search while on page 5; query fires with stale page=5 | `setFilter('q', value)` in `useCatalogFilters` resets page to 1 atomically. Documented and tested. |
| **`tiene_stock` stale after stock decrement** — admin decrements stock, public user still sees `tiene_stock: true` | `staleTime: 30_000` means at most 30 s of stale data. Acceptable for public browsing; no real-time requirement in this change. |
| **Allergen exclusion with wrong IDs** — client sends ingredient IDs that are not allergens | The SQL filter uses only the IDs in `NOT EXISTS`; if the IDs don't match any allergen, the filter has no effect. Documented as expected behavior — filtering is by ingredient ID, not by `es_alergeno` flag. |

---

## Migration Plan

1. **Backend**:
   1. Add schemas, repository methods, service, router (no DB changes yet). Add `list_public_alergenos()` to `IngredienteRepository` (or inline in service). Add `GET /catalog/ingredientes-alergenos` to `catalog_router`. Add `IngredienteAlergenicoListResponse` schema to `catalog_public.py`.
   2. Add Alembic migration for `idx_productos_disponible_deleted_at` (partial index) — run `alembic upgrade head`. CRITICAL: migration MUST use `with op.get_context().autocommit_block():` for `CREATE INDEX CONCURRENTLY`.
   3. Optional: add `idx_productos_nombre_lower` in the same migration (within same `autocommit_block`).
   4. Include catalog router in `build_v1_router`.

2. **Frontend**:
   1. Add public types, fetchers, hooks to `entities/products/`.
   2. Add `useDebounce` and `PaginationControls` to `shared/`.
   3. Implement features (`product-list`, `product-detail`, `filters`).
   4. Implement `CatalogFilters` widget.
   5. Implement `CatalogPage` and `ProductDetailPage`; register `/catalog/:id` sub-route.

3. **Rollback**: the index creation uses `CREATE INDEX CONCURRENTLY IF NOT EXISTS` — safe to run on live DB. Rollback migration drops the index. Router inclusion can be reverted by removing the include statement. No data migrations involved.

---

## Open Questions

~~1. **Ordering default** [RESOLVED — Decision D-OQ-1]~~
**Decision**: `nombre ASC`. User-friendly alphabetical ordering for public catalog. Clients wishing a different order can use the `ordenar` query param. Pagination drift on new insertions is inherent to any mutable dataset and acceptable at MVP scale (< 10 k products). The `id ASC` reference in the API Contracts section has been corrected to match this decision.

~~2. **`excluir_alergenos` max items cap** [RESOLVED — Decision D-OQ-2]~~
**Decision**: Cap=20 items. Sufficient for all known allergen categories. Easy to raise in a future delta spec if needed.

~~3. **`categoria_id` inexistente** [RESOLVED — Decision D-OQ-3]~~
**Decision**: Returns 0 results (not 422). Avoids exposing internal category UUID existence as an oracle; consistent with principle of least surprise for public consumers.
