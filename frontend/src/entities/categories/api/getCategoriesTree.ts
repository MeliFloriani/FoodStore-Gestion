/**
 * Fetcher for GET /api/v1/categorias — returns the full category tree.
 *
 * This is a plain async function (not a React hook) — lives in api/
 * following FSD conventions. The React hook wrapping this with useQuery
 * lives in model/useCategoriesTree.ts.
 */
import { http } from '@/shared/api/http'
import { CATEGORIAS } from '@/shared/api/endpoints'
import type { CategoriaTreeNode } from '../model/types'

export async function getCategoriesTree(): Promise<CategoriaTreeNode[]> {
  const { data } = await http.get<CategoriaTreeNode[]>(CATEGORIAS)
  return data
}
