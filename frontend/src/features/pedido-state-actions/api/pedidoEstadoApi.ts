/**
 * API functions for FSM state transitions (Change 18).
 *
 * Calls backend endpoints:
 *   PATCH  /api/v1/pedidos/{id}/estado  — staff state transition
 *   DELETE /api/v1/pedidos/{id}         — client self-cancellation
 *   GET    /api/v1/pedidos/{id}/historial — order state history
 *
 * The http client (shared/api/http.ts) attaches the Bearer token automatically.
 *
 * FRONTEND_ALLOWED_TRANSITIONS is a UI hint only — NEVER used for authorization.
 * Authorization is enforced exclusively by the backend (FSM + RBAC per transition).
 * This map drives which action buttons are shown in EstadoActionBar.
 */

import { http } from '@/shared/api/http'
import type { HistorialEstadoPedidoRead } from '@/entities/pedido/model/historialTypes'
import type { PedidoRead } from '@/features/checkout/model/types'

/**
 * Frontend FSM transition map — UI hint only.
 *
 * Maps current order state → list of states the UI should offer buttons for.
 * The actual allowed transitions and RBAC are enforced by the backend.
 * Never use this for authorization logic.
 *
 * Normative reference: backend/app/services/state_transition.py ALLOWED_TRANSITIONS.
 *
 * Used by EstadoActionBar when showAdminActions=true (admin panel context).
 */
export const FRONTEND_ALLOWED_TRANSITIONS: Record<string, string[]> = {
  PENDIENTE: ['CANCELADO'],      // Staff via PATCH; CLIENT via DELETE
  CONFIRMADO: ['EN_PREP', 'CANCELADO'],
  EN_PREP: ['EN_CAMINO', 'CANCELADO'],
  EN_CAMINO: ['ENTREGADO'],
  ENTREGADO: [],                  // Terminal — no buttons
  CANCELADO: [],                  // Terminal — no buttons
}

/**
 * Client-allowed transition map — UI hint only.
 *
 * CLIENT users can only cancel their own orders (PENDIENTE or CONFIRMADO)
 * via DELETE /api/v1/pedidos/{id}. All other state advances are staff-only.
 *
 * Used by EstadoActionBar when showAdminActions=false (default, client context).
 */
export const CLIENT_ALLOWED_TRANSITIONS: Record<string, string[]> = {
  PENDIENTE: ['CANCELADO'],
  CONFIRMADO: ['CANCELADO'],
  EN_PREP: [],
  EN_CAMINO: [],
  ENTREGADO: [],
  CANCELADO: [],
}

export interface TransitionEstadoRequest {
  nuevo_estado: string
  motivo?: string | null
}

/**
 * Advance order state (staff: PEDIDOS or ADMIN role required).
 * Calls PATCH /api/v1/pedidos/{id}/estado.
 *
 * @param pedidoId - UUID of the order to transition.
 * @param request - nuevo_estado and optional motivo.
 * @returns Updated PedidoRead.
 */
export async function transitionEstado(
  pedidoId: string,
  request: TransitionEstadoRequest,
): Promise<PedidoRead> {
  const response = await http.patch<PedidoRead>(`/api/v1/pedidos/${pedidoId}/estado`, request)
  return response.data
}

/**
 * Cancel own order (CLIENT role required).
 * Calls DELETE /api/v1/pedidos/{id}.
 *
 * @param pedidoId - UUID of the order to cancel.
 * @param motivo - Required reason for cancellation (RN-05).
 * @returns Cancelled PedidoRead.
 */
export async function cancelarPedidoCliente(
  pedidoId: string,
  motivo: string,
): Promise<PedidoRead> {
  const response = await http.delete<PedidoRead>(`/api/v1/pedidos/${pedidoId}`, {
    data: { nuevo_estado: 'CANCELADO', motivo },
  })
  return response.data
}

/**
 * Fetch order state history ordered by created_at ASC.
 * Calls GET /api/v1/pedidos/{id}/historial.
 *
 * @param pedidoId - UUID of the order.
 * @returns List of HistorialEstadoPedidoRead ordered chronologically.
 */
export async function getHistorialPedido(
  pedidoId: string,
): Promise<HistorialEstadoPedidoRead[]> {
  const response = await http.get<HistorialEstadoPedidoRead[]>(`/api/v1/pedidos/${pedidoId}/historial`)
  return response.data
}
