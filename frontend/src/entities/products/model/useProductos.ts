/**
 * TanStack Query v5 read hooks for the Producto entity.
 *
 * Lives in model/ following the FSD entities layer conventions.
 * Mutation hooks are in useProductoMutations.ts.
 *
 * Hooks:
 *   useProductos           — GET /api/v1/productos (paginated, with filters)
 *   useProducto            — GET /api/v1/productos/{id} (full detail)
 *   useProductoIngredientes — GET /api/v1/productos/{id}/ingredientes
 */

import { useQuery } from '@tanstack/react-query'
import { productQueryKeys } from './queryKeys'
import {
  listProductos,
  getProducto,
  listProductoIngredientes,
} from '../api/productoFetchers'
import type { ProductoListFilters } from './types'

/** Fetch a paginated list of products with optional filters. */
export function useProductos(filters?: ProductoListFilters) {
  return useQuery({
    queryKey: productQueryKeys.list(filters),
    queryFn: () => listProductos(filters),
  })
}

/** Fetch a single product (with categories and ingredients) by UUID string. */
export function useProducto(id: string) {
  return useQuery({
    queryKey: productQueryKeys.detail(id),
    queryFn: () => getProducto(id),
    enabled: Boolean(id),
  })
}

/** Fetch the ingredient list associated with a product by UUID string. */
export function useProductoIngredientes(id: string) {
  return useQuery({
    queryKey: productQueryKeys.ingredientes(id),
    queryFn: () => listProductoIngredientes(id),
    enabled: Boolean(id),
  })
}
