/**
 * Barrel export for the pre-checkout-validation feature.
 *
 * Exposes only the public API of the feature:
 * - Hook: useValidatePreCheckout
 * - Component: PreCheckoutReview
 * - Types: ValidarPreCheckoutResponse, CambioRead, ItemValidadoRead, ItemAValidar, TipoCambio
 *
 * Internal implementation details (validatePreCheckout API function, etc.)
 * are NOT re-exported — they are private to the feature.
 */

// Hook
export { useValidatePreCheckout } from './hooks/useValidatePreCheckout'

// Component
export { PreCheckoutReview } from './ui/PreCheckoutReview'

// Public types
export type {
  ValidarPreCheckoutResponse,
  ValidarPreCheckoutRequest,
  CambioRead,
  ItemValidadoRead,
  ItemAValidar,
  TipoCambio,
} from './model/types'
