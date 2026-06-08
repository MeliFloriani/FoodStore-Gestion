/**
 * useUsersQuery — TanStack Query hook for fetching paginated user list.
 *
 * Change 21: admin-users-management.
 *
 * Query key: ['admin', 'users', params]
 * Endpoint: GET /api/v1/admin/usuarios
 * staleTime: 30 seconds
 *
 * q param: only sent to server if q.length >= 3 or q is empty/undefined.
 * (Prevents full-table scans on short search terms.)
 */

import { useQuery } from '@tanstack/react-query'
import { http } from '@/shared/api/http'
import { ADMIN_USUARIOS } from '@/shared/api/endpoints'
import type { UsuarioAdminRead, UsersQueryParams } from '../types'

/** Generic paginated response envelope (mirrors backend Page[T]). */
export interface UsersPage {
  items: UsuarioAdminRead[]
  total: number
  page: number
  size: number
  pages: number
}

/**
 * Fetch a paginated list of users for the admin panel.
 *
 * @param params - Filter and pagination params. q is omitted if fewer than 3 chars.
 */
export function useUsersQuery(params: UsersQueryParams) {
  // Only send q to the server if it's >= 3 chars or empty/undefined
  const effectiveQ =
    params.q !== undefined && params.q.length > 0 && params.q.length < 3
      ? undefined
      : params.q

  const effectiveParams: UsersQueryParams = {
    ...params,
    q: effectiveQ,
  }

  return useQuery<UsersPage, Error>({
    queryKey: ['admin', 'users', effectiveParams],
    queryFn: async () => {
      const response = await http.get<UsersPage>(ADMIN_USUARIOS, {
        params: effectiveParams,
      })
      return response.data
    },
    staleTime: 30_000,
  })
}
