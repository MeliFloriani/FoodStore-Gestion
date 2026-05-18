## ADDED Requirements

### Requirement: CATEGORIAS endpoint constant in shared/api/endpoints.ts
The system SHALL add `export const CATEGORIAS = '/api/v1/categorias' as const` to `frontend/src/shared/api/endpoints.ts`, following the existing named export pattern (same as `AUTH_LOGIN`, `AUTH_REFRESH`, etc.). The fetcher SHALL import it as `import { CATEGORIAS } from '@/shared/api/endpoints'`. This constant SHALL be used by all category-related API calls to avoid hardcoded strings.

#### Scenario: CATEGORIAS constant is exported and used
- **WHEN** `frontend/src/shared/api/endpoints.ts` is imported
- **THEN** `CATEGORIAS` is a named export equal to `'/api/v1/categorias'`
- **THEN** no other file in `frontend/src/entities/categories/` hardcodes the string `/api/v1/categorias`

---

### Requirement: TypeScript types for Categoria domain
The system SHALL provide TypeScript interface types in `frontend/src/entities/categories/model/types.ts` mirroring the backend Pydantic schemas:

```typescript
interface Categoria {
  id: string;          // UUID as string
  nombre: string;
  descripcion: string | null;
  parent_id: string | null;
  created_at: string;  // ISO datetime string
  updated_at: string;
}

interface CategoriaTreeNode {
  id: string;
  nombre: string;
  descripcion: string | null;
  subcategorias: CategoriaTreeNode[];
}
```

These types SHALL be exported from the entity's public index file.

#### Scenario: CategoriaTreeNode is correctly typed for recursive nesting
- **WHEN** `CategoriaTreeNode` is imported and used in TypeScript
- **THEN** `node.subcategorias` is typed as `CategoriaTreeNode[]`
- **THEN** TypeScript does not require a cast to access nested subcategorias
- **THEN** the type compiles without errors under strict TypeScript mode

---

### Requirement: getCategoriesTree fetcher
The system SHALL provide an async fetcher function `getCategoriesTree` at `frontend/src/entities/categories/api/getCategoriesTree.ts` that calls `GET /api/v1/categorias` via the shared Axios instance and returns `CategoriaTreeNode[]`.

The fetcher SHALL import and use the `CATEGORIAS` named constant (`import { CATEGORIAS } from '@/shared/api/endpoints'`) rather than a hardcoded string. The fetcher SHALL type the response as `CategoriaTreeNode[]`.

#### Scenario: getCategoriesTree calls the correct endpoint
- **WHEN** `getCategoriesTree()` is invoked
- **THEN** an HTTP GET request is made to `/api/v1/categorias`
- **THEN** the function returns an array of `CategoriaTreeNode` objects matching the API response

#### Scenario: getCategoriesTree propagates Axios errors
- **WHEN** the API returns a non-2xx response
- **THEN** the Axios error is propagated (not swallowed)
- **THEN** TanStack Query captures the error in `isError` state

---

### Requirement: useCategoriesTree TanStack Query hook
The system SHALL provide a custom hook `useCategoriesTree` at `frontend/src/entities/categories/model/useCategoriesTree.ts` that wraps `getCategoriesTree` in a TanStack Query v5 `useQuery` call. The hook lives in `model/` (NOT `api/`) because it uses `useQuery` (a React hook); the `api/` directory contains only non-hook fetcher functions such as `getCategoriesTree.ts`.

The hook SHALL:
- Use `queryKeys.catalog.categories()` as the query key (already declared in `frontend/src/shared/lib/queryKeys.ts`).
- Use `getCategoriesTree` as the `queryFn`.
- Return the full `UseQueryResult<CategoriaTreeNode[]>` so consumers can access `data`, `isPending`, `isError`, `error`.
- NOT manage mutation state — this hook is read-only.

#### Scenario: useCategoriesTree returns pending state on first load
- **WHEN** `useCategoriesTree()` is called and the API has not responded yet
- **THEN** `isPending` is `true`
- **THEN** `data` is `undefined`

#### Scenario: useCategoriesTree returns data after successful fetch
- **WHEN** `useCategoriesTree()` is called and the API responds with a valid tree
- **THEN** `isPending` is `false`
- **THEN** `data` is an array of `CategoriaTreeNode` objects

#### Scenario: useCategoriesTree returns error state on API failure
- **WHEN** the API returns an error response
- **THEN** `isError` is `true`
- **THEN** `error` contains the Axios error

---

### Requirement: CatalogPage minimal tree render
The system SHALL update `frontend/src/pages/catalog/ui/CatalogPage.tsx` to replace the placeholder content with a minimal functional render of the category tree using `useCategoriesTree`.

The render SHALL:
- Show a loading indicator when `isPending` is `true`.
- Show an error message when `isError` is `true`.
- Render the category tree as nested `<ul><li>` HTML elements when data is available.
- Each category node SHALL display its `nombre`. Subcategories SHALL be rendered as a nested `<ul>` inside the parent `<li>`.
- Use basic Tailwind classes for readable spacing (e.g., `ml-4` for indent). No rich UI components, no breadcrumbs, no sidebar.

#### Scenario: CatalogPage renders loading state
- **WHEN** `useCategoriesTree()` returns `isPending: true`
- **THEN** the page renders a loading indicator (e.g., text "Cargando categorías..." or a spinner element)
- **THEN** no category list is rendered

#### Scenario: CatalogPage renders category tree when data is available
- **WHEN** `useCategoriesTree()` returns `data: [{ id: '1', nombre: 'Bebidas', subcategorias: [{...}] }]`
- **THEN** the page renders an `<ul>` with a `<li>` containing "Bebidas"
- **THEN** the nested subcategory appears inside a nested `<ul>` under the parent `<li>`

#### Scenario: CatalogPage renders error state
- **WHEN** `useCategoriesTree()` returns `isError: true`
- **THEN** the page renders an error message (e.g., "Error al cargar las categorías.")
- **THEN** no category list is rendered
