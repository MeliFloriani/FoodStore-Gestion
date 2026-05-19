/**
 * TypeScript interfaces for the Producto entity.
 * Mirror backend Pydantic schemas exactly.
 *
 * Field names are snake_case — FastAPI serializes them as-is.
 *
 * Key note: precio_base is typed as string (not number) because the backend
 * serializes Decimal as string to prevent float precision loss (H-02).
 */

import type { Categoria } from '@/entities/categories/model/types'

/** Full product read response (from GET /api/v1/productos/{id} list view). */
export interface ProductoRead {
  id: string // UUID as string
  nombre: string
  descripcion: string | null
  imagen_url: string | null
  precio_base: string // Decimal serialized as string by backend (H-02)
  stock_cantidad: number
  disponible: boolean
  created_at: string // ISO 8601
  updated_at: string
}

/** Ingredient association read (from GET /api/v1/productos/{id}/ingredientes). */
export interface ProductoIngredienteRead {
  ingrediente_id: string // UUID as string
  nombre: string
  es_alergeno: boolean
  es_removible: boolean
}

/** Full product detail response (from GET /api/v1/productos/{id}).
 *
 * Extends ProductoRead with M2M associations.
 */
export interface ProductoDetail extends ProductoRead {
  categorias: Categoria[] // from entities/categories/model/types
  ingredientes: ProductoIngredienteRead[]
}

/** Paginated product list response. */
export interface PaginatedProductos {
  items: ProductoRead[]
  total: number
  page: number
  size: number
  pages: number
}

/** Payload for POST /api/v1/productos — create a new product.
 *
 * precio_base is sent as string to avoid float precision loss.
 */
export interface ProductoCreatePayload {
  nombre: string
  descripcion?: string | null
  imagen_url?: string | null
  precio_base: string // Send as string to preserve Decimal precision
  stock_cantidad?: number
  disponible?: boolean
  categoria_ids?: string[] | null // UUIDs as strings
}

/** Payload for PATCH /api/v1/productos/{id} — partial update.
 *
 * All fields are optional — only supplied fields are updated (model_fields_set).
 */
export interface ProductoUpdatePayload {
  nombre?: string
  descripcion?: string | null
  imagen_url?: string | null
  precio_base?: string
  stock_cantidad?: number
  disponible?: boolean
  categoria_ids?: string[] | null // [] removes all categories; absent = no change
}

/** Payload for PATCH /api/v1/productos/{id}/disponibilidad. */
export interface DisponibilidadUpdatePayload {
  disponible: boolean
}

/** Payload for POST /api/v1/productos/{id}/ingredientes. */
export interface AsociarIngredientePayload {
  ingrediente_id: string // UUID as string
  es_removible: boolean // Required — no default
}

/** Query params for GET /api/v1/productos listing. */
export interface ProductoListFilters {
  page?: number
  size?: number
  categoria_id?: string | null // UUID as string
  disponible?: boolean | null
  search?: string | null
}
