/**
 * Hook for fetching all orders for PEDIDOS/ADMIN roles (Change 20).
 *
 * Uses TanStack Query useQuery to call GET /api/v1/pedidos with admin filters.
 * The backend applies filters based on the authenticated user's PEDIDOS/ADMIN role.
 *
 * Query key: ['pedidos', 'admin', params]
 * Kept separate from pedidoEstadoKeys.list() to avoid contaminating the
 * CLIENT cache with admin filter variants.
 *
 * D-10: ?cliente= filter is only sent when >= 3 characters to prevent
 * full-table scans on the backend.
 */

import { useQuery } from '@tanstack/react-query'
import { listPedidos } from '@/entities/pedido/api/pedidosApi'
import type { PedidoPage, AdminOrdersParams } from '@/entities/pedido/model/types'

/**
 * Fetch a paginated list of all orders (PEDIDOS/ADMIN only).
 *
 * @param params - Filter and pagination params. cliente is omitted if < 3 chars.
 * @returns TanStack Query result with PedidoPage data.
 */
export function useAdminOrders(params: AdminOrdersParams = {}) {
  // D-10: omit cliente if fewer than 3 characters
  const effectiveParams: AdminOrdersParams = {
    ...params,
    cliente:
      params.cliente && params.cliente.length >= 3 ? params.cliente : undefined,
  }

  return useQuery<PedidoPage, Error>({
    queryKey: ['pedidos', 'admin', effectiveParams],
    queryFn: () => listPedidos(effectiveParams),
    staleTime: 30_000,
  })
}
