/**
 * Tests for useCancelarPedidoCliente hook (Change 18).
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, act, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { createElement } from 'react'

vi.mock('@/shared/api/http', () => ({
  http: {
    delete: vi.fn(),
  },
}))

describe('useCancelarPedidoCliente', () => {
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

  it('calls DELETE /pedidos/{id} with motivo in body', async () => {
    const { http } = await import('@/shared/api/http')
    const mockDelete = vi.mocked(http.delete)

    mockDelete.mockResolvedValueOnce({
      data: {
        id: 'order-uuid',
        estado_codigo: 'CANCELADO',
        forma_pago_codigo: 'EFECTIVO',
        usuario_id: 'user-uuid',
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

    const { useCancelarPedidoCliente } = await import('../hooks/useCancelarPedidoCliente')
    const { result } = renderHook(() => useCancelarPedidoCliente(), { wrapper })

    await act(async () => {
      await result.current.mutateAsync({
        pedidoId: 'order-uuid',
        motivo: 'ya no lo necesito',
      })
    })

    expect(mockDelete).toHaveBeenCalledWith('/pedidos/order-uuid', {
      data: { nuevo_estado: 'CANCELADO', motivo: 'ya no lo necesito' },
    })
  })

  it('returns cancelled PedidoRead on success', async () => {
    const { http } = await import('@/shared/api/http')
    const mockDelete = vi.mocked(http.delete)

    mockDelete.mockResolvedValueOnce({
      data: {
        id: 'order-uuid',
        estado_codigo: 'CANCELADO',
        forma_pago_codigo: 'EFECTIVO',
        usuario_id: 'user-uuid',
        direccion_id: null,
        subtotal: '50.00',
        costo_envio: '0.00',
        total: '50.00',
        notas: null,
        items: [],
        historial: [],
        created_at: '2026-05-20T00:00:00Z',
      },
    })

    const { useCancelarPedidoCliente } = await import('../hooks/useCancelarPedidoCliente')
    const { result } = renderHook(() => useCancelarPedidoCliente(), { wrapper })

    await act(async () => {
      await result.current.mutateAsync({ pedidoId: 'order-uuid', motivo: 'cambié de opinión' })
    })

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true)
    })
    expect(result.current.data?.estado_codigo).toBe('CANCELADO')
  })

  it('sets isError=true on 409 (EN_PREP cannot be cancelled by client)', async () => {
    const { http } = await import('@/shared/api/http')
    const mockDelete = vi.mocked(http.delete)

    mockDelete.mockRejectedValueOnce(
      Object.assign(new Error('Conflict'), {
        response: {
          status: 409,
          data: { code: 'INVALID_TRANSITION', detail: 'Cannot cancel', status: 409 },
        },
        isAxiosError: true,
      }),
    )

    const { useCancelarPedidoCliente } = await import('../hooks/useCancelarPedidoCliente')
    const { result } = renderHook(() => useCancelarPedidoCliente(), { wrapper })

    await act(async () => {
      try {
        await result.current.mutateAsync({ pedidoId: 'order-uuid', motivo: 'test' })
      } catch {
        // expected
      }
    })

    await waitFor(() => {
      expect(result.current.isError).toBe(true)
    })
  })
})
