import { useEffect } from 'react'
import { useAuthStore } from '@/entities/auth/model/store'
import { http } from '@/shared/api/http'
import { AUTH_ME } from '@/shared/api/endpoints'
import { initCrossTabSync } from '@/shared/api/cross-tab-sync'
import type { User } from '@/entities/auth/types'

/**
 * AuthSync — watches authStore.status === 'authenticating' and calls GET /auth/me.
 * Decouples the authStore (entities layer) from http.ts (shared/api layer).
 * Lives in app/providers/ because only app/ can import from both layers.
 *
 * Also initializes cross-tab storage synchronization on mount so that login,
 * logout, and token rotation events are propagated to all open tabs.
 */
export function AuthSync() {
  const status = useAuthStore((s) => s.status)
  const setUser = useAuthStore((s) => s.setUser)
  const logout = useAuthStore((s) => s.logout)

  // Initialize cross-tab sync once on mount; clean up on unmount.
  useEffect(() => {
    const cleanup = initCrossTabSync()
    return cleanup
  }, [])

  useEffect(() => {
    if (status !== 'authenticating') return

    let cancelled = false

    http
      .get<User>(AUTH_ME)
      .then((res) => {
        if (!cancelled) {
          setUser(res.data)
        }
      })
      .catch(() => {
        if (!cancelled) {
          logout()
        }
      })

    return () => {
      cancelled = true
    }
  }, [status, setUser, logout])

  return null
}
