/**
 * Tests for useValidatePreCheckout hook.
 *
 * Tasks 9.1-9.5:
 *   9.2 - precio number → string ".XX" in payload
 *   9.3 - ok=true on successful response
 *   9.4 - isError=true on 401
 *   9.5 - isPending is true while mutation is in-flight
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, waitFor, act } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { createElement } from 'react'
import type { CartItem } from '@/entities/cart/types'

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

// Mock the http client
vi.mock('@/shared/api/http', () => ({
  http: {
    post: vi.fn(),
  },
}))

// Mock cartStore to control items returned
const mockItems: CartItem[] = []
vi.mock('@/entities/cart/model/store', () => ({
  useCartStore: vi.fn((selector: (s: { items: CartItem[] }) => unknown) =>
    selector({ items: mockItems }),
  ),
}))

// ---------------------------------------------------------------------------
// Setup
// ---------------------------------------------------------------------------

describe('useValidatePreCheckout', () => {
  let queryClient: QueryClient

  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
        mutations: { retry: false },
      },
    })
    vi.clearAllMocks()
    // Reset mock items
    mockItems.length = 0
  })

  function wrapper({ children }: { children: React.ReactNode }) {
    return createElement(QueryClientProvider, { client: queryClient }, children)
  }

  // -------------------------------------------------------------------------
  // Task 9.2 — precio number → string ".XX" in payload
  // -------------------------------------------------------------------------
  it('Task 9.2: converts precio from number to string with 2 decimal places', async () => {
    const { http } = await import('@/shared/api/http')
    const mockPost = vi.mocked(http.post)

    mockPost.mockResolvedValueOnce({
      data: { ok: true, items: [], cambios: [] },
    })

    // Add a cart item with precio as number
    mockItems.push({
      producto_id: 'prod-uuid-1',
      nombre: 'Pizza',
      precio: 250, // number — should become "250.00"
      cantidad: 1,
      imagen_url: '',
      personalizacion: [],
    })

    const { useValidatePreCheckout } = await import('../useValidatePreCheckout')
    const { result } = renderHook(() => useValidatePreCheckout(), { wrapper })

    await act(async () => {
      await result.current.mutateAsync()
    })

    expect(mockPost).toHaveBeenCalledWith('/pedidos/validar', {
      items: [
        expect.objectContaining({
          producto_id: 'prod-uuid-1',
          precio: '250.00', // Must be string "250.00", not number 250
        }),
      ],
    })
  })

  // -------------------------------------------------------------------------
  // Task 9.3 — ok=true on successful response
  // -------------------------------------------------------------------------
  it('Task 9.3: data.ok === true on successful response', async () => {
    const { http } = await import('@/shared/api/http')
    const mockPost = vi.mocked(http.post)

    mockPost.mockResolvedValueOnce({
      data: {
        ok: true,
        items: [
          {
            producto_id: 'prod-uuid-1',
            cantidad_solicitada: 1,
            stock_disponible: 5,
            precio_actual: '100.00',
            precio_percibido: '100.00',
            vigente: true,
            disponible: true,
          },
        ],
        cambios: [],
      },
    })

    mockItems.push({
      producto_id: 'prod-uuid-1',
      nombre: 'Test',
      precio: 100,
      cantidad: 1,
      imagen_url: '',
      personalizacion: [],
    })

    const { useValidatePreCheckout } = await import('../useValidatePreCheckout')
    const { result } = renderHook(() => useValidatePreCheckout(), { wrapper })

    await act(async () => {
      await result.current.mutateAsync()
    })

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true)
    })

    expect(result.current.data?.ok).toBe(true)
    expect(result.current.data?.cambios).toEqual([])
  })

  // -------------------------------------------------------------------------
  // Task 9.4 — isError=true on 401
  // -------------------------------------------------------------------------
  it('Task 9.4: isError === true on 401 response', async () => {
    const { http } = await import('@/shared/api/http')
    const mockPost = vi.mocked(http.post)

    const axiosError = Object.assign(new Error('Unauthorized'), {
      response: { status: 401 },
      isAxiosError: true,
    })
    mockPost.mockRejectedValueOnce(axiosError)

    mockItems.push({
      producto_id: 'prod-uuid-1',
      nombre: 'Test',
      precio: 100,
      cantidad: 1,
      imagen_url: '',
      personalizacion: [],
    })

    const { useValidatePreCheckout } = await import('../useValidatePreCheckout')
    const { result } = renderHook(() => useValidatePreCheckout(), { wrapper })

    await act(async () => {
      try {
        await result.current.mutateAsync()
      } catch {
        // expected to throw
      }
    })

    await waitFor(() => {
      expect(result.current.isError).toBe(true)
    })
  })

  // -------------------------------------------------------------------------
  // Task 9.5 — isPending is true while mutation is in-flight
  // -------------------------------------------------------------------------
  it('Task 9.5: isPending is true while the mutation is in-flight', async () => {
    const { http } = await import('@/shared/api/http')
    const mockPost = vi.mocked(http.post)

    // Return a promise that never resolves during the test to keep isPending=true
    let resolvePost!: (value: unknown) => void
    const pendingPromise = new Promise((res) => {
      resolvePost = res
    })
    mockPost.mockReturnValueOnce(pendingPromise as ReturnType<typeof mockPost>)

    mockItems.push({
      producto_id: 'prod-uuid-1',
      nombre: 'Test',
      precio: 100,
      cantidad: 1,
      imagen_url: '',
      personalizacion: [],
    })

    const { useValidatePreCheckout } = await import('../useValidatePreCheckout')
    const { result } = renderHook(() => useValidatePreCheckout(), { wrapper })

    // Start mutation without awaiting
    act(() => {
      void result.current.mutateAsync()
    })

    await waitFor(() => {
      expect(result.current.isPending).toBe(true)
    })

    // Resolve the promise to clean up
    resolvePost({ data: { ok: true, items: [], cambios: [] } })
  })
})
