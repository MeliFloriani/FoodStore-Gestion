/**
 * TanStack Query v5 mutation hooks for the Producto entity.
 *
 * All mutation hooks invalidate the relevant cache entries on success:
 * - create      → invalidates lists
 * - update      → invalidates lists + specific detail
 * - delete      → invalidates lists + specific detail
 * - disponibilidad → invalidates lists + specific detail
 * - asociarIngrediente  → invalidates detail + ingredientes list
 * - removerIngrediente  → invalidates detail + ingredientes list
 *
 * Hooks:
 *   useCreateProducto        — POST /api/v1/productos/
 *   useUpdateProducto        — PATCH /api/v1/productos/{id}
 *   useDeleteProducto        — DELETE /api/v1/productos/{id}
 *   useUpdateDisponibilidad  — PATCH /api/v1/productos/{id}/disponibilidad
 *   useAsociarIngrediente    — POST /api/v1/productos/{id}/ingredientes
 *   useRemoverIngrediente    — DELETE /api/v1/productos/{id}/ingredientes/{ing_id}
 */

import { useMutation, useQueryClient } from '@tanstack/react-query'
import { productQueryKeys } from './queryKeys'
import {
  createProducto,
  updateProducto,
  deleteProducto,
  updateDisponibilidad,
  asociarIngrediente,
  removerIngrediente,
} from '../api/productoFetchers'
import type {
  ProductoCreatePayload,
  ProductoUpdatePayload,
  DisponibilidadUpdatePayload,
  AsociarIngredientePayload,
} from './types'

/** Create a new product. Requires ADMIN role. Invalidates the product list cache. */
export function useCreateProducto() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: ProductoCreatePayload) => createProducto(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: productQueryKeys.lists() })
    },
  })
}

/** Partial update of a product. Requires ADMIN role.
 * Invalidates the product list and the specific product detail cache. */
export function useUpdateProducto(id: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: ProductoUpdatePayload) => updateProducto(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: productQueryKeys.lists() })
      queryClient.invalidateQueries({ queryKey: productQueryKeys.detail(id) })
    },
  })
}

/** Soft-delete a product. Requires ADMIN role.
 * Invalidates the product list and the specific product detail cache. */
export function useDeleteProducto() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => deleteProducto(id),
    onSuccess: (_data, id) => {
      queryClient.invalidateQueries({ queryKey: productQueryKeys.lists() })
      queryClient.invalidateQueries({ queryKey: productQueryKeys.detail(id) })
    },
  })
}

/** Update product availability. Requires ADMIN or STOCK role.
 * Invalidates the product list and the specific product detail cache. */
export function useUpdateDisponibilidad(id: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: DisponibilidadUpdatePayload) =>
      updateDisponibilidad(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: productQueryKeys.lists() })
      queryClient.invalidateQueries({ queryKey: productQueryKeys.detail(id) })
    },
  })
}

/** Associate an ingredient with a product. Requires ADMIN role.
 * Invalidates the product detail and its ingredient list cache. */
export function useAsociarIngrediente(productoId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: AsociarIngredientePayload) =>
      asociarIngrediente(productoId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: productQueryKeys.detail(productoId),
      })
      queryClient.invalidateQueries({
        queryKey: productQueryKeys.ingredientes(productoId),
      })
    },
  })
}

/** Remove an ingredient from a product. Requires ADMIN role.
 * Invalidates the product detail and its ingredient list cache. */
export function useRemoverIngrediente(productoId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (ingredienteId: string) =>
      removerIngrediente(productoId, ingredienteId),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: productQueryKeys.detail(productoId),
      })
      queryClient.invalidateQueries({
        queryKey: productQueryKeys.ingredientes(productoId),
      })
    },
  })
}
