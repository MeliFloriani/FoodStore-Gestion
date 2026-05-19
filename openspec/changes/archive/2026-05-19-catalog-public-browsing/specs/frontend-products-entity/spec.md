## ADDED Requirements

### Requirement: TypeScript public types for catalog entity
The system SHALL add the following TypeScript interfaces to `frontend/src/entities/products/model/types.ts`, extending the existing type definitions without modifying any existing interface.

```typescript
export interface ProductoPublicoRead {
  id: string
  nombre: string
  descripcion: string | null
  imagen_url: string | null
  precio_base: string        // Decimal serialized as string
  disponible: boolean
  tiene_stock: boolean       // NEVER stock_cantidad — public-safe boolean
}

export interface CategoriaPublicaRead {
  id: string
  nombre: string
}

export interface IngredientePublicoRead {
  ingrediente_id: string
  nombre: string
  es_alergeno: boolean
  // es_removible is intentionally absent (admin-only detail)
}

export interface ProductoPublicoDetalleRead extends ProductoPublicoRead {
  categorias: CategoriaPublicaRead[]
  ingredientes: IngredientePublicoRead[]
}

export interface CatalogFilters {
  page?: number
  size?: number
  categoria_id?: string | null
  q?: string | null
  excluir_alergenos?: string | null  // comma-separated positive integer IDs
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

#### Scenario: ProductoPublicoRead does not have stock_cantidad
- **WHEN** `ProductoPublicoRead` is used in TypeScript
- **THEN** `stock_cantidad` is NOT a property of the interface
- **THEN** attempting to access `.stock_cantidad` on a `ProductoPublicoRead` value causes a TypeScript compile error
- **THEN** `tiene_stock` IS a property typed as `boolean`

#### Scenario: ProductoPublicoDetalleRead includes relations
- **WHEN** `ProductoPublicoDetalleRead` is used in TypeScript
- **THEN** `categorias` is typed as `CategoriaPublicaRead[]`
- **THEN** `ingredientes` is typed as `IngredientePublicoRead[]`

---

### Requirement: Axios public catalog fetchers
The system SHALL add the following fetcher functions to `frontend/src/entities/products/api/productoFetchers.ts`, alongside the existing admin fetchers.

```typescript
// GET /api/v1/catalog/productos (public — no auth)
export function fetchCatalogProductos(filters: CatalogFilters): Promise<PaginatedCatalogProductos>

// GET /api/v1/catalog/productos/{id} (public — no auth)
export function fetchCatalogProductoDetalle(id: string): Promise<ProductoPublicoDetalleRead>

// GET /api/v1/catalog/ingredientes-alergenos (public — no auth)
export function fetchCatalogAlergenos(): Promise<IngredienteAlergenicoListResponse>
```

The following endpoint constants SHALL be added to `frontend/src/shared/api/endpoints.ts`:
```typescript
export const CATALOG_PRODUCTOS = '/api/v1/catalog/productos' as const
export const CATALOG_ALERGENOS = '/api/v1/catalog/ingredientes-alergenos' as const
```

The following type SHALL be added to `frontend/src/entities/products/model/types.ts`:
```typescript
export interface IngredienteAlergenicoListResponse {
  items: IngredientePublicoRead[]
  total: number
}
```

Both fetchers SHALL use the centralized Axios instance from `shared/api/`. They SHALL NOT attach an `Authorization` header (the Axios interceptor only attaches the token when a token is present in the auth store — public requests have no token and therefore no header is added automatically).

`fetchCatalogProductos` SHALL serialize `CatalogFilters` to query string, omitting `undefined` and `null` values.

#### Scenario: fetchCatalogProductos builds correct query string
- **WHEN** `fetchCatalogProductos({ page: 2, size: 10, q: 'pizza', excluir_alergenos: '1,2' })` is called
- **THEN** the Axios request URL is `GET /api/v1/catalog/productos?page=2&size=10&q=pizza&excluir_alergenos=1%2C2` (or equivalent encoding)
- **THEN** undefined/null filter params are NOT included in the query string

#### Scenario: fetchCatalogProductoDetalle hits the correct endpoint
- **WHEN** `fetchCatalogProductoDetalle("some-uuid")` is called
- **THEN** the Axios request URL is `GET /api/v1/catalog/productos/some-uuid`

---

### Requirement: TanStack Query public catalog hooks
The system SHALL provide TanStack Query v5 hooks in `frontend/src/entities/products/model/useCatalogProducts.ts`.

Query key factory extensions (added to `productQueryKeys` in `queryKeys.ts` or inline):
```typescript
catalogLists: () => [...productQueryKeys.all, 'catalog', 'list'] as const,
catalogList:  (f: CatalogFilters) => [...productQueryKeys.catalogLists(), f] as const,
catalogDetail:(id: string) => [...productQueryKeys.all, 'catalog', 'detail', id] as const,
```

```typescript
// Hook for paginated public product listing
export function useCatalogProducts(filters: CatalogFilters): UseQueryResult<PaginatedCatalogProductos>

