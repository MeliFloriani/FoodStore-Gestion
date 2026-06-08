# frontend-payment-polling Specification

## Purpose
`usePaymentStatus` TanStack Query hook polling `GET /api/v1/pedidos/{pedido_id}/latest` every 30s while order is `PENDIENTE`. Provides CheckoutReturnPage that handles the MP back_url redirect after Checkout Pro payment. Introduced in Change 19 (payments-mercadopago-integration).

## ADDED Requirements

### Requirement: usePaymentStatus polling hook
The system SHALL provide `usePaymentStatus(pedidoId: string | null)` in `src/features/checkout-payment/model/usePaymentStatus.ts` using TanStack Query `useQuery`.

The hook SHALL:
- Query `GET /api/v1/pedidos/{pedidoId}` using the Axios client.
- Use `queryKey: ["pedido", pedidoId]`.
- Use `refetchInterval: 30_000` (30 seconds).
- Use `enabled: pedidoId !== null && paymentStore.status === 'pending'` — polling is active ONLY while the payment store indicates a pending state. Polling SHALL also be disabled when `paymentStore.status` is `'success'`, `'failed'`, or `'idle'`.
- Stop polling automatically when `data.estado_codigo` is not `"PENDIENTE"` (i.e., any terminal or post-pending state: `CONFIRMADO`, `ENTREGADO`, `CANCELADO`, `EN_PREP`, etc.). Implementation: set `refetchInterval: (query) => (query.state.data?.estado_codigo === "PENDIENTE" ? 30_000 : false)`.
- On terminal states detected via polling: update `paymentStore.status` accordingly — see scenarios below.
- The UI SHALL NOT show a retry banner if the pedido is already in a terminal state (`CANCELADO`, `ENTREGADO`).
- Return `{ data: PedidoPollingResult | undefined, isLoading, isError, refetch }`.

`PedidoPollingResult` SHALL be typed as:
```typescript
interface PedidoPollingResult {
  id: string
  estado_codigo: string      // "PENDIENTE" | "CONFIRMADO" | ...
  updated_at: string
}
```

**Checkout Pro context**: This hook is mounted on `/checkout/return` (`CheckoutReturnPage`) after the user returns from MercadoPago's hosted payment page via `back_urls`. The hook polls the pedido state while awaiting webhook-triggered confirmation. The `paymentStore.status` is set to `'pending'` by `CheckoutReturnPage` on mount (when `?status=pending` or `?status=approved` is in the query params).

The hook SHALL NOT be used for order history display (that belongs to Change 20). Its sole purpose is detecting when `estado_codigo` transitions from `PENDIENTE`.

#### Scenario: Hook polls every 30 seconds while order is PENDIENTE
- **WHEN** `usePaymentStatus("some-pedido-id")` is called with `paymentStore.status = "pending"`
- **THEN** `GET /api/v1/pedidos/{pedidoId}` is called every 30 seconds
- **THEN** the hook remains active as long as `estado_codigo === "PENDIENTE"`

#### Scenario: Hook stops polling when CONFIRMADO is detected
- **WHEN** the backend returns `estado_codigo = "CONFIRMADO"` in the query response
- **THEN** `refetchInterval` returns `false` (polling stops)
- **THEN** no further `GET /api/v1/pedidos/{pedidoId}` requests are sent

#### Scenario: Hook is disabled when pedidoId is null
- **WHEN** `usePaymentStatus(null)` is called
- **THEN** the query `enabled` is `false`
- **THEN** no HTTP requests are made

#### Scenario: Hook is disabled when paymentStore.status is not 'pending'
- **WHEN** `paymentStore.status = "idle"` or `"success"` or `"failed"`
- **THEN** `enabled` is `false`
- **THEN** no polling occurs

#### Scenario: CANCELADO terminal state sets paymentStore status to failed and stops polling
- **WHEN** polling returns `data.estado_codigo === "CANCELADO"`
- **THEN** `paymentStore.setStatus('failed')` is called
- **THEN** `refetchInterval` returns `false` (polling stops)
- **THEN** the UI MUST NOT show a retry banner (the order is terminal — no further payment is possible)
- **THEN** the UI shows an informational message indicating the order was cancelled

#### Scenario: ENTREGADO terminal state sets paymentStore status to success and stops polling
- **WHEN** polling returns `data.estado_codigo === "ENTREGADO"`
- **THEN** `paymentStore.setStatus('success')` is called
- **THEN** `refetchInterval` returns `false` (polling stops)
- **THEN** the success UI is shown (order delivered)

