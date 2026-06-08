/**
 * Hook for fetching order state history.
 *
 * Uses TanStack Query useQuery to call GET /api/v1/pedidos/{id}/historial.
 * Returns the history ordered by created_at ASC (as returned by the backend).
 *
 * Change 18: GET /pedidos/{id}/historial.
 */

import { useQuery } from '@tanstack/react-query'
import { getHistorialPedido } from '../api/pedidoEstadoApi'
import type { HistorialEstadoPedidoRead } from '@/entities/pedido/model/historialTypes'

/**
 * Query hook for order state history.
 *
 * Only fetches when pedidoId is truthy (guards against undefined in conditional renders).
 * Stale time is kept short (30s) since historial can change with state transitions.
 *
 * @param pedidoId - UUID of the order, or null/undefined to disable the query.
 * @returns TanStack Query result with historial data.
 */
export function useHistorialPedido(pedidoId: string | null | undefined) {
  return useQuery<HistorialEstadoPedidoRead[], Error>({
    queryKey: ['pedido-historial', pedidoId],
    queryFn: () => getHistorialPedido(pedidoId!),
    enabled: !!pedidoId,
    staleTime: 30_000,  // 30 seconds
  })
}
