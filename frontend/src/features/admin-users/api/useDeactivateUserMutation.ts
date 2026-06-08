/**
 * useDeactivateUserMutation — TanStack Query mutation for deactivating a user.
 *
 * Change 21: admin-users-management.
 *
 * Endpoint: PATCH /api/v1/admin/usuarios/{id}/estado
 * Body: UsuarioEstadoUpdate { activo: boolean }
 *
 * Frontend scope (D-05, OQ-02 CLOSED): only exposes activo=false (deactivation).
 * The reactivation endpoint exists on the backend but is NOT wired to the UI.
 *
 * On success: invalidates ['admin', 'users'].
 * On error LAST_ADMIN_PROTECTED: propagates for UI to show specific message.
 */

import { useMutation, useQueryClient } from '@tanstack/react-query'
import { http } from '@/shared/api/http'
import { ADMIN_USUARIOS } from '@/shared/api/endpoints'
import type { UsuarioAdminRead, UsuarioEstadoUpdate } from '../types'

interface DeactivateUserVars {
  id: string
  data: UsuarioEstadoUpdate
}

export function useDeactivateUserMutation() {
  const queryClient = useQueryClient()

  return useMutation<UsuarioAdminRead, Error, DeactivateUserVars>({
    mutationFn: ({ id, data }: DeactivateUserVars) =>
      http
        .patch<UsuarioAdminRead>(`${ADMIN_USUARIOS}/${id}/estado`, data)
        .then((r) => r.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'users'] })
    },
    // On error, always propagate — caller decides whether to invalidate.
    // LAST_ADMIN_PROTECTED errors should show inline in the modal, not toast.
  })
}
