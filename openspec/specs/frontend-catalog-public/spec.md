# frontend-catalog-public Specification

## Purpose
Public catalog UI: CatalogPage, ProductDetailPage, CatalogFilters widget, URL-synced filters, debounced search, pagination component, skeleton/empty/error states, accessibility (a11y), and responsive grid. Introduced in Change 12 (catalog-public-browsing). Pure read-only public surface — no admin, no cart, no auth.

## ADDED Requirements

### Requirement: useCatalogFilters hook with URL-sync
The system SHALL provide `useCatalogFilters()` in `frontend/src/features/catalog/filters/useCatalogFilters.ts`. This hook is the single source of truth for all catalog filter state — components SHALL NOT use local `useState` for filter fields.

Responsibilities:
- Reads initial filter values from `useSearchParams` (React Router v6).
- Exposes `filters: CatalogFilters` (derived from URL params).
- Exposes `setFilter(key: keyof CatalogFilters, value: unknown): void` — writes a single filter to URL params and resets `page` to `1` atomically.
- Exposes `resetFilters(): void` — clears all filter params from URL.
- The `q` field SHALL be debounced 300 ms before being applied to `filters.q`. The raw (immediate) value is exposed as `rawQ: string` for binding to the search input. The debounced value is what flows into `filters.q` and ultimately into the TanStack Query key.
- Uses `useDebounce<string>(rawQ, 300)` from `frontend/src/shared/hooks/useDebounce.ts`.

#### Scenario: setFilter resets page to 1
- **GIVEN** the URL has `?q=pizza&page=3`
- **WHEN** `setFilter('categoria_id', 'some-uuid')` is called
- **THEN** the URL becomes `?q=pizza&page=1&categoria_id=some-uuid`
- **THEN** the previous page=3 is replaced with page=1

#### Scenario: q debounce prevents immediate query
- **WHEN** the user types "piz" into the search input (rawQ = "piz")
- **THEN** `filters.q` remains at its previous value for 300 ms
- **THEN** after 300 ms, `filters.q` becomes "piz"
- **THEN** only one HTTP request is fired (not one per keystroke)

#### Scenario: resetFilters clears all URL params
- **GIVEN** the URL has `?q=pizza&categoria_id=uuid&page=2`
- **WHEN** `resetFilters()` is called
- **THEN** the URL query string is cleared (only the pathname remains)

#### Scenario: filters survive page refresh
- **GIVEN** the URL is `/catalog?q=pizza&page=2&categoria_id=some-uuid`
- **WHEN** the page is refreshed
- **THEN** `useCatalogFilters` reads the same values from URL params
- **THEN** `filters.q` is "pizza", `filters.page` is 2, `filters.categoria_id` is "some-uuid"

---

### Requirement: useDebounce shared hook
The system SHALL provide `useDebounce<T>(value: T, delayMs: number): T` in `frontend/src/shared/hooks/useDebounce.ts`. If this file already exists with a compatible signature, it SHALL NOT be duplicated — the existing implementation is used.

```typescript
export function useDebounce<T>(value: T, delayMs: number): T {
  // Returns value, but only updates after delayMs ms of no change
}
```

#### Scenario: useDebounce returns initial value immediately
- **WHEN** `useDebounce("hello", 300)` is first called
- **THEN** the returned value is `"hello"` immediately

#### Scenario: useDebounce delays update
- **WHEN** the value changes from "a" to "b"
- **THEN** the returned value remains "a" for 300 ms
- **THEN** after 300 ms, the returned value becomes "b"

---

### Requirement: PaginationControls shared component
The system SHALL provide `frontend/src/shared/ui/PaginationControls.tsx` (or confirm it exists and matches the required contract). If the file already exists with a compatible interface, it SHALL NOT be duplicated.

Props:
```typescript
interface PaginationControlsProps {
  page: number
  pages: number
  onPageChange: (newPage: number) => void
  disabled?: boolean
}
```

Behavior:
- Renders "Previous" button (disabled when `page === 1`).
- Renders numeric page buttons for pages 1..pages, with ellipsis for long ranges (show first, last, and up to 3 pages around current).
- Renders "Next" button (disabled when `page === pages`).
- Active page button has `aria-current="page"`.
- Navigation wrapper has `<nav aria-label="Paginación del catálogo">`.
- All buttons are keyboard-focusable and activatable with Enter/Space.
- When `disabled` is `true`, all buttons are `disabled` and have `aria-disabled="true"`.

