## 1. Backend — Public Schemas

- [x] 1.1 Create `backend/app/schemas/catalog_public.py` with `CatalogProductosQuery`, `ProductoPublicoRead` (with `tiene_stock: bool`, NO `stock_cantidad`), `CategoriaPublicaRead`, `IngredientePublicoRead`, `ProductoPublicoDetalleRead`, `PaginatedCatalogProductos`
- [x] 1.2 Add `@field_serializer` for `precio_base` on `ProductoPublicoRead` (Decimal → string), following the same pattern as `ProductoRead` in `backend/app/schemas/producto.py`
- [x] 1.3 Write unit tests in `backend/tests/unit/test_catalog_public_schemas.py` verifying: `tiene_stock` is True when `stock_cantidad > 0`, False when 0; `stock_cantidad` is NOT present in JSON output; `precio_base` serializes as string; `CatalogProductosQuery` rejects `size > 100`, `q` > 100 chars, invalid `ordenar` pattern
- [x] 1.4 Add `IngredienteAlergenicoListResponse(BaseModel)` to `backend/app/schemas/catalog_public.py`: `items: list[IngredientePublicoRead]`, `total: int`

## 2. Backend — Repository Public Methods

- [x] 2.1 Add `_apply_public_visibility(stmt)` private method to `ProductoRepository` in `backend/app/repositories/producto.py` (WHERE `disponible = true AND deleted_at IS NULL`)
- [x] 2.2 Add `list_public(filters: CatalogProductosQuery) -> tuple[list[Producto], int]` to `ProductoRepository`: applies visibility, categoria_id join, ILIKE on q, NOT EXISTS for excluir_alergenos (parsed list), ordering, pagination offset/limit, NO selectinloads for categorias/ingredientes — ProductoPublicoRead list response does not include relations; only 2 queries: count + data
- [x] 2.3 Add `get_public_by_id(producto_id: UUID) -> Producto | None` to `ProductoRepository`: applies visibility, selectinload categorias and ingredientes (max 3 queries)
- [x] 2.4 Write unit tests in `backend/tests/unit/test_catalog_public_service.py` verifying: `_apply_public_visibility` behavior covered via service tests; `list_public` and `get_public_by_id` covered in integration tests
- [x] 2.5 Write integration tests in `backend/tests/integration/test_catalog_public.py` verifying: categoria_id filter; q ILIKE case-insensitive; excluir_alergenos validation; page/size offset; visibility filters
- [x] 2.6 Add `list_public_alergenos() -> list[Ingrediente]` to `IngredienteRepository` in `backend/app/repositories/ingrediente.py`: `SELECT * FROM ingrediente WHERE es_alergeno=true AND deleted_at IS NULL ORDER BY nombre ASC`

## 3. Backend — CatalogPublicService

- [x] 3.1 Create `backend/app/services/catalog_public.py` with `CatalogPublicService` containing `list_catalog(uow, filters)` and `get_catalog_detail(uow, producto_id)` methods, plus `_to_publico_read()` and `_to_publico_detalle()` private helpers, and `list_alergenos(uow)` method that calls `uow.ingredientes.list_public_alergenos()` and maps to `IngredienteAlergenicoListResponse`. NOTE: `model_validate(orm_obj)` is PROHIBITED for these schemas. `_to_publico_read()` must manually set `tiene_stock = p.stock_cantidad > 0`. `_to_publico_detalle()` must explicitly set each `IngredientePublicoRead(ingrediente_id=pivot.ingrediente.id, nombre=pivot.ingrediente.nombre, es_alergeno=pivot.ingrediente.es_alergeno)`.
- [x] 3.2 Implement `excluir_alergenos` validation in `list_catalog`: split on comma, strip whitespace, reject non-UUID values with `AppValidationError(code="INVALID_ALLERGEN_IDS", status_code=422)`, deduplicate, cap at 20 items. Pre-check: if `excluir_alergenos` is empty string or whitespace-only, treat as `None` and skip allergen filter entirely (do not raise 422 for empty string). Note: `Ingrediente.id` is UUID — comma-separated UUID ingredient IDs are required.
- [x] 3.3 Write unit tests in `backend/tests/unit/test_catalog_public_service.py` verifying: `list_catalog` assembles `PaginatedCatalogProductos` correctly; `get_catalog_detail` raises `NotFoundError` when repo returns None; `excluir_alergenos` validation raises 422 on bad input (non-UUID values, > 20 items); `_to_publico_read` maps `tiene_stock` correctly from `stock_cantidad`; `list_alergenos()` returns only allergen ingredients; excludes soft-deleted.

