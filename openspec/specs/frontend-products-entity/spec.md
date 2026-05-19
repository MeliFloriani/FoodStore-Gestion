# frontend-products-entity Specification

## Purpose
Frontend entity layer for the product domain: TypeScript types, Axios fetchers, TanStack Query key factory, query and mutation hooks for admin/stock management. Introduced in Change 11 (catalog-products-management). No pages or feature components in this change — pure entity layer (FSD).

## ADDED Requirements

### Requirement: TypeScript types for Producto entity
The system SHALL provide TypeScript interfaces in `frontend/src/entities/products/model/types.ts` mirroring the backend Pydantic schemas.

```typescript
export interface ProductoRead {
  id: string            // UUID as string
  nombre: string
  descripcion: string | null
  imagen_url: string | null
  precio_base: string   // Decimal serialized as string by backend
  stock_cantidad: number
  disponible: boolean
  created_at: string    // ISO 8601
  updated_at: string
}

export interface ProductoIngredienteRead {
  ingrediente_id: string
  nombre: string
  es_alergeno: boolean
  es_removible: boolean
}

export interface ProductoDetail extends ProductoRead {
  categorias: CategoriaRead[]    // from entities/categories/model/types
  ingredientes: ProductoIngredienteRead[]
}

export interface PaginatedProductos {
  items: ProductoRead[]
  total: number
  page: number
  size: number
  pages: number
}

export interface ProductoCreatePayload {
  nombre: string
  descripcion?: string | null
  imagen_url?: string | null
  precio_base: string   // sent as string to avoid float precision loss
  stock_cantidad?: number
  disponible?: boolean
  categoria_ids?: string[] | null
}

export interface ProductoUpdatePayload {
  nombre?: string
  descripcion?: string | null
  imagen_url?: string | null
  precio_base?: string
  stock_cantidad?: number
  disponible?: boolean
  categoria_ids?: string[] | null
}

export interface DisponibilidadUpdatePayload {
  disponible: boolean
}

export interface AsociarIngredientePayload {
  ingrediente_id: string
  es_removible: boolean
}

export interface ProductoListFilters {
  page?: number
  size?: number
  categoria_id?: string | null
  disponible?: boolean | null
  search?: string | null
}
```

#### Scenario: ProductoRead price is typed as string
- **WHEN** `ProductoRead` is used in TypeScript
- **THEN** `precio_base` is typed as `string`, not `number`
- **THEN** TypeScript compiler rejects assignment of `number` to `precio_base`

---

### Requirement: Axios fetchers for Producto API
The system SHALL provide Axios fetcher functions in `frontend/src/entities/products/api/productoFetchers.ts` using the centralized Axios instance.

```typescript
// GET /api/v1/productos (public)
export function fetchProductos(filters: ProductoListFilters): Promise<PaginatedProductos>

// GET /api/v1/productos/{id} (public)
export function fetchProductoDetail(id: string): Promise<ProductoDetail>

// GET /api/v1/productos/{id}/ingredientes (public)
export function fetchProductoIngredientes(id: string): Promise<ProductoIngredienteRead[]>

// POST /api/v1/productos (ADMIN — token via interceptor)
export function createProducto(payload: ProductoCreatePayload): Promise<ProductoRead>

// PATCH /api/v1/productos/{id} (ADMIN)
export function updateProducto(id: string, payload: ProductoUpdatePayload): Promise<ProductoRead>

// DELETE /api/v1/productos/{id} (ADMIN)
export function deleteProducto(id: string): Promise<void>

// PATCH /api/v1/productos/{id}/disponibilidad (ADMIN, STOCK)
export function updateDisponibilidad(id: string, payload: DisponibilidadUpdatePayload): Promise<ProductoRead>

// POST /api/v1/productos/{id}/ingredientes (ADMIN)
export function addIngredienteToProducto(id: string, payload: AsociarIngredientePayload): Promise<ProductoIngredienteRead>

// DELETE /api/v1/productos/{id}/ingredientes/{ing_id} (ADMIN)
export function removeIngredienteFromProducto(productoId: string, ingredienteId: string): Promise<void>
```

