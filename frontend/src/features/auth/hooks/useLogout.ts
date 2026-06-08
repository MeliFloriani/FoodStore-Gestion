/**
 * useLogout — orchestrates the full client-side logout flow.
 *
 * Flow:
 *   1. POST /api/v1/auth/logout (best-effort, backend invalidates refresh token in DB).
 *   2. Clear local auth store (tokens + user → status = 'unauthenticated').
 *   3. Clear TanStack Query cache so any user-scoped query is dropped.
 *   4. Navigate to /login with replace=true so the user cannot go "back" into a protected route.
 *
 * The backend call is wrapped in try/catch: if the request fails (network down,
 * server 5xx, etc.) we still clear local state. This mirrors the policy already
 * documented in `shared/api/http.ts` for refresh failures — we never leave the
 * UI in a half-logged-in state.
 */

import { useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import { http } from '@/shared/api/http'
import { AUTH_LOGOUT } from '@/shared/api/endpoints'
import { useAuthStore } from '@/entities/auth/model/store'
import { useToast } from '@/shared/ui/toast'

export function useLogout() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const storeLogout = useAuthStore((s) => s.logout)
  const { toast } = useToast()

  return useCallback(async () => {
    try {
      await http.post(AUTH_LOGOUT)
    } catch {
      // Ignore: tokens may already be expired or the network may be down.
      // Local state must be cleared regardless to avoid a stale-session UI.
    }
    toast({ variant: 'success', title: 'Sesión cerrada', description: 'Hasta pronto.' })
    storeLogout()
    queryClient.clear()
    navigate('/login', { replace: true })
  }, [navigate, queryClient, storeLogout, toast])
}
