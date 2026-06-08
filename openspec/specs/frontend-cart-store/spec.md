# frontend-cart-store Specification

## Purpose
Define the Zustand cart store for the Food Store frontend: the canonical `CartItem` type with exact snake_case domain shape (required for checkout `DetallePedido` compatibility), `cartStore` with add/remove/incrementQuantity/decrementQuantity/setQuantity/clearCart actions and derived `totalItems`/`subtotal`/`costoEnvio`/`total` selectors, `localStorage` persistence of `items` and `version` only, and a deliberate RN-CR02 rule that the cart survives user logout. This store is the client-side source of truth for all cart state and is consumed by the shopping and checkout features.

## Requirements

### Requirement: CartItem type with exact domain shape
`src/entities/cart/types.ts` SHALL export a `CartItem` type and `AddItemResult` type with the following exact shapes:

```typescript
export interface CartItem {
  producto_id: string        // UUID string — was number in Change 05
  nombre: string
  precio: number             // unit price at time of add-to-cart
  cantidad: number           // quantity
  imagen_url: string
  personalizacion: string[]  // sorted, deduplicated UUIDs — was number[] in Change 05
}

export type AddItemResult =
  | { ok: true }
  | { ok: false; reason: 'INGREDIENT_NOT_REMOVABLE'; invalidIds: string[] }
```

No additional fields shall be added to `CartItem` without a spec update. The field names SHALL use snake_case to match the backend domain schema.

#### Scenario: CartItem uses string UUID for producto_id
- **WHEN** a `CartItem` is created with `producto_id: "prod-uuid"`
- **THEN** TypeScript accepts the value without error
- **THEN** TypeScript rejects `producto_id: 42` (number) at compile time

#### Scenario: CartItem.personalizacion is string array
- **WHEN** a `CartItem` is created with `personalizacion: ["ing-uuid-1", "ing-uuid-2"]`
- **THEN** TypeScript accepts the value without error
- **THEN** TypeScript rejects `personalizacion: [1, 2]` (number[]) at compile time

#### Scenario: CartItem satisfies checkout input shape
- **WHEN** a `CartItem` value is mapped to a `DetallePedido` create input
- **THEN** all required fields (`producto_id`, `cantidad`, `personalizacion`) are present with correct types

#### Scenario: CartItem has no derived fields
- **WHEN** `CartItem` is inspected
- **THEN** there is no `subtotal`, `total`, or similar derived field in the type definition

---

### Requirement: CartItem identity by itemKey
`src/entities/cart/model/cartUtils.ts` SHALL export a `buildItemKey` function that produces a stable string identifier for a cart item from its `producto_id` and normalized `personalizacion`.

```typescript
export function buildItemKey(item: Pick<CartItem, 'producto_id' | 'personalizacion'>): string
// Example: { producto_id: "prod-uuid", personalizacion: ["ing-3", "ing-1"] } → "prod-uuid::ing-1,ing-3"
// Example: { producto_id: "prod-uuid", personalizacion: [] }                 → "prod-uuid::"
```

All store actions that target a specific item (`removeItem`, `incrementQuantity`, `decrementQuantity`, `setQuantity`) SHALL accept `itemKey: string` and locate the item by recomputing `buildItemKey` for each item in `items`.

#### Scenario: Two items with same product and same personalization have the same itemKey
- **WHEN** `buildItemKey({ producto_id: "prod-5", personalizacion: ["ing-1", "ing-3"] })` is called
- **WHEN** `buildItemKey({ producto_id: "prod-5", personalizacion: ["ing-3", "ing-1"] })` is called
- **THEN** both return the same string value

#### Scenario: Two items with same product but different personalization have different itemKeys
- **WHEN** `buildItemKey({ producto_id: "prod-5", personalizacion: [] })` is called
- **WHEN** `buildItemKey({ producto_id: "prod-5", personalizacion: ["ing-1"] })` is called
- **THEN** they return different string values

#### Scenario: itemKey is stable — recomputable from persisted CartItem fields
- **WHEN** a `CartItem` is retrieved from localStorage after a page reload
- **WHEN** `buildItemKey(item)` is called on the rehydrated item
- **THEN** the result matches the key that was used to identify the item before the reload

---

### Requirement: cartStore state, actions, and selectors
`src/entities/cart/model/store.ts` SHALL export a Zustand store (`cartStore`) with:

**State**:
- `items: CartItem[]`
- `version: number` — for migration compatibility, initialized to `2` (bumped from `1` in Change 05)

