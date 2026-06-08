/**
 * API function for listing the authenticated user's orders (Change 20).
 *
 * Calls GET /api/v1/pedidos via the configured Axios http client.
 * The http client (shared/api/http.ts) automatically attaches the Bearer token
 * and handles 401 refresh queue.
 *
 * Returns the same PedidoRead shape as POST /api/v1/pedidos — full payload
 * including items, historial, and monetary fields as decimal strings (D-09).
 */

import { http } from '@/shared/api/http'
import type { PedidoRead } from '@/features/checkout/model/types'

/**
 * Fetch the authenticated user's own orders from the backend.
 *
 * Orders are returned sorted by created_at DESC (most recent first).
 *
 * @param limit  Maximum number of orders to fetch (default 50, backend cap).
 * @param offset Pagination offset (default 0).
 * @returns Array of PedidoRead — may be empty if the user has no orders.
 * @throws AxiosError on 401 (not authenticated), 403, or network failure.
 */
export async function listMisPedidos(
  limit = 50,
  offset = 0,
): Promise<PedidoRead[]> {
  const response = await http.get<PedidoRead[]>('/api/v1/pedidos', {
    params: { limit, offset },
  })
  return response.data
}
