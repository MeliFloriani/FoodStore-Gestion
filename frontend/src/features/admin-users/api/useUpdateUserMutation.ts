/**
 * useUpdateUserMutation — TanStack Query mutation for updating user data.
 *
 * Change 21: admin-users-management.
 *
 * Endpoint: PUT /api/v1/admin/usuarios/{id}
 * Body: UsuarioAdminUpdate { nombre?, apellido? }
 * D-01: email is NOT sent (not in UsuarioAdminUpdate type).
 *
 * On success: invalidates ['admin', 'users'] and ['admin', 'user', id].
 */

import { useMutation, useQueryClient } from '@tanstack/react-query'
import { http } from '@/shared/api/http'
import { ADMIN_USUARIOS } from '@/shared/api/endpoints'
import type { UsuarioAdminRead, UsuarioAdminUpdate } from '../types'

interface UpdateUserVars {
  id: string
  data: UsuarioAdminUpdate
}

export function useUpdateUserMutation() {
  const queryClient = useQueryClient()

  return useMutation<UsuarioAdminRead, Error, UpdateUserVars>({
    mutationFn: ({ id, data }: UpdateUserVars) =>
      http
        .put<UsuarioAdminRead>(`${ADMIN_USUARIOS}/${id}`, data)
        .then((r) => r.data),
    onSuccess: (_, { id }) => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'users'] })
      queryClient.invalidateQueries({ queryKey: ['admin', 'user', id] })
    },
  })
}