**Actions**:
- `addItem(item: CartItem, availableIngredients: ProductoIngredienteRead[]): AddItemResult` — if an equivalent item already exists (same `producto_id` AND same normalized `personalizacion`), increment its `cantidad`. If an ingredient in `personalizacion` is not `es_removible`, return `{ ok: false, reason: 'INGREDIENT_NOT_REMOVABLE', invalidIds: string[] }` without mutating state. On success return `{ ok: true }`.
- `removeItem(itemKey: string): void` — removes the item whose `buildItemKey` matches `itemKey`.
- `incrementQuantity(itemKey: string): void` — increments `cantidad` by 1 for the matching item.
- `decrementQuantity(itemKey: string): void` — decrements `cantidad` by 1; if result is `<= 0`, removes the item.
- `setQuantity(itemKey: string, cantidad: number): void` — sets quantity; if `cantidad <= 0`, removes the item.
- `clearCart(): void` — resets `items` to `[]`

**Selectors** (derived, not stored as state, NOT persisted):
- `totalItems(): number` — sum of all `cantidad` values
- `subtotal(): number` — sum of `precio * cantidad` for all items
- `costoEnvio(): number` — returns `0` (placeholder; dynamic delivery cost is a future change)
- `total(): number` — `subtotal() + costoEnvio()`

**REMOVED from Change 05**:
- `updateQuantity(producto_id: number, cantidad: number): void` — replaced by `incrementQuantity`/`decrementQuantity`/`setQuantity`
- `totalPrice` selector — replaced by `subtotal` and `total`

#### Scenario: addItem increments quantity for equivalent item (same product + same personalization)
- **WHEN** `addItem` is called with a `CartItemInput` whose `producto_id` and `personalizacion` (normalized) match an existing item
- **THEN** the existing item's `cantidad` increases by the added item's `cantidad`
- **THEN** `items.length` does not increase
- **THEN** result is `{ ok: true }`

#### Scenario: addItem creates new slot for same product with different personalization
- **WHEN** `addItem` is called with `{ producto_id: "prod-1", personalizacion: [] }` and cart already has `{ producto_id: "prod-1", personalizacion: ["ing-1"] }`
- **THEN** `items.length` increases by 1
- **THEN** both items are present as distinct slots
- **THEN** result is `{ ok: true }`

#### Scenario: addItem with same personalization in different order is equivalent
- **WHEN** cart has item `{ producto_id: "prod-5", personalizacion: ["ing-3", "ing-1"] }`
- **WHEN** `addItem` is called with `{ producto_id: "prod-5", personalizacion: ["ing-1", "ing-3"] }`
- **THEN** items.length does not increase (treated as same slot)
- **THEN** the existing item's `cantidad` is incremented

#### Scenario: addItem normalizes personalizacion before storing
- **WHEN** `addItem({ producto_id: "prod-1", personalizacion: ["ing-3", "ing-1", "ing-3"], ... }, availableIngredients)` is called with all ingredients removable
- **THEN** result is `{ ok: true }`
- **THEN** the stored item's `personalizacion` equals `["ing-1", "ing-3"]` (sorted lexicographically, deduplicated)

#### Scenario: removeItem by itemKey removes correct item
- **WHEN** cart has two items with different `itemKey` values
- **WHEN** `removeItem(itemKey)` is called with one item's key
- **THEN** only that item is removed; the other remains

#### Scenario: decrementQuantity reduces quantity without removal when cantidad > 1
- **WHEN** an item has `cantidad = 3`
- **WHEN** `decrementQuantity(itemKey)` is called
- **THEN** the item's `cantidad` is `2`
- **THEN** the item is NOT removed from `items`

#### Scenario: decrementQuantity removes item when quantity reaches zero
- **WHEN** an item has `cantidad = 1`
- **WHEN** `decrementQuantity(itemKey)` is called
- **THEN** the item is removed from `items`

#### Scenario: setQuantity with zero removes item
- **WHEN** `setQuantity(itemKey, 0)` is called
- **THEN** the item is removed from `items`

#### Scenario: subtotal is sum of precio times cantidad
- **WHEN** cart has items `[{ precio: 10, cantidad: 2 }, { precio: 5, cantidad: 3 }]`
- **THEN** `subtotal()` returns `35`

#### Scenario: costoEnvio returns zero placeholder
- **WHEN** `costoEnvio()` is called regardless of cart contents
- **THEN** it returns `0`

#### Scenario: total equals subtotal plus costoEnvio
- **WHEN** `subtotal()` is `35` and `costoEnvio()` is `0`
- **THEN** `total()` returns `35`

#### Scenario: clearCart empties the items array
- **WHEN** `clearCart()` is called with items present
- **THEN** `items` equals `[]`
- **THEN** `totalItems()` returns `0`
- **THEN** `subtotal()` returns `0`

---

### Requirement: es_removible validation in addItem
`cartStore.addItem` SHALL validate that every ingredient ID in `personalizacion` corresponds to an ingredient with `es_removible === true` in the provided `availableIngredients` array. If any ID fails this check, the action SHALL return `{ ok: false, reason: 'INGREDIENT_NOT_REMOVABLE', invalidIds: string[] }` and SHALL NOT mutate `items`.

