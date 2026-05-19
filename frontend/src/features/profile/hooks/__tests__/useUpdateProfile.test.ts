/**
 * Tests for useUpdateProfile mutation hook.
 *
 * Task 5.3 — TDD.
 *
 * Tests:
 *   - mutate({ nombre, apellido }) sends PATCH to PROFILE_ME without email field
 *   - On success → queryClient.invalidateQueries with auth/me query key
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { createElement } from 'react'
import { PROFILE_ME } from '@/shared/api/endpoints'
import { queryKeys } from '@/shared/lib/queryKeys'

// Mock the http client
vi.mock('@/shared/api/http', () => ({
  http: {
    patch: vi.fn(),
  },
}))

describe('useUpdateProfile', () => {
  let queryClient: QueryClient

  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
        mutations: { retry: false },
      },
    })
    vi.clearAllMocks()
  })

  function wrapper({ children }: { children: React.ReactNode }) {
    return createElement(QueryClientProvider, { client: queryClient }, children)
  }

  it('sends PATCH to PROFILE_ME without email field', async () => {
    const { http } = await import('@/shared/api/http')
    const mockPatch = vi.mocked(http.patch)
    mockPatch.mockResolvedValueOnce({
      data: { id: '1', nombre: 'New', apellido: 'User', email: 'test@test.com', roles: [] },
    })

    const { useUpdateProfile } = await import('../useUpdateProfile')
    const { result } = renderHook(() => useUpdateProfile(), { wrapper })

    result.current.mutate({ nombre: 'New', apellido: 'User' })

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true)
    })

    expect(mockPatch).toHaveBeenCalledWith(PROFILE_ME, { nombre: 'New', apellido: 'User' })
    // Verify no email field was sent
    const callArgs = mockPatch.mock.calls[0]
    expect(callArgs[1]).not.toHaveProperty('email')
  })

  it('on success invalidates the auth/me query key', async () => {
    const { http } = await import('@/shared/api/http')
    const mockPatch = vi.mocked(http.patch)
    mockPatch.mockResolvedValueOnce({
      data: { id: '1', nombre: 'New', apellido: 'User', email: 'test@test.com', roles: [] },
    })

    const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries')

    const { useUpdateProfile } = await import('../useUpdateProfile')
    const { result } = renderHook(() => useUpdateProfile(), { wrapper })

    result.current.mutate({ nombre: 'New' })

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true)
    })

    expect(invalidateSpy).toHaveBeenCalledWith(
      expect.objectContaining({ queryKey: queryKeys.auth.me() })
    )
  })
})
