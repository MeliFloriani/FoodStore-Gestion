/**
 * Plain async fetchers for Categoria write operations.
 *
 * Read tree fetcher lives in getCategoriesTree.ts (kept separate to preserve
 * the original FSD boundary). Write fetchers (POST/PUT/DELETE) require
 * ADMIN or STOCK role at the backend.
 */
import { http } from '@/shared/api/http'
import { CATEGORIAS } from '@/shared/api/endpoints'
import type { Categoria, CategoriaCreate, CategoriaUpdate } from '../model/types'

/** Get a single category by UUID string. */
export async function getCategoria(id: string): Promise<Categoria> {
  const { data } = await http.get<Categoria>(`${CATEGORIAS}/${id}`)
  return data
}

/** Create a new category. */
export async function createCategoria(body: CategoriaCreate): Promise<Categoria> {
  const { data } = await http.post<Categoria>(`${CATEGORIAS}/`, body)
  return data
}

/** Partial update of a category. Only supplied fields are touched. */
export async function updateCategoria(
  id: string,
  body: CategoriaUpdate,
): Promise<Categoria> {
  const { data } = await http.put<Categoria>(`${CATEGORIAS}/${id}`, body)
  return data
}

/** Soft-delete a category by UUID string. Returns void on success (204). */
export async function deleteCategoria(id: string): Promise<void> {
  await http.delete(`${CATEGORIAS}/${id}`)
}