The validation is defense-in-depth: the calling feature component is responsible for validating `es_removible` at the UX layer before calling `addItem`. Both layers must validate (see design.md D-03).

#### Scenario: addItem with removable ingredient succeeds
- **GIVEN** `availableIngredients = [{ ingrediente_id: "ing-uuid-1", es_removible: true, ... }]`
- **WHEN** `addItem({ ..., personalizacion: ["ing-uuid-1"] }, availableIngredients)` is called
- **THEN** result is `{ ok: true }`
- **THEN** `items` contains the new item

#### Scenario: addItem with non-removable ingredient is rejected
- **GIVEN** `availableIngredients = [{ ingrediente_id: "ing-uuid-2", es_removible: false, ... }]`
- **WHEN** `addItem({ ..., personalizacion: ["ing-uuid-2"] }, availableIngredients)` is called
- **THEN** result is `{ ok: false, reason: 'INGREDIENT_NOT_REMOVABLE', invalidIds: ["ing-uuid-2"] }`
- **THEN** `items` is unchanged

#### Scenario: addItem with empty personalizacion always succeeds (no exclusions)
- **WHEN** `addItem({ ..., personalizacion: [] }, availableIngredients)` is called
- **THEN** result is `{ ok: true }` regardless of `availableIngredients` contents

#### Scenario: addItem with unknown ingredient ID is rejected
- **GIVEN** `availableIngredients` does not contain an ingredient with `ingrediente_id: "ing-unknown"`
- **WHEN** `addItem({ ..., personalizacion: ["ing-unknown"] }, availableIngredients)` is called
- **THEN** result is `{ ok: false, reason: 'INGREDIENT_NOT_REMOVABLE', invalidIds: ["ing-unknown"] }`

---

### Requirement: cartStore persistence (items and version only)
`cartStore` SHALL use Zustand `persist` middleware with `storage: localStorage`. The `partialize` function SHALL include only `items` and `version`. Storage key: `food-store-cart`. The `version` field SHALL be `2` (bumped from `1` in Change 05). The `onRehydrateStorage` callback SHALL migrate v1 data: if `state.version !== 2`, clear `items` and reset `version` to `2`.

#### Scenario: Cart persists across page reload (v2 data)
- **WHEN** a user adds items to the cart with valid personalization and reloads the page
- **THEN** the same items (with `nombre`, `precio`, `imagen_url`, `personalizacion`) are present in `cartStore.getState().items`

#### Scenario: Full item data is hydrated (not just IDs)
- **WHEN** localStorage contains a serialized cart item with `{ nombre: "Pizza", precio: 12.50, imagen_url: "...", ... }`
- **WHEN** the page is reloaded
- **THEN** `cartStore.getState().items[0].nombre` is `"Pizza"` and `precio` is `12.50`

#### Scenario: Derived selectors are not stored
- **WHEN** localStorage is inspected after cart operations
- **THEN** the stored value does NOT contain `subtotal`, `costoEnvio`, `total`, or `totalItems` fields

#### Scenario: v1 data triggers migration and clears cart
- **WHEN** localStorage contains `{ version: 1, items: [...] }`
- **WHEN** the page is reloaded
- **THEN** `onRehydrateStorage` detects `version !== 2` and resets `items` to `[]` and `version` to `2`

---

### Requirement: Slice subscription obligation for cartStore consumers
All React components and hooks that consume `cartStore` SHALL use selector functions. Direct full-store subscriptions (`useCartStore()` with no argument) are forbidden.

```typescript
// CORRECT — only re-renders when items changes
const items = useCartStore(state => state.items)

// CORRECT — subscribe to a computed selector
const subtotal = useCartStore(state => state.subtotal())

// FORBIDDEN — re-renders on any store mutation
const store = useCartStore()
```

This constraint SHALL be enforced via:
1. Code review checklist item documented in design.md.
2. (Optional) `eslint-plugin-zustand` or equivalent ESLint rule.

#### Scenario: Consumer subscribes to items slice only
- **WHEN** a component uses `useCartStore(state => state.items)`
- **THEN** the component only re-renders when `items` reference changes
- **THEN** changes to unrelated state (if any were added) do not cause re-renders

#### Scenario: Consumer subscribes to subtotal selector
- **WHEN** a component uses `useCartStore(state => state.subtotal())`
- **THEN** the component re-renders only when `subtotal()` returns a different value
- **THEN** adding an item with `precio=0, cantidad=1` does not cause a re-render if `subtotal` value is unchanged (edge case: `precio=0` items exist)

---

### Requirement: Cart survives logout/login cycle (RN-CR02)
The cart SHALL survive user logout and re-login. Since the cart persists in `localStorage` independently of auth state, `cartStore.logout()` or `authStore.logout()` SHALL NOT call `cartStore.clearCart()`.

#### Scenario: Cart items remain after logout
- **WHEN** a user has items in cart and `authStore.logout()` is called
- **THEN** `cartStore.getState().items` is unchanged
