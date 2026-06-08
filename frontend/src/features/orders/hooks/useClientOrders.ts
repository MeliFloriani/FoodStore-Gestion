/**
 * Hook for fetching the authenticated CLIENT's paginated order list (Change 20).
 *
 * Uses TanStack Query useQuery to call GET /api/v1/pedidos.
 * The backend enforces CLIENT isolation server-side (filters by usuario_id).
 *
 * Query key: [...pedidoEstadoKeys.list(), params]
 * This allows invalidation via prefix match ['pedidos'] from useTransitionEstado.
 *
 * IMPORTANT: This hook NEVER sends admin filters (?desde, ?hasta, ?cliente).
 * Only estado, page, and size are forwarded. (D-15 strict role separation)
 */

import { useQuery } from '@tanstack/react-query'
import { listPedidos } from '@/entities/pedido/api/pedidosApi'
import { pedidoEstadoKeys } from '@/entities/pedido/model/pedidoEstadoKeys'
import type { PedidoPage, ClientOrdersParams } from '@/entities/pedido/model/types'

/**
 * Fetch the authenticated CLIENT's paginated order list.
 *
 * @param params - Filter and pagination params (CLIENT-safe only).
 * @returns TanStack Query result with PedidoPage data.
 */
export function useClientOrders(params: ClientOrdersParams = {}) {
  // Explicitly extract only CLIENT-allowed params — never leaks admin filters
  const clientParams: ClientOrdersParams = {
    estado: params.estado,
    page: params.page,
    size: params.size,
  }

  return useQuery<PedidoPage, Error>({
    queryKey: [...pedidoEstadoKeys.list(), clientParams],
    queryFn: () => listPedidos(clientParams),
    staleTime: 30_000,
  })
}
