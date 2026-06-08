/**
 * Hook for client self-cancellation (CLIENT role only).
 *
 * Uses TanStack Query useMutation to call DELETE /api/v1/pedidos/{id}.
 * After a successful cancellation, invalidates relevant query keys.
 *
 * Change 18: client DELETE /pedidos/{id}.
 */

import { useMutation, useQueryClient } from '@tanstack/react-query'
import { cancelarPedidoCliente } from '../api/pedidoEstadoApi'
import type { PedidoRead } from '@/features/checkout/model/types'

export interface CancelarPedidoArgs {
  pedidoId: string
  motivo: string
}

/**
 * Mutation hook for client order self-cancellation.
 *
 * motivo is required by the backend (RN-05). This hook does NOT enforce
 * motivo validation — use CancelReasonModal to collect and validate the reason
 * before calling mutateAsync.
 *
 * @returns TanStack Query mutation with:
 *   - mutateAsync({ pedidoId, motivo }): trigger cancellation
 *   - isPending: loading indicator
 *   - isError / error: error state (AxiosError with RFC 7807 body)
 *   - isSuccess / data: success state with cancelled PedidoRead
 */
export function useCancelarPedidoCliente() {
  const queryClient = useQueryClient()

  const mutation = useMutation<PedidoRead, Error, CancelarPedidoArgs>({
    mutationFn: ({ pedidoId, motivo }) => cancelarPedidoCliente(pedidoId, motivo),
    onSuccess: (_data, variables) => {
      // Invalidate pedido queries so lists and detail views refresh
      queryClient.invalidateQueries({ queryKey: ['pedidos'] })
      queryClient.invalidateQueries({
        queryKey: ['pedido', variables.pedidoId],
      })
      queryClient.invalidateQueries({
        queryKey: ['pedido-historial', variables.pedidoId],
      })
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
