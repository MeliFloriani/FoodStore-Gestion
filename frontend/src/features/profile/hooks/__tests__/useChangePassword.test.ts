/**
 * Tests for useChangePassword mutation hook.
 *
 * Task 5.5 — TDD.
 *
 * Tests:
 *   - mutate({ current_password, new_password }) sends POST to PROFILE_ME_PASSWORD
 *     WITHOUT password_confirm
 *   - On 409 error → isError is true, error contains the HTTP error response
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { createElement } from 'react'
import axios from 'axios'
import { PROFILE_ME_PASSWORD } from '@/shared/api/endpoints'

// Mock the http client
vi.mock('@/shared/api/http', () => ({
  http: {
    post: vi.fn(),
  },
}))

describe('useChangePassword', () => {
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

  it('sends POST to PROFILE_ME_PASSWORD without password_confirm', async () => {
    const { http } = await import('@/shared/api/http')
    const mockPost = vi.mocked(http.post)
    mockPost.mockResolvedValueOnce({ data: null, status: 204 })

    const { useChangePassword } = await import('../useChangePassword')
    const { result } = renderHook(() => useChangePassword(), { wrapper })

    result.current.mutate({ current_password: 'OldPass1!', new_password: 'NewPass1!' })

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true)
    })

    expect(mockPost).toHaveBeenCalledWith(PROFILE_ME_PASSWORD, {
      current_password: 'OldPass1!',
      new_password: 'NewPass1!',
    })

    // Verify password_confirm was NOT sent
    const callArgs = mockPost.mock.calls[0]
    expect(callArgs[1]).not.toHaveProperty('password_confirm')
  })

  it('on 409 error → isError is true', async () => {
    const { http } = await import('@/shared/api/http')
    const mockPost = vi.mocked(http.post)

    // Simulate axios 409 error
    const axiosError = new Error('Request failed with status code 409') as Error & {
      isAxiosError: boolean
      response: { status: number; data: { detail: string; code: string } }
    }
    axiosError.isAxiosError = true
    axiosError.response = {
      status: 409,
      data: { detail: 'La contraseña actual no coincide', code: 'CURRENT_PASSWORD_MISMATCH' },
    }
    mockPost.mockRejectedValueOnce(axiosError)

    const { useChangePassword } = await import('../useChangePassword')
    const { result } = renderHook(() => useChangePassword(), { wrapper })

    result.current.mutate({ current_password: 'WrongPass!', new_password: 'NewPass1!' })

    await waitFor(() => {
      expect(result.current.isError).toBe(true)
    })

    expect(result.current.isError).toBe(true)
    expect(result.current.error).toBeDefined()
  })
})
