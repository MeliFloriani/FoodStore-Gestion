/**
 * TanStack Query v5 hook for fetching the category tree.
 *
 * Lives in model/ (not api/) because it is a React hook using useQuery.
 * The api/ directory contains only non-hook fetcher functions.
 *
 * Uses queryKeys.catalog.categories() as the stable query key — this key
 * already exists in shared/lib/queryKeys.ts (no duplication needed).
 */
import { useQuery } from '@tanstack/react-query'
import { queryKeys } from '@/shared/lib/queryKeys'
import { getCategoriesTree } from '../api/getCategoriesTree'

export function useCategoriesTree() {
  return useQuery({
    queryKey: queryKeys.catalog.categories(),
    queryFn: getCategoriesTree,
  })
}
