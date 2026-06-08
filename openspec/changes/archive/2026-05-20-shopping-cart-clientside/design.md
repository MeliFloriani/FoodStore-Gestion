## Context

Change 05 (`frontend-core-foundation`) introduced a minimal `cartStore` that fulfilled the basic scaffold requirement. It identifies cart items solely by `producto_id`, exposes only `totalItems`/`totalPrice`, and does not validate ingredient removability. Before checkout (Change 16) and order creation (Change 17) can be implemented, the store must be upgraded to:

1. Handle the same product with different personalizations as distinct cart items.
2. Enforce the domain invariant that only `es_removible === true` ingredients may be excluded.
3. Expose checkout-ready selectors (`subtotal`, `costoEnvio`, `total`).
4. Enforce performant slice subscriptions to prevent unnecessary re-renders.

This change is **purely client-side** — no backend changes, no new endpoints.

**Current state** (`frontend-cart-store` spec after Change 05):
- `CartItem`: `{ producto_id, nombre, precio, cantidad, imagen_url, personalizacion: number[] }`
- `addItem` deduplicates by `producto_id` only
- `removeItem(producto_id: number)` — by ID only
- `updateQuantity(producto_id: number, cantidad: number)` — by ID only
- Selectors: `totalItems`, `totalPrice`
- Persistence: `localStorage`, key `food-store-cart`, version `1`

## Goals / Non-Goals

**Goals:**
- Composite item identity: same product + same personalization = same slot in cart
- `es_removible` validation as defense-in-depth in the store (caller validates too)
- Deterministic `itemKey` for all item-scoped actions
- Checkout-compatible selectors: `subtotal`, `costoEnvio`, `total`
- Mandatory slice subscription convention documented and enforceable via code review
- `localStorage` migration from v1 to v2 without runtime errors
- TDD-first: every requirement covered by a vitest unit test written before implementation

**Non-Goals:**
- Any UI component (drawer, badge, page, modal)
- Checkout flow, payment integration, coupon logic
- Backend endpoints or server-side state
- Dynamic `costoEnvio` (delivery quote service is a future change)
- Migrating existing callers from Change 05's `removeItem(id)` / `updateQuantity` signatures (caller migration is Change 15 apply responsibility, not part of the store contract itself)

## Decisions

### D-01: Item equality algorithm (composite identity)

**Problem**: A customer adds "Hamburguesa" plain, then adds "Hamburguesa" without pickles. These must be two separate cart slots.

**Decision**: Two `CartItem` values are considered equivalent if and only if `producto_id` matches AND the normalized `personalizacion` arrays are equal (same set of integers, order-independent, no duplicates).

**Normalization**: `normalizePersonalizacion(arr: string[]): string[]` → `[...new Set(arr)].sort()` (lexicographic — correct for UUID strings).

**Equality check**:
```typescript
function areItemsEquivalent(a: CartItem, b: CartItem): boolean {
  if (a.producto_id !== b.producto_id) return false
  const na = normalizePersonalizacion(a.personalizacion)
  const nb = normalizePersonalizacion(b.personalizacion)
  return na.length === nb.length && na.every((v, i) => v === nb[i])
}
```

**Alternatives considered**:
- JSON.stringify comparison: fragile to insertion order.
- Set symmetric difference: correct but verbose; the sorted array approach is simpler and O(n log n).

---

### D-02: `itemKey` — derivation strategy

**Decision**: `itemKey` is a derived string computed on-demand from a `CartItem`, NOT stored in the `CartItem` shape and NOT persisted.

```typescript
function buildItemKey(item: Pick<CartItem, 'producto_id' | 'personalizacion'>): string {
  const sorted = normalizePersonalizacion(item.personalizacion)
  return `${item.producto_id}::${sorted.join(',')}`
}
```

Examples (using UUID-style string IDs):
- `buildItemKey({ producto_id: "prod-uuid", personalizacion: [] })` → `"prod-uuid::"`
- `buildItemKey({ producto_id: "prod-uuid", personalizacion: ["ing-3", "ing-1"] })` → `"prod-uuid::ing-1,ing-3"` (sorted lexicographically)
- `buildItemKey({ producto_id: "prod-uuid", personalizacion: ["ing-1", "ing-3"] })` → `"prod-uuid::ing-1,ing-3"` (same as above)

