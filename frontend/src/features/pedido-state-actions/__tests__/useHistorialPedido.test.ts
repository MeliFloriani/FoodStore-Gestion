/**
 * Tests for useHistorialPedido hook (Change 18).
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

describe('useHistorialPedido', () => {
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

  it('calls GET /pedidos/{id}/historial and returns data', async () => {
    const { http } = await import('@/shared/api/http')
    const mockGet = vi.mocked(http.get)

    const mockHistorial = [
      {
        id: 'hist-1',
        estado_desde: null,
        estado_hacia: 'PENDIENTE',
        motivo: null,
        actor_user_id: null,
        created_at: '2026-05-20T10:00:00Z',
      },
      {
        id: 'hist-2',
        estado_desde: 'PENDIENTE',
        estado_hacia: 'CONFIRMADO',
        motivo: null,
        actor_user_id: 'user-uuid',
        created_at: '2026-05-20T10:05:00Z',
      },
    ]

    mockGet.mockResolvedValueOnce({ data: mockHistorial })

    const { useHistorialPedido } = await import('../hooks/useHistorialPedido')
    const { result } = renderHook(() => useHistorialPedido('order-uuid'), { wrapper })

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true)
    })

    expect(mockGet).toHaveBeenCalledWith('/pedidos/order-uuid/historial')
    expect(result.current.data).toHaveLength(2)
    expect(result.current.data![0].estado_hacia).toBe('PENDIENTE')
    expect(result.current.data![1].actor_user_id).toBe('user-uuid')
  })

  it('does not fetch when pedidoId is null', async () => {
    const { http } = await import('@/shared/api/http')
    const mockGet = vi.mocked(http.get)

    const { useHistorialPedido } = await import('../hooks/useHistorialPedido')
    renderHook(() => useHistorialPedido(null), { wrapper })

    // Allow microtasks to run
    await new Promise((r) => setTimeout(r, 50))

    expect(mockGet).not.toHaveBeenCalled()
  })

  it('does not fetch when pedidoId is undefined', async () => {
    const { http } = await import('@/shared/api/http')
    const mockGet = vi.mocked(http.get)

    const { useHistorialPedido } = await import('../hooks/useHistorialPedido')
    renderHook(() => useHistorialPedido(undefined), { wrapper })

    await new Promise((r) => setTimeout(r, 50))

    expect(mockGet).not.toHaveBeenCalled()
  })
})
