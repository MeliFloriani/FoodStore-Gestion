/**
 * Public API for the categories entity (FSD entity layer).
 *
 * Re-exports types and hooks for consumers in higher layers
 * (pages, features, widgets).
 */
export type {
  Categoria,
  CategoriaTreeNode,
  CategoriaCreate,
  CategoriaUpdate,
} from './model/types'
export { useCategoriesTree } from './model/useCategoriesTree'
export { categoriaKeys } from './api/queryKeys'
export {
  useCreateCategoria,
  useUpdateCategoria,
  useDeleteCategoria,
} from './api/hooks'