**Why not persisted**: It is fully recomputable from the persisted `CartItem` fields. Adding it to the persisted shape would require a migration every time the derivation logic changes and would add redundant data to `localStorage`.

**Why not a field on `CartItem`**: Adding a derived field violates the principle that `CartItem` shape must stay compatible with `DetallePedido` (which has no `itemKey`). Keeping it as a utility function preserves the clean domain shape.

**Alternatives considered**:
- UUID assigned at `addItem` time and persisted: would survive normalization changes but adds complexity, requires migration, and is unnecessary since the key is always recomputable.
- Computed property on `CartItem` at runtime (not persisted): tempting but causes confusion about what is "in state" vs. "derived". The utility function is explicit.

---

### D-03: Validation of `es_removible` — two-layer strategy

**Decision**: Validation occurs at TWO layers:

**Layer 1 — Caller (feature `add-to-cart`)**: Before calling `cartStore.addItem`, the feature component must verify that all IDs in `personalizacion` belong to ingredients with `es_removible === true`. The caller has access to `ProductoIngredienteRead[]` from the product detail query. This is the user-facing UX layer: it prevents UI from ever submitting an invalid exclusion.

**Layer 2 — Store (`cartStore.addItem`)**: The store receives `item: CartItemInput` which includes `personalizacion: number[]`. It also receives `availableIngredients: ProductoIngredienteRead[]` as a second parameter. The store checks that every ID in `personalizacion` maps to an ingredient with `es_removible === true`. If any is invalid, it returns `{ ok: false, reason: 'INGREDIENT_NOT_REMOVABLE' }` without mutating state.

**Important note about `es_removible` data**: The public catalog endpoint returns `IngredientePublicoRead` which intentionally omits `es_removible` (security boundary). The `add-to-cart` feature MUST use the public `fetchProductoIngredientes(id)` fetcher (`GET /api/v1/productos/{id}/ingredientes` — no auth required) which returns `ProductoIngredienteRead[]` including `es_removible`. The admin endpoint MUST NOT be used in the add-to-cart flow — the Cliente role has no ADMIN token. The store cannot be responsible for fetching this data — it must be passed in by the caller.

**ID comparison strategy** (H-01): `CartItem.personalizacion` is `string[]` (UUID strings). `ProductoIngredienteRead.ingrediente_id` is also `string` (UUID). The validation uses **strict string equality** — no type coercion:
```typescript
const invalidIds = personalizacion.filter(id =>
  !availableIngredients.find(i => i.ingrediente_id === id && i.es_removible)
)
```
`CartItemInput` is NOT a separate type — `CartItem` is used directly as the `addItem` parameter.

**Interface**:
```typescript
type AddItemResult =
  | { ok: true }
  | { ok: false; reason: 'INGREDIENT_NOT_REMOVABLE'; invalidIds: string[] }

// Store action signature:
addItem(item: CartItem, availableIngredients: ProductoIngredienteRead[]): AddItemResult
```

**Alternatives considered**:
- Store-only validation without caller validation: caller still shows bad UX if store rejects.
- Caller-only validation: store becomes a passive receiver with no defense; any code path that bypasses the feature can corrupt state.
- Throw instead of return: See D-04.

---

### D-04: Error semantics for `addItem` validation failure

**Decision**: `addItem` returns a **discriminated union** `AddItemResult` instead of throwing.

```typescript
type AddItemResult =
  | { ok: true }
  | { ok: false; reason: 'INGREDIENT_NOT_REMOVABLE'; invalidIds: string[] }
```

**Rationale**: React event handlers that call `addItem` cannot use `try/catch` ergonomically. A discriminated union lets the feature component branch on `result.ok` and render a toast/error message without a try/catch block. This is consistent with the "no exceptions for control flow" principle in the frontend domain.

**Alternatives considered**:
- Throw `AppError`: forces callers into try/catch; bad DX in React components.
- Return `undefined` on success and `Error` on failure: non-standard pattern; harder to narrow types.
- Return `boolean`: loses information about which ingredient IDs were invalid.

---

### D-05: `costoEnvio` in this change

**Decision**: `costoEnvio` is a **computed selector** that returns a **constant `0`** in this change.

```typescript
// In cartStore selectors:
costoEnvio: () => 0,
```

