## 1. Setup & Structure

- [x] 1.1 Create directory `frontend/src/entities/cart/model/` if not already present (verify FSD structure from Change 05)
- [x] 1.2 Create `frontend/src/entities/cart/model/cartUtils.ts` as a new empty file with module exports scaffold
- [x] 1.3 Read `frontend/src/entities/cart/types.ts` and confirm `CartItem` shape is unchanged; add `AddItemResult` type export
- [x] 1.4 Verify `ProductoIngredienteRead` is imported-ready from `entities/products/model/types.ts` (no circular dependency)

---

## 2. Types (TDD — types first, tests second, implementation third)

- [x] 2.1 Export `AddItemResult` discriminated union from `frontend/src/entities/cart/types.ts`:
  `{ ok: true } | { ok: false; reason: 'INGREDIENT_NOT_REMOVABLE'; invalidIds: string[] }`
- [x] 2.2 Update `CartItem` in `frontend/src/entities/cart/types.ts`: change `producto_id: number` → `string` and `personalizacion: number[]` → `string[]` (Breaking Change from Change 05 — required for UUID alignment with `ProductoPublicoRead.id` and `ProductoIngredienteRead.ingrediente_id`)
- [x] 2.3 Confirm NO `CartItemInput` alias is exported — `CartItem` is used directly as the `addItem` parameter type. Remove the alias if it was created in Change 05.

**Maps to**: D-08 (shape), delta spec `CartItem identity`, `es_removible validation`
**US**: US-029, US-030

---

## 3. Cart Utilities — Tests First

- [x] 3.1 Write `frontend/src/entities/cart/model/cartUtils.test.ts`:
  - Test `normalizePersonalizacion(["ing-3", "ing-1", "ing-3"])` → `["ing-1", "ing-3"]` (dedup + lexicographic sort)
  - Test `normalizePersonalizacion([])` → `[]`
  - Test `buildItemKey({ producto_id: "prod-uuid", personalizacion: ["ing-3", "ing-1"] })` → `"prod-uuid::ing-1,ing-3"`
  - Test `buildItemKey({ producto_id: "prod-uuid", personalizacion: [] })` → `"prod-uuid::"`
  - Test `buildItemKey` is order-independent (same result for `["ing-1","ing-3"]` and `["ing-3","ing-1"]`)
  - Test `areItemsEquivalent` — true when same product + same (unordered) personalization (string IDs)
  - Test `areItemsEquivalent` — false when different product
  - Test `areItemsEquivalent` — false when same product, different personalization
- [x] 3.2 Implement `normalizePersonalizacion(ids: number[]): number[]` in `cartUtils.ts`
- [x] 3.3 Implement `buildItemKey(item): string` in `cartUtils.ts`
- [x] 3.4 Implement `areItemsEquivalent(a, b): boolean` in `cartUtils.ts`
- [x] 3.5 Run `cartUtils.test.ts` — all green

**Maps to**: Spec delta `CartItem identity by itemKey` (D-01, D-02)
**US**: US-029, US-031, US-032

---

## 4. cartStore — Tests First (core actions)

- [x] 4.1 Write `frontend/src/entities/cart/model/store.test.ts` — `addItem` suite (use string UUIDs in all test data — `producto_id: "prod-uuid"`, `personalizacion: ["ing-uuid-1"]`, `ingrediente_id: "ing-uuid-1"`):
  - New item is added to `items`
  - Equivalent item (same product + same personalization, different order) increments `cantidad`
  - Same product + different personalization creates new slot
  - Non-removable ingredient returns `{ ok: false, reason: 'INGREDIENT_NOT_REMOVABLE', invalidIds: string[] }` and does not mutate
  - Unknown ingredient ID (string UUID not in availableIngredients) returns `{ ok: false }` and does not mutate
  - Empty `personalizacion: []` always returns `{ ok: true }`
  - `personalizacion` is normalized before storing: `["ing-3", "ing-1", "ing-3"]` → stored as `["ing-1", "ing-3"]`
- [x] 4.2 Write `store.test.ts` — `removeItem` suite:
  - `removeItem(itemKey)` removes correct item; other items remain
  - `removeItem` with unknown key is a no-op
- [x] 4.3 Write `store.test.ts` — quantity actions suite:
  - `incrementQuantity(itemKey)` increments by 1
  - `decrementQuantity(itemKey)` decrements by 1; at `cantidad=1` removes item
  - `setQuantity(itemKey, 3)` sets to 3
  - `setQuantity(itemKey, 0)` removes item
  - `setQuantity(itemKey, -1)` removes item (treats negative as 0)
- [x] 4.4 Write `store.test.ts` — `clearCart` suite:
  - `clearCart()` resets `items` to `[]`
  - `totalItems()` returns 0 after clear
- [x] 4.5 Write `store.test.ts` — RN-CR02 suite:
  - Simulate `authStore.logout()` call; assert `cartStore.getState().items` is unchanged

**Maps to**: Spec delta MODIFIED `addItem`, MODIFIED `removeItem`, MODIFIED quantity actions, `es_removible` validation
**US**: US-029, US-030, US-031, US-032, US-034

---

## 5. cartStore — Implementation (core actions)

- [x] 5.1 Rewrite `frontend/src/entities/cart/model/store.ts`:
  - State: `{ items: CartItem[], version: 2 }`
  - Import and use `areItemsEquivalent`, `buildItemKey`, `normalizePersonalizacion` from `cartUtils.ts`
  - Implement `addItem(item, availableIngredients)` with validation + composite equality
  - Implement `removeItem(itemKey)` — locate by `buildItemKey`
  - Implement `incrementQuantity(itemKey)`, `decrementQuantity(itemKey)`, `setQuantity(itemKey, n)`
  - Implement `clearCart()`
  - Remove `updateQuantity` action