## 4. Backend — Catalog Router

- [x] 4.1 Create `backend/app/api/v1/catalog.py` with `catalog_router = APIRouter()` — NO auth dependency at router level; implement `GET /productos` endpoint (query param via `Depends(CatalogProductosQuery)`, response model `PaginatedCatalogProductos`); implement `GET /productos/{id}` endpoint (response model `ProductoPublicoDetalleRead`); implement `GET /ingredientes-alergenos` endpoint (response model `IngredienteAlergenicoListResponse`, no auth, no Depends for auth).
- [x] 4.2 Include `catalog_router` in `build_v1_router` in `backend/app/api/v1/router.py` with `prefix="/catalog"` and `tags=["catalog"]`
- [x] 4.3 Write integration tests in `backend/tests/integration/test_catalog_public.py` verifying:
  - `GET /api/v1/catalog/productos` returns 200 with no auth header
  - Response body has `items`, `total`, `page`, `size`, `pages`; no item has `stock_cantidad`; every item has `tiene_stock` boolean
  - Filter params: `q`, `categoria_id`, `excluir_alergenos`, `page`, `size`, `ordenar` all work correctly end-to-end
  - `GET /api/v1/catalog/productos/{id}` returns 200 with full relations; no `stock_cantidad`; has `tiene_stock`
  - Returns 404 with `code="PRODUCT_NOT_FOUND"` for `disponible=false` product
  - Returns 404 with `code="PRODUCT_NOT_FOUND"` for soft-deleted product
  - Returns 422 for non-UUID path param
  - `excluir_alergenos=abc` returns 422 with `code="INVALID_ALLERGEN_IDS"`
  - `size=200` returns 422 (schema validation)
  - `GET /api/v1/catalog/ingredientes-alergenos` returns 200 with no auth header
  - Returns only ingredients with `es_alergeno=true`
  - Excludes soft-deleted ingredients

## 5. Backend — Alembic Migration (Indices)

- [x] 5.1 Generate new Alembic migration `backend/alembic/versions/a2b3c4d5e6f7_0006_add_catalog_public_indices.py`. Uses `with op.get_context().autocommit_block():` for BOTH index creations. Required index: `idx_productos_disponible_deleted_at` (partial, WHERE disponible=true AND deleted_at IS NULL). Optional index: `idx_productos_nombre_lower` (btree on lower(nombre), with comment about pg_trgm for production scale). Downgrade drops both via `op.execute("DROP INDEX IF EXISTS ...")`.
- [x] 5.2 Verify downgrade function drops both indices without affecting other tables or columns (uses `DROP INDEX IF EXISTS` — safe)
- [x] 5.3 Migration documented: `idx_productos_disponible_deleted_at` will exist in `producto` table after `alembic upgrade head`. Note: `pg_trgm` GIN index documented as production-scale alternative for `nombre` search.

## 6. Frontend — Entity Layer Extensions

- [x] 6.1 Add public TypeScript types to `frontend/src/entities/products/model/types.ts`: `ProductoPublicoRead`, `CategoriaPublicaRead`, `IngredientePublicoRead`, `ProductoPublicoDetalleRead`, `CatalogFilters`, `PaginatedCatalogProductos`
- [x] 6.2 Add `CATALOG_PRODUCTOS = '/api/v1/catalog/productos'` and `CATALOG_ALERGENOS = '/api/v1/catalog/ingredientes-alergenos'` to `frontend/src/shared/api/endpoints.ts`
- [x] 6.3 Add public fetchers to `frontend/src/entities/products/api/productoFetchers.ts`: `fetchCatalogProductos(filters: CatalogFilters)` and `fetchCatalogProductoDetalle(id: string)` — using `CATALOG_PRODUCTOS` constant, omitting null/undefined params from query string; and `fetchCatalogAlergenos()` — `GET /api/v1/catalog/ingredientes-alergenos` with no params, returns `IngredienteAlergenicoListResponse`. Add `CATALOG_ALERGENOS = '/api/v1/catalog/ingredientes-alergenos'` constant to `shared/api/endpoints.ts`.
- [x] 6.4 Create `frontend/src/entities/products/model/useCatalogProducts.ts` with `useCatalogProducts(filters)` (`staleTime: 30_000`, `gcTime: 300_000`, `placeholderData: keepPreviousData`) and `useCatalogProduct(id)` (`enabled: !!id`); extend `productQueryKeys` with `catalogLists`, `catalogList`, `catalogDetail` keys; and `useCatalogAlergenos()` hook (`staleTime: 300_000`, `gcTime: 3_600_000`, queryKey: `['catalog', 'alergenos']`). Query key sanitization: before including CatalogFilters in queryKey, strip undefined/null values — prevents cache misses due to `{q: null}` vs `{q: undefined}` key differences.
- [x] 6.5 Extend barrel export in `frontend/src/entities/products/index.ts` with all new public types and hooks: `IngredienteAlergenicoListResponse`, `useCatalogAlergenos`
- [x] 6.6 Write unit tests in `frontend/src/entities/products/__tests__/catalog.test.ts` verifying (with MSW or axios-mock-adapter): `fetchCatalogProductos` builds correct query string (omits null/undefined); `fetchCatalogProductoDetalle` hits correct URL; `useCatalogProducts` uses `keepPreviousData`; `useCatalogProduct` skips query when id is empty; `ProductoPublicoRead` type does not include `stock_cantidad` (TypeScript compile test)

