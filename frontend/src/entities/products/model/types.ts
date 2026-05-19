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

// ── Public catalog types (Change 12: catalog-public-browsing) ────────────────

/** Public product read response (from GET /api/v1/catalog/productos).
 *
 * Does NOT contain stock_cantidad — only the boolean tiene_stock.
 * Does NOT contain created_at, updated_at, deleted_at.
 */
export interface ProductoPublicoRead {
  id: string
  nombre: string
  descripcion: string | null
  imagen_url: string | null
  precio_base: string // Decimal serialized as string
  disponible: boolean
  tiene_stock: boolean // NEVER stock_cantidad — public-safe boolean
}

/** Public category read (nested inside ProductoPublicoDetalleRead). */
export interface CategoriaPublicaRead {
  id: string
  nombre: string
}

/** Public ingredient read (nested inside ProductoPublicoDetalleRead).
 *
 * Uses ingrediente_id (not id) to avoid ambiguity with the product id.
 * es_removible is intentionally absent (admin-only detail).
 */
export interface IngredientePublicoRead {
  ingrediente_id: string
  nombre: string
  es_alergeno: boolean
}

/** Public product detail response (from GET /api/v1/catalog/productos/{id}).
 *
 * Extends ProductoPublicoRead with M2M associations.
 */
export interface ProductoPublicoDetalleRead extends ProductoPublicoRead {
  categorias: CategoriaPublicaRead[]
  ingredientes: IngredientePublicoRead[]
}

/** Filters for the public catalog listing. Serialized as URL search params. */
export interface CatalogFilters {
  page?: number
  size?: number
  categoria_id?: string | null
  q?: string | null
  excluir_alergenos?: string | null // comma-separated positive integer IDs
  ordenar?: string | null
}

/** Paginated response for GET /api/v1/catalog/productos. */
export interface PaginatedCatalogProductos {
  items: ProductoPublicoRead[]
  total: number
  page: number
  size: number
  pages: number
}

/** Response for GET /api/v1/catalog/ingredientes-alergenos. */
export interface IngredienteAlergenicoListResponse {
  items: IngredientePublicoRead[]
  total: number
}