#### Scenario: Active page has aria-current
- **GIVEN** `PaginationControls` rendered with `page=3, pages=10`
- **WHEN** the component renders
- **THEN** the button for page 3 has `aria-current="page"`
- **THEN** no other page button has `aria-current="page"`

#### Scenario: Previous button disabled on first page
- **GIVEN** `PaginationControls` rendered with `page=1, pages=5`
- **WHEN** the component renders
- **THEN** the "Previous" button is disabled
- **THEN** the "Next" button is NOT disabled

#### Scenario: Next button disabled on last page
- **GIVEN** `PaginationControls` rendered with `page=5, pages=5`
- **WHEN** the component renders
- **THEN** the "Next" button is disabled
- **THEN** clicking "Next" does NOT call `onPageChange`

#### Scenario: onPageChange called with correct page number
- **GIVEN** `PaginationControls` rendered with `page=2, pages=5`
- **WHEN** the user clicks the button for page 4
- **THEN** `onPageChange(4)` is called

---

### Requirement: CatalogFilters widget
The system SHALL provide the `CatalogFilters` widget in `frontend/src/widgets/catalog/CatalogFilters/`. This widget consumes `useCatalogFilters` and renders the full filter panel.

Sub-components:
- `SearchInput.tsx` — controlled input bound to `rawQ` from `useCatalogFilters`; `aria-label="Buscar productos por nombre"`. Updates `rawQ` on every keystroke (debounce is inside the hook).
- `CategoriaSelect.tsx` — `<select>` populated from `useCategorias()` (existing categories entity hook); bound to `filters.categoria_id`; has an "Todas las categorías" default option (`value=""`); `aria-label="Filtrar por categoría"`.
- `AllergenosExclusion.tsx` — multi-select toggle grid. Uses `useCatalogAlergenos()` hook from `entities/products/` (calls `GET /api/v1/catalog/ingredientes-alergenos`) to populate items. This is the public endpoint introduced in this change — the admin `GET /api/v1/ingredientes` endpoint requires ADMIN/STOCK role and MUST NOT be used here. Each item is a toggle button. Selected IDs are serialized to comma-separated string for `filters.excluir_alergenos`. Wrapped in `role="group"` with `aria-labelledby` pointing to a heading "Excluir alérgenos". Each allergen toggle button SHALL have `aria-pressed='true'` when selected and `aria-pressed='false'` when not selected, for screen reader state announcement.
- `CatalogFilters/index.tsx` — assembles SearchInput, CategoriaSelect, AllergenosExclusion. Renders a "Limpiar filtros" button that calls `resetFilters()`.

FSD boundary: `widgets/catalog/CatalogFilters/` SHALL import from `features/catalog/filters/`, `entities/categories/`, `entities/ingredientes/`, and `shared/` only.

#### Scenario: SearchInput changes update rawQ
- **WHEN** the user types into `SearchInput`
- **THEN** the input value updates immediately (uncontrolled feel)
- **THEN** `filters.q` updates after 300 ms debounce

#### Scenario: CategoriaSelect shows all categories
- **GIVEN** `useCategorias` returns [{ id: "1", nombre: "Pizzas" }, { id: "2", nombre: "Bebidas" }]
- **WHEN** `CategoriaSelect` renders
- **THEN** the select has options: "Todas las categorías", "Pizzas", "Bebidas"

#### Scenario: AllergenosExclusion toggles allergen IDs
- **WHEN** the user toggles allergen with id=1
- **THEN** `filters.excluir_alergenos` becomes `"1"`
- **WHEN** the user then toggles allergen with id=2
- **THEN** `filters.excluir_alergenos` becomes `"1,2"` (or `"2,1"` — order stable within session)

#### Scenario: Limpiar filtros button resets all filters
- **GIVEN** filters are `{ q: "pizza", categoria_id: "uuid", excluir_alergenos: "1" }`
- **WHEN** the user clicks "Limpiar filtros"
- **THEN** `resetFilters()` is called
- **THEN** all filter inputs visually reset to their default/empty state

---

