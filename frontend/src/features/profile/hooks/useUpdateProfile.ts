/**
 * useUpdateProfile — TanStack Query mutation hook for updating profile.
 *
 * Change 13: customer-profile-management.
 *
 * Calls PATCH /api/v1/profile/me with { nombre, apellido } only.
 * On success, invalidates the auth/me query key so the user data is refreshed.
 *
 * NOTE: email is NOT included in the payload — it is immutable on the backend
 * (ProfileUpdate schema uses extra='ignore' to silently drop it).
 */

import { useMutation, useQueryClient } from '@tanstack/react-query'
import { http } from '@/shared/api/http'
import { PROFILE_ME } from '@/shared/api/endpoints'
import { queryKeys } from '@/shared/lib/queryKeys'
import type { User } from '@/entities/auth/types'

/** Profile update payload — only editable fields (no email). */
export type ProfileUpdatePayload = {
  nombre?: string
  apellido?: string
}

/**
 * Mutation hook for PATCH /api/v1/profile/me.
 *
 * On success, invalidates the auth.me query key so AuthSync re-fetches
 * the user profile and the store is updated.
 */
export function useUpdateProfile() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (data: ProfileUpdatePayload) =>
      http.patch<User>(PROFILE_ME, data).then((res) => res.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.auth.me() })
    },
  })
}
