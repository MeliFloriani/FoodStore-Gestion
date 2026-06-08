/**
 * API client functions for the DireccionEntrega entity.
 *
 * Change 14: delivery-addresses-management.
 *
 * Uses the shared Axios instance (http) from @/shared/api/http which:
 *   - Attaches the Bearer token from the auth store on every request.
 *   - Handles 401 → refresh token flow automatically.
 *
 * All functions propagate AxiosError so TanStack Query can handle them.
 */

import { http } from '@/shared/api/http'
import type { DireccionEntrega, DireccionEntregaCreateDto, DireccionEntregaUpdateDto } from '../model/types'

const BASE_URL = '/api/v1/direcciones'

/**
 * GET /api/v1/direcciones
 * Returns all active delivery addresses for the authenticated user.
 */
export async function getAddresses(): Promise<DireccionEntrega[]> {
  const response = await http.get<DireccionEntrega[]>(BASE_URL)
  return response.data
}

/**
 * GET /api/v1/direcciones/{id}
 * Returns a single delivery address by ID.
 */
export async function getAddress(id: string): Promise<DireccionEntrega> {
  const response = await http.get<DireccionEntrega>(`${BASE_URL}/${id}`)
  return response.data
}

/**
 * POST /api/v1/direcciones
 * Creates a new delivery address for the authenticated user.
 */
export async function createAddress(data: DireccionEntregaCreateDto): Promise<DireccionEntrega> {
  const response = await http.post<DireccionEntrega>(BASE_URL, data)
  return response.data
}

/**
 * PATCH /api/v1/direcciones/{id}
 * Partially updates an existing delivery address.
 */
export async function updateAddress(
  id: string,
  data: DireccionEntregaUpdateDto,
): Promise<DireccionEntrega> {
  const response = await http.patch<DireccionEntrega>(`${BASE_URL}/${id}`, data)
  return response.data
}

/**
 * PATCH /api/v1/direcciones/{id}/principal
 * Marks the address as the user's principal address.
 * No body required.
 */
export async function setMainAddress(id: string): Promise<DireccionEntrega> {
  const response = await http.patch<DireccionEntrega>(`${BASE_URL}/${id}/principal`)
  return response.data
}

/**
 * DELETE /api/v1/direcciones/{id}
 * Soft-deletes a delivery address. Returns void on HTTP 204.
 */
export async function deleteAddress(id: string): Promise<void> {
  await http.delete(`${BASE_URL}/${id}`)
}
