/**
 * Tests for useOrderDetail hook (Change 20 — Task 15.5)
 *
 * Task 15.5: uses query key ['pedido', pedidoId] — same structural base as
 * useTransitionEstado invalidation. Verifies query key is set correctly.
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

describe('useOrderDetail', () => {
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

  // Task 15.5: query key is ['pedido', pedidoId]
  it('15.5 — uses query key [\'pedido\', pedidoId]', async () => {
    const { http } = await import('@/shared/api/http')
    const mockGet = vi.mocked(http.get)

    const mockPedidoDetail = {
      id: 'pedido-uuid-1',
      usuario_id: 'user-uuid',
      usuario: null,
      estado_codigo: 'PENDIENTE',
      forma_pago_codigo: 'MERCADOPAGO',
      subtotal: '100.00',
      costo_envio: '50.00',
      total: '150.00',
      notas: null,
      direccion_id: null,
      direccion: null,
      items: [],
      historial: [],
      pago: null,
      created_at: '2026-05-20T10:00:00Z',
    }

    mockGet.mockResolvedValueOnce({ data: mockPedidoDetail })

    const { useOrderDetail } = await import('../hooks/useOrderDetail')
    const { result } = renderHook(() => useOrderDetail('pedido-uuid-1'), { wrapper })

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true)
    })

    // Verify the query key was set in the cache
    const cachedData = queryClient.getQueryData(['pedido', 'pedido-uuid-1'])
    expect(cachedData).toEqual(mockPedidoDetail)

    // Verify the API was called correctly
    expect(mockGet).toHaveBeenCalledWith('/api/v1/pedidos/pedido-uuid-1')
  })

  it('does not fetch when pedidoId is null', async () => {
    const { http } = await import('@/shared/api/http')
    const mockGet = vi.mocked(http.get)

    const { useOrderDetail } = await import('../hooks/useOrderDetail')
    renderHook(() => useOrderDetail(null), { wrapper })

    await new Promise((r) => setTimeout(r, 50))
    expect(mockGet).not.toHaveBeenCalled()
  })

  it('propagates 403 error for cross-user access', async () => {
    const { http } = await import('@/shared/api/http')
    const mockGet = vi.mocked(http.get)

    const error403 = Object.assign(new Error('Forbidden'), {
      response: { status: 403, data: { code: 'ORDER_NOT_OWNED' } },
    })
    mockGet.mockRejectedValueOnce(error403)

    const { useOrderDetail } = await import('../hooks/useOrderDetail')
    const { result } = renderHook(() => useOrderDetail('other-pedido'), { wrapper })

    await waitFor(() => {
      expect(result.current.isError).toBe(true)
    })
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    expect((result.current.error as any)?.response?.status).toBe(403)
  })
})
