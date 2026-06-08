/**
 * API function for transactional order creation (Change 17).
 *
 * Calls POST /api/v1/pedidos via the configured Axios http client.
 * The http client (shared/api/http.ts) automatically attaches the Bearer token
 * and handles 401 refresh queue (frontend-http-client spec).
 *
 * Errors (409 INSUFFICIENT_STOCK, 400 CART_EMPTY, etc.) are thrown as AxiosError
 * with a response.data containing the RFC 7807 error body — the calling hook
 * (useCreateOrder) is responsible for extracting the error code.
 */

import { http } from '@/shared/api/http'
import type { CreateOrderRequest, PedidoRead } from '../model/types'

/**
 * Create a transactional order for the authenticated user.
 *
 * The backend re-validates all items (stock, availability, customization, payment)
 * inside a SELECT FOR UPDATE transaction — no need to trust Change 16 results.
 *
 * @param request - Order creation payload derived from cartStore.
 * @returns PedidoRead with the created order including snapshots and initial history.
 * @throws AxiosError on 400, 403, 409, 422, or network failure.
 */
export async function createOrder(request: CreateOrderRequest): Promise<PedidoRead> {
  const response = await http.post<PedidoRead>('/api/v1/pedidos', request)
  return response.data
}
