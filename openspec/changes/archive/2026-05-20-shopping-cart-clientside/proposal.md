## Why

The Food Store shopping flow requires a robust, fully client-side cart before checkout (Change 16) and order creation (Change 17) can be built. The foundational `cartStore` introduced in Change 05 (`frontend-core-foundation`) covers only the bare minimum: it increments by `producto_id` alone, ignores personalization equality, lacks `es_removible` validation, and exposes only `totalItems`/`totalPrice`. Change 15 upgrades this store to production-grade: composite item identity (product + personalization), ingredient removability validation, a complete action surface, and the derived selectors required for checkout UI — all still 100% client-side, zero backend endpoints.

**Why now**: Change 14 (delivery addresses) is archived. The critical path to checkout (Changes 16–17) is unblocked and depends on a correct cart contract. Every day without this change delays the entire checkout sprint.

## What Changes

- **CartItem equality** changes from `producto_id`-only to composite `(producto_id, personalizacion)` — order-independent, normalized array comparison.
- **`itemKey`** is introduced as a derived identifier (computed in-memory, NOT persisted) to uniquely address an item regardless of position in the `items` array.
- **`addItem` action** now validates `es_removible === true` for every ingredient in `personalizacion`; returns a discriminated-union result `{ ok: boolean, reason?: string }`.
- **`removeItem` action** changes signature from `removeItem(producto_id)` to `removeItem(itemKey)`.
- **Quantity actions** split into `incrementQuantity(itemKey)`, `decrementQuantity(itemKey)`, and `setQuantity(itemKey, n)` — quantity reaching 0 auto-removes the item.
- **Selectors** replace `totalItems`/`totalPrice` with `subtotal`, `costoEnvio`, and `total`; `totalItems` is kept as a convenience count.
- **Persistence** remains `localStorage` key `food-store-cart` with `partialize({ items, version })`; derived selectors are NOT persisted; `version` bumps to `2`.
- **Slice-subscription convention** is formalized: consumers MUST use selector functions, never the full store reference.
- **`clearCart` action** is retained unchanged.
- **RN-CR02** (cart survives logout) is retained unchanged.

**Breaking changes relative to Change 05 spec**:
- `BREAKING` — `removeItem` signature changes from `(producto_id: number)` to `(itemKey: string)`.
- `BREAKING` — `updateQuantity` is removed; replaced by `incrementQuantity` / `decrementQuantity` / `setQuantity`.
- `BREAKING` — `addItem` return type changes from `void` to `AddItemResult`.
- `BREAKING` — `totalPrice` selector removed; replaced by `subtotal`/`total`.
- `BREAKING` — `version` bumps from `1` to `2`; migration clears stale `v1` state on hydration.

## Capabilities

### New Capabilities

_(None — no entirely new spec. All work is a delta on the existing `frontend-cart-store` spec.)_

### Modified Capabilities

- `frontend-cart-store`: Core behavioral changes to item equality, action signatures, selector surface, validation layer, and persistence version. This delta replaces several foundational requirements from Change 05 while preserving RN-CR02 and the persistence strategy.

## Impact

**Frontend files affected** (implementation-time):
- `frontend/src/entities/cart/model/store.ts` — full rewrite of actions and selectors
- `frontend/src/entities/cart/types.ts` — `CartItem` shape stable; `AddItemResult` type added
- `frontend/src/entities/cart/model/cartUtils.ts` — new: `areItemsEquivalent`, `buildItemKey`, `normalizePersonalizacion`

**Downstream (apply time, not this change)**:
- `features/cart/add-to-cart/` — will call `cartStore.addItem` and handle `AddItemResult`
- Changes 16–17 — depend on `CartItem` shape being compatible with `DetallePedido` (unchanged snake_case contract)

**Specs affected**:
- `openspec/specs/frontend-cart-store/spec.md` — delta applied from `openspec/changes/shopping-cart-clientside/specs/frontend-cart-store/spec.md`

**Packages / dependencies**: No new npm packages. Zustand persist middleware already installed in Change 05.

## User Stories Covered

| Story | Title | How this change covers it |
|---|---|---|
| US-029 | Agregar producto al carrito | `addItem` with composite identity + persistence |
| US-030 | Personalizar producto (exclusión de ingredientes) | `es_removible` validation + `personalizacion: number[]` in `CartItem` |
| US-031 | Modificar cantidad de ítem | `incrementQuantity` / `decrementQuantity` / `setQuantity` with auto-remove at 0 |
| US-032 | Eliminar ítem del carrito | `removeItem(itemKey)` |
| US-033 | Ver resumen del carrito | `subtotal`, `costoEnvio`, `total` selectors; `totalItems` |
| US-034 | Vaciar carrito | `clearCart()` |

## Dependencies

| Change | Name | Status | Why needed |
|---|---|---|---|
| Change 05 | `frontend-core-foundation` | Archived 2026-05-14 | Base Zustand setup, persist middleware, FSD structure, Axios interceptor |
| Change 12 | `catalog-public-browsing` | Archived 2026-05-19 | `ProductoPublicoDetalleRead` with `ingredientes[].es_removible` exposed; cart add-to-cart features consume this type |

## Non-Goals (explicit)

- **No UI components**: No cart drawer, cart badge, cart page, or any React component. Those belong to future UI changes.
- **No checkout flow**: Checkout validation (Change 16) and order creation (Change 17) are out of scope.
- **No payment logic**: MercadoPago integration is Change 19.
- **No coupon / discount logic**: Not in scope for v1.
- **No backend endpoints**: The cart is 100% client-side. Zero new API routes.
- **No server-side persistence**: Cart lives in `localStorage` only.
- **No dynamic `costoEnvio`**: A placeholder value (`0`) is used; real delivery quote logic is deferred to a future change (likely Change 17 or a dedicated delivery-cost change).
- **No cart UI pages**: Drawer, summary page, and mini-cart badge are intentionally excluded. This change delivers only the state layer.

## Risks

| # | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| R-01 | Breaking existing code that calls `removeItem(producto_id)` or `updateQuantity` | High (if any code was written) | High | Audit `entities/cart` and `features/` for callers at apply time; update call sites atomically |
| R-02 | `localStorage` hydration of v1 data causes runtime errors on version bump | Medium | Medium | `version` migration in `onRehydrateStorage` clears state when `version !== 2`; documented in D-09 |
| R-03 | `es_removible` data missing at call site (catalog returns `IngredientePublicoRead` which lacks `es_removible`) | Medium | High | The `add-to-cart` feature MUST use the public `fetchProductoIngredientes(id)` fetcher (`GET /api/v1/productos/{id}/ingredientes` — no auth required) which returns `ProductoIngredienteRead[]` including `es_removible`. The `ProductoPublicoDetalleRead.ingredientes` array uses `IngredientePublicoRead` which intentionally omits `es_removible` — it MUST NOT be used for validation. The admin endpoint MUST NOT be used in the add-to-cart flow — the Cliente role has no ADMIN token. |
