/**
 * useLogout — hook integration tests.
 *
 * Verifies that the logout flow:
 *  - POSTs /api/v1/auth/logout to the backend
 *  - clears the local auth store (status → 'unauthenticated')
 *  - clears the TanStack Query cache
 *  - redirects to /login with replace=true
 *  - still cleans local state when the backend call fails
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import AxiosMockAdapter from 'axios-mock-adapter'
import { renderHook, act, waitFor } from '@testing-library/react'
import { MemoryRouter, Routes, Route, useLocation } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import { http } from '@/shared/api/http'
import { AUTH_LOGOUT } from '@/shared/api/endpoints'
import { useAuthStore } from '@/entities/auth/model/store'
import type { User } from '@/entities/auth/types'
import { useLogout } from '../useLogout'

const mockUser: User = {
  id: '550e8400-e29b-41d4-a716-446655440000',
  nombre: 'Test',
  apellido: 'User',
  email: 'test@example.com',
  roles: ['CLIENT'],
}

function makeQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0 },
      mutations: { retry: false },
    },
  })
}

function makeWrapper(queryClient: QueryClient, onLocationChange?: (path: string) => void) {
  function LocationProbe() {
    const location = useLocation()
    onLocationChange?.(location.pathname)
    return null
  }

  return ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={['/some-protected-route']}>
        <LocationProbe />
        <Routes>
          <Route path="*" element={<>{children}</>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  )
}

describe('useLogout', () => {
  let axiosMock: AxiosMockAdapter
  let queryClient: QueryClient

  beforeEach(() => {
    axiosMock = new AxiosMockAdapter(http)
    queryClient = makeQueryClient()
    // Seed an authenticated user.
    useAuthStore.getState().login('access-token', 'refresh-token', mockUser)
    // Seed some query cache to verify it gets wiped.
    queryClient.setQueryData(['auth', 'me'], mockUser)
    queryClient.setQueryData(['catalog', 'products'], [{ id: 1 }])
  })

  afterEach(() => {
    axiosMock.restore()
    useAuthStore.getState().clear()
    queryClient.clear()
    vi.restoreAllMocks()
  })

  it('POSTs to /auth/logout, clears store, clears query cache, and navigates to /login', async () => {
    axiosMock.onPost(AUTH_LOGOUT).reply(204)
    const paths: string[] = []
    const wrapper = makeWrapper(queryClient, (p) => paths.push(p))

    const { result } = renderHook(() => useLogout(), { wrapper })

    await act(async () => {
      await result.current()
    })

    // 1. Backend call made.
    expect(axiosMock.history.post.filter((r) => r.url === AUTH_LOGOUT)).toHaveLength(1)
    // 2. Auth store cleared.
    const state = useAuthStore.getState()
    expect(state.status).toBe('unauthenticated')
    expect(state.accessToken).toBeNull()
    expect(state.refreshToken).toBeNull()
    expect(state.user).toBeNull()
    // 3. Query cache wiped.
    expect(queryClient.getQueryData(['auth', 'me'])).toBeUndefined()
    expect(queryClient.getQueryData(['catalog', 'products'])).toBeUndefined()
    // 4. Redirected to /login.
    await waitFor(() => {
      expect(paths.at(-1)).toBe('/login')
    })
  })

  it('still clears local state and redirects when the backend logout call fails', async () => {
    axiosMock.onPost(AUTH_LOGOUT).reply(500)
    const paths: string[] = []
    const wrapper = makeWrapper(queryClient, (p) => paths.push(p))

    const { result } = renderHook(() => useLogout(), { wrapper })

    await act(async () => {
      await result.current()
    })

    // Backend was attempted.
    expect(axiosMock.history.post.filter((r) => r.url === AUTH_LOGOUT)).toHaveLength(1)
    // Local state still cleared — no half-logged-in UI.
    expect(useAuthStore.getState().status).toBe('unauthenticated')
    expect(queryClient.getQueryData(['auth', 'me'])).toBeUndefined()
    await waitFor(() => {
      expect(paths.at(-1)).toBe('/login')
    })
  })
})
