/**
 * TanStack Query hook for the authenticated user's order list (Change 20).
 *
 * Wraps GET /api/v1/pedidos via listMisPedidos().
 * staleTime = 30 s — avoids unnecessary re-fetches on quick navigation.
 *
 * Design decisions:
 * - Uses TanStack Query useQuery (not useMutation) because order listing is a
 *   read operation that benefits from caching and background refetch.
 * - queryKey ['mis-pedidos'] is intentionally short — the user always sees
 *   their own orders (scoped by JWT on the backend). No user-id in the key.
 * - refetch is exposed so the UI can offer a manual retry on error.
 */

import { useQuery } from '@tanstack/react-query'
import { listMisPedidos } from '../api/listMisPedidos'
import type { PedidoRead } from '@/features/checkout/model/types'

/**
 * Fetch and cache the authenticated user's orders.
 *
 * @returns TanStack Query result with:
 *   - data: PedidoRead[] | undefined (undefined while loading or on error)
 *   - isLoading: true during the initial fetch
 *   - isError: true if the request failed
 *   - error: Error object on failure (AxiosError in practice)
 *   - refetch: manual trigger to re-fetch (e.g. retry after error)
 */
export function useMisPedidos() {
  const query = useQuery<PedidoRead[], Error>({
    queryKey: ['mis-pedidos'],
    queryFn: () => listMisPedidos(),
    staleTime: 30_000,
  })

  return {
    data: query.data,
    isLoading: query.isLoading,
    isError: query.isError,
    error: query.error,
    refetch: query.refetch,
  }
}
