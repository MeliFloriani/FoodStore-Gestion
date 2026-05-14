import { describe, it, expect, beforeEach } from 'vitest'
import { useAuthStore } from '@/entities/auth/model/store'
import type { User } from '@/entities/auth/types'

const mockUser: User = {
  id: '550e8400-e29b-41d4-a716-446655440000',
  nombre: 'Test User',
  apellido: 'Test Apellido',
  email: 'test@example.com',
  roles: ['CLIENT'],
}

describe('authStore', () => {
  beforeEach(() => {
    useAuthStore.getState().clear()
  })

  it('initial state is idle with no tokens or user', () => {
    const state = useAuthStore.getState()
    expect(state.accessToken).toBeNull()
    expect(state.refreshToken).toBeNull()
    expect(state.user).toBeNull()
    expect(state.status).toBe('idle')
  })

  it('login sets tokens, user and status to authenticated', () => {
    useAuthStore.getState().login('access-token', 'refresh-token', mockUser)
    const state = useAuthStore.getState()
    expect(state.accessToken).toBe('access-token')
    expect(state.refreshToken).toBe('refresh-token')
    expect(state.user).toEqual(mockUser)
    expect(state.status).toBe('authenticated')
  })

  it('logout clears tokens, user and sets status to unauthenticated', () => {
    useAuthStore.getState().login('access-token', 'refresh-token', mockUser)
    useAuthStore.getState().logout()
    const state = useAuthStore.getState()
    expect(state.accessToken).toBeNull()
    expect(state.refreshToken).toBeNull()
    expect(state.user).toBeNull()
    expect(state.status).toBe('unauthenticated')
  })

  it('updateTokens replaces access and refresh tokens', () => {
    useAuthStore.getState().login('old-access', 'old-refresh', mockUser)
    useAuthStore.getState().updateTokens('new-access', 'new-refresh')
    const state = useAuthStore.getState()
    expect(state.accessToken).toBe('new-access')
    expect(state.refreshToken).toBe('new-refresh')
    // user and status unchanged
    expect(state.user).toEqual(mockUser)
  })

  it('hasRole returns true when user has the role', () => {
    useAuthStore.getState().login('token', 'refresh', mockUser)
    expect(useAuthStore.getState().hasRole('CLIENT')).toBe(true)
    expect(useAuthStore.getState().hasRole('ADMIN')).toBe(false)
  })

  it('hasRole returns false when user is null', () => {
    expect(useAuthStore.getState().hasRole('CLIENT')).toBe(false)
  })

  it('isAuthenticated returns true only when status is authenticated', () => {
    expect(useAuthStore.getState().isAuthenticated()).toBe(false)
    useAuthStore.getState().login('token', 'refresh', mockUser)
    expect(useAuthStore.getState().isAuthenticated()).toBe(true)
    useAuthStore.getState().logout()
    expect(useAuthStore.getState().isAuthenticated()).toBe(false)
  })

  it('triggerRehydrationFetch sets status to authenticating', () => {
    useAuthStore.getState().triggerRehydrationFetch()
    expect(useAuthStore.getState().status).toBe('authenticating')
  })

  it('partialize persists only accessToken and refreshToken', () => {
    // The persist middleware config is tested by verifying partialize logic
    useAuthStore.getState().login('token', 'refresh', mockUser)
    // We can inspect persist config via the store's persist property
    const persistApi = useAuthStore.persist
    const partial = persistApi.getOptions().partialize?.(useAuthStore.getState())
    expect(partial).toHaveProperty('accessToken', 'token')
    expect(partial).toHaveProperty('refreshToken', 'refresh')
    expect(partial).not.toHaveProperty('user')
    expect(partial).not.toHaveProperty('status')
  })

  it('onRehydrateStorage sets status to authenticating when accessToken present', () => {
    const onRehydrate = useAuthStore.persist.getOptions().onRehydrateStorage
    if (!onRehydrate) throw new Error('onRehydrateStorage not defined')
    // Simulate rehydration callback with a state that has a token
    const fakeState = {
      ...useAuthStore.getState(),
      accessToken: 'some-token',
      status: 'idle' as const,
    }
    // Call the factory to get the callback — pass current state as the argument
    const callback = onRehydrate(useAuthStore.getState())
    if (callback) {
      callback(fakeState, undefined)
      expect(fakeState.status).toBe('authenticating')
    }
  })
})
