# frontend-ingredientes-entity Specification

## Purpose
Frontend ingredient entity layer: TypeScript types, Axios fetchers, TanStack Query key factory, hooks, and public barrel export for the `ingrediente` domain. Introduced in Change 10 (catalog-ingredients-management).

## ADDED Requirements

### Requirement: Ingrediente TypeScript types
The system SHALL provide TypeScript interfaces in `frontend/src/entities/ingrediente/model/types.ts` mirroring the backend `IngredienteRead` schema.

The file SHALL export:
```typescript
// CORRECT — matches FastAPI JSON output directly (no camelCase conversion)
interface Ingrediente {
  id: string;           // UUID as string (NOT number)
  nombre: string;
  es_alergeno: boolean; // snake_case — FastAPI serializes as is
  created_at: string;   // ISO datetime string (NOT creadoEn)
  updated_at: string;   // ISO datetime string (NOT actualizadoEn)
}

interface IngredienteCreate {
  nombre: string;
  es_alergeno?: boolean; // defaults to false on backend
}

interface IngredienteUpdate {
  nombre?: string;
  es_alergeno?: boolean;
}
```

**Convention**: Backend uses `snake_case` field names (`es_alergeno`, `created_at`, `updated_at`) in JSON output — FastAPI serializes as-is. The frontend types use `snake_case` directly, consistent with the archived Change 09 (`frontend-categories-entity`) convention. No camelCase conversion layer.

#### Scenario: Ingrediente interface is importable from entity barrel
- **WHEN** `import { Ingrediente } from '@/entities/ingrediente'` is resolved
- **THEN** TypeScript resolves the `Ingrediente` type without error
- **THEN** `Ingrediente.es_alergeno` is typed as `boolean`
- **THEN** `Ingrediente.id` is typed as `string` (UUID as string, NOT number)
- **THEN** `Ingrediente.created_at` is typed as `string` (NOT `creadoEn`)

---

### Requirement: Ingrediente Axios fetchers
The system SHALL provide Axios-based fetcher functions in `frontend/src/entities/ingrediente/api/ingredienteApi.ts`.

The file SHALL export these async functions:
- `listIngredientes(params?: { es_alergeno?: boolean }): Promise<Ingrediente[]>` — `GET /api/v1/ingredientes?es_alergeno={value}` (optional filter). Query param MUST be `es_alergeno` (snake_case — NOT `esAlergeno`).
- `getIngrediente(id: string): Promise<Ingrediente>` — `GET /api/v1/ingredientes/{id}`. `id` is a UUID string (NOT number).
- `createIngrediente(data: IngredienteCreate): Promise<Ingrediente>` — `POST /api/v1/ingredientes`.
- `updateIngrediente(id: string, data: IngredienteUpdate): Promise<Ingrediente>` — `PUT /api/v1/ingredientes/{id}`. `id` is a UUID string.
- `deleteIngrediente(id: string): Promise<void>` — `DELETE /api/v1/ingredientes/{id}`. `id` is a UUID string.

All fetchers SHALL use the project's shared Axios instance (with JWT interceptor) from `frontend/src/shared/api/`.

The endpoint constant SHALL be added to `frontend/src/shared/api/endpoints.ts` as:
```ts
export const INGREDIENTES = '/api/v1/ingredientes' as const
```

#### Scenario: listIngredientes calls correct endpoint
- **WHEN** `listIngredientes()` is called
- **THEN** an HTTP GET to `/api/v1/ingredientes` is made with the project's Axios instance

#### Scenario: listIngredientes with filter passes query param in snake_case
- **WHEN** `listIngredientes({ es_alergeno: true })` is called
- **THEN** the request URL includes `?es_alergeno=true` (snake_case — NOT `?esAlergeno=true`)

#### Scenario: createIngrediente posts to correct endpoint
- **WHEN** `createIngrediente({ nombre: "Sal", es_alergeno: false })` is called
- **THEN** an HTTP POST to `/api/v1/ingredientes` is made with the correct body

---

### Requirement: Ingrediente TanStack Query key factory
The system SHALL provide a query key factory in `frontend/src/entities/ingrediente/api/queryKeys.ts`.

