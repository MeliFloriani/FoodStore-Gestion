/**
 * TypeScript interfaces for the DireccionEntrega entity.
 *
 * Change 14: delivery-addresses-management.
 *
 * Field names use snake_case to match the backend API response directly
 * (same pattern as other entities in this project — no camelCase transform).
 *
 * The backend serializes UUID fields as strings.
 */

/** Full address read response (from GET /api/v1/direcciones). */
export interface DireccionEntrega {
  id: string // UUID as string
  usuario_id: string // UUID as string
  alias: string | null
  linea1: string
  linea2: string | null
  ciudad: string | null
  provincia: string | null
  codigo_postal: string | null
  referencia: string | null
  es_principal: boolean
  created_at: string // ISO 8601
  updated_at: string // ISO 8601
}

/** Payload for POST /api/v1/direcciones — create a new address. */
export interface DireccionEntregaCreateDto {
  linea1: string
  alias?: string | null
  linea2?: string | null
  ciudad?: string | null
  provincia?: string | null
  codigo_postal?: string | null
  referencia?: string | null
}

/** Payload for PATCH /api/v1/direcciones/{id} — partial update.
 *
 * All fields are optional — only supplied fields are updated.
 * es_principal is intentionally excluded (use PATCH /{id}/principal instead).
 */
export interface DireccionEntregaUpdateDto {
  linea1?: string
  alias?: string | null
  linea2?: string | null
  ciudad?: string | null
  provincia?: string | null
  codigo_postal?: string | null
  referencia?: string | null
}
