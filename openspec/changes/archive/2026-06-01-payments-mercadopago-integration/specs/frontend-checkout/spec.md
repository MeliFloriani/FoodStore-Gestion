## ADDED Requirements

### Requirement: Checkout final step shows PayWithMercadoPagoButton after order creation
The checkout flow SHALL be extended so that after a successful `POST /api/v1/pedidos` (order creation — Change 17), the user is presented with the `<PayWithMercadoPagoButton>` component from `frontend-checkout-payment` to complete payment via MercadoPago Checkout Pro.

The flow SHALL be:
1. User completes order review (Change 16 pre-checkout).
2. `<CheckoutSubmit>` fires `useCreateOrder.mutateAsync(...)` → order created → `PedidoRead` returned.
3. `paymentStore.startCheckout(pedidoId)` is called (sets `checkoutStep` to `'order-summary'`).
4. UI transitions to payment step: `<PayWithMercadoPagoButton pedidoId={pedido.id} className="w-full" />` is rendered.
5. On click: the button generates `idempotency_key = crypto.randomUUID()`, calls `POST /api/v1/pagos`, and redirects the browser to `sandbox_init_point` (dev) or `init_point` (prod).
6. MP redirects back to `/checkout/return?status=<status>&pedido_id=<uuid>` after the user pays.

The `<CheckoutSubmit>` component (Change 17) SHALL NOT be modified to include payment logic — the payment step is a separate UI transition triggered by `onSuccess` of the order creation mutation.

The checkout page (`/checkout`) SHALL be updated to conditionally render either `<CheckoutSubmit>` (step 1) or `<PayWithMercadoPagoButton>` (step 2) based on `paymentStore.checkoutStep`.

**Note**: `<CardPaymentWidget>` and `<MercadoPagoProvider>` are REMOVED. The embedded card payment widget has been replaced by the Checkout Pro redirect flow.

#### Scenario: PayWithMercadoPagoButton rendered after successful order creation
- **WHEN** `useCreateOrder.onSuccess` fires with a new `PedidoRead`
- **THEN** `paymentStore.startCheckout(pedidoId)` is called
- **THEN** the checkout UI transitions to show `<PayWithMercadoPagoButton>`
- **THEN** `<CheckoutSubmit>` is no longer visible

#### Scenario: Payment step is only shown for MERCADOPAGO payment method
- **WHEN** the order was created with `forma_pago_codigo = "MERCADOPAGO"`
- **THEN** `<PayWithMercadoPagoButton>` is rendered in the payment step
- **NOTE**: Cash and transfer flows are out of scope for this change; only MERCADOPAGO triggers the redirect button

#### Scenario: Navigating away from checkout step resets paymentStore
- **WHEN** the user navigates away from the checkout page during the payment step
- **THEN** `paymentStore.resetCheckout()` is called (via `useEffect` cleanup)
- **THEN** `paymentStore.checkoutStep` returns to `"idle"`
- **THEN** if the user returns, they see the initial checkout form (not the payment button mid-flow)

#### Scenario: Existing CheckoutSubmit behavior is preserved
- **WHEN** `<CheckoutSubmit>` is in step 1 (before order creation)
- **THEN** all behaviors from the `frontend-checkout` spec (Change 17) remain valid
- **THEN** the addition of the payment step does NOT alter `useCreateOrder` behavior, cart clearing logic, or error handling of the order creation step

#### Scenario: PaymentStatusScreen is NOT mounted on CheckoutPage
- **WHEN** the user clicks "Pagar con MercadoPago" and is redirected to MP
- **THEN** `<PaymentStatusScreen>` is NOT shown on CheckoutPage
- **THEN** `<PaymentStatusScreen>` IS shown on `/checkout/return` (CheckoutReturnPage) after MP redirects back