The `PRODUCTOS` endpoint constant SHALL be added to `frontend/src/shared/api/endpoints.ts`:
```typescript
export const PRODUCTOS = '/api/v1/productos' as const
```

#### Scenario: fetchProductos builds correct query string
- **WHEN** `fetchProductos({ page: 2, size: 10, search: 'pizza' })` is called
- **THEN** the Axios request URL is `GET /api/v1/productos?page=2&size=10&search=pizza`
- **THEN** undefined/null filter params are NOT included in the query string

#### Scenario: createProducto sends precio_base as string
- **WHEN** `createProducto({ precio_base: "19.99", nombre: "Pizza", ... })` is called
- **THEN** the request body JSON has `"precio_base": "19.99"` (string, not number)

---

### Requirement: TanStack Query hooks for Producto reads
The system SHALL provide TanStack Query v5 hooks in `frontend/src/entities/products/model/useProductos.ts`.

Query key factory (defined in `frontend/src/entities/products/model/queryKeys.ts` or inline):
```typescript
export const productQueryKeys = {
  all: ['products'] as const,
  lists: () => [...productQueryKeys.all, 'list'] as const,
  list: (filters: ProductoListFilters) => [...productQueryKeys.lists(), filters] as const,
  details: () => [...productQueryKeys.all, 'detail'] as const,
  detail: (id: string) => [...productQueryKeys.details(), id] as const,
  ingredientes: (id: string) => [...productQueryKeys.all, 'ingredientes', id] as const,
}
```

```typescript
// Hook for paginated product listing
export function useProductos(filters: ProductoListFilters): UseQueryResult<PaginatedProductos>

// Hook for product detail (includes categorias and ingredientes)
export function useProductoDetail(id: string): UseQueryResult<ProductoDetail>

// Hook for product ingredients list
export function useProductoIngredientes(id: string): UseQueryResult<ProductoIngredienteRead[]>
```

#### Scenario: useProductos returns paginated products
- **WHEN** `useProductos({ page: 1, size: 20 })` is used in a component
- **THEN** the hook calls `fetchProductos` with the provided filters
- **THEN** the hook returns `{ data: PaginatedProductos, isLoading, isError }` states

#### Scenario: useProductoDetail returns ProductoDetail with relations
- **WHEN** `useProductoDetail(id)` is used in a component
- **THEN** the hook calls `fetchProductoDetail(id)`
- **THEN** the resolved data includes `categorias` and `ingredientes` arrays

---

### Requirement: TanStack Query mutation hooks for Producto writes
The system SHALL provide mutation hooks in `frontend/src/entities/products/model/useProductoMutations.ts`.

```typescript
// Creates product — invalidates list
export function useCreateProducto(): UseMutationResult<ProductoRead, Error, ProductoCreatePayload>

// Updates product — invalidates list and detail
export function useUpdateProducto(id: string): UseMutationResult<ProductoRead, Error, ProductoUpdatePayload>

// Deletes product (soft) — invalidates list and detail
export function useDeleteProducto(): UseMutationResult<void, Error, string>

// Toggles availability — invalidates list and detail (for ADMIN and STOCK)
export function useUpdateDisponibilidad(id: string): UseMutationResult<ProductoRead, Error, DisponibilidadUpdatePayload>

// Associates ingredient — invalidates detail and ingredientes
export function useAddIngrediente(productoId: string): UseMutationResult<ProductoIngredienteRead, Error, AsociarIngredientePayload>

// Removes ingredient association — invalidates detail and ingredientes
export function useRemoveIngrediente(productoId: string): UseMutationResult<void, Error, string>
```