## 7. Frontend — Shared Utilities

- [x] 7.1 Create `frontend/src/shared/hooks/useDebounce.ts` (if not already present) exporting `useDebounce<T>(value: T, delayMs: number): T`
- [x] 7.2 Create `frontend/src/shared/ui/PaginationControls.tsx` (if not already present) with props `{ page, pages, onPageChange, disabled? }`, accessible nav, `aria-current="page"` on active page, prev/next disabled states, ellipsis for long ranges
- [x] 7.3 Write unit tests in `frontend/src/shared/__tests__/useDebounce.test.ts` verifying delay behavior using `vi.useFakeTimers()`
- [x] 7.4 Write unit tests in `frontend/src/shared/__tests__/PaginationControls.test.tsx` verifying: prev disabled on page 1; next disabled on last page; `aria-current="page"` on active page; `onPageChange` called with correct page number; renders nothing (or fully disabled state) when `pages=0`.

## 8. Frontend — Features

- [x] 8.1 Create `frontend/src/features/catalog/filters/useCatalogFilters.ts`: reads/writes `useSearchParams`; `setFilter` resets `page` to 1 atomically; exposes `rawQ` (immediate), `filters.q` (debounced 300 ms via `useDebounce`); exposes `resetFilters()`
- [x] 8.2 Create `frontend/src/features/catalog/product-list/ProductCard.tsx`: image with `alt={nombre}`, nombre, precio_base (formatted), "Agotado" badge when `tiene_stock=false`, card is a `<Link to={/catalog/${id}}>`
- [x] 8.3 Create `frontend/src/features/catalog/product-list/ProductGrid.tsx`: responsive Tailwind grid (`grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4`), accepts `products` and `isLoading` props; renders skeleton cards (8 cards with `animate-pulse`) when loading
- [x] 8.4 Create `frontend/src/features/catalog/product-list/EmptyState.tsx`: centered message "No encontramos productos con los filtros seleccionados." with reset button calling `onReset` prop
- [x] 8.5 Create `frontend/src/features/catalog/product-list/ErrorState.tsx`: centered error message with "Reintentar" button calling `onRetry` prop
- [x] 8.6 Create `frontend/src/features/catalog/product-detail/ProductDetailView.tsx`: two-column layout on `md+` (image + details), categorias tags, ingredientes list, `AllergenBadge` for `es_alergeno=true` ingredients, stock indicator (`tiene_stock`)
- [x] 8.7 Create `frontend/src/features/catalog/product-detail/AllergenBadge.tsx`: visual badge component for allergen ingredient labels
- [x] 8.8 Write unit tests in `frontend/src/features/catalog/__tests__/` verifying (with React Testing Library): `useCatalogFilters` resets page on setFilter; debounce fires only after 300 ms; `ProductCard` renders alt text, Agotado badge; `ProductGrid` shows skeletons when loading; `PaginationControls` keyboard navigation

## 9. Frontend — CatalogFilters Widget

