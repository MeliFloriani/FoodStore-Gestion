/**
 * Hook for advancing order state (staff only — PEDIDOS or ADMIN role).
 *
 * Uses TanStack Query useMutation to call PATCH /api/v1/pedidos/{id}/estado.
 * After a successful transition, invalidates relevant query keys.
 *
 * Change 18: staff FSM transitions.
 */

import { useMutation, useQueryClient } from '@tanstack/react-query'
import { transitionEstado, type TransitionEstadoRequest } from '../api/pedidoEstadoApi'
import type { PedidoRead } from '@/features/checkout/model/types'

export interface TransitionEstadoArgs {
  pedidoId: string
  request: TransitionEstadoRequest
}

/**
 * Mutation hook for staff state transitions.
 *
 * @returns TanStack Query mutation with:
 *   - mutateAsync(args): trigger the state transition
 *   - isPending: loading indicator
 *   - isError / error: error state (AxiosError with RFC 7807 body)
 *   - isSuccess / data: success state with updated PedidoRead
 */
export function useTransitionEstado() {
  const queryClient = useQueryClient()

  const mutation = useMutation<PedidoRead, Error, TransitionEstadoArgs>({
    mutationFn: ({ pedidoId, request }) => transitionEstado(pedidoId, request),
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
