/**
 * useUpdateUserRolesMutation — TanStack Query mutation for replacing user roles.
 *
 * Change 21: admin-users-management.
 *
 * Endpoint: PUT /api/v1/admin/usuarios/{id}/roles
 * Body: UsuarioRolesUpdate { roles: string[] }
 * Semantics: PUT replace — payload is the COMPLETE desired set of roles (D-02).
 *
 * On success: invalidates ['admin', 'users'].
 * On error LAST_ADMIN_PROTECTED: does NOT invalidate cache — propagates error
 *   for the UI to show an inline message.
 */

import { useMutation, useQueryClient } from '@tanstack/react-query'
import { http } from '@/shared/api/http'
import { ADMIN_USUARIOS } from '@/shared/api/endpoints'
import type { UsuarioAdminRead, UsuarioRolesUpdate } from '../types'

interface UpdateUserRolesVars {
  id: string
  data: UsuarioRolesUpdate
}

/** Backend RFC 7807 error shape. */
interface ApiError {
  code?: string
  detail?: string
}

function getErrorCode(error: unknown): string | undefined {
  if (error && typeof error === 'object' && 'response' in error) {
    const response = (error as { response?: { data?: ApiError } }).response
    return response?.data?.code
  }
  return undefined
}

export function useUpdateUserRolesMutation() {
  const queryClient = useQueryClient()

  return useMutation<UsuarioAdminRead, Error, UpdateUserRolesVars>({
    mutationFn: ({ id, data }: UpdateUserRolesVars) =>
      http
        .put<UsuarioAdminRead>(`${ADMIN_USUARIOS}/${id}/roles`, data)
        .then((r) => r.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'users'] })
    },
    onError: (error) => {
      // On LAST_ADMIN_PROTECTED: do NOT invalidate cache — let UI handle the error message.
      const code = getErrorCode(error)
      if (code !== 'LAST_ADMIN_PROTECTED') {
        // For other errors, still invalidate to refresh stale data
        queryClient.invalidateQueries({ queryKey: ['admin', 'users'] })
      }
    },
  })
}

export { getErrorCode }
