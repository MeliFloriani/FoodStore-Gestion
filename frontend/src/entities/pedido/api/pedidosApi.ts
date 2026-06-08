/**
 * API functions for orders listing and detail (Change 20).
 *
 * Calls:
 *   GET /api/v1/pedidos           — paginated listing (CLIENT or PEDIDOS/ADMIN)
 *   GET /api/v1/pedidos/{id}      — full detail
 *
 * The http client (shared/api/http.ts) attaches the Bearer token automatically.
 */

import { http } from '@/shared/api/http'
import type {
  PedidoPage,
  PedidoDetail,
  ClientOrdersParams,
  AdminOrdersParams,
} from '../model/types'

/**
 * Fetch a paginated list of orders.
 *
 * For CLIENT callers, the backend always filters by the authenticated user's id.
 * Admin-specific filters (desde, hasta, cliente) are silently ignored if the
 * caller is CLIENT — the hook layer enforces this separately.
 *
 * @param params - Optional filter and pagination params.
 * @returns Page<PedidoListItem> from the backend.
 */
export async function listPedidos(
  params: ClientOrdersParams | AdminOrdersParams = {},
): Promise<PedidoPage> {
  // Build query params, omitting undefined values
  const queryParams: Record<string, string | number> = {}

  if (params.estado) queryParams.estado = params.estado
  if (params.page !== undefined) queryParams.page = params.page
  if (params.size !== undefined) queryParams.size = params.size

  // Admin-only params (narrowed — only present in AdminOrdersParams)
  const adminParams = params as AdminOrdersParams
  if (adminParams.desde) queryParams.desde = adminParams.desde
  if (adminParams.hasta) queryParams.hasta = adminParams.hasta
  // cliente requires min 3 chars — enforcement is also done in useAdminOrders
  if (adminParams.cliente && adminParams.cliente.length >= 3) {
    queryParams.cliente = adminParams.cliente
  }

  const response = await http.get<PedidoPage>('/api/v1/pedidos', {
    params: queryParams,
  })
  return response.data
}

/**
 * Fetch the full detail of a single order.
 *
 * @param pedidoId - UUID of the order.
 * @returns PedidoDetail with items, historial, direccion, pago.
 * @throws AxiosError 403 if CLIENT accesses another user's order.
 * @throws AxiosError 404 if the order does not exist.
 */
export async function getPedidoDetail(pedidoId: string): Promise<PedidoDetail> {
  const response = await http.get<PedidoDetail>(`/api/v1/pedidos/${pedidoId}`)
  return response.data
}
