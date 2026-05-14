# frontend-ui-payment-stores Specification

## Purpose
Define the Zustand UI and payment stores for the Food Store frontend: `uiStore` with theme (persisted via `partialize`), sidebar, and toast queue (all other fields ephemeral), and `paymentStore` with checkout-flow state (preferenceId, pedidoId, status, checkoutStep) that is strictly transitional and never persisted. These stores separate global UI concerns from payment-flow concerns and enforce the constraint that `startCheckout()` is a UI state signal only — no networking belongs in the store layer.

## Requirements

### Requirement: uiStore with theme, sidebar, and toast queue
`src/shared/store/uiStore.ts` SHALL export a Zustand store (`uiStore`) with:

**State**:
- `theme: 'light' | 'dark'` — initialized to `'light'`
- `sidebarOpen: boolean` — initialized to `false`
- `toasts: Toast[]` — initialized to `[]`

Where `Toast` SHALL be a type with at minimum: `id: string`, `message: string`, `type: 'success' | 'error' | 'warning' | 'info'`.

**Actions**:
- `setTheme(theme: 'light' | 'dark'): void`
- `toggleTheme(): void`
- `setSidebarOpen(open: boolean): void`
- `toggleSidebar(): void`
- `addToast(toast: Omit<Toast, 'id'>): void` — generates `id` internally (e.g., `crypto.randomUUID()`)
- `removeToast(id: string): void`

#### Scenario: toggleTheme switches between light and dark
- **WHEN** `uiStore.getState().toggleTheme()` is called with `theme: 'light'`
- **THEN** `uiStore.getState().theme` becomes `'dark'`

#### Scenario: addToast adds to queue with generated ID
- **WHEN** `addToast({ message: 'Saved', type: 'success' })` is called
- **THEN** `uiStore.getState().toasts` contains one item with `message: 'Saved'` and a non-empty `id`

#### Scenario: removeToast removes by ID
- **WHEN** `removeToast(id)` is called with a valid toast `id`
- **THEN** `uiStore.getState().toasts` no longer contains an item with that `id`

---

### Requirement: uiStore SHALL persist exclusively the theme field via partialize
`uiStore` SHALL use the Zustand `persist` middleware with `partialize: (s) => ({ theme: s.theme })`. No other `uiStore` field SHALL be persisted. Storage: `localStorage`, key `food-store-ui-theme`. All fields other than `theme` are ephemeral and reset to initial values on page reload.

#### Scenario: theme is restored after page reload
- **WHEN** the user toggles theme to `dark` and reloads the page
- **THEN** `uiStore.getState().theme` returns `'dark'` (restored from localStorage on rehydration)

#### Scenario: modal and sidebar state is not persisted
- **WHEN** the user opens a modal or sidebar and reloads the page
- **THEN** `uiStore.getState().sidebarOpen` is `false` and `uiStore.getState().toasts` is `[]` (not restored — ephemeral)

#### Scenario: uiStore resets non-theme fields on reload
- **WHEN** the page reloads
- **THEN** `uiStore.getState().toasts` is `[]` and `sidebarOpen` is `false`

---

### Requirement: paymentStore with checkout flow state
`src/shared/store/paymentStore.ts` SHALL export a Zustand store (`paymentStore`) with:

**State**:
- `preferenceId: string | null` — MercadoPago preference ID, set when checkout is initiated
- `pedidoId: number | null` — ID of the order being paid. Set by `startCheckout(pedidoId)`. Used by the checkout feature to call `POST /api/v1/pedidos/{id}/payment-preference`. Initialized to `null`.
- `status: 'idle' | 'pending' | 'processing' | 'success' | 'failed'` — initialized to `'idle'`
- `lastErrorCode: string | null` — last error code from payment provider or backend
- `checkoutStep: 'idle' | 'order-summary' | 'payment' | 'confirmation'` — tracks the current step of the checkout flow. Defaults to `'idle'`.

**Actions**:
- `setPreferenceId(id: string): void`
- `setStatus(status: PaymentStatus): void`
- `setLastErrorCode(code: string | null): void`
- `reset(): void` — resets all fields to initial values
- `startCheckout(pedidoId: number): void` — sets `checkoutStep` to `'order-summary'` and stores `pedidoId` in state. **This is a UI state transition stub only — no networking. The actual API call to create a payment preference belongs to the checkout feature, not the foundation store.**
- `advanceStep(step: 'payment' | 'confirmation'): void` — moves checkout to a later step.
- `resetCheckout(): void` — alias to `reset()` that also resets `checkoutStep` to `'idle'`.

> **Constraint — UI state only**: `startCheckout()` is a UI state transition — it does NOT call any API. The actual backend call to `POST /api/v1/pedidos/{id}/payment-preference` belongs to the `checkout-payment` feature. The store receives the result (preferenceId) via `setPreferenceId()` after the API call completes.

#### Scenario: setPreferenceId stores the preference ID
- **WHEN** `paymentStore.getState().setPreferenceId('pref_abc123')` is called
- **THEN** `paymentStore.getState().preferenceId` equals `'pref_abc123'`

#### Scenario: reset returns store to initial state
- **WHEN** `paymentStore.getState().reset()` is called after setting some fields
- **THEN** `preferenceId` is `null`, `status` is `'idle'`, `lastErrorCode` is `null`

#### Scenario: startCheckout transitions to order-summary step and stores pedidoId
- **WHEN** `startCheckout(42)` is called
- **THEN** `checkoutStep` is `'order-summary'`
- **THEN** `pedidoId` is `42`

#### Scenario: resetCheckout returns checkout to idle
- **WHEN** `resetCheckout()` is called
- **THEN** `checkoutStep` is `'idle'`, `preferenceId` is `null`, `pedidoId` is `null`, `status` is `'idle'`

#### Scenario: Consumer contract on navigation away
- **WHEN** the component unmounts or user navigates away from checkout
- **THEN** `resetCheckout()` SHALL be called (consumer contract — not an enforced store requirement)

---

### Requirement: paymentStore has no localStorage persistence
`paymentStore` SHALL NOT use the Zustand `persist` middleware. Payment flow state (including `checkoutStep`, `preferenceId`, `status`, and `lastErrorCode`) is strictly transitional and SHALL NOT survive page reload. This prevents stale payment state from interfering with a new checkout session.

#### Scenario: paymentStore resets on reload
- **WHEN** a user sets `preferenceId` and reloads the page
- **THEN** `paymentStore.getState().preferenceId` is `null`

#### Scenario: checkoutStep resets on reload
- **WHEN** a user is in `checkoutStep: 'payment'` and reloads the page
- **THEN** `paymentStore.getState().checkoutStep` is `'idle'`
