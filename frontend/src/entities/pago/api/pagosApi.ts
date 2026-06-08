/**
 * API functions for the Pago (payment) entity.
 *
 * Change 19 — payments-mercadopago-integration (Checkout Pro migration).
 *
 * Calls backend endpoints at /api/v1/pagos via the configured Axios http client.
 * The http client (shared/api/http.ts) automatically attaches the Bearer token
 * and handles 401 refresh queue.
 *
 * Error handling: errors are thrown as AxiosError with RFC 7807 response body.
 * Callers (hooks/features) are responsible for extracting error codes.
 *
 * Checkout Pro flow:
 *   createPayment() → POST /api/v1/pagos → returns preference_id + init_point
 *   Frontend redirects to sandbox_init_point (dev) or init_point (prod).
 *   No card data involved — tokenization is handled by MP hosted page.
 */

import { http } from '@/shared/api/http'
import type {
  PagoCreateRequest,
  PagoReconcileRequest,
  PagoReconcileResponse,
  PagoResponse,
} from '../model/types'

/**
 * Start a MercadoPago Checkout Pro payment for a given order.
 *
 * POST /api/v1/pagos
 *
 * @param data - Request with pedido_id and client-generated idempotency_key.
 * @returns PagoResponse with preference_id, init_point, sandbox_init_point on HTTP 201.
 * @throws AxiosError on 403 ORDER_NOT_OWNED, 404 ORDER_NOT_FOUND,
 *         409 ORDER_NOT_PAYABLE | PAYMENT_METHOD_MISMATCH, 502 MP_PREFERENCE_ERROR.
 */
export async function createPayment(data: PagoCreateRequest): Promise<PagoResponse> {
  const response = await http.post<PagoResponse>('/api/v1/pagos', data)
  return response.data
}

/**
 * Get the latest payment record for a given order.
 *
 * GET /api/v1/pagos/{pedido_id}/latest
 *
 * @param pedidoId - UUID of the order to query.
 * @returns PagoResponse — the most recent Pago for this order.
 * @throws AxiosError on 404 PAYMENT_NOT_FOUND or ORDER_NOT_FOUND.
 */
export async function getLatestPayment(pedidoId: string): Promise<PagoResponse> {
  const response = await http.get<PagoResponse>(`/api/v1/pagos/${pedidoId}/latest`)
  return response.data
}

/**
 * Reconcile a Pago against MercadoPago after the user returned from Checkout Pro.
 *
 * POST /api/v1/pagos/reconcile
 *
 * Frontend-driven fallback for local development where MP webhook servers
 * cannot reach localhost. The backend re-queries MP using payment_id and
 * applies the same FSM transitions as the webhook would.
 *
 * @param data - Request with pedido_id and (at least) payment_id.
 * @returns PagoReconcileResponse with updated mp_status and pedido_estado.
 * @throws AxiosError on 400 PAYMENT_ID_REQUIRED, 404 ORDER_NOT_FOUND |
 *         PAYMENT_NOT_FOUND, 409 PAYMENT_METHOD_MISMATCH |
 *         EXTERNAL_REFERENCE_MISMATCH, 502 MP_RECONCILE_ERROR.
 */
export async function reconcilePayment(
  data: PagoReconcileRequest,
): Promise<PagoReconcileResponse> {
  const response = await http.post<PagoReconcileResponse>(
    '/api/v1/pagos/reconcile',
    data,
  )
  return response.data
}
