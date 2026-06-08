/**
 * TanStack Query key factory for the Categoria entity (admin/write surface).
 *
 * The public catalog tree uses its own key in useCategoriesTree; admin mutations
 * invalidate both keys when relevant.
 */
export const categoriaKeys = {
  all: ['categorias'] as const,
  lists: () => [...categoriaKeys.all, 'list'] as const,
  tree: () => [...categoriaKeys.all, 'tree'] as const,
  details: () => [...categoriaKeys.all, 'detail'] as const,
  detail: (id: string) => [...categoriaKeys.details(), id] as const,
}
