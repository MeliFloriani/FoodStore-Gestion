## MODIFIED Requirements

### Requirement: paymentStore.pedidoId type corrected to string (UUID)

The original `frontend-ui-payment-stores` spec (Change 05) defined `pedidoId` as `number | null` and `startCheckout(pedidoId: number)`. This Change 19 delta corrects the type to `string | null` (UUID) to align with the actual `Pedido.id` field type (UUID stored as string in TypeScript).

**Affected fields and actions** in `src/shared/store/paymentStore.ts`:

- `pedidoId: string | null` — MODIFIED from `number | null`. The pedido ID is a UUID string, not a numeric integer. Initialized to `null`.
- `startCheckout(pedidoId: string): void` — MODIFIED from `startCheckout(pedidoId: number)`. Accepts a UUID string. Sets `checkoutStep` to `'order-summary'` and stores `pedidoId` in state.

All other `paymentStore` fields, actions, and behaviors remain unchanged from the original spec.

> **Checkout Pro update**: The `startCheckout()` action is called after order creation (from `useCreateOrder.onSuccess`). It stores the `pedidoId` and advances `checkoutStep` to `'order-summary'`, which triggers rendering of `<PayWithMercadoPagoButton>`. The `preferenceId` field is retained in the store schema for forward compatibility. The `startCheckout()` action remains a UI state stub only — no networking.

> **Removed reference**: The legacy spec reference to `POST /api/v1/pedidos/{id}/payment-preference` and `card_token` storage in the store do NOT apply. Change 19 uses `POST /api/v1/pagos` with only `{ pedido_id, idempotency_key }`. Card data never touches the browser — Checkout Pro.

#### Scenario: startCheckout accepts UUID string and stores it correctly
- **WHEN** `paymentStore.getState().startCheckout("a3b4c5d6-1234-5678-abcd-ef0123456789")` is called
- **THEN** `paymentStore.getState().checkoutStep` is `'order-summary'`
- **THEN** `paymentStore.getState().pedidoId` is `"a3b4c5d6-1234-5678-abcd-ef0123456789"` (string UUID)

#### Scenario: pedidoId is null on initialization and after reset
- **WHEN** the store is initialized or `reset()` / `resetCheckout()` is called
- **THEN** `paymentStore.getState().pedidoId` is `null`

#### Scenario: PayWithMercadoPagoButton receives pedidoId as string prop
- **WHEN** `<PayWithMercadoPagoButton pedidoId={paymentStore.pedidoId} ...>` is rendered after `startCheckout` was called
- **THEN** `pedidoId` prop is a UUID string (e.g. `"a3b4c5d6-..."`)
- **THEN** `POST /api/v1/pagos` body includes `pedido_id: "a3b4c5d6-..."` (string UUID, not a number)

#### Scenario: setStatus transitions used by CheckoutReturnPage
- **WHEN** `CheckoutReturnPage` mounts and reads `?status=pending` from MP back_url
- **THEN** `paymentStore.setStatus('pending')` is called
- **WHEN** `usePaymentStatus` polling detects `estado_codigo = "CONFIRMADO"`
- **THEN** `paymentStore.setStatus('success')` is called and polling stops
- **WHEN** `?status=failure` is in back_url params
- **THEN** `paymentStore.setStatus('failed')` is called
