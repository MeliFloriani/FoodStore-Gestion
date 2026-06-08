# frontend-checkout-payment Specification

## Purpose
`PayWithMercadoPagoButton` redirect in checkout final step, `usePaymentStatus` polling hook, payment success/error UI. Introduced in Change 19 (payments-mercadopago-integration). Replaces the embedded `<CardPaymentWidget>` approach with MercadoPago Checkout Pro redirect flow.

## ADDED Requirements

### Requirement: PayWithMercadoPagoButton component (Checkout Pro)
The system SHALL provide `<PayWithMercadoPagoButton>` in `src/features/checkout-payment/ui/PayWithMercadoPagoButton.tsx`. This component:

- Accepts props: `pedidoId: string`, `className?: string`.
- On click:
  1. Generates `idempotency_key = crypto.randomUUID()`.
  2. Calls `useCreatePayment.mutateAsync({ idempotency_key })` (pedido_id comes from `paymentStore.pedidoId`).
  3. Determines redirect URL: if `import.meta.env.DEV || import.meta.env.VITE_MP_USE_SANDBOX === 'true'`, use `response.sandbox_init_point`; otherwise use `response.init_point`.
  4. Sets `window.location.href = redirectUrl`.
- While `isPending`: button is disabled with a loading spinner.
- On mutation error: shows an inline error message.
- Button color: `#009ee3` (MercadoPago blue).

**Note**: `@mercadopago/sdk-react`, `<MercadoPagoProvider>`, and `<CardPaymentWidget>` are REMOVED. Checkout Pro hosts the payment form on MP's own pages — no browser card tokenization.

#### Scenario: PayWithMercadoPagoButton redirects to sandbox_init_point in dev
- **WHEN** `import.meta.env.DEV` is `true` and `POST /api/v1/pagos` returns `sandbox_init_point`
- **THEN** `window.location.href` is set to `sandbox_init_point`

#### Scenario: PayWithMercadoPagoButton redirects to init_point in production
- **WHEN** `import.meta.env.DEV` is `false` and `VITE_MP_USE_SANDBOX !== 'true'`
- **THEN** `window.location.href` is set to `init_point`

#### Scenario: Button is disabled while request is in-flight
- **WHEN** `mutateAsync` is in flight (`isPending = true`)
- **THEN** the button is disabled
- **THEN** a loading spinner is visible
- **THEN** the user cannot click the button again (prevents double-submit)

#### Scenario: Button shows error on mutation failure
- **WHEN** `POST /api/v1/pagos` returns an error (4xx or 502)
- **THEN** an inline error message is displayed below the button
- **THEN** the button is re-enabled for retry

#### Scenario: idempotency_key is generated fresh on each click
- **WHEN** the user clicks "Pagar con MercadoPago"
- **THEN** `crypto.randomUUID()` is called to generate a new `idempotency_key`
- **THEN** the generated key is passed as `idempotency_key` in `PagoCreateRequest`

---

### Requirement: useCreatePayment mutation hook (Checkout Pro)
The system SHALL provide `useCreatePayment()` in `src/features/checkout-payment/model/useCreatePayment.ts` using TanStack Query `useMutation`.

The hook SHALL:
- Send `POST /api/v1/pagos` using the Axios client from `frontend-http-client`.
- Accept mutation variables: `{ idempotency_key: string }` (no card fields).
- Read `pedido_id` from `paymentStore.pedidoId` inside the mutation function.
- Return `{ mutateAsync, isPending, isError, isSuccess, data, error }`.
- On error: call `paymentStore.setStatus('failed')` and `paymentStore.setLastErrorCode(errorCode)`.

**Note**: The hook no longer calls `paymentStore.setStatus('pending')` after mutation success — the redirect to MP's hosted page happens immediately, and status is read from the back_url on return.

#### Scenario: Hook sends POST /api/v1/pagos with correct body
- **WHEN** `mutateAsync({ idempotency_key: "some-uuid-string" })` is called
- **THEN** an HTTP POST request is sent to `/api/v1/pagos` with `{ pedido_id: "<uuid>", idempotency_key: "<uuid>" }`
- **THEN** the request includes the Authorization header (via Axios interceptor)

#### Scenario: Hook response includes init_point and sandbox_init_point
- **WHEN** `POST /api/v1/pagos` returns HTTP 201
- **THEN** `data.init_point` is a non-null string (URL to MP live checkout)
- **THEN** `data.sandbox_init_point` is a non-null string (URL to MP sandbox checkout)
- **THEN** `data.mp_payment_id` is `null` (not assigned until webhook fires)

#### Scenario: Hook updates paymentStore on failure
- **WHEN** `POST /api/v1/pagos` returns an error response
- **THEN** `paymentStore.setStatus('failed')` is called
- **THEN** `paymentStore.setLastErrorCode` is called with the error code from the response

---

### Requirement: Payment retry flow (Checkout Pro)
The system SHALL support payment retry when a payment is `rejected`. The retry flow:

