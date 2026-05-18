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
