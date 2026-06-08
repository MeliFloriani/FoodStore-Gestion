/**
 * Tests for DireccionEntrega entity hooks.
 *
 * Change 14: delivery-addresses-management.
 *
 * Tests:
 *   - useAddresses is disabled when user is not authenticated (enabled: false)
 *   - useAddresses fetches when user is authenticated
 *   - useCreateAddress invalidates ['addresses'] cache on success
 *   - useDeleteAddress invalidates ['addresses'] cache on success
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import AxiosMockAdapter from 'axios-mock-adapter'
import { renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { createElement } from 'react'
import { http } from '@/shared/api/http'
import type { DireccionEntrega } from '../model/types'

// Mock auth store — controls enabled state of useAddresses
let mockUser: { id: string; email: string } | null = null

vi.mock('@/entities/auth/model/store', () => {
  const useAuthStore = (selector: (state: { user: typeof mockUser }) => unknown) => {
    return selector({ user: mockUser })
  }
  // Provide getState so the http interceptor (useAuthStore.getState().accessToken) doesn't throw
  useAuthStore.getState = () => ({ user: mockUser, accessToken: null, refreshToken: null })
  return { useAuthStore }
})

// ---------------------------------------------------------------------------
// Sample data
// ---------------------------------------------------------------------------

const mockAddress: DireccionEntrega = {
  id: 'addr-uuid-001',
  usuario_id: 'user-uuid-001',
  alias: 'Casa',
  linea1: 'Av. Siempre Viva 742',
  linea2: null,
  ciudad: 'Springfield',
  provincia: null,
  codigo_postal: null,
  referencia: null,
  es_principal: true,
  created_at: '2026-05-20T00:00:00Z',
  updated_at: '2026-05-20T00:00:00Z',
}

// ---------------------------------------------------------------------------
// Test helpers
// ---------------------------------------------------------------------------

function makeWrapper(queryClient: QueryClient) {
  return ({ children }: { children: React.ReactNode }) =>
    createElement(QueryClientProvider, { client: queryClient }, children)
}

function makeQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0 },
      mutations: { retry: false },
    },
  })
}

// ---------------------------------------------------------------------------
// Task 10.2 — useAddresses is disabled when user is not authenticated
// ---------------------------------------------------------------------------

describe('useAddresses', () => {
  let axiosMock: AxiosMockAdapter
  let queryClient: QueryClient

  beforeEach(() => {
    axiosMock = new AxiosMockAdapter(http)
    queryClient = makeQueryClient()
    vi.clearAllMocks()
  })

  afterEach(() => {
    axiosMock.restore()
    queryClient.clear()
  })

  it('does not fetch when user is not authenticated (enabled: false)', async () => {
    mockUser = null // unauthenticated
    axiosMock.onGet('/api/v1/direcciones').reply(200, [mockAddress])

    const { useAddresses } = await import('../api/use-direcciones')
    const { result } = renderHook(() => useAddresses(), {
      wrapper: makeWrapper(queryClient),
    })

    // Query should not be pending or fetching — it's disabled
    expect(result.current.fetchStatus).toBe('idle')
    expect(result.current.data).toBeUndefined()

    // Axios should NOT have been called
    expect(axiosMock.history.get.length).toBe(0)
  })

  it('fetches when user is authenticated', async () => {
    mockUser = { id: 'user-uuid-001', email: 'test@test.com' }
    axiosMock.onGet('/api/v1/direcciones').reply(200, [mockAddress])

    const { useAddresses } = await import('../api/use-direcciones')
    const { result } = renderHook(() => useAddresses(), {
      wrapper: makeWrapper(queryClient),
    })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data).toHaveLength(1)
    expect(result.current.data?.[0].linea1).toBe('Av. Siempre Viva 742')
  })
})

// ---------------------------------------------------------------------------
// Task 10.3 — useCreateAddress invalidates ['addresses'] on success
// ---------------------------------------------------------------------------

describe('useCreateAddress', () => {
  let axiosMock: AxiosMockAdapter
  let queryClient: QueryClient

  beforeEach(() => {
    axiosMock = new AxiosMockAdapter(http)
    queryClient = makeQueryClient()
    mockUser = { id: 'user-uuid-001', email: 'test@test.com' }
    vi.clearAllMocks()
  })

  afterEach(() => {
    axiosMock.restore()
    queryClient.clear()
  })

  it('invalidates addresses cache on success', async () => {
    axiosMock.onPost('/api/v1/direcciones').reply(201, mockAddress)
    axiosMock.onGet('/api/v1/direcciones').reply(200, [mockAddress])

    const { useCreateAddress } = await import('../api/use-direcciones')
    const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries')

    const { result } = renderHook(() => useCreateAddress(), {
      wrapper: makeWrapper(queryClient),
    })

    result.current.mutate({ linea1: 'Av. Siempre Viva 742' })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    expect(invalidateSpy).toHaveBeenCalledWith(
      expect.objectContaining({ queryKey: ['addresses'] }),
    )
  })
})

// ---------------------------------------------------------------------------
// useDeleteAddress invalidates ['addresses'] on success
// ---------------------------------------------------------------------------

describe('useDeleteAddress', () => {
  let axiosMock: AxiosMockAdapter
  let queryClient: QueryClient

  beforeEach(() => {
    axiosMock = new AxiosMockAdapter(http)
    queryClient = makeQueryClient()
    mockUser = { id: 'user-uuid-001', email: 'test@test.com' }
    vi.clearAllMocks()
  })

  afterEach(() => {
    axiosMock.restore()
    queryClient.clear()
  })

  it('invalidates addresses cache on success', async () => {
    axiosMock.onDelete('/api/v1/direcciones/addr-uuid-001').reply(204)

    const { useDeleteAddress } = await import('../api/use-direcciones')
    const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries')

    const { result } = renderHook(() => useDeleteAddress(), {
      wrapper: makeWrapper(queryClient),
    })

    result.current.mutate('addr-uuid-001')

    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    expect(invalidateSpy).toHaveBeenCalledWith(
      expect.objectContaining({ queryKey: ['addresses'] }),
    )
  })
})