1. User returns to `/checkout/return?status=failure&pedido_id=<uuid>` after MP rejects the payment.
2. `CheckoutReturnPage` maps the `?status=failure` to `paymentStore.setStatus('failed')`.
3. The `<PaymentStatusScreen>` shows a rejection message with a "Reintentar pago" button.
4. On click: redirects user back to the checkout page (`/checkout`) where `<PayWithMercadoPagoButton>` is rendered again.
5. The pedido MUST still be in `PENDIENTE` state for retry to be valid. If the pedido is no longer `PENDIENTE`, show an appropriate message.

#### Scenario: Retry button shown on failed return status
- **WHEN** `paymentStore.status = "failed"` is detected on `/checkout/return`
- **THEN** a retry banner/button is visible with the status detail message

#### Scenario: Retry creates new payment for same pedido
- **WHEN** user returns to checkout and clicks "Pagar con MercadoPago" again
- **THEN** a new `idempotency_key` is generated via `crypto.randomUUID()`
- **THEN** `POST /api/v1/pagos` is called with the same `pedido_id`
- **THEN** a new Pago row is created on the backend with the new `idempotency_key`
- **THEN** the previous rejected Pago row is preserved (1:N relationship)

---

### Requirement: Payment UI state integration with paymentStore
The `<PayWithMercadoPagoButton>` and checkout payment feature SHALL use the existing `paymentStore` (Change 05 — `frontend-ui-payment-stores`) for in-flight state management. No new store is created.

The feature SHALL call:
- `paymentStore.startCheckout(pedidoId)` after order creation (from `useCreateOrder` onSuccess in Change 17) to transition the store to `order-summary` step.
- `paymentStore.setStatus('pending')` when `CheckoutReturnPage` mounts (user is back from MP, awaiting webhook).
- `paymentStore.setStatus('success')` when polling detects `estado_codigo = "CONFIRMADO"`.
- `paymentStore.setStatus('failed')` when `?status=failure` is in back_url params.
- `paymentStore.resetCheckout()` when the user navigates away from the payment pages.

Sensitive card data (PAN, CVV) SHALL NEVER be stored in `paymentStore` or any other Zustand store (they never reach the browser — Checkout Pro).

#### Scenario: paymentStore.startCheckout called after order creation
- **WHEN** `useCreateOrder.onSuccess` fires with the new pedido
- **THEN** `paymentStore.startCheckout(pedidoId)` is called
- **THEN** `paymentStore.pedidoId` equals the new pedido's id

#### Scenario: paymentStore resets on navigation away
- **WHEN** the user navigates away from the checkout payment page
- **THEN** `paymentStore.resetCheckout()` is called (via `useEffect` cleanup)
- **THEN** `paymentStore.status` returns to `"idle"`

---

### Requirement: pagosApi — HTTP client functions for pagos (Checkout Pro)
The system SHALL provide `src/entities/pago/api/pagosApi.ts` with typed Axios call functions:

- `createPayment(data: PagoCreateRequest): Promise<PagoResponse>` — calls `POST /api/v1/pagos`.
- `getLatestPayment(pedidoId: string): Promise<PagoResponse>` — calls `GET /api/v1/pagos/{pedidoId}/latest`.

Both functions SHALL use the configured Axios instance (with JWT interceptor from `frontend-http-client`). All errors are propagated as-is (TanStack Query handles them).

`PagoResponse` type SHALL be defined in `src/entities/pago/model/types.ts`:
```typescript
export interface PagoResponse {
  id: string
  pedido_id: string
  mp_payment_id: number | null
  mp_preference_id: string | null
  preference_id: string | null
  init_point: string | null
  sandbox_init_point: string | null
  mp_status: 'pending' | 'approved' | 'rejected' | 'in_process' | 'cancelled'
  mp_status_detail: string | null
  idempotency_key: string
  external_reference: string
  monto: string | null
  created_at: string
}

export interface PagoCreateRequest {
  pedido_id: string
  idempotency_key: string   // client-generated via crypto.randomUUID() — min 8 chars
}
```

#### Scenario: createPayment sends authenticated POST request with Checkout Pro body
- **WHEN** `createPayment({ pedido_id: "uuid", idempotency_key: "uuid" })` is called
- **THEN** a `POST /api/v1/pagos` request is sent with an `Authorization: Bearer <token>` header
- **THEN** the request body contains `{ pedido_id, idempotency_key }` (no card fields)
- **THEN** the response is typed as `PagoResponse` with `init_point` and `sandbox_init_point`

#### Scenario: getLatestPayment returns PagoResponse or throws 404
- **WHEN** `getLatestPayment(pedidoId)` is called for a pedido with a Pago
- **THEN** the latest `PagoResponse` is returned
- **WHEN** `getLatestPayment(pedidoId)` is called for a pedido with no Pago
- **THEN** an Axios error is thrown with HTTP 404 status
