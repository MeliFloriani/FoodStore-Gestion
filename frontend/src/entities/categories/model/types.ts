/**
 * TypeScript interfaces for the Categoria domain.
 * Mirror backend schemas: CategoriaRead and CategoriaTreeNode.
 */

/** Full category read response (from GET /api/v1/categorias/{id}). */
export interface Categoria {
  id: string
  nombre: string
  descripcion: string | null
  parent_id: string | null
  created_at: string
  updated_at: string
}

/** Recursive tree node (from GET /api/v1/categorias). */
export interface CategoriaTreeNode {
  id: string
  nombre: string
  descripcion: string | null
  subcategorias: CategoriaTreeNode[]
}

/** Payload for POST /api/v1/categorias — create a new category.
 *
 * parent_id=null creates a root category.
 * parent_id=<UUID> creates a subcategory.
 */
export interface CategoriaCreate {
  nombre: string
  descripcion?: string | null
  parent_id?: string | null
}

/** Payload for PUT /api/v1/categorias/{id} — partial update.
 *
 * Backend uses model_fields_set sentinel for parent_id:
 *   - absent  → no reparenting
 *   - null    → promote to root
 *   - UUID    → reparent
 * Senders should only include keys they intend to change.
 */
export interface CategoriaUpdate {
  nombre?: string
  descripcion?: string | null
  parent_id?: string | null
}
