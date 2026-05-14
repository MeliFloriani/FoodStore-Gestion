import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { User, AuthStatus } from '@/entities/auth/types'

type AuthState = {
  accessToken: string | null
  refreshToken: string | null
  user: User | null
  status: AuthStatus
}

type AuthActions = {
  setTokens: (accessToken: string, refreshToken: string) => void
  setUser: (user: User) => void
  login: (accessToken: string, refreshToken: string, user: User) => void
  updateTokens: (accessToken: string, refreshToken: string) => void
  logout: () => void
  clear: () => void
  triggerRehydrationFetch: () => void
  isAuthenticated: () => boolean
  hasRole: (role: string) => boolean
}

type AuthStore = AuthState & AuthActions

const initialState: AuthState = {
  accessToken: null,
  refreshToken: null,
  user: null,
  status: 'idle',
}

export const useAuthStore = create<AuthStore>()(
  persist(
    (set, get) => ({
      ...initialState,

      setTokens: (accessToken, refreshToken) =>
        set({ accessToken, refreshToken }),

      setUser: (user) => set({ user, status: 'authenticated' }),

      login: (accessToken, refreshToken, user) =>
        set({ accessToken, refreshToken, user, status: 'authenticated' }),

      updateTokens: (accessToken, refreshToken) =>
        set({ accessToken, refreshToken }),

      logout: () =>
        set({
          accessToken: null,
          refreshToken: null,
          user: null,
          status: 'unauthenticated',
        }),

      clear: () => set(initialState),

      triggerRehydrationFetch: () => set({ status: 'authenticating' }),

      isAuthenticated: () => get().status === 'authenticated',

      hasRole: (role: string) => get().user?.roles?.includes(role) ?? false,
    }),
    {
      name: 'food-store-auth',
      partialize: (state) => ({
        accessToken: state.accessToken,
        refreshToken: state.refreshToken,
      }),
      onRehydrateStorage: () => (state) => {
        if (state?.accessToken) {
          state.status = 'authenticating'
        }
      },
    },
  ),
)
