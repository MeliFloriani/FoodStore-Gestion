/**
 * TypeScript types for HistorialEstadoPedido (Change 18).
 *
 * These types model the GET /api/v1/pedidos/{id}/historial response.
 *
 * Design decisions:
 * - actor_user_id corresponds to ORM.cambiado_por_id — the backend aliases it.
 *   null = system-generated transition (Change 19 webhook) or initial PENDIENTE.
 *   non-null = manual human transition (Change 18).
 * - estado_hacia is the response field name (ORM field is estado_hasta).
 */

/**
 * A single state transition record from the order history.
 *
 * Returned by GET /api/v1/pedidos/{id}/historial ordered by created_at ASC.
 */
export interface HistorialEstadoPedidoRead {
  /** UUID of this history record */
  id: string
  /** Previous state — null for the initial PENDIENTE entry (RN-02) */
  estado_desde: string | null
  /** Target state (mapped from ORM.estado_hasta) */
  estado_hacia: string
  /** Reason for the transition — required for CANCELADO (RN-05) */
  motivo: string | null
  /**
   * UUID of the user who performed the transition.
   * null = initial system entry (Change 17) or MP webhook (Change 19).
   * non-null = manual transition by a human user (Change 18).
   * Mapped from ORM.cambiado_por_id on the backend.
   */
  actor_user_id: string | null
  /** ISO 8601 timestamp of the transition */
  created_at: string
}
