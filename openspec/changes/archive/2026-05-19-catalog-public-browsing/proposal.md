## Why

Food Store's product catalog exists in the backend (Change 11) but is only exposed through admin endpoints — public users have no browsable, filterable catalog experience. Sprint 3 (Catálogo II) requires delivering read-only public access so that end users can discover products, filter by category, search by name, and exclude allergens before placing an order.

## What Changes

- **NEW** public catalog listing endpoint `GET /api/v1/catalog/productos` — paginated, filterable, no auth required.
- **NEW** public product detail endpoint `GET /api/v1/catalog/productos/{id}` — includes categories, ingredients, allergen flags; no auth required.
- **NEW** `CatalogPublicService` orchestrating public visibility rules (`disponible=true AND deleted_at IS NULL`).
- **NEW** `list_public()` and `get_public_by_id()` methods on `ProductoRepository` — separate from admin query paths.
- **NEW** Public-safe Pydantic schemas: `ProductoPublicoRead`, `ProductoPublicoDetalleRead`, `CategoriaPublicaRead`, `IngredientePublicoRead` — NEVER expose `stock_cantidad` (returns `tiene_stock: bool` instead).
- **NEW** Optional Alembic migration adding a partial index `idx_productos_disponible_deleted_at` on `(disponible, deleted_at)` WHERE `disponible=true AND deleted_at IS NULL` to support catalog queries efficiently.
- **NEW** public allergen ingredient list endpoint `GET /api/v1/catalog/ingredientes-alergenos` — returns only active allergen ingredients for the frontend filter widget; no auth required. Added because `GET /api/v1/ingredientes` requires ADMIN/STOCK role (Change 10).
- **NEW** Frontend `CatalogPage` and `ProductDetailPage` under `/catalog` public route (placeholder wired in Change 08 — now implemented).
- **NEW** Frontend `CatalogFilters` widget with category select, name search (debounced 300 ms), and allergen multi-select exclusion toggle.
- **NEW** Frontend TanStack Query hooks `useCatalogProducts(filters)` and `useCatalogProduct(id)` with stale-while-revalidate caching.
- **NEW** `useCatalogFilters()` hook syncing filters to URL search params.
- **MODIFIED** `backend-api-v1-router` — add public catalog router mounted at `/catalog`.
- **MODIFIED** `frontend-products-entity` — add public fetchers, public TS types, and catalog query hooks.

## Capabilities

### New Capabilities

- `backend-catalog-public-browsing`: Public-facing backend API — visibility rules, public schemas, public repository methods, public service, catalog router, performance indices. Public allergen list endpoint for frontend filter widget.
- `frontend-catalog-public`: Public catalog UI — CatalogPage, ProductDetailPage, CatalogFilters widget, URL-sync filters hook, pagination component, skeleton/empty/error states, a11y, responsive grid.

### Modified Capabilities

- `backend-api-v1-router`: Add the new catalog router (`catalog_router`) mounted at `/catalog` inside `build_v1_router`.
- `frontend-products-entity`: Add public Axios fetchers (`fetchCatalogProductos`, `fetchCatalogProductoDetalle`), public TS types (`ProductoPublicoRead`, `ProductoPublicoDetalleRead`, `CatalogFilters`), and public query hooks (`useCatalogProducts`, `useCatalogProduct`).

## Impact

**Backend**
- `backend/app/api/v1/catalog.py` — new router file (public endpoints); also includes `GET /catalog/ingredientes-alergenos` endpoint.
- `backend/app/services/catalog_public.py` — new service file.
- `backend/app/repositories/producto.py` — extend with `list_public()` and `get_public_by_id()`.
- `backend/app/schemas/catalog_public.py` — new schema file with public DTOs; also includes `IngredienteAlergenicoListResponse`.
- `backend/app/core/uow.py` — no changes needed (re-uses existing `productos` repo property).
- `backend/app/api/v1/router.py` — include new catalog router.
- `backend/alembic/versions/` — new migration for partial index (conditional on absence in DB).

**Frontend**
- `frontend/src/entities/products/api/productoFetchers.ts` — add public fetchers.
- `frontend/src/entities/products/model/types.ts` — add public types.
- `frontend/src/entities/products/model/useCatalogProducts.ts` — add public hooks.
- `frontend/src/entities/products/index.ts` — extend barrel exports.
- `frontend/src/pages/catalog/CatalogPage.tsx` — new page.
- `frontend/src/pages/catalog/ProductDetailPage.tsx` — new page.
- `frontend/src/widgets/catalog/CatalogFilters/` — new widget.
- `frontend/src/features/catalog/product-list/` — new feature.
- `frontend/src/features/catalog/product-detail/` — new feature.
- `frontend/src/features/catalog/filters/` — new feature.
- `frontend/src/shared/hooks/useDebounce.ts` — new shared hook (if absent).
- `frontend/src/shared/api/endpoints.ts` — add `CATALOG` endpoint constant.

**No changes to**: auth system, cart store, admin management endpoints, `Producto`/`Categoria`/`Ingrediente` SQLModel definitions, existing admin schemas.

## User Stories Addressed

