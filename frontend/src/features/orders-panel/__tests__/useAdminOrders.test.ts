/**
 * Tests for useAdminOrders hook (Change 20 — Tasks 15.6–15.7)
 *
 * Task 15.6: omits ?cliente when < 3 chars
 * Task 15.7: includes ?cliente when >= 3 chars
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { createElement } from 'react'

vi.mock('@/shared/api/http', () => ({
  http: {
    get: vi.fn(),
  },
}))

const mockPedidoPage = {
  items: [],
  total: 0,
  page: 1,
  size: 20,
  pages: 0,
}

describe('useAdminOrders', () => {
  let queryClient: QueryClient

  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    })
    vi.clearAllMocks()
  })

  function wrapper({ children }: { children: React.ReactNode }) {
    return createElement(QueryClientProvider, { client: queryClient }, children)
  }

  // Task 15.6: omits ?cliente when < 3 characters
  it('15.6 — omits ?cliente when fewer than 3 characters', async () => {
    const { http } = await import('@/shared/api/http')
    const mockGet = vi.mocked(http.get)
    mockGet.mockResolvedValue({ data: mockPedidoPage })

    const { useAdminOrders } = await import('../hooks/useAdminOrders')
    const { result } = renderHook(
      () => useAdminOrders({ cliente: 'ab', page: 1 }),
      { wrapper },
    )

    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    // cliente='ab' (2 chars) should NOT be sent as a query param
    const callArgs = mockGet.mock.calls[0]
    const params = callArgs[1]?.params as Record<string, unknown> | undefined
    expect(params?.cliente).toBeUndefined()
  })

  // Task 15.7: includes ?cliente when >= 3 characters
  it('15.7 — includes ?cliente when 3+ characters', async () => {
    const { http } = await import('@/shared/api/http')
    const mockGet = vi.mocked(http.get)
    mockGet.mockResolvedValue({ data: mockPedidoPage })

    const { useAdminOrders } = await import('../hooks/useAdminOrders')
    const { result } = renderHook(
      () => useAdminOrders({ cliente: 'juan', page: 1 }),
      { wrapper },
    )

    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    // cliente='juan' (4 chars) SHOULD be sent
    const callArgs = mockGet.mock.calls[0]
    const params = callArgs[1]?.params as Record<string, unknown> | undefined
    expect(params?.cliente).toBe('juan')
  })

  it('omits cliente param when cliente is exactly 2 chars', async () => {
    const { http } = await import('@/shared/api/http')
    const mockGet = vi.mocked(http.get)
    mockGet.mockResolvedValue({ data: mockPedidoPage })

    const { useAdminOrders } = await import('../hooks/useAdminOrders')
    const { result } = renderHook(
      () => useAdminOrders({ cliente: 'jo' }),
      { wrapper },
    )

    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    const callArgs = mockGet.mock.calls[0]
    const params = callArgs[1]?.params as Record<string, unknown> | undefined
    expect(params?.cliente).toBeUndefined()
  })

  it('includes cliente param when exactly 3 chars', async () => {
    const { http } = await import('@/shared/api/http')
    const mockGet = vi.mocked(http.get)
    mockGet.mockResolvedValue({ data: mockPedidoPage })

    const { useAdminOrders } = await import('../hooks/useAdminOrders')
    const { result } = renderHook(
      () => useAdminOrders({ cliente: 'abc' }),
      { wrapper },
    )

    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    const callArgs = mockGet.mock.calls[0]
    const params = callArgs[1]?.params as Record<string, unknown> | undefined
    expect(params?.cliente).toBe('abc')
  })
})