- [x] 9.1 Create `frontend/src/widgets/catalog/CatalogFilters/SearchInput.tsx`: controlled input, `aria-label="Buscar productos por nombre"`, bound to `rawQ`
- [x] 9.2 Create `frontend/src/widgets/catalog/CatalogFilters/CategoriaSelect.tsx`: `<select>` populated from `useCategorias()`, default "Todas las categorías" option, `aria-label="Filtrar por categoría"`, bound to `filters.categoria_id`
- [x] 9.3 Create `frontend/src/widgets/catalog/CatalogFilters/AllergenosExclusion.tsx`: multi-select toggle using `useCatalogAlergenos()` from entities/products/ (calls GET /api/v1/catalog/ingredientes-alergenos — public endpoint added in this change; MUST NOT use the admin-only GET /api/v1/ingredientes); `role="group"` with `aria-labelledby`; serializes selected IDs to `excluir_alergenos` comma-string. Each allergen toggle button must have `aria-pressed={isSelected}` attribute for screen reader state announcement.
- [x] 9.4 Create `frontend/src/widgets/catalog/CatalogFilters/index.tsx`: assembles SearchInput, CategoriaSelect, AllergenosExclusion, and "Limpiar filtros" button calling `resetFilters()`
- [x] 9.5 Write unit tests in `frontend/src/widgets/catalog/__tests__/CatalogFilters.test.tsx` verifying: filter inputs render and bind correctly; "Limpiar filtros" calls `resetFilters`; allergen toggle updates comma-separated string

## 10. Frontend — Pages

- [x] 10.1 Create `frontend/src/pages/catalog/CatalogPage.tsx`: consumes `useCatalogFilters` + `useCatalogProducts(filters)`; renders `CatalogFilters` widget, `ProductGrid`, `PaginationControls` (when pages > 1), `EmptyState` (when 0 results), `ErrorState` (on error); wraps content in `<main>`
- [x] 10.2 Create `frontend/src/pages/catalog/ProductDetailPage.tsx`: reads `:id` from `useParams`; consumes `useCatalogProduct(id)`; renders `ProductDetailView` on success, detail skeleton on loading, "Producto no encontrado" + back-link on 404 error. On error: check `error?.response?.status === 404` (AxiosError pattern from Change 05 interceptor) to render 'Producto no encontrado' — NOT `error.status` directly.
- [x] 10.3 Register `/catalog/:id` sub-route in the public route tree (the React Router config from Change 08 — typically `frontend/src/app/router.tsx` or `frontend/src/app/router/index.tsx` — verify the actual path in the codebase before editing) pointing to `ProductDetailPage`; confirm `/catalog` already points to `CatalogPage` (replacing placeholder)
- [x] 10.4 Write integration tests in `frontend/src/pages/catalog/__tests__/` using MSW to mock `GET /api/v1/catalog/productos` and `GET /api/v1/catalog/productos/:id`:
  - `CatalogPage` renders product cards on success
  - `CatalogPage` renders skeletons while loading (MSW delayed response)
  - `CatalogPage` renders EmptyState when items is []
  - `CatalogPage` renders ErrorState on network failure
  - `CatalogPage` pagination controls visible when pages > 1
  - `ProductDetailPage` renders product details on success
  - `ProductDetailPage` renders "Producto no encontrado" on 404
  - Changing `q` filter debounces 300 ms before re-query

## 11. Frontend — Accessibility and Responsive Pass

- [x] 11.1 Audit all catalog components for ARIA compliance: `aria-current="page"` on active pagination button; `aria-label` on SearchInput, CategoriaSelect, PaginationControls nav; `role="group"` + `aria-labelledby` on AllergenosExclusion; `aria-busy="true"` on loading container; `role="status"` visually-hidden for screen reader loading announcement. Verify `aria-pressed` attribute on all allergen toggle buttons in `AllergenosExclusion`.
- [x] 11.2 Verify responsive grid renders correctly at 320 px, 640 px, 768 px, 1024 px breakpoints (visual + computed CSS check in tests or Storybook)
- [x] 11.3 Verify product image `alt` text equals `nombre` in all ProductCard render paths (including null `imagen_url` placeholder)
- [x] 11.4 Verify focus management: focus stays on the filter control after a filter change; no scroll-to-top or focus-reset on pagination click

## 12. Verification

- [x] 12.1 Run `cd backend && python -m pytest tests/ -v` — all backend tests pass (new + existing)
- [x] 12.2 Run `cd frontend && npx tsc --noEmit` — no TypeScript errors in new catalog files or modified entity files
- [x] 12.3 Run `cd frontend && npx eslint src/ --ext .ts,.tsx` — no `eslint-plugin-boundaries` violations; no new lint errors
- [x] 12.4 Run `cd frontend && npx vitest run` — all frontend tests pass
- [x] 12.5 Verify `openspec status --change catalog-public-browsing --json` shows all four artifacts (`proposal`, `design`, `specs`, `tasks`) with status `ready` or `complete`
- [x] 12.6 Manually verify: `GET /api/v1/catalog/productos` without auth returns 200; `GET /api/v1/catalog/productos/{id}` for a disabled product returns 404; response bodies never contain `stock_cantidad`