### Requirement: CatalogPage
The system SHALL provide `frontend/src/pages/catalog/CatalogPage.tsx`, replacing the `/catalog` route placeholder from Change 08.

Responsibilities:
- Consumes `useCatalogFilters()` for filter state.
- Consumes `useCatalogProducts(filters)` for product data.
- Renders `<CatalogFilters />` widget.
- Renders `<ProductGrid />` feature component (or equivalent product grid from `features/catalog/product-list/`).
- Renders `<PaginationControls />` when `pages > 1`.
- Passes `isLoading` to `ProductGrid` to trigger skeleton rendering.
- On `isError`: renders `<ErrorState />`.
- On `data.items.length === 0` (not loading, no error): renders `<EmptyState />`.
- Route: `/catalog` (registered in the public route tree under `PublicLayout` — wired in Change 08).

Layout: `<main>` landmark wrapping the page content. Filters in a `<aside>` or `<section>` with appropriate landmark role.

#### Scenario: CatalogPage renders product grid on success
- **GIVEN** `useCatalogProducts` returns 12 products
- **WHEN** `CatalogPage` renders
- **THEN** the page renders 12 product cards
- **THEN** `PaginationControls` is rendered

#### Scenario: CatalogPage renders skeletons while loading
- **GIVEN** `useCatalogProducts` is in loading state (`isLoading=true`)
- **WHEN** `CatalogPage` renders
- **THEN** skeleton card placeholders are visible (not the real product cards)

#### Scenario: CatalogPage renders empty state when no products match
- **GIVEN** `useCatalogProducts` returns `{ items: [], total: 0, pages: 0 }`
- **WHEN** `CatalogPage` renders
- **THEN** the empty state component is visible
- **THEN** `PaginationControls` is NOT rendered

#### Scenario: CatalogPage renders error state on network failure
- **GIVEN** `useCatalogProducts` returns `isError=true`
- **WHEN** `CatalogPage` renders
- **THEN** the error state component is visible with a user-friendly message

---

### Requirement: ProductDetailPage
The system SHALL provide `frontend/src/pages/catalog/ProductDetailPage.tsx`.

Responsibilities:
- Reads `:id` param from React Router `useParams`.
- Consumes `useCatalogProduct(id)`.
- On success: renders `<ProductDetailView />` feature component.
- On `isLoading`: renders a detail skeleton.
- On `isError` / `error.status === 404`: renders an inline not-found message (or redirects to `/catalog`).
- Route: `/catalog/:id` (registered under `PublicLayout`).

Layout: two-column on `md+` (image left, details right); single column on mobile.

#### Scenario: ProductDetailPage renders product details on success
- **GIVEN** `useCatalogProduct` returns a full `ProductoPublicoDetalleRead`
- **WHEN** `ProductDetailPage` renders
- **THEN** the product nombre, precio_base (formatted), descripcion, categorias, and ingredientes are visible
- **THEN** allergen ingredients are visually marked (e.g., with an allergen badge)
- **THEN** `tiene_stock: true` shows a "Disponible" indicator; `tiene_stock: false` shows "Agotado"

#### Scenario: ProductDetailPage renders skeleton while loading
- **GIVEN** `useCatalogProduct` is in loading state
- **WHEN** `ProductDetailPage` renders
- **THEN** skeleton placeholders fill the two-column layout

#### Scenario: ProductDetailPage handles 404 gracefully
- **GIVEN** `useCatalogProduct` returns a 404 error
- **WHEN** `ProductDetailPage` renders
- **THEN** a user-friendly "Producto no encontrado" message is shown
- **THEN** a link back to `/catalog` is provided

Technical note: TanStack Query surfaces the Axios error as `AxiosError`. To check for 404, use `error?.response?.status === 404` (consistent with the error handling pattern established in Change 05 and Change 07).

---

### Requirement: Responsive product grid
The system SHALL provide `frontend/src/features/catalog/product-list/ProductGrid.tsx` rendering a responsive grid layout.

Grid CSS: `grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4` (Tailwind utility classes consistent with project design system).

