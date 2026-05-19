/**
 * TanStack Query key factory for the Ingrediente entity.
 *
 * Follows the nested key factory pattern for efficient cache invalidation:
 * - ingredienteKeys.all            → all keys for this entity
 * - ingredienteKeys.lists()        → all list variants
 * - ingredienteKeys.list(filters)  → specific list with filters
 * - ingredienteKeys.details()      → all detail variants
 * - ingredienteKeys.detail(id)     → specific detail by UUID string
 */

export const ingredienteKeys = {
  all: ['ingredientes'] as const,

  lists: () => [...ingredienteKeys.all, 'list'] as const,

  list: (filters?: { es_alergeno?: boolean }) =>
    [...ingredienteKeys.lists(), filters] as const,

  details: () => [...ingredienteKeys.all, 'detail'] as const,

  detail: (id: string) => [...ingredienteKeys.details(), id] as const,
}
