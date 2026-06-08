/**
 * Types for the checkout order creation feature (Change 17).
 *
 * These types model the request/response for POST /api/v1/pedidos.
 *
 * Design decisions:
 * - D-09 / Nota R-01: exclusiones are string[] (UUID strings) — NOT number[].
 *   CartItem.personalizacion stores UUIDs as string[]; they pass through directly
 *   without any parseInt conversion (which would return NaN for UUID strings).
 * - D-11: subtotal, costo_envio, total are NOT sent in the request — backend
 *   calculates them. They appear only in PedidoRead (response).
 * - D-09 wire format: monetary fields (subtotal, costo_envio, total, precio_snapshot)
 *   are decimal strings ("50.00", "0.00") in the response.
 */

// ---------------------------------------------------------------------------
// Request types
// ---------------------------------------------------------------------------

export interface OrderItemRequest {
  /** UUID of the product to order */
  producto_id: string
  /** Quantity (>= 1) */
  cantidad: number
  /** UUIDs of excluded ingredients — identical to CartItem.personalizacion (string[]) */
  exclusiones: string[]
}

export interface CreateOrderRequest {
  items: OrderItemRequest[]
  /** Semantic code from FormaPago catalog: "MERCADOPAGO" | "EFECTIVO" | "TRANSFERENCIA" */
  forma_pago_codigo: string
  /** UUID of delivery address, or null for pickup (retiro en local) */
  direccion_id: string | null
  /** Optional free-text instructions */
  notas?: string
}

// ---------------------------------------------------------------------------
// Response types
// ---------------------------------------------------------------------------

export interface DetallePedidoRead {
  id: string
  producto_id: string
  /** Product name at time of order creation — immutable snapshot (D-03) */
  nombre_snapshot: string
  /** Unit price at time of order creation — decimal string, immutable (D-03) */
  precio_snapshot: string
  cantidad: number
  /** UUIDs of excluded ingredients — may be [] */
  personalizacion: string[]
}

export interface HistorialEstadoPedidoRead {
  id: string
  /** null for the initial entry (RN-02) */
  estado_desde: string | null
  /** "PENDIENTE" for the initial entry */
  estado_hacia: string
  motivo: string | null
  created_at: string
}

export interface PedidoRead {
  id: string
  usuario_id: string
  /** Always "PENDIENTE" on creation */
  estado_codigo: string
  forma_pago_codigo: string
  /** null if retiro en local */
  direccion_id: string | null
  /** Decimal string — sum of precio_snapshot × cantidad */
  subtotal: string
  /** Decimal string — "50.00" with address, "0.00" for pickup */
  costo_envio: string
  /** Decimal string — subtotal + costo_envio */
  total: string
  notas: string | null
  /** Line items with immutable snapshots */
  items: DetallePedidoRead[]
  /** Order state history — always has at least one entry (initial PENDIENTE) */
  historial: HistorialEstadoPedidoRead[]
  created_at: string
}

// ---------------------------------------------------------------------------
// Error response type (RFC 7807)
// ---------------------------------------------------------------------------

export interface OrderErrorResponse {
  code:
    | 'CART_EMPTY'
    | 'PRODUCT_NOT_FOUND'
    | 'PRODUCT_NOT_AVAILABLE'
    | 'INSUFFICIENT_STOCK'
    | 'INVALID_CUSTOMIZATION'
    | 'PAYMENT_METHOD_INVALID'
    | 'ADDRESS_NOT_FOUND'
    | 'ADDRESS_NOT_OWNED'
  detail: string | Record<string, unknown>
  status: number
  title: string
}
