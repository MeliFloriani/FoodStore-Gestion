/**
 * TanStack Query key factory for the Producto entity.
 *
 * Follows the nested key factory pattern for efficient cache invalidation:
 * - productQueryKeys.all                → all keys for this entity
 * - productQueryKeys.lists()            → all list variants
 * - productQueryKeys.list(filters)      → specific list with filters
 * - productQueryKeys.details()          → all detail variants
 * - productQueryKeys.detail(id)         → specific detail by UUID string
 * - productQueryKeys.ingredientes(id)   → ingredient list for a product
 */

import type { ProductoListFilters } from './types'

export const productQueryKeys = {
  all: ['products'] as const,

  lists: () => [...productQueryKeys.all, 'list'] as const,

  list: (filters?: ProductoListFilters) =>
    [...productQueryKeys.lists(), filters] as const,

  details: () => [...productQueryKeys.all, 'detail'] as const,

  detail: (id: string) => [...productQueryKeys.details(), id] as const,

  ingredientes: (id: string) =>
    [...productQueryKeys.all, 'ingredientes', id] as const,
}
