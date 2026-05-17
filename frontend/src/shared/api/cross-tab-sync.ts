import { useAuthStore } from '@/entities/auth/model/store'
import { isRefreshing } from '@/shared/api/http'

/** The localStorage key used by Zustand persist for the auth store. */
const AUTH_STORE_KEY = 'food-store-auth'

type PersistedAuthState = {
  state: {
    accessToken: string | null
    refreshToken: string | null
  }
}

/**
 * Install a cross-tab synchronization listener for auth state.
 *
 * When another browser tab logs in or rotates tokens, this listener picks up
 * the updated `localStorage` entry and calls `updateTokens()` on this tab's
 * auth store — keeping all tabs in sync without a page reload.
 *
 * When another tab logs out (`localStorage.removeItem('food-store-auth')`),
 * this listener calls `logout()` on this tab, clearing local auth state.
 *
 * If a token refresh is already in progress on THIS tab (`isRefreshing()`),
 * the incoming cross-tab token update is skipped to prevent a race condition
 * where stale tokens from another tab overwrite the ones being acquired locally.
 *
 * @returns A cleanup function that removes the storage event listener.
 *          Call the returned function on component unmount (e.g., in a useEffect cleanup).
 */
export function initCrossTabSync(): () => void {
  function handleStorageEvent(e: StorageEvent): void {
    if (e.key !== AUTH_STORE_KEY) return

    if (e.newValue === null) {
      // Another tab cleared storage (logout)
      useAuthStore.getState().logout()
      return
    }

    // Another tab updated the auth state (login or token rotation)
    // Skip if THIS tab is already refreshing — avoid overwriting in-flight tokens
    if (isRefreshing()) return

    try {
      const parsed = JSON.parse(e.newValue) as PersistedAuthState
      const { accessToken, refreshToken } = parsed.state ?? {}
      if (accessToken && refreshToken) {
        useAuthStore.getState().updateTokens(accessToken, refreshToken)
      }
    } catch {
      // Malformed JSON — ignore silently
    }
  }

  window.addEventListener('storage', handleStorageEvent)

  return () => {
    window.removeEventListener('storage', handleStorageEvent)
  }
}