- [x] 5.2 Run `store.test.ts` — all green

**Maps to**: All MODIFIED requirements in spec delta
**US**: US-029–US-034

---

## 6. Selectors — Tests First

- [x] 6.1 Write `store.test.ts` — selectors suite:
  - `totalItems()` = sum of all `cantidad`
  - `subtotal()` = sum of `precio * cantidad` for all items (two items case)
  - `subtotal()` = 0 when cart is empty
  - `costoEnvio()` = 0 always (constant placeholder)
  - `total()` = `subtotal() + costoEnvio()`
- [x] 6.2 Implement selectors in `store.ts`:
  - `totalItems(): number`
  - `subtotal(): number`
  - `costoEnvio(): number` → return `0`
  - `total(): number` → `subtotal() + costoEnvio()`
- [x] 6.3 Confirm selectors are NOT included in `partialize`
- [x] 6.4 Run selectors tests — all green

**Maps to**: Spec delta MODIFIED selectors (D-05); REMOVED `totalPrice`
**US**: US-033

---

## 7. Persistence — Tests First

- [x] 7.1 Write `frontend/src/entities/cart/model/store.persist.test.ts`:
  - Mock `localStorage`; assert persisted value contains `items` and `version: 2`
  - Assert persisted value does NOT contain `subtotal`, `costoEnvio`, `total`, `totalItems`
  - Assert full item data is persisted (`nombre`, `precio`, `imagen_url` present in localStorage)
  - Assert `version: 1` data in localStorage triggers migration: `items` cleared, `version` set to `2`
  - Assert RN-CR02: cart items remain after simulated logout (authStore logout does not call clearCart)
- [x] 7.2 Configure `persist` middleware in `store.ts`:
  - Key: `food-store-cart`
  - Storage: `localStorage`
  - `partialize: (state) => ({ items: state.items, version: state.version })`
  - **Do NOT set `version` in the persist middleware config object and do NOT use the `migrate` function** — the Zustand built-in versioning mechanism is not used here. Migration is handled exclusively via `state.version` (a plain state field) checked inside the `onRehydrateStorage` callback.
  - `onRehydrateStorage`: check `state.version !== 2` → clear `items`, set `version = 2` (migrate v1 → v2)
- [x] 7.3 Run `store.persist.test.ts` — all green

**Maps to**: Spec delta MODIFIED persistence, v1→v2 migration (D-09)
**US**: US-029, US-031

---

## 8. Validation Layer Documentation (no code — review artifact)

- [x] 8.1 Add inline JSDoc comment to `addItem` in `store.ts` explaining the two-layer validation strategy (D-03): caller validates UX, store validates defense-in-depth
- [x] 8.2 Add inline comment on `costoEnvio` explaining the placeholder and hook for future delivery-cost change (D-05)
- [x] 8.3 Add comment block at top of `store.ts` with slice-subscription example and forbidden pattern (D-06)

**Maps to**: D-03, D-05, D-06

---

## 9. Barrel Exports & FSD Compliance

- [x] 9.1 Update `frontend/src/entities/cart/index.ts` to export:
  - `CartItem`, `AddItemResult` from `./types`
  - `useCartStore` from `./model/store`
  - `buildItemKey`, `normalizePersonalizacion`, `areItemsEquivalent` from `./model/cartUtils`
- [x] 9.2 Verify `entities/cart/` does NOT import from `features/`, `pages/`, or `widgets/`
- [x] 9.3 Verify `eslint-plugin-boundaries` reports no violations for `entities/cart/` (run `npx eslint src/entities/cart/` if configured)

**Maps to**: FSD compliance, D-06 slice subscription convention
**US**: All (structural)

---

## 10. Tests Coverage & Final Run

- [x] 10.1 Run full test suite: `npx vitest run src/entities/cart/`
- [x] 10.2 Confirm all scenarios from spec delta have at least one passing test (map each `#### Scenario` to a test)
- [x] 10.3 Confirm no TypeScript errors: `npx tsc --noEmit` in `frontend/`
- [x] 10.4 Confirm no ESLint boundary violations: `npx eslint src/entities/cart/ --ext .ts,.tsx`

**Maps to**: D-10 (testing strategy)
**US**: US-029–US-034

---

## Task ↔ Requirement ↔ US Mapping

| Task Group | Spec Delta Requirements | User Stories |
|---|---|---|
| 2 (Types) | `CartItem` shape, `AddItemResult` type | US-029, US-030 |
| 3 (Cart Utils) | `CartItem identity by itemKey` | US-029, US-031, US-032 |
| 4–5 (Store Core) | MODIFIED `addItem`, MODIFIED `removeItem`, MODIFIED quantity actions, `es_removible` validation | US-029, US-030, US-031, US-032, US-034 |
| 6 (Selectors) | MODIFIED selectors (`subtotal`, `costoEnvio`, `total`), REMOVED `totalPrice` | US-033 |
| 7 (Persistence) | MODIFIED persistence (v2, migration, full item data) | US-029, US-031 |
| 8 (Docs) | D-03, D-05, D-06 in-code documentation | — |
| 9 (FSD) | Slice subscription obligation, FSD boundary compliance | All US |
| 10 (Coverage) | All spec scenarios → tests | All US |
