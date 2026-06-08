/**
 * Tests for useCreateOrder hook (Change 17).
 *
 * Tasks 13.1-13.4:
 *   13.2 — payload includes exclusiones as string[] (UUIDs, not parsed integers)
 *   13.3 — on success: isSuccess=true, clearCart() was called
 *   13.4 — on 409 INSUFFICIENT_STOCK: isError=true, cart NOT cleared
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

// Mock cartStore with controlled items and clearCart spy
const mockItems: CartItem[] = []
const mockClearCart = vi.fn()

vi.mock('@/entities/cart/model/store', () => ({
  useCartStore: vi.fn((selector: (s: { items: CartItem[]; clearCart: () => void }) => unknown) =>
    selector({ items: mockItems, clearCart: mockClearCart }),
  ),
}))

// ---------------------------------------------------------------------------
// Setup
// ---------------------------------------------------------------------------

describe('useCreateOrder', () => {
  let queryClient: QueryClient

  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
        mutations: { retry: false },
      },
    })
    vi.clearAllMocks()
    mockItems.length = 0
    mockClearCart.mockReset()
  })

  function wrapper({ children }: { children: React.ReactNode }) {
    return createElement(QueryClientProvider, { client: queryClient }, children)
  }

  // -------------------------------------------------------------------------
  // Task 13.2: exclusiones are UUID strings, NOT parsed as integers
  // -------------------------------------------------------------------------
  it('Task 13.2: sends exclusiones as string[] (UUID strings, not parseInt)', async () => {
    const { http } = await import('@/shared/api/http')
    const mockPost = vi.mocked(http.post)

    const uuidExclusion = '550e8400-e29b-41d4-a716-446655440000'

    mockPost.mockResolvedValueOnce({
      data: {
        id: 'order-uuid',
        usuario_id: 'user-uuid',
        estado_codigo: 'PENDIENTE',
        forma_pago_codigo: 'EFECTIVO',
        direccion_id: null,
        subtotal: '100.00',
        costo_envio: '0.00',
        total: '100.00',
        notas: null,
        items: [],
        historial: [],
        created_at: '2026-05-20T00:00:00Z',
      },
    })

    // Add a cart item with UUID exclusions
    mockItems.push({
      producto_id: 'prod-uuid-1',
      nombre: 'Pizza',
      precio: 100,
      cantidad: 1,
      imagen_url: '',
      personalizacion: [uuidExclusion],  // UUID string
    })

    const { useCreateOrder } = await import('../useCreateOrder')
    const { result } = renderHook(() => useCreateOrder(), { wrapper })

    await act(async () => {
      await result.current.mutateAsync({
        forma_pago_codigo: 'EFECTIVO',
        direccion_id: null,
      })
    })

    expect(mockPost).toHaveBeenCalledWith('/pedidos', {
      items: [
        expect.objectContaining({
          producto_id: 'prod-uuid-1',
          cantidad: 1,
          exclusiones: [uuidExclusion],  // UUID string, NOT parseInt result (NaN)
        }),
      ],
      forma_pago_codigo: 'EFECTIVO',
      direccion_id: null,
    })

    // Verify exclusiones is string[], not NaN[]
    const callArgs = mockPost.mock.calls[0]
    const requestBody = callArgs[1] as { items: Array<{ exclusiones: unknown[] }> }
    const sentExclusion = requestBody.items[0].exclusiones[0]
    expect(typeof sentExclusion).toBe('string')
    expect(sentExclusion).toBe(uuidExclusion)
    expect(Number.isNaN(sentExclusion)).toBe(false)
  })

  // -------------------------------------------------------------------------
  // Task 13.3: success → isSuccess=true, clearCart() called
  // -------------------------------------------------------------------------
  it('Task 13.3: on success, isSuccess=true and clearCart() is called', async () => {
    const { http } = await import('@/shared/api/http')
    const mockPost = vi.mocked(http.post)

    mockPost.mockResolvedValueOnce({
      data: {
        id: 'order-uuid',
        usuario_id: 'user-uuid',
        estado_codigo: 'PENDIENTE',
        forma_pago_codigo: 'EFECTIVO',
        direccion_id: null,
        subtotal: '100.00',
        costo_envio: '0.00',
        total: '100.00',
        notas: null,
        items: [],
        historial: [
          {
            id: 'hist-uuid',
            estado_desde: null,
            estado_hacia: 'PENDIENTE',
            motivo: null,
            created_at: '2026-05-20T00:00:00Z',
          },
        ],
        created_at: '2026-05-20T00:00:00Z',
      },
    })

    mockItems.push({
      producto_id: 'prod-uuid-1',
      nombre: 'Pizza',
      precio: 100,
      cantidad: 2,
      imagen_url: '',
      personalizacion: [],
    })

    const { useCreateOrder } = await import('../useCreateOrder')
    const { result } = renderHook(() => useCreateOrder(), { wrapper })

    await act(async () => {
      await result.current.mutateAsync({
        forma_pago_codigo: 'EFECTIVO',
        direccion_id: null,
      })
    })

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true)
    })

    // Cart must be cleared on success (D-13)
    expect(mockClearCart).toHaveBeenCalledTimes(1)

    // Response data available
    expect(result.current.data?.estado_codigo).toBe('PENDIENTE')
    expect(result.current.data?.historial[0].estado_desde).toBeNull()
  })

  // -------------------------------------------------------------------------
  // Task 13.4: 409 INSUFFICIENT_STOCK → isError=true, cart NOT cleared
  // -------------------------------------------------------------------------
  it('Task 13.4: on 409 INSUFFICIENT_STOCK, isError=true and cart is NOT cleared', async () => {
    const { http } = await import('@/shared/api/http')
    const mockPost = vi.mocked(http.post)

    const axiosError = Object.assign(new Error('Conflict'), {
      response: {
        status: 409,
        data: {
          code: 'INSUFFICIENT_STOCK',
          detail: { stock_disponible: 0, cantidad_solicitada: 1 },
          status: 409,
          title: 'Conflict',
        },
      },
      isAxiosError: true,
    })
    mockPost.mockRejectedValueOnce(axiosError)

    mockItems.push({
      producto_id: 'prod-uuid-1',
      nombre: 'Pizza',
      precio: 100,
      cantidad: 1,
      imagen_url: '',
      personalizacion: [],
    })

    const { useCreateOrder } = await import('../useCreateOrder')
    const { result } = renderHook(() => useCreateOrder(), { wrapper })

    await act(async () => {
      try {
        await result.current.mutateAsync({
          forma_pago_codigo: 'EFECTIVO',
          direccion_id: null,
        })
      } catch {
        // expected to throw on error
      }
    })

    await waitFor(() => {
      expect(result.current.isError).toBe(true)
    })

    // Cart must NOT be cleared on error (D-13)
    expect(mockClearCart).not.toHaveBeenCalled()
  })
})
