/**
 * TypeScript interfaces for the Ingrediente domain.
 * Mirror backend schemas: IngredienteRead, IngredienteCreate, IngredienteUpdate.
 *
 * Field names are snake_case — FastAPI serializes them as-is, no camelCase conversion.
 */

/** Full ingredient read response (from GET /api/v1/ingredientes/{id}). */
export interface Ingrediente {
  id: string // UUID as string
  nombre: string
  es_alergeno: boolean // snake_case — FastAPI serializes as is
  created_at: string // ISO datetime string
  updated_at: string
}

/** Payload for POST /api/v1/ingredientes — create a new ingredient. */
export interface IngredienteCreate {
  nombre: string
  es_alergeno?: boolean
}

/** Payload for PUT /api/v1/ingredientes/{id} — partial update.
 *
 * All fields are optional. Only supplied fields are updated;
 * absent fields are preserved at their current DB values (model_fields_set pattern).
 */
export interface IngredienteUpdate {
  nombre?: string
  es_alergeno?: boolean
}
