/**
 * useChangePassword — TanStack Query mutation hook for changing password.
 *
 * Change 13: customer-profile-management.
 *
 * Calls POST /api/v1/profile/me/password with { current_password, new_password }.
 * password_confirm is a client-side only field and is NEVER sent to the backend.
 *
 * The caller (ChangePasswordForm) is responsible for the logout+redirect flow
 * on onSuccess. This hook does NOT call authStore.logout() directly.
 */

import { useMutation } from '@tanstack/react-query'
import { http } from '@/shared/api/http'
import { PROFILE_ME_PASSWORD } from '@/shared/api/endpoints'

/** Change password payload — only current and new password (no password_confirm). */
export type ChangePasswordPayload = {
  current_password: string
  new_password: string
}

/**
 * Mutation hook for POST /api/v1/profile/me/password.
 *
 * Returns standard TanStack Query mutation state.
 * The caller is responsible for handling onSuccess (logout + redirect)
 * and onError (409 → inline error, 429 → toast).
 */
export function useChangePassword() {
  return useMutation({
    mutationFn: (data: ChangePasswordPayload) =>
      http.post(PROFILE_ME_PASSWORD, data).then((res) => res.data),
    // No onSuccess here — caller is responsible for logout() + navigate('/login')
    // This keeps the hook decoupled from navigation and auth state concerns.
  })
}
