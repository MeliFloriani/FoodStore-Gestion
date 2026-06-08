/**
 * Task 15.12 — TanStack Query deduplication: useOrderDetail + usePaymentStatus
 * mounted simultaneously with the same pedidoId realize only 1 active fetch
 * for the ['pedido', pedidoId] key.
 *
 * Note: usePaymentStatus actually uses queryKey ['pago-status', pedidoId]
 * (not ['pedido', pedidoId]), as confirmed by reading the Change 19 code.
 * useOrderDetail uses ['pedido', pedidoId].
 * They are different keys — no duplication between them by design.
 *
 * This test verifies that when TWO consumers mount useOrderDetail with the same
 * pedidoId, TanStack Query deduplicates and calls GET /api/v1/pedidos/{id} ONCE.
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

const mockPedidoDetail = {
  id: 'pedido-uuid-dedup',
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

describe('TanStack Query deduplication — useOrderDetail', () => {
  let queryClient: QueryClient

  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false, staleTime: 30_000 } },
    })
    vi.clearAllMocks()
  })

  function wrapper({ children }: { children: React.ReactNode }) {
    return createElement(QueryClientProvider, { client: queryClient }, children)
  }

  // Task 15.12: two simultaneous useOrderDetail with same pedidoId → 1 request
  it('15.12 — two useOrderDetail hooks with same pedidoId make only 1 HTTP request', async () => {
    const { http } = await import('@/shared/api/http')
    const mockGet = vi.mocked(http.get)

    // Single mock that resolves once
    mockGet.mockResolvedValue({ data: mockPedidoDetail })

    const { useOrderDetail } = await import('../hooks/useOrderDetail')

    // Mount two hooks simultaneously with the SAME pedidoId
    const { result: r1 } = renderHook(() => useOrderDetail('pedido-uuid-dedup'), { wrapper })
    const { result: r2 } = renderHook(() => useOrderDetail('pedido-uuid-dedup'), { wrapper })

    await waitFor(() => {
      expect(r1.current.isSuccess).toBe(true)
      expect(r2.current.isSuccess).toBe(true)
    })

    // TanStack Query deduplication: only ONE HTTP request should have been made
    // (both hooks share the same ['pedido', 'pedido-uuid-dedup'] query key)
    expect(mockGet).toHaveBeenCalledTimes(1)
    expect(r1.current.data?.id).toBe('pedido-uuid-dedup')
    expect(r2.current.data?.id).toBe('pedido-uuid-dedup')
  })
})
