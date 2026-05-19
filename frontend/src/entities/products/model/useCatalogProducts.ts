/**
 * TanStack Query v5 hooks for the public catalog (no auth required).
 *
 * Change 12: catalog-public-browsing
 *
 * Hooks:
 *   useCatalogProducts  — paginated public product listing with keepPreviousData
 *   useCatalogProduct   — single public product detail
 *   useCatalogAlergenos — public allergen ingredient list
 */

import { useQuery, keepPreviousData } from '@tanstack/react-query'
import {
  fetchCatalogProductos,
  fetchCatalogProductoDetalle,
  fetchCatalogAlergenos,
} from '../api/productoFetchers'
import type {
  CatalogFilters,
  PaginatedCatalogProductos,
  ProductoPublicoDetalleRead,
  IngredienteAlergenicoListResponse,
} from './types'

/**
 * Strips null/undefined values from a CatalogFilters object.
 * Prevents cache misses caused by {q: null} vs {q: undefined} key differences.
 */
function sanitizeFilters(f: CatalogFilters): Partial<CatalogFilters> {
  return Object.fromEntries(Object.entries(f).filter(([, v]) => v != null))
}

/** Query key factory for the public catalog. */
export const catalogQueryKeys = {
  all: ['catalog', 'products'] as const,
  lists: () => [...catalogQueryKeys.all, 'list'] as const,
  list: (f: CatalogFilters) =>
    [...catalogQueryKeys.lists(), sanitizeFilters(f)] as const,
  detail: (id: string) => [...catalogQueryKeys.all, 'detail', id] as const,
  alergenos: () => ['catalog', 'alergenos'] as const,
}

/** Fetch paginated public catalog products. Uses keepPreviousData for smooth pagination. */
export function useCatalogProducts(filters: CatalogFilters) {
  return useQuery<PaginatedCatalogProductos>({
    queryKey: catalogQueryKeys.list(filters),
    queryFn: () => fetchCatalogProductos(filters),
    staleTime: 30_000,
    gcTime: 300_000,
    placeholderData: keepPreviousData,
  })
}

/** Fetch a single public product by UUID. Skips query when id is empty. */
export function useCatalogProduct(id: string) {
  return useQuery<ProductoPublicoDetalleRead>({
    queryKey: catalogQueryKeys.detail(id),
    queryFn: () => fetchCatalogProductoDetalle(id),
    enabled: !!id,
    staleTime: 30_000,
    gcTime: 300_000,
  })
}

/** Fetch the public allergen ingredient list. Long staleTime — changes infrequently. */
export function useCatalogAlergenos() {
  return useQuery<IngredienteAlergenicoListResponse>({
    queryKey: catalogQueryKeys.alergenos(),
    queryFn: fetchCatalogAlergenos,
    staleTime: 300_000,
    gcTime: 3_600_000,
  })
}