**Rationale**:
- Change 17 (`order-creation-with-snapshots`) hardcodes `costo_envio = 50.00` on the backend for orders where `direccion_id !== NULL`, and `0` for local pickup. The frontend doesn't know at cart time which delivery mode the user will choose.
- A future delivery-quote change (possibly co-located with Change 16 or a dedicated change) will replace this with a dynamic value derived from the selected `DireccionEntrega`.
- Using `0` avoids showing a misleading `$50` cost before the user selects an address.
- The `total` selector is `subtotal + costoEnvio` — when `costoEnvio` becomes dynamic, only the selector implementation changes, not the contract.

**Hook for future change**: The `costoEnvio` selector is purposely exposed from the store so downstream code always reads it from one source. When the future change arrives, it can replace the `() => 0` with a value derived from the delivery context (e.g., injected via a separate store or prop).

**Alternatives considered**:
- `costoEnvio: null` (unknown): requires every consumer to null-check; worse DX.
- `costoEnvio: 50` (backend default): misleading for local pickup; shows incorrect total.
- Not exposing `costoEnvio` yet: Change 33 spec explicitly requires it; omitting it breaks the contract.

---

### D-06: Slice subscriptions — mandatory pattern

**Decision**: All consumers of `cartStore` MUST use selector functions to subscribe only to the slice of state they need. Full-store subscriptions are forbidden.

**Correct pattern**:
```typescript
// Subscribe only to items array
const items = useCartStore(state => state.items)

// Subscribe only to a single selector
const subtotal = useCartStore(state => state.subtotal())

// Subscribe to multiple independent values — use separate hooks
const totalItems = useCartStore(state => state.totalItems())
const clearCart = useCartStore(state => state.clearCart)
```

**Forbidden pattern**:
```typescript
// BAD — causes re-render on ANY store change
const store = useCartStore()
```

**Enforcement**:
1. ESLint rule (if available): `eslint-plugin-zustand` or custom rule rejecting `useCartStore()` with no arguments.
2. Code review checklist item: "All `useCartStore` calls include a selector function argument."
3. Documented in this design.md and the spec delta so reviewers know this is a formalized invariant.

**Why this matters**: Without slice subscriptions, a component subscribing to `total()` re-renders whenever any cart item changes — including re-renders from `clearCart`, `addItem`, and `incrementQuantity` even when the component only shows the total badge. At large cart sizes this compounds.

**Alternatives considered**:
- `shallow` comparisons with full store: reduces re-renders but doesn't prevent them on array mutations; slice subscriptions are stricter.
- Zustand's `subscribeWithSelector` middleware: adds middleware complexity; the selector pattern is sufficient.

---

### D-07: Migration from Change 05 spec (delta strategy)

**What changes** (MODIFIED in delta spec):
- `addItem`: signature `(item, availableIngredients)` → returns `AddItemResult`, equality is composite.
- `removeItem`: signature changes to `removeItem(itemKey: string)`.
- `updateQuantity`: REMOVED — replaced by `incrementQuantity`, `decrementQuantity`, `setQuantity`.
- Selectors: `totalPrice` REMOVED; `subtotal`, `costoEnvio`, `total` ADDED; `totalItems` KEPT.

**What is kept** (unchanged, not in delta):
- `CartItem` base shape: `{ producto_id, nombre, precio, cantidad, imagen_url, personalizacion: number[] }` (snake_case, compatible with `DetallePedido`).
- `clearCart(): void` — behavior unchanged.
- RN-CR02: cart survives logout.
- Persistence key `food-store-cart`, `partialize({ items, version })`.
- FSD location: `src/entities/cart/`.

**What is added** (ADDED in delta spec):
- `es_removible` validation requirement.
- `itemKey` identity requirement.
- Slice subscription requirement.
- Hydration/migration for v1 → v2.

---

### D-08: `CartItem` final shape

**Decision**: `CartItem` shape is updated in this change. `producto_id` and `personalizacion` change from `number`/`number[]` (Change 05 legacy) to `string`/`string[]` to align with the UUID types established in `ProductoPublicoRead.id: string` (Change 12) and `ProductoIngredienteRead.ingrediente_id: string` (Change 11). This is a **Breaking Change** relative to Change 05's spec — the existing code in `entities/cart/types.ts` must be updated at apply time.

```typescript
export interface CartItem {
  producto_id: string        // UUID string — matches ProductoPublicoRead.id
  nombre: string
  precio: number             // unit price at time of add-to-cart (snapshot)
  cantidad: number
  imagen_url: string
  personalizacion: string[]  // sorted, deduplicated UUIDs of excluded ingredient IDs
}
```

