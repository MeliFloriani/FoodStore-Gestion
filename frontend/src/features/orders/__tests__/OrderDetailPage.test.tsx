/**
 * Tests for OrderDetailPage (Change 20 — Tasks 15.8 + CLIENT permissions).
 *
 * Task 15.8: OrderDetailPage redirects to /403 when API returns HTTP 403.
 *
 * CLIENT permission tests:
 *   - CLIENT does NOT see admin state-transition buttons.
 *   - CLIENT sees a cancel button for PENDIENTE/CONFIRMADO orders.
 *   - CLIENT sees no action buttons for EN_PREP, EN_CAMINO, ENTREGADO.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { createElement } from 'react'
import OrderDetailPage from '@/pages/OrderDetailPage'
import type { PedidoDetail } from '@/entities/pedido/model/types'
import { ConfirmDialogProvider } from '@/shared/ui/confirm-dialog'
import { ToastProvider } from '@/shared/ui/toast/ToastProvider'

// ---------------------------------------------------------------------------
// Mock entire @/features/orders module
// ---------------------------------------------------------------------------

vi.mock('@/features/orders', () => ({
  useOrderDetail: vi.fn(),
  OrderHistoryTimeline: () => null,
}))

// Keep the real EstadoActionBar so we can assert which buttons appear/don't appear.
// Only mock hooks that would make network calls.
vi.mock('@/features/pedido-state-actions', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/features/pedido-state-actions')>()
  return {
    ...actual,
    useCancelarPedidoCliente: vi.fn(() => ({ mutateAsync: vi.fn(), isPending: false })),
  }
})

vi.mock('@/features/checkout-payment', () => ({
  usePaymentStatus: vi.fn(() => ({ data: null })),
}))

vi.mock('@/shared/store/paymentStore', () => ({
  usePaymentStore: vi.fn(() => 'idle'),
}))

// ---------------------------------------------------------------------------
// Import mocked modules for configuration
// ---------------------------------------------------------------------------

import { useOrderDetail } from '@/features/orders'
const mockUseOrderDetail = vi.mocked(useOrderDetail)

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makePedido(overrides: Partial<PedidoDetail> = {}): PedidoDetail {
  return {
    id: 'pedido-uuid-1',
    estado_codigo: 'PENDIENTE',
    forma_pago_codigo: 'EFECTIVO',
    total: '1500.00',
    subtotal: '1400.00',
    costo_envio: '100.00',
    created_at: '2024-01-01T00:00:00Z',
    items: [],
    direccion: null,
    notas: null,
    pago: null,
    historial: [],
    usuario: null,
    ...overrides,
  } as unknown as PedidoDetail
}

describe('OrderDetailPage', () => {
  let queryClient: QueryClient

  beforeEach(() => {
    queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    vi.clearAllMocks()
    // Default: loading state
    mockUseOrderDetail.mockReturnValue({
      data: undefined,
      isLoading: true,
      isError: false,
      error: null,
    } as ReturnType<typeof useOrderDetail>)
  })

  function renderPage(pedidoId = 'pedido-uuid-1') {
    return render(
      createElement(
        QueryClientProvider,
        { client: queryClient },
        createElement(
          MemoryRouter,
          { initialEntries: [`/orders/${pedidoId}`] },
          createElement(
            ToastProvider,
            null,
            createElement(
              ConfirmDialogProvider,
              null,
              createElement(
                Routes,
                null,
                createElement(Route, { path: '/orders/:id', element: createElement(OrderDetailPage) }),
                createElement(Route, { path: '/403', element: createElement('div', null, 'ForbiddenPage') }),
                createElement(Route, { path: '/404', element: createElement('div', null, 'NotFoundPage') }),
              ),
            ),
          ),
        ),
      ),
    )
  }

  // ── Task 15.8 ──────────────────────────────────────────────────────────────

  it('15.8 — redirects to /403 when API returns HTTP 403', async () => {
    const error403 = { response: { status: 403, data: { code: 'ORDER_NOT_OWNED' } } }
    mockUseOrderDetail.mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: true,
      error: error403 as unknown as Error,
    } as unknown as ReturnType<typeof useOrderDetail>)

    renderPage()

    await waitFor(() => {
      expect(screen.queryByText('ForbiddenPage')).not.toBeNull()
    })
  })

  it('shows skeleton while loading', () => {
    renderPage()
    const skeleton = document.querySelector('[aria-busy="true"]')
    expect(skeleton).not.toBeNull()
  })

  // ── CLIENT permission tests ────────────────────────────────────────────────

  describe('CLIENT — no admin state-action buttons', () => {
    it('PENDIENTE order: shows Cancelar button, NOT admin transitions', async () => {
      mockUseOrderDetail.mockReturnValue({
        data: makePedido({ estado_codigo: 'PENDIENTE' }),
        isLoading: false,
        isError: false,
        error: null,
      } as unknown as ReturnType<typeof useOrderDetail>)
      renderPage()
      await waitFor(() => expect(screen.queryByRole('group', { name: /acciones/i })).not.toBeNull())
      // CANCELADO is allowed for CLIENT
      expect(screen.getByRole('button', { name: /cancelado/i })).toBeInTheDocument()
      // Staff-only transitions must NOT appear
      expect(screen.queryByRole('button', { name: /confirmado/i })).toBeNull()
      expect(screen.queryByRole('button', { name: /preparaci/i })).toBeNull()
      expect(screen.queryByRole('button', { name: /en camino/i })).toBeNull()
      expect(screen.queryByRole('button', { name: /entregado/i })).toBeNull()
    })

    it('CONFIRMADO order: shows Cancelar, NOT Pasar a preparación', async () => {
      mockUseOrderDetail.mockReturnValue({
        data: makePedido({ estado_codigo: 'CONFIRMADO' }),
        isLoading: false,
        isError: false,
        error: null,
      } as unknown as ReturnType<typeof useOrderDetail>)
      renderPage()
      await waitFor(() => expect(screen.queryByRole('group', { name: /acciones/i })).not.toBeNull())
      expect(screen.getByRole('button', { name: /cancelado/i })).toBeInTheDocument()
      expect(screen.queryByRole('button', { name: /preparaci/i })).toBeNull()
    })

    it('EN_PREP order: shows NO action buttons', async () => {
      mockUseOrderDetail.mockReturnValue({
        data: makePedido({ estado_codigo: 'EN_PREP' }),
        isLoading: false,
        isError: false,
        error: null,
      } as unknown as ReturnType<typeof useOrderDetail>)
      renderPage()
      await waitFor(() =>
        expect(screen.queryByText(/Pedido #/)).not.toBeNull(),
      )
      expect(screen.queryByRole('group', { name: /acciones/i })).toBeNull()
    })

    it('EN_CAMINO order: shows NO action buttons', async () => {
      mockUseOrderDetail.mockReturnValue({
        data: makePedido({ estado_codigo: 'EN_CAMINO' }),
        isLoading: false,
        isError: false,
        error: null,
      } as unknown as ReturnType<typeof useOrderDetail>)
      renderPage()
      await waitFor(() =>
        expect(screen.queryByText(/Pedido #/)).not.toBeNull(),
      )
      expect(screen.queryByRole('group', { name: /acciones/i })).toBeNull()
    })

    it('ENTREGADO order: shows NO action buttons (terminal)', async () => {
      mockUseOrderDetail.mockReturnValue({
        data: makePedido({ estado_codigo: 'ENTREGADO' }),
        isLoading: false,
        isError: false,
        error: null,
      } as unknown as ReturnType<typeof useOrderDetail>)
      renderPage()
      await waitFor(() =>
        expect(screen.queryByText(/Pedido #/)).not.toBeNull(),
      )
      expect(screen.queryByRole('group', { name: /acciones/i })).toBeNull()
    })
  })
})