`ProductCard.tsx` SHALL display:
- Product image (`<img src={imagen_url} alt={nombre} />` — if `imagen_url` is null, a placeholder image is used, still with `alt={nombre}`).
- Product `nombre` (heading level appropriate to context — typically `h3`).
- `precio_base` formatted as currency string (e.g., "$ 12.50").
- `tiene_stock: false` → "Agotado" badge; `tiene_stock: true` → no badge or "Disponible" indicator.
- Card is a link to `/catalog/{id}`.

Skeleton cards (for loading state): 8 placeholder cards with pulsing animation (`animate-pulse`), same dimensions as real cards.

`EmptyState.tsx` SHALL display a centered message: "No encontramos productos con los filtros seleccionados." with a button calling `resetFilters()`.

`ErrorState.tsx` SHALL display a centered error message with a retry button (calls `refetch` from the query hook).

#### Scenario: Product grid renders correct column count on each breakpoint
- **WHEN** the viewport is 320 px wide (mobile)
- **THEN** products render in 1 column
- **WHEN** the viewport is 640 px wide (sm)
- **THEN** products render in 2 columns
- **WHEN** the viewport is 768 px wide (md)
- **THEN** products render in 3 columns
- **WHEN** the viewport is 1024 px wide (lg)
- **THEN** products render in 4 columns

#### Scenario: ProductCard image has alt text equal to product nombre
- **WHEN** a `ProductCard` renders for product with `nombre="Pizza Margherita"`
- **THEN** the `<img>` element has `alt="Pizza Margherita"`

#### Scenario: ProductCard shows Agotado badge when tiene_stock is false
- **GIVEN** a product with `tiene_stock=false`
- **WHEN** `ProductCard` renders
- **THEN** an "Agotado" badge or label is visible on the card

---

### Requirement: Accessibility compliance for public catalog
The system SHALL comply with the following accessibility requirements across all catalog UI components.

- All product images SHALL have meaningful `alt` text equal to `producto.nombre`.
- Search input SHALL have `aria-label="Buscar productos por nombre"` or equivalent visible label.
- Category select SHALL have `aria-label="Filtrar por categoría"` or an associated `<label>`.
- Allergen exclusion group SHALL use `role="group"` with `aria-labelledby` pointing to "Excluir alérgenos" text.
- Pagination `<nav>` SHALL have `aria-label="Paginación del catálogo"`. Active page button SHALL have `aria-current="page"`.
- Loading skeleton containers SHALL have `aria-busy="true"` and a visually-hidden `<span role="status">Cargando productos…</span>`.
- The `<main>` landmark SHALL wrap the catalog page content. Filters SHALL be in a `<aside>` or `<section>` with an appropriate `aria-label`.
- Focus SHALL remain on the filter control that triggered a change — no unexpected focus jumps when filters update the product grid.

#### Scenario: Catalog page has main landmark
- **WHEN** the accessibility tree of `CatalogPage` is inspected
- **THEN** a `<main>` element wraps the primary content

#### Scenario: Loading state announces to screen readers
- **WHEN** `CatalogPage` transitions to loading state
- **THEN** `aria-busy="true"` is set on the loading container
- **THEN** a `role="status"` element with "Cargando productos…" text is present (visually hidden is acceptable)

#### Scenario: Pagination nav has accessible label
- **WHEN** `PaginationControls` renders
- **THEN** the wrapping `<nav>` has `aria-label="Paginación del catálogo"`
- **THEN** screen readers announce the navigation region correctly

---

### Requirement: FSD layer boundary compliance for catalog public
All catalog public UI files SHALL comply with Feature-Sliced Design import rules (imports flow DOWN only — no upward or cross-layer imports at the same level).

- `pages/catalog/` SHALL import from `widgets/catalog/`, `features/catalog/`, `entities/products/`, `shared/` only.
- `widgets/catalog/` SHALL import from `features/catalog/filters/`, `entities/categories/`, `entities/ingredientes/`, `shared/` only. SHALL NOT import from `pages/`.
- `features/catalog/` SHALL import from `entities/products/`, `entities/categories/`, `entities/ingredientes/`, `shared/` only. SHALL NOT import from `widgets/` or `pages/`.

#### Scenario: FSD boundaries enforced by ESLint
- **WHEN** `eslint --ext .tsx,.ts frontend/src/` is run
- **THEN** no `eslint-plugin-boundaries` violations are reported for any catalog public file
- **THEN** no import from a higher-level FSD layer is detected in any catalog file
