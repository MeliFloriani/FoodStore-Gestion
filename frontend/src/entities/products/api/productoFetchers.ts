/**
 * Plain async fetchers for the Producto entity.
 *
 * Uses the shared Axios instance (http) from @/shared/api/http.
 * Query parameter names are snake_case to match FastAPI's expected format.
 *
 * These are NOT React hooks — they live in api/ following FSD conventions.
 * The React Query hooks that wrap these live in model/useProductos.ts and
 * model/useProductoMutations.ts.
 */

import { http } from '@/shared/api/http'
import { PRODUCTOS } from '@/shared/api/endpoints'
import type {
  PaginatedProductos,
  ProductoDetail,
  ProductoIngredienteRead,
  ProductoListFilters,
  ProductoCreatePayload,
  ProductoUpdatePayload,
  DisponibilidadUpdatePayload,
  AsociarIngredientePayload,
} from '../model/types'

/** List products with optional filters and pagination. */
export async function listProductos(
  filters?: ProductoListFilters,
): Promise<PaginatedProductos> {
  const { data } = await http.get<PaginatedProductos>(PRODUCTOS, {
    params: filters,
  })
  return data
}

/** Get a single product with categories and ingredients by UUID string. */
export async function getProducto(id: string): Promise<ProductoDetail> {
  const { data } = await http.get<ProductoDetail>(`${PRODUCTOS}/${id}`)
  return data
}

/** Create a new product. Requires ADMIN role. */
export async function createProducto(
  body: ProductoCreatePayload,
): Promise<ProductoDetail> {
  const { data } = await http.post<ProductoDetail>(`${PRODUCTOS}/`, body)
  return data
}

/** Partial update of a product. Requires ADMIN role. */
export async function updateProducto(
  id: string,
  body: ProductoUpdatePayload,
): Promise<ProductoDetail> {
  const { data } = await http.patch<ProductoDetail>(`${PRODUCTOS}/${id}`, body)
  return data
}

/** Soft-delete a product by UUID string. Requires ADMIN role. Returns void on success (204). */
export async function deleteProducto(id: string): Promise<void> {
  await http.delete(`${PRODUCTOS}/${id}`)
}

/** Update the availability of a product. Requires ADMIN or STOCK role. */
export async function updateDisponibilidad(
  id: string,
  body: DisponibilidadUpdatePayload,
): Promise<ProductoDetail> {
  const { data } = await http.patch<ProductoDetail>(
    `${PRODUCTOS}/${id}/disponibilidad`,
    body,
  )
  return data
}

/** List ingredients associated with a product by UUID string. */
export async function listProductoIngredientes(
  id: string,
): Promise<ProductoIngredienteRead[]> {
  const { data } = await http.get<ProductoIngredienteRead[]>(
    `${PRODUCTOS}/${id}/ingredientes`,
  )
  return data
}

/** Associate an ingredient with a product. Requires ADMIN role. */
export async function asociarIngrediente(
  id: string,
  body: AsociarIngredientePayload,
): Promise<ProductoIngredienteRead> {
  const { data } = await http.post<ProductoIngredienteRead>(
    `${PRODUCTOS}/${id}/ingredientes`,
    body,
  )
  return data
}

/** Remove an ingredient from a product. Requires ADMIN role. Returns void on success (204). */
export async function removerIngrediente(
  productoId: string,
  ingredienteId: string,
): Promise<void> {
  await http.delete(`${PRODUCTOS}/${productoId}/ingredientes/${ingredienteId}`)
}
