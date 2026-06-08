/**
 * Hook for transactional order creation (Change 17).
 *
 * Uses TanStack Query useMutation to call POST /api/v1/pedidos.
 *
 * Design decisions:
 * - D-09 / Nota R-01: CartItem.personalizacion (string[] of UUID strings) is passed
 *   directly as exclusiones — NO parseInt, NO conversion. parseInt("uuid") === NaN.
 * - D-11: Does NOT include subtotal, costo_envio, or total in the request — the
 *   backend calculates them server-side.
 * - D-13: clearCart() is called ONLY in onSuccess — never on error.
 * - Slice subscription: reads only items slice from cartStore (D-slice obligation).
 *   The hook does NOT subscribe to the full store — only state.items.
 */

import { useMutation } from '@tanstack/react-query'
import { useCartStore } from '@/entities/cart/model/store'
import { createOrder } from '../api/createOrder'
import type { CreateOrderRequest, PedidoRead } from '../model/types'

/** Arguments passed to mutateAsync() */
export interface CreateOrderArgs {
  forma_pago_codigo: string
  direccion_id: string | null
  notas?: string
}

/**
 * Custom hook for creating a transactional order.
 *
 * @returns TanStack Query mutation object exposing:
 *   - mutateAsync: trigger the order creation with CreateOrderArgs
 *   - isPending: true while the request is in-flight
 *   - isError: true if the request failed (400, 403, 409, network)
 *   - isSuccess: true after HTTP 201 response
 *   - data: PedidoRead on success
 *   - error: AxiosError on failure (contains RFC 7807 body with code)
 */
export function useCreateOrder() {
  // Slice subscription — only re-renders when items change (D-slice obligation)
  const items = useCartStore((state) => state.items)
  const clearCart = useCartStore((state) => state.clearCart)

  const mutation = useMutation<PedidoRead, Error, CreateOrderArgs>({
    mutationFn: async (args: CreateOrderArgs) => {
      // Map CartItem[] → OrderItemRequest[]
      // personalizacion (string[] of UUID strings) → exclusiones (string[])
      // NO parseInt — they are UUID strings, not integers (D-09 / Nota R-01)
      const request: CreateOrderRequest = {
        items: items.map((item) => ({
          producto_id: item.producto_id,
          cantidad: item.cantidad,
          exclusiones: item.personalizacion,  // UUID strings — no conversion
        })),
        forma_pago_codigo: args.forma_pago_codigo,
        direccion_id: args.direccion_id,
        notas: args.notas,
      }
      return createOrder(request)
    },
    onSuccess: () => {
      // D-13: clearCart only on success — never on error
      clearCart()
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
