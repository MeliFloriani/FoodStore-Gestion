/**
 * TanStack Query v5 hooks for the Ingrediente entity.
 *
 * Lives in api/ (hooks that directly wrap fetchers).
 * All mutation hooks invalidate the relevant list + detail cache entries on success.
 *
 * Hooks:
 *   useIngredientes       — GET /api/v1/ingredientes (with optional es_alergeno filter)
 *   useIngrediente        — GET /api/v1/ingredientes/{id}
 *   useCreateIngrediente  — POST /api/v1/ingredientes/
 *   useUpdateIngrediente  — PUT /api/v1/ingredientes/{id}
 *   useDeleteIngrediente  — DELETE /api/v1/ingredientes/{id}
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ingredienteKeys } from './queryKeys'
import {
  createIngrediente,
  deleteIngrediente,
  getIngrediente,
  listIngredientes,
  updateIngrediente,
} from './ingredienteApi'
import type { IngredienteCreate, IngredienteUpdate } from '../model/types'

/** Fetch all active ingredients, optionally filtered by es_alergeno. */
export function useIngredientes(filters?: { es_alergeno?: boolean }) {
  return useQuery({
    queryKey: ingredienteKeys.list(filters),
    queryFn: () => listIngredientes(filters),
  })
}

/** Fetch a single ingredient by UUID string. */
export function useIngrediente(id: string) {
  return useQuery({
    queryKey: ingredienteKeys.detail(id),
    queryFn: () => getIngrediente(id),
    enabled: Boolean(id),
  })
}

/** Create a new ingredient. Invalidates the list cache on success. */
export function useCreateIngrediente() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: IngredienteCreate) => createIngrediente(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ingredienteKeys.lists() })
    },
  })
}

/** Update an existing ingredient. Invalidates the list and the specific detail on success. */
export function useUpdateIngrediente(id: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: IngredienteUpdate) => updateIngrediente(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ingredienteKeys.lists() })
      queryClient.invalidateQueries({ queryKey: ingredienteKeys.detail(id) })
    },
  })
}

/** Soft-delete an ingredient. Invalidates the list and the specific detail on success. */
export function useDeleteIngrediente() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => deleteIngrediente(id),
    onSuccess: (_data, id) => {
      queryClient.invalidateQueries({ queryKey: ingredienteKeys.lists() })
      queryClient.invalidateQueries({ queryKey: ingredienteKeys.detail(id) })
    },
  })
}