The file SHALL export:
```ts
export const ingredienteKeys = {
  all: ['ingredientes'] as const,
  lists: () => [...ingredienteKeys.all, 'list'] as const,
  list: (filters: { es_alergeno?: boolean }) => [...ingredienteKeys.lists(), filters] as const,
  details: () => [...ingredienteKeys.all, 'detail'] as const,
  detail: (id: string) => [...ingredienteKeys.details(), id] as const,  // id is UUID string
}
```

#### Scenario: Query key factory produces stable keys
- **WHEN** `ingredienteKeys.list({ es_alergeno: true })` is called twice
- **THEN** both calls return structurally equal arrays: `['ingredientes', 'list', { es_alergeno: true }]`

#### Scenario: list and detail keys are disjoint
- **WHEN** `ingredienteKeys.list({})` and `ingredienteKeys.detail('some-uuid')` are produced
- **THEN** they share the `['ingredientes']` prefix
- **THEN** they differ in the second element (`'list'` vs `'detail'`)

---

### Requirement: Ingrediente TanStack Query hooks
The system SHALL provide TanStack Query v5 hooks in `frontend/src/entities/ingrediente/api/hooks.ts`.

The file SHALL export:

**Query hooks:**
- `useIngredientes(filters?: { es_alergeno?: boolean })` — `useQuery({ queryKey: ingredienteKeys.list(filters ?? {}), queryFn: () => listIngredientes(filters) })`.
- `useIngrediente(id: string)` — `useQuery({ queryKey: ingredienteKeys.detail(id), queryFn: () => getIngrediente(id), enabled: !!id })`. `id` is a UUID string.

**Mutation hooks:**
- `useCreateIngrediente()` — `useMutation({ mutationFn: createIngrediente, onSuccess: () => queryClient.invalidateQueries({ queryKey: ingredienteKeys.lists() }) })`.
- `useUpdateIngrediente()` — `useMutation({ mutationFn: ({ id, data }) => updateIngrediente(id, data), onSuccess: (_, { id }) => { queryClient.invalidateQueries({ queryKey: ingredienteKeys.lists() }); queryClient.invalidateQueries({ queryKey: ingredienteKeys.detail(id) }) } })`.
- `useDeleteIngrediente()` — `useMutation({ mutationFn: deleteIngrediente, onSuccess: () => queryClient.invalidateQueries({ queryKey: ingredienteKeys.lists() }) })`.

All mutation hooks SHALL invalidate the list cache on success. `useUpdateIngrediente` SHALL also invalidate the specific detail cache.

#### Scenario: useIngredientes returns list data
- **WHEN** the backend returns `[{id: "uuid-string", nombre: "Sal", es_alergeno: false, created_at: "...", updated_at: "..."}]`
- **THEN** `useIngredientes().data` contains that array
- **THEN** the query key used is `['ingredientes', 'list', {}]`

#### Scenario: useCreateIngrediente invalidates list on success
- **WHEN** `useCreateIngrediente().mutate({ nombre: "Pimienta", es_alergeno: false })` succeeds
- **THEN** the TanStack Query cache for `['ingredientes', 'list']` is invalidated
- **THEN** a refetch of the ingredient list is triggered automatically

#### Scenario: useDeleteIngrediente invalidates list on success
- **WHEN** `useDeleteIngrediente().mutate('some-uuid-string')` succeeds
- **THEN** the TanStack Query cache for `['ingredientes', 'list']` is invalidated

---

### Requirement: Ingrediente entity public barrel
The system SHALL provide a public barrel export in `frontend/src/entities/ingrediente/index.ts` that re-exports the public API of the entity:

```ts
export type { Ingrediente, IngredienteCreate, IngredienteUpdate } from './model/types'
export { ingredienteKeys } from './api/queryKeys'
export {
  useIngredientes,
  useIngrediente,
  useCreateIngrediente,
  useUpdateIngrediente,
  useDeleteIngrediente,
} from './api/hooks'
```

Internal fetcher functions (`listIngredientes`, `getIngrediente`, etc.) SHALL NOT be re-exported from the barrel — they are implementation details consumed only by the hooks.

#### Scenario: Barrel exports are importable from outside the entity
- **WHEN** `import { Ingrediente, useIngredientes } from '@/entities/ingrediente'` is resolved
- **THEN** TypeScript resolves both the type and the hook without error
- **THEN** no circular imports are introduced

#### Scenario: TypeScript compiles with no errors
- **WHEN** `tsc --noEmit` is run after all entity files are created
- **THEN** no TypeScript errors exist in the `ingrediente` entity
