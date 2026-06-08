/**
 * Types for the pre-checkout-validation feature.
 *
 * Mirrors the backend Pydantic schemas in backend/app/schemas/pedidos_validar.py.
 * Wire format: precio as string decimal (not float) to avoid JSON precision loss.
 *
 * Design decisions from spec:
 * - D-03: precio sent as string "250.00" (not 250 number) to preserve Decimal precision.
 * - D-05: Response always 200 OK with ok: boolean. Business changes (stock, price) are
 *   data in the payload, not HTTP 4xx errors.
 * - PRECIO_CAMBIADO is informative (non-blocking). All other tipos are blocking (ok=false).
 */

// ---------------------------------------------------------------------------
// Request types
// ---------------------------------------------------------------------------

/**
 * One cart item to validate against current database state.
 * Maps from CartItem (entities/cart) with precio converted to string.
 */
export interface ItemAValidar {
  producto_id: string
  cantidad: number
  personalizacion: string[]
  /** Perceived price — always string with 2 decimal places, e.g. "250.00" */
  precio: string
}

export interface ValidarPreCheckoutRequest {
  items: ItemAValidar[]
}

// ---------------------------------------------------------------------------
// Response types
// ---------------------------------------------------------------------------

/**
 * Union of all detectable change types.
 * PRECIO_CAMBIADO is non-blocking (ok can still be true).
 * All others are blocking (ok=false).
 */
export type TipoCambio =
  | 'PRODUCTO_NO_VIGENTE'
  | 'PRODUCTO_NO_DISPONIBLE'
  | 'STOCK_INSUFICIENTE'
  | 'PRECIO_CAMBIADO'
  | 'PERSONALIZACION_INVALIDA'

/** Validation result for one cart item. */
export interface ItemValidadoRead {
  producto_id: string
  cantidad_solicitada: number
  /** null if product does not exist or was soft-deleted */
  stock_disponible: number | null
  /** Current precio_base as decimal string. null if product not vigent. */
  precio_actual: string | null
  /** Price the client has in their cart (from the request). */
  precio_percibido: string
  /** true if product exists and deleted_at IS NULL */
  vigente: boolean
  /** null if not vigent */
  disponible: boolean | null
}

/** Detalle shape varies by tipo — typed as Record to avoid over-constraining. */
export interface CambioRead {
  producto_id: string
  tipo: TipoCambio
  detalle: Record<string, unknown>
}

/**
 * Full validation response.
 * Always HTTP 200 — business changes are data, not errors.
 */
export interface ValidarPreCheckoutResponse {
  /** true if no blocking changes. PRECIO_CAMBIADO alone does NOT block ok. */
  ok: boolean
  /** One entry per item in the request (same length). */
  items: ItemValidadoRead[]
  /** List of changes detected. Empty if all good and prices match. */
  cambios: CambioRead[]
}