**`itemKey` is NOT a field** — it is a utility function result (see D-02).
**No `CartItemInput` alias** — `CartItem` is used directly as the `addItem` parameter type (see D-03).

**Compatibility with `DetallePedido`**: `DetallePedido` requires `producto_id`, `cantidad`, `personalizacion` — all present. `producto_id: string` (UUID) aligns with `DetallePedido.producto_id UUID FK`. `personalizacion: string[]` aligns with the actual UUID-typed `ingrediente.id`. `nombre_snapshot` and `precio_snapshot` are added by the backend at order creation time.

**Note on `personalizacion` storage**: At `addItem` time, the store normalizes `personalizacion` (sorted, deduplicated) before storing, so the persisted value is always in canonical form. This ensures `itemKey` computed from persisted items is identical to `itemKey` computed at `addItem` time.

---

### D-09: Persistence strategy (v1 → v2 migration)

**Key**: `food-store-cart` (unchanged)
**Version**: bumped from `1` to `2`
**Partialize**: `{ items, version }` — derived selectors are NOT persisted

**Migration strategy** (in `onRehydrateStorage` callback):
```typescript
onRehydrateStorage: () => (state) => {
  if (state && state.version !== 2) {
    // Stale v1 data: clear all items and reset to v2
    state.items = []
    state.version = 2
  }
}
```

**Why clear rather than migrate**: v1 items may have been added without normalized `personalizacion`, making `itemKey` derivation unreliable. A clean slate is safer than a potentially inconsistent cart.

**User impact**: Any user with v1 cart data loses their cart on the first load after Change 15 deploy. Acceptable given: (a) the cart is client-side, not purchased, (b) users are informed via the RN-CR02 invariant that cart state is best-effort, and (c) this is a development/staging environment.

**Alternatives considered**:
- Attempt to migrate v1 items: risk of denormalized `personalizacion` causing duplicate items.
- Bump the storage key: leaves stale v1 data in localStorage indefinitely.

---

### D-10: Testing strategy

**Framework**: Vitest + `@testing-library/react` + `jsdom`
**TDD order**: write failing test → implement → green

**Coverage targets by requirement**:

| Requirement | Test file | Coverage target |
|---|---|---|
| `areItemsEquivalent` / `normalizePersonalizacion` | `cartUtils.test.ts` | 100% branches |
| `buildItemKey` | `cartUtils.test.ts` | 100% lines |
| `addItem` — happy path (new item) | `store.test.ts` | ✓ |
| `addItem` — increment on equivalent item | `store.test.ts` | ✓ |
| `addItem` — non-removable ingredient rejected | `store.test.ts` | ✓ |
| `addItem` — different personalization = new slot | `store.test.ts` | ✓ |
| `removeItem(itemKey)` — removes correct item | `store.test.ts` | ✓ |
| `incrementQuantity` / `decrementQuantity` | `store.test.ts` | ✓ |
| `setQuantity(itemKey, 0)` removes item | `store.test.ts` | ✓ |
| `clearCart` | `store.test.ts` | ✓ |
| `subtotal`, `costoEnvio`, `total` selectors | `store.test.ts` | ✓ |
| Persistence: hydration after reload | `store.persist.test.ts` | ✓ |
| Persistence: v1 → v2 migration clears items | `store.persist.test.ts` | ✓ |
| RN-CR02: logout does not clear cart | `store.test.ts` | ✓ |

**Test setup**: Use Zustand's `create` with a `beforeEach` reset pattern:
```typescript
beforeEach(() => {
  useCartStore.setState(initialState)
})
```

## Architecture Overview

```
+------------------+          +----------------------------+
| ProductDetailPage|          | features/cart/add-to-cart  |
| (pages/)         |          | useAddToCart hook          |
|                  |  calls   |                            |
|  useCatalogProduct+-------> | 1. validate es_removible   |
|  (TanStack Query)|          | 2. call addItem(item, ings)|
+------------------+          +-----------+----------------+
                                          |
                              +-----------v----------------+
                              | entities/cart/model/       |
                              | cartStore (Zustand)        |
                              |                            |
                              | State: items[], version    |
                              | Actions: addItem, remove,  |
                              |   increment, decrement,    |
                              |   setQuantity, clearCart   |
                              | Selectors: subtotal,       |
                              |   costoEnvio, total,       |
                              |   totalItems               |
                              +-----------+----------------+
                                          |
                              +-----------v----------------+
                              | Zustand persist middleware |
                              | localStorage               |
                              | key: food-store-cart       |
                              | partialize: {items,version}|
                              +----------------------------+
```

