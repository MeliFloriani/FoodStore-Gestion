/**
 * TypeScript types for the Pedido entity (Change 20).
 *
 * These types mirror the backend Pydantic schemas:
 *   - PedidoListItem (GET /api/v1/pedidos — listado)
 *   - PedidoDetail   (GET /api/v1/pedidos/{id} — detalle)
 *
 * Design decisions (D-16): snake_case end-to-end — frontend consumes JSON
 * as-is without camelCase transformation. Decimal fields are strings.
 *
 * Normative reference: openspec/changes/orders-visualization/specs/
 *   frontend-orders-history/spec.md
 *   frontend-orders-detail/spec.md
 */

import type { HistorialEstadoPedidoRead } from './historialTypes'
import type { DetallePedidoRead } from '@/features/checkout/model/types'
import type { PagoResponse } from '@/entities/pago/model/types'

// ---------------------------------------------------------------------------
// Sub-types
// ---------------------------------------------------------------------------

/** Basic user information returned inside PedidoDetail */
export interface UsuarioBasic {
  id: string
  nombre: string
  apellido: string
  email: string
}

/** Basic address info (best-effort, deuda OQ-01) */
export interface DireccionBasic {
  alias: string | null
  linea1: string
  linea2: string | null
  ciudad: string | null
  provincia: string | null
  codigo_postal: string | null
  referencia: string | null
}

// ---------------------------------------------------------------------------
// Listado
// ---------------------------------------------------------------------------

/** Single item in the paginated order list (GET /api/v1/pedidos) */
export interface PedidoListItem {
  id: string
  estado_codigo: string
  /** Decimal string — e.g. "150.00" */
  total: string
  forma_pago_codigo: string
  items_count: number
  created_at: string
  /** null for CLIENT responses — only populated for PEDIDOS/ADMIN */
  usuario_nombre: string | null
  /** null for CLIENT responses — only populated for PEDIDOS/ADMIN */
  usuario_email: string | null
}

/** Paginated response from GET /api/v1/pedidos */
export interface PedidoPage {
  items: PedidoListItem[]
  total: number
  page: number
  size: number
  pages: number
}

// ---------------------------------------------------------------------------
// Detalle
// ---------------------------------------------------------------------------

/** Full order detail (GET /api/v1/pedidos/{id}) */
export interface PedidoDetail {
  id: string
  usuario_id: string
  usuario: UsuarioBasic | null
  estado_codigo: string
  forma_pago_codigo: string
  /** Decimal string */
  subtotal: string
  /** Decimal string */
  costo_envio: string
  /** Decimal string */
  total: string
  notas: string | null
  direccion_id: string | null
  /** Best-effort — may be null if address was deleted after order */
  direccion: DireccionBasic | null
  items: DetallePedidoRead[]
  /** Ordered chronologically ASC */
  historial: HistorialEstadoPedidoRead[]
  pago: PagoResponse | null
  created_at: string
}

// ---------------------------------------------------------------------------
// Query parameters
// ---------------------------------------------------------------------------

/** Parameters for useClientOrders — CLIENT-only (no admin filters) */
export interface ClientOrdersParams {
  estado?: string
  page?: number
  size?: number
}

/** Parameters for useAdminOrders — PEDIDOS/ADMIN */
export interface AdminOrdersParams {
  estado?: string
  /** ISO 8601 date string */
  desde?: string
  /** ISO 8601 date string */
  hasta?: string
  /** Minimum 3 characters to activate backend filter */
  cliente?: string
  page?: number
  size?: number
}
