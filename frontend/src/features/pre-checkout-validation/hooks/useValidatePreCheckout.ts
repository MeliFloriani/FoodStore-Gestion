/**
 * Hook for pre-checkout validation.
 *
 * Uses TanStack Query useMutation to call POST /api/v1/pedidos/validar.
 * Reads items from cartStore (read-only — NEVER calls setters on cartStore).
 * Converts CartItem.precio (number) to string with .toFixed(2) before sending.
 *
 * Design decisions:
 * - D-09: Mutation fires on-mount via useEffect in PreCheckoutReview, not here.
 * - D-03: precio number → string conversion happens here (item.precio.toFixed(2)).
 * - Slice subscription: reads only items slice from cartStore (no full store sub).
 * - CartStore contract: reads items but never calls addItem, removeItem, clearCart.
 */

import { useMutation } from '@tanstack/react-query'
import { useCartStore } from '@/entities/cart/model/store'
import { validatePreCheckout } from '../api/validatePreCheckout'
import type { ItemAValidar, ValidarPreCheckoutResponse } from '../model/types'

/**
 * Custom hook that wraps the pre-checkout validation API call.
 *
 * @returns TanStack Query mutation object exposing:
 *   - mutateAsync: trigger the validation (called with no args from PreCheckoutReview)
 *   - isPending: true while the request is in-flight
 *   - isError: true if the request failed (401, 403, network error)
 *   - isSuccess: true after a successful response
 *   - data: ValidarPreCheckoutResponse on success
 *   - error: AxiosError on failure
 */
export function useValidatePreCheckout() {
  // Read items slice from cartStore using selector (D-slice subscription obligation)
  const items = useCartStore((state) => state.items)

  const mutation = useMutation<ValidarPreCheckoutResponse, Error, void>({
    mutationFn: async () => {
      // Map CartItem[] → ItemAValidar[] with precio as string (D-03)
      const payload: ItemAValidar[] = items.map((item) => ({
        producto_id: item.producto_id,
        cantidad: item.cantidad,
        personalizacion: item.personalizacion,
        precio: item.precio.toFixed(2),
      }))
      return validatePreCheckout(payload)
    },
  })

  return {
    mutateAsync: mutation.mutateAsync,
    isPending: mutation.isPending,
    isError: mutation.isError,
    isSuccess: mutation.isSuccess,
    data: mutation.data,
    error: mutation.error,
  }
}