**Invalidation rules** (applied in `onSuccess` callback):
- After `createProducto`: `queryClient.invalidateQueries({ queryKey: productQueryKeys.lists() })`
- After `updateProducto(id)`: invalidate `productQueryKeys.lists()` and `productQueryKeys.detail(id)`
- After `deleteProducto(id)`: invalidate `productQueryKeys.lists()` and `productQueryKeys.detail(id)`
- After `updateDisponibilidad(id)`: invalidate `productQueryKeys.lists()` and `productQueryKeys.detail(id)`
- After `addIngrediente(productoId)`: invalidate `productQueryKeys.detail(productoId)`, `productQueryKeys.ingredientes(productoId)`, **and `productQueryKeys.lists()`** — lists may show ingredient counts or affect display in admin
- After `removeIngrediente(productoId)`: invalidate `productQueryKeys.detail(productoId)`, `productQueryKeys.ingredientes(productoId)`, **and `productQueryKeys.lists()`** — same rationale

> **Rationale for lists() on M2M mutations**: If any admin list view renders ingredient associations (e.g., ingredient count badge, allergen indicator), invalidating `lists()` ensures those views are refreshed consistently. Cross-entity invalidation of `ingredienteQueryKeys` or `categoriaQueryKeys` is out of scope for Change 11 — document in Change 22 if needed.

#### Scenario: useCreateProducto invalidates product list on success
- **WHEN** `useCreateProducto()` mutation succeeds
- **THEN** `queryClient.invalidateQueries` is called with `productQueryKeys.lists()`
- **THEN** components using `useProductos` re-fetch automatically

#### Scenario: useAddIngrediente invalidates list, detail, and ingredientes on success
- **WHEN** `useAddIngrediente(productoId)` mutation succeeds
- **THEN** `queryClient.invalidateQueries` is called with `productQueryKeys.lists()`, `productQueryKeys.detail(productoId)`, AND `productQueryKeys.ingredientes(productoId)`
- **THEN** all three caches are refreshed to reflect the new association

#### Scenario: useUpdateDisponibilidad can be used by STOCK role
- **WHEN** `useUpdateDisponibilidad(id)` is used in a STOCK-role component
- **THEN** the mutation calls `updateDisponibilidad` (which attaches the JWT via Axios interceptor)
- **THEN** no role check is in the hook itself — role enforcement is at the route guard level (Change 22)

---

### Requirement: Barrel export for products entity
The system SHALL provide `frontend/src/entities/products/index.ts` exporting all public API of the products entity slice.

```typescript
export type {
  ProductoRead,
  ProductoDetail,
  ProductoIngredienteRead,
  PaginatedProductos,
  ProductoCreatePayload,
  ProductoUpdatePayload,
  DisponibilidadUpdatePayload,
  AsociarIngredientePayload,
  ProductoListFilters,
} from './model/types'

export {
  useProductos,
  useProductoDetail,
  useProductoIngredientes,
} from './model/useProductos'

export {
  useCreateProducto,
  useUpdateProducto,
  useDeleteProducto,
  useUpdateDisponibilidad,
  useAddIngrediente,
  useRemoveIngrediente,
} from './model/useProductoMutations'

export { productQueryKeys } from './model/queryKeys'
```

#### Scenario: Barrel export compiles without TypeScript errors
- **WHEN** `tsc --noEmit` is run after creating all entity files
- **THEN** no TypeScript errors are reported for `entities/products/`
- **THEN** all exported types and hooks are accessible from the barrel

---

### Requirement: FSD boundary compliance
The `entities/products/` slice SHALL NOT import from `features/`, `pages/`, or `widgets/` layers. It MAY import from `entities/categories/` (for `CategoriaRead` type) and `shared/api/` (for the Axios instance and endpoint constants).

#### Scenario: FSD layer boundary is not violated
- **WHEN** eslint-plugin-boundaries runs on `frontend/src/entities/products/`
- **THEN** no import from `features/`, `pages/`, or `widgets/` is detected
- **THEN** no cross-entity import other than `entities/categories` is detected

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
