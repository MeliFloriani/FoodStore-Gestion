/**
 * Hook for fetching a single order's full detail (Change 20).
 *
 * Uses TanStack Query useQuery to call GET /api/v1/pedidos/{id}.
 *
 * Query key: pedidoEstadoKeys.detail(pedidoId) = ['pedido', pedidoId]
 *
 * This key is IDENTICAL to the key used by usePaymentStatus (Change 19),
 * which uses queryKey: ['pago-status', pedidoId] for the payment poll.
 * Wait — usePaymentStatus actually uses ['pago-status', pedidoId] NOT ['pedido', pedidoId].
 * This hook uses ['pedido', pedidoId], which matches useTransitionEstado's invalidation.
 *
 * Error propagation: 403 and 404 are NOT caught here — they propagate as
 * query.error so the page can redirect to /403 or /404 respectively.
 */

import { useQuery } from '@tanstack/react-query'
import { getPedidoDetail } from '@/entities/pedido/api/pedidosApi'
import { pedidoEstadoKeys } from '@/entities/pedido/model/pedidoEstadoKeys'
import type { PedidoDetail } from '@/entities/pedido/model/types'

/**
 * Fetch the full detail of a single order.
 *
 * @param pedidoId - UUID of the order, or null/undefined to disable.
 * @returns TanStack Query result with PedidoDetail data.
 */
export function useOrderDetail(pedidoId: string | null | undefined) {
  return useQuery<PedidoDetail, Error>({
    queryKey: pedidoEstadoKeys.detail(pedidoId ?? ''),
    queryFn: () => getPedidoDetail(pedidoId!),
    enabled: !!pedidoId,
    staleTime: 30_000,
    retry: false,
  })
}
