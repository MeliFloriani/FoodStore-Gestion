/**
 * TanStack Query v5 mutation hooks for the Categoria entity.
 *
 * All mutation hooks invalidate:
 *  - the public catalog tree (used by useCategoriesTree)
 *  - the admin categoria details
 *
 * Backend write endpoints require ADMIN or STOCK role.
 */
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { queryKeys as sharedQueryKeys } from '@/shared/lib/queryKeys'
import { categoriaKeys } from './queryKeys'
import {
  createCategoria,
  deleteCategoria,
  updateCategoria,
} from './categoriasApi'
import type { CategoriaCreate, CategoriaUpdate } from '../model/types'

function invalidateAll(qc: ReturnType<typeof useQueryClient>) {
  qc.invalidateQueries({ queryKey: sharedQueryKeys.catalog.categories() })
  qc.invalidateQueries({ queryKey: categoriaKeys.all })
}

/** Create a new category. Requires ADMIN or STOCK role. */
export function useCreateCategoria() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: CategoriaCreate) => createCategoria(data),
    onSuccess: () => invalidateAll(qc),
  })
}

/** Partial update of a category. Requires ADMIN or STOCK role. */
export function useUpdateCategoria(id: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: CategoriaUpdate) => updateCategoria(id, data),
    onSuccess: () => {
      invalidateAll(qc)
      qc.invalidateQueries({ queryKey: categoriaKeys.detail(id) })
    },
  })
}

/** Soft-delete a category. Requires ADMIN or STOCK role. */
export function useDeleteCategoria() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => deleteCategoria(id),
    onSuccess: (_data, id) => {
      invalidateAll(qc)
      qc.invalidateQueries({ queryKey: categoriaKeys.detail(id) })
    },
  })
}
