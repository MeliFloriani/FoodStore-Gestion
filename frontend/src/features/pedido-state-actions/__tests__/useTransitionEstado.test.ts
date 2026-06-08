/**
 * Tests for useTransitionEstado hook (Change 18).
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, act, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { createElement } from 'react'

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

vi.mock('@/shared/api/http', () => ({
  http: {
    patch: vi.fn(),
  },
}))

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('useTransitionEstado', () => {
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

  it('calls PATCH /pedidos/{id}/estado with correct body', async () => {
    const { http } = await import('@/shared/api/http')
    const mockPatch = vi.mocked(http.patch)

    const mockPedidoRead = {
      id: 'order-uuid',
      usuario_id: 'user-uuid',
      estado_codigo: 'EN_PREP',
      forma_pago_codigo: 'EFECTIVO',
      direccion_id: null,
      subtotal: '100.00',
      costo_envio: '0.00',
      total: '100.00',
      notas: null,
      items: [],
      historial: [],
      created_at: '2026-05-20T00:00:00Z',
    }

    mockPatch.mockResolvedValueOnce({ data: mockPedidoRead })

    const { useTransitionEstado } = await import('../hooks/useTransitionEstado')
    const { result } = renderHook(() => useTransitionEstado(), { wrapper })

    await act(async () => {
      await result.current.mutateAsync({
        pedidoId: 'order-uuid',
        request: { nuevo_estado: 'EN_PREP' },
      })
    })

    expect(mockPatch).toHaveBeenCalledWith('/pedidos/order-uuid/estado', {
      nuevo_estado: 'EN_PREP',
    })
  })

  it('returns updated PedidoRead on success', async () => {
    const { http } = await import('@/shared/api/http')
    const mockPatch = vi.mocked(http.patch)

    mockPatch.mockResolvedValueOnce({
      data: {
        id: 'order-uuid',
        estado_codigo: 'EN_CAMINO',
        forma_pago_codigo: 'EFECTIVO',
        usuario_id: 'user-uuid',
        direccion_id: null,
        subtotal: '100.00',
        costo_envio: '50.00',
        total: '150.00',
        notas: null,
        items: [],
        historial: [],
        created_at: '2026-05-20T00:00:00Z',
      },
    })

    const { useTransitionEstado } = await import('../hooks/useTransitionEstado')
    const { result } = renderHook(() => useTransitionEstado(), { wrapper })

    await act(async () => {
      await result.current.mutateAsync({
        pedidoId: 'order-uuid',
        request: { nuevo_estado: 'EN_CAMINO' },
      })
    })

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true)
    })
    expect(result.current.data?.estado_codigo).toBe('EN_CAMINO')
  })

  it('sets isError=true on 409 INVALID_TRANSITION', async () => {
    const { http } = await import('@/shared/api/http')
    const mockPatch = vi.mocked(http.patch)

    mockPatch.mockRejectedValueOnce(
      Object.assign(new Error('Conflict'), {
        response: {
          status: 409,
          data: { code: 'INVALID_TRANSITION', detail: 'Invalid', status: 409 },
        },
        isAxiosError: true,
      }),
    )

    const { useTransitionEstado } = await import('../hooks/useTransitionEstado')
    const { result } = renderHook(() => useTransitionEstado(), { wrapper })

    await act(async () => {
      try {
        await result.current.mutateAsync({
          pedidoId: 'order-uuid',
          request: { nuevo_estado: 'ENTREGADO' },
        })
      } catch {
        // expected
      }
    })

    await waitFor(() => {
      expect(result.current.isError).toBe(true)
    })
  })
})
