/**
 * API function for pre-checkout validation.
 *
 * Calls POST /api/v1/pedidos/validar via the configured Axios http client.
 * The http client (shared/api/http.ts) automatically attaches the Bearer token
 * and handles 401 refresh queue (frontend-http-client spec).
 */

import { http } from '@/shared/api/http'
import type { ItemAValidar, ValidarPreCheckoutResponse } from '../model/types'

/**
 * Validate cart items against the current database state.
 *
 * @param items - Array of cart items with perceived prices as strings.
 * @returns ValidarPreCheckoutResponse with ok flag, validated items, and detected changes.
 * @throws AxiosError on 401, 403, 422, or network failure.
 */
export async function validatePreCheckout(
  items: ItemAValidar[],
): Promise<ValidarPreCheckoutResponse> {
  const response = await http.post<ValidarPreCheckoutResponse>('/api/v1/pedidos/validar', { items })
  return response.data
}
