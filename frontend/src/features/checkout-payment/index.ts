/**
 * checkout-payment feature — public API barrel export.
 *
 * Change 19 — payments-mercadopago-integration (Checkout Pro migration).
 *
 * Public API for the checkout payment feature (FSD strict layering).
 * Pages and widgets import from this barrel only.
 *
 * FSD rule: imports into this feature must only come from entities/ or shared/.
 *
 * Checkout Pro migration:
 *   - CardPaymentWidget removed (was @mercadopago/sdk-react based).
 *   - PayWithMercadoPagoButton added (redirect to MP hosted checkout).
 *   - useCreatePayment kept but delegates to Checkout Pro API.
 */

// Hooks
export { useCreatePayment } from './model/useCreatePayment'
export type { CreatePaymentArgs } from './model/useCreatePayment'
export { usePaymentStatus } from './model/usePaymentStatus'

// UI components
export { PayWithMercadoPagoButton } from './ui/PayWithMercadoPagoButton'
export { PaymentRetryBanner } from './ui/PaymentRetryBanner'
export { PaymentStatusScreen } from './ui/PaymentStatusScreen'