---

### Requirement: CheckoutReturnPage — handles MP back_url return
The system SHALL provide `src/pages/checkout/ui/CheckoutReturnPage.tsx`. This page:

- Is mounted at route `/checkout/return`.
- Reads `useSearchParams()`: `status` (from MP back_url) and `pedido_id` (from MP back_url `external_reference`).
- On mount (`useEffect`):
  - Calls `paymentStore.startCheckout(pedidoId)` with the `pedido_id` from search params.
  - Maps `?status=approved` → `paymentStore.setStatus('success')`.
  - Maps `?status=pending` or no status → `paymentStore.setStatus('pending')`.
  - Maps `?status=failure` → `paymentStore.setStatus('failed')`.
- Renders `<PaymentStatusScreen>` with the polling hook active.
- Cleanup: calls `paymentStore.resetCheckout()` on unmount.

**Note**: The `?status=` from MP's back_url is used only for UX (initial screen state). The webhook is the sole source of truth for order state transitions. The page polls `GET /api/v1/pedidos/{pedidoId}` for confirmation.

#### Scenario: CheckoutReturnPage shows pending UI on return from MP
- **WHEN** MP redirects to `/checkout/return?status=pending&pedido_id=<uuid>`
- **THEN** `paymentStore.setStatus('pending')` is called
- **THEN** `<PaymentStatusScreen>` shows the spinner and "Procesando tu pago..." message
- **THEN** polling starts for `GET /api/v1/pedidos/{pedidoId}` every 30s

#### Scenario: CheckoutReturnPage shows success UI when polling detects CONFIRMADO
- **WHEN** `usePaymentStatus` returns `estado_codigo = "CONFIRMADO"`
- **THEN** `paymentStore.setStatus('success')` is called
- **THEN** the success UI is displayed with the order ID

#### Scenario: CheckoutReturnPage shows failure UI on failure return
- **WHEN** MP redirects to `/checkout/return?status=failure&pedido_id=<uuid>`
- **THEN** `paymentStore.setStatus('failed')` is called
- **THEN** `<PaymentStatusScreen>` shows the rejection message
- **THEN** a "Reintentar pago" button is visible

---

### Requirement: PaymentStatusScreen component
The system SHALL provide `<PaymentStatusScreen>` in `src/features/checkout-payment/ui/PaymentStatusScreen.tsx` that displays the current payment/order status to the user after returning from MercadoPago.

The component SHALL:
- Render one of three states based on `paymentStore.status` and `usePaymentStatus` polling result:
  1. **Pending**: "Procesando tu pago..." with a spinner. Shows "Estamos esperando confirmación de MercadoPago."
  2. **Confirmed** (`estado_codigo = "CONFIRMADO"`): Success screen. "¡Tu pedido fue confirmado!" with the order ID and a link to order details (pending Change 20 — show order ID as text for now).
  3. **Failed/Rejected**: "El pago fue rechazado." with `mp_status_detail` reason and a "Reintentar pago" button that navigates back to `/checkout`.
- When `estado_codigo = "CONFIRMADO"` is detected via polling: call `paymentStore.setStatus('success')`.
- The component SHALL include a note for `pending` state: "Esto puede demorar hasta 30 segundos." to set user expectations.

#### Scenario: Pending state shows spinner and message
- **WHEN** `paymentStore.status = "pending"` and polling has not yet detected CONFIRMADO
- **THEN** a spinner is visible
- **THEN** the message "Procesando tu pago..." is displayed

#### Scenario: Success state shown when CONFIRMADO detected
- **WHEN** `usePaymentStatus` returns `estado_codigo = "CONFIRMADO"`
- **THEN** `paymentStore.setStatus('success')` is called
- **THEN** the success UI is displayed with the order ID
- **THEN** the spinner disappears

#### Scenario: Failed state shows retry option (navigates to /checkout)
- **WHEN** `paymentStore.status = "failed"`
- **THEN** an error message is displayed with the rejection reason
- **THEN** a "Reintentar pago" button is visible
- **THEN** clicking the button navigates the user back to `/checkout` where `<PayWithMercadoPagoButton>` is rendered

#### Scenario: Polling stops when success is shown
- **WHEN** success state is displayed
- **THEN** no further polling requests are made (hook disabled after CONFIRMADO)