| US | Title | Acceptance |
|----|-------|------------|
| US-018 | Listar productos público | Paginated list filtered `disponible=true AND deleted_at IS NULL`; supports `categoria_id`, `q`, `excluir_alergenos`; returns `{ items, total, page, size, pages }` |
| US-019 | Detalle producto público | Returns product with categories and ingredients; stock shown as boolean `tiene_stock` (never exact `stock_cantidad`); 404 on `disponible=false` or soft-deleted |
| US-023 | Filtrar/excluir por alérgenos | `excluir_alergenos` query param (comma-separated ingrediente IDs) excludes products that contain any of the specified allergen ingredients; only applied when param is provided |

## Out of Scope

- **Cart / checkout** — handled in a future change.
- **Admin CRUD** — fully covered in Change 11 (`catalog-products-management`).
- **Authentication design** — public endpoints are openly accessible; no JWT, no role check.
- **Order placement or payment** — unrelated to catalog browsing.
- **Stock management** (increment/decrement stock) — Change 11 / STOCK role only.
- **Product creation, update, or deletion** — admin surface only (Change 11).
- **Wishlist or favorites** — not in scope for this sprint.
- **Price filtering or sorting beyond basic `ordenar` hint** — deferred to a future change.

## Dependencies

- **Change 11 — `catalog-products-management`** (archived 2026-05-19): Provides `Producto`, `ProductoCategoria`, `ProductoIngrediente` SQLModel tables, `ProductoRepository`, `UnitOfWork.productos`, admin schemas, and all existing migrations. This change builds on top without modifying any of those.
- **Change 08 — `frontend-navigation-route-guards`** (archived 2026-05-18): Provides the `PublicLayout` and `/catalog` route placeholder in the React Router tree. This change replaces that placeholder with real pages.

## Acceptance Criteria

1. `GET /api/v1/catalog/productos` without an Authorization header returns HTTP 200 with body `{ items: [...], total: N, page: 1, size: 20, pages: P }` containing only products where `disponible=true AND deleted_at IS NULL`.
2. `GET /api/v1/catalog/productos?categoria_id=<uuid>` returns only products belonging to that category.
3. `GET /api/v1/catalog/productos?q=pizza` returns only products whose `nombre ILIKE '%pizza%'` (case-insensitive).
4. `GET /api/v1/catalog/productos?excluir_alergenos=1,2` returns only products that do NOT contain any ingredient with `ingrediente_id IN (1, 2)` and `es_alergeno=true`.
5. `GET /api/v1/catalog/productos/{id}` for a `disponible=true, deleted_at=NULL` product returns HTTP 200 with `categorias[]`, `ingredientes[]` (including `es_alergeno` per ingredient), and a boolean `tiene_stock` — never `stock_cantidad`.
6. `GET /api/v1/catalog/productos/{id}` for a product with `disponible=false` OR `deleted_at IS NOT NULL` returns HTTP 404 RFC 7807 with `code="PRODUCT_NOT_FOUND"`.
7. The response body for any catalog endpoint NEVER includes `stock_cantidad`, `created_at`, `updated_at`, or `deleted_at`.
8. Frontend `/catalog` renders a responsive product grid (1 col mobile / 2 sm / 3 md / 4 lg) with skeleton loaders during fetch, empty state when no products match filters, and error state on network failure.
9. Frontend filter search input debounces 300 ms before triggering a new query; changing any filter resets page to 1.
10. Frontend pagination component shows numeric pages and prev/next; current page has `aria-current="page"`.
11. Product images use `alt={producto.nombre}`; filter inputs have `aria-label`; page has proper semantic landmarks.
12. All new backend endpoints return RFC 7807 error shapes on 404 and 422.
13. `GET /api/v1/catalog/ingredientes-alergenos` without an Authorization header returns HTTP 200 with `{ items: [...], total: N }` containing only ingredients where `es_alergeno=true AND deleted_at IS NULL`.

## Risks

- **Stock field leakage**: If a developer accidentally reuses `ProductoRead` or `ProductoDetail` (admin schema from Change 11) for public endpoints, `stock_cantidad` will be exposed. Mitigated by defining completely separate public schemas and enforcing via spec.
- **Admin/public schema drift**: As the admin `Producto` schema evolves (e.g., new fields), the public schema must be reviewed and explicitly kept in sync. Mitigated by specifying drift review as a recurring task item for schema changes.
- **ILIKE performance degradation**: On large datasets, `nombre ILIKE '%q%'` without a GIN/trigram index will degrade to sequential scan. Mitigated by recommending `idx_productos_nombre_trgm` (pg_trgm extension) and documenting the trade-off.
- **Filter URL desync**: If filters are stored in state and not in URL params, browser back/refresh loses the filter state. Mitigated by `useCatalogFilters()` hook that bidirectionally syncs filters to `useSearchParams`.

## Assumptions

1. Change 11's `Producto`, `ProductoCategoria`, and `ProductoIngrediente` SQLModel classes are stable and will not be modified in this sprint.
2. The DB seed from Change 03 has at least 10 products with varied categories and allergen ingredients for meaningful testing.
3. The `backend-pagination-schema` spec (generic `Page[T]`) is already in the codebase — public catalog reuses this schema without modification.
4. The `/catalog` route is already registered in the React Router tree (Change 08) — this change only replaces the placeholder component with real pages.
5. `pg_trgm` extension availability is not guaranteed in all environments; the trigram index is therefore optional and documented as a performance enhancement, not a hard requirement.
6. Public endpoints do not require rate limiting in this change — deferred to a future security hardening change.
