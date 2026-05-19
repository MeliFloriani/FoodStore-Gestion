/**
 * Plain async fetchers for the Ingrediente entity.
 *
 * Uses the shared Axios instance (http) from @/shared/api/http.
 * Query parameter names are snake_case to match FastAPI's expected format.
 *
 * These are NOT React hooks — they live in api/ following FSD conventions.
 * The React Query hooks that wrap these live in api/hooks.ts.
 */

import { http } from '@/shared/api/http'
import { INGREDIENTES } from '@/shared/api/endpoints'
import type { Ingrediente, IngredienteCreate, IngredienteUpdate } from '../model/types'

/** List all active ingredients, optionally filtered by es_alergeno. */
export async function listIngredientes(params?: {
  es_alergeno?: boolean
}): Promise<Ingrediente[]> {
  const { data } = await http.get<Ingrediente[]>(INGREDIENTES, {
    params: params?.es_alergeno !== undefined ? { es_alergeno: params.es_alergeno } : undefined,
  })
  return data
}

/** Get a single ingredient by UUID string. */
export async function getIngrediente(id: string): Promise<Ingrediente> {
  const { data } = await http.get<Ingrediente>(`${INGREDIENTES}/${id}`)
  return data
}

/** Create a new ingredient. */
export async function createIngrediente(body: IngredienteCreate): Promise<Ingrediente> {
  const { data } = await http.post<Ingrediente>(`${INGREDIENTES}/`, body)
  return data
}

/** Update an existing ingredient (partial update — only supplied fields are changed). */
export async function updateIngrediente(
  id: string,
  body: IngredienteUpdate,
): Promise<Ingrediente> {
  const { data } = await http.put<Ingrediente>(`${INGREDIENTES}/${id}`, body)
  return data
}

/** Soft-delete an ingredient by UUID string. Returns void on success (204). */
export async function deleteIngrediente(id: string): Promise<void> {
  await http.delete(`${INGREDIENTES}/${id}`)
}
