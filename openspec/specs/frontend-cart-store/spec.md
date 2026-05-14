# frontend-cart-store Specification

## Purpose
Define the Zustand cart store for the Food Store frontend: the canonical `CartItem` type with exact snake_case domain shape (required for checkout `DetallePedido` compatibility), `cartStore` with add/remove/updateQuantity/clearCart actions and derived `totalItems`/`totalPrice` selectors, `localStorage` persistence of `items` and `version` only, and a deliberate RN-CR02 rule that the cart survives user logout. This store is the client-side source of truth for all cart state and is consumed by the shopping and checkout features.

## Requirements

### Requirement: CartItem type with exact domain shape
`src/entities/cart/types.ts` SHALL export a `CartItem` type with the following exact shape (required for compatibility with the checkout `DetallePedido` schema):

```
CartItem {
  producto_id: number
  nombre: string
  precio: number          // unit price at time of add-to-cart
  cantidad: number        // quantity
  imagen_url: string
  personalizacion: number[]  // array of ingredient IDs to exclude
}
```

No additional fields shall be added to `CartItem` without a spec update. The field names SHALL use snake_case to match the backend domain schema.

#### Scenario: CartItem satisfies checkout input shape
- **WHEN** a `CartItem` value is mapped to a `DetallePedido` create input
- **THEN** all required fields (`producto_id`, `cantidad`, `personalizacion`) are present with correct types

#### Scenario: CartItem has no derived fields
- **WHEN** `CartItem` is inspected
- **THEN** there is no `subtotal`, `total`, or similar derived field in the type definition

---

### Requirement: cartStore state, actions, and selectors
`src/entities/cart/model/store.ts` SHALL export a Zustand store (`cartStore`) with:

**State**:
- `items: CartItem[]`
- `version: number` — for future migration compatibility, initialized to `1`

**Actions**:
- `addItem(item: CartItem): void` — if `producto_id` already exists in `items`, increment `cantidad`; do not duplicate.
- `removeItem(producto_id: number): void` — removes the item with matching `producto_id`
- `updateQuantity(producto_id: number, cantidad: number): void` — sets quantity; if `cantidad <= 0`, removes the item
- `clearCart(): void` — resets `items` to `[]`

**Selectors** (derived, not stored as state):
- `totalItems` — sum of all `cantidad` values
- `totalPrice` — sum of `precio * cantidad` for all items

#### Scenario: addItem increments quantity for duplicate product
- **WHEN** `addItem` is called with a `CartItem` whose `producto_id` is already in `items`
- **THEN** the existing item's `cantidad` increases by the added item's `cantidad`
- **THEN** `items` length does not increase

#### Scenario: removeItem deletes the correct item
- **WHEN** `removeItem(producto_id)` is called
- **THEN** the item with that `producto_id` is no longer in `items`

#### Scenario: updateQuantity with zero removes item
- **WHEN** `updateQuantity(producto_id, 0)` is called
- **THEN** the item is removed from `items`

#### Scenario: clearCart empties the items array
- **WHEN** `clearCart()` is called with items present
- **THEN** `items` equals `[]`

---

### Requirement: cartStore persistence (items and version only)
`cartStore` SHALL use Zustand `persist` middleware with `storage: localStorage`. The `partialize` function SHALL include only `items` and `version`. Storage key: `food-store-cart`.

#### Scenario: Cart persists across page reload
- **WHEN** a user adds items to the cart and reloads the page
- **THEN** the same items are present in `cartStore.getState().items`

#### Scenario: Derived values are not stored
- **WHEN** localStorage is inspected after cart operations
- **THEN** the stored value does NOT contain `totalItems` or `totalPrice` fields

---

### Requirement: Cart survives logout/login cycle (RN-CR02)
The cart SHALL survive user logout and re-login. Since the cart persists in `localStorage` independently of auth state, `cartStore.logout()` or `authStore.logout()` SHALL NOT call `cartStore.clearCart()`.

#### Scenario: Cart items remain after logout
- **WHEN** a user has items in cart and `authStore.logout()` is called
- **THEN** `cartStore.getState().items` is unchanged