**Flow**: Catalog → Product Detail → AddToCart feature → `cartStore.addItem` → persist to `localStorage`

## FSD Cross-Entity Dependency Note

`entities/cart/` imports `ProductoIngredienteRead` from `entities/products/model/types.ts`. In FSD v2, same-layer cross-entity imports are permitted when there is a genuine domain dependency — the cart's `addItem` validation depends on the product ingredient type. The dependency direction is `cart → products` (cart depends on products, never the reverse). If `eslint-plugin-boundaries` is configured to flag same-layer cross-entity imports, add an explicit exception for `entities/cart → entities/products` in the boundaries config. Verify with `npx eslint src/entities/cart/ --ext .ts` at apply time (task 10.4).

## Data Shapes

### `CartItem` (persisted shape — Breaking Change from Change 05: `producto_id` and `personalizacion` now use `string`)
```typescript
export interface CartItem {
  producto_id: string        // UUID string — Breaking Change from Change 05 (was number)
  nombre: string
  precio: number
  cantidad: number
  imagen_url: string
  personalizacion: string[]  // sorted, deduped UUID strings — Breaking Change from Change 05 (was number[])
}
```

### `AddItemResult` (new)
```typescript
export type AddItemResult =
  | { ok: true }
  | { ok: false; reason: 'INGREDIENT_NOT_REMOVABLE'; invalidIds: string[] }
```

### `CartState` (Zustand state + actions + selectors)
```typescript
interface CartState {
  // Persisted state
  items: CartItem[]
  version: number  // = 2

  // Actions (mutate state)
  addItem(item: CartItem, availableIngredients: ProductoIngredienteRead[]): AddItemResult
  removeItem(itemKey: string): void
  incrementQuantity(itemKey: string): void
  decrementQuantity(itemKey: string): void
  setQuantity(itemKey: string, cantidad: number): void
  clearCart(): void

  // Derived selectors (NOT persisted)
  totalItems(): number
  subtotal(): number
  costoEnvio(): number  // = 0 placeholder; see D-05
  total(): number       // = subtotal() + costoEnvio()
}
```

### `ProductoIngredienteRead` (from `entities/products/model/types.ts`, Change 11)
```typescript
export interface ProductoIngredienteRead {
  ingrediente_id: string
  nombre: string
  es_alergeno: boolean
  es_removible: boolean  // ← key field for validation
}
```

### Cart utility functions (new file: `entities/cart/model/cartUtils.ts`)
```typescript
export function normalizePersonalizacion(ids: string[]): string[]
export function buildItemKey(item: Pick<CartItem, 'producto_id' | 'personalizacion'>): string
export function areItemsEquivalent(a: CartItem, b: CartItem): boolean
```

## Risks / Trade-offs

| Risk | Mitigation |
|---|---|
| Breaking existing callers of `removeItem(producto_id)` | Audit at apply time; TypeScript compiler catches type mismatch |
| v1 localStorage data causes hydration errors | `onRehydrateStorage` migration clears v1 state (D-09) |
| `es_removible` data unavailable at call site (public catalog omits it) | Documented: caller MUST use product detail endpoint including `ProductoIngredienteRead`; enforced by TypeScript via parameter type |
| Slice subscription violation in future PR | Code review checklist + optional ESLint rule; design.md serves as documentation |
| `costoEnvio = 0` confuses users who expect to see delivery cost | Show `costoEnvio` only after address selection (responsibility of checkout UI, not cart store) |

## Migration Plan

1. Change 15 is purely client-side. No database migrations, no API changes.
2. On deploy: existing `v1` localStorage cart data is cleared by `onRehydrateStorage` migration.
3. Callers from Change 05 (`removeItem(id)`, `updateQuantity`) must be updated at apply time — the TypeScript compiler surfaces these as type errors.
4. Rollback: revert to Change 05 `cartStore` — localStorage v2 data is cleared by same migration logic in reverse (version mismatch → clear).

## Open Questions

_(None — all decisions resolved in D-01..D-10. No blocking ambiguities remain for apply phase.)_