// Hook for public product detail
export function useCatalogProduct(id: string): UseQueryResult<ProductoPublicoDetalleRead>

// Hook for public allergen list (used by AllergenosExclusion widget)
export function useCatalogAlergenos(): UseQueryResult<IngredienteAlergenicoListResponse>
```

Cache configuration for product hooks:
- `staleTime: 30_000` (30 seconds)
- `gcTime: 300_000` (5 minutes)
- `useCatalogProducts` SHALL use `placeholderData: keepPreviousData` (TanStack Query v5 idiom for smooth pagination transitions)
- `useCatalogProduct` SHALL set `enabled: !!id` (skip query if id is empty/undefined)

Cache configuration for `useCatalogAlergenos`:
- `staleTime: 300_000` (5 minutes — allergen list changes very infrequently)
- `gcTime: 3_600_000` (1 hour)
- Query key: `['catalog', 'alergenos'] as const`

Query key sanitization: before including `f: CatalogFilters` in the queryKey, the hook SHALL omit undefined/null values to ensure cache hit consistency. Use `Object.fromEntries(Object.entries(f).filter(([_, v]) => v != null))` or equivalent.

**Invalidation note** (for future Cart/Checkout — Change 16): When a purchase is completed, the cart feature SHALL invalidate `productQueryKeys.catalogLists()` to refresh stock status indicators. This is NOT implemented in this change — documented as a contractual note.

#### Scenario: useCatalogProducts returns paginated catalog products
- **WHEN** `useCatalogProducts({ page: 1, size: 20 })` is used in a component
- **THEN** the hook calls `fetchCatalogProductos` with the provided filters
- **THEN** the hook returns `{ data: PaginatedCatalogProductos, isLoading, isError }` states
- **THEN** items have `tiene_stock` (boolean) and NOT `stock_cantidad`

#### Scenario: useCatalogProducts uses keepPreviousData for pagination
- **WHEN** the user navigates from page 1 to page 2 (filters.page changes from 1 to 2)
- **THEN** the hook renders the page 1 data until page 2 data arrives (no flash of empty/loading state)
- **THEN** `isPlaceholderData` is `true` while page 2 is being fetched

#### Scenario: useCatalogProduct is disabled when id is empty
- **WHEN** `useCatalogProduct("")` is used in a component
- **THEN** no HTTP request is made
- **THEN** the hook is in `idle` state

#### Scenario: useCatalogProduct returns product detail with relations
- **WHEN** `useCatalogProduct("some-uuid")` is used in a component
- **THEN** the hook calls `fetchCatalogProductoDetalle("some-uuid")`
- **THEN** resolved data includes `categorias` and `ingredientes` arrays

---

### Requirement: Barrel export extended for public catalog types and hooks
The system SHALL extend `frontend/src/entities/products/index.ts` to export all new public types and hooks.

New exports to add:
```typescript
export type {
  ProductoPublicoRead,
  ProductoPublicoDetalleRead,
  CategoriaPublicaRead,
  IngredientePublicoRead,
  IngredienteAlergenicoListResponse,
  CatalogFilters,
  PaginatedCatalogProductos,
} from './model/types'

export {
  useCatalogProducts,
  useCatalogProduct,
  useCatalogAlergenos,
} from './model/useCatalogProducts'
```

Existing exports SHALL remain unchanged.

#### Scenario: Extended barrel export compiles without TypeScript errors
- **WHEN** `tsc --noEmit` is run after adding all new entity files
- **THEN** no TypeScript errors are reported for `entities/products/`
- **THEN** all new types and hooks are accessible from the barrel
