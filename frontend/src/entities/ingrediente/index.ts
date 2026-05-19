/**
 * Public API for the ingrediente entity (FSD entity layer).
 *
 * Re-exports types, query keys, and hooks for consumers in higher layers
 * (pages, features, widgets).
 *
 * NOTE: Raw fetchers (ingredienteApi.ts) are intentionally NOT re-exported here.
 * Consumers should use the React Query hooks instead of calling the API directly.
 */

// Types
export type { Ingrediente, IngredienteCreate, IngredienteUpdate } from './model/types'

// Query key factory
export { ingredienteKeys } from './api/queryKeys'

// React Query hooks
export {
  useIngredientes,
  useIngrediente,
  useCreateIngrediente,
  useUpdateIngrediente,
  useDeleteIngrediente,
} from './api/hooks'
