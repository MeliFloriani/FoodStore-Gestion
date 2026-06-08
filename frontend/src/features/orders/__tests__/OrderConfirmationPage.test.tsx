/**
 * Tests for OrderConfirmationPage (Change 20 — Task 15.13)
 *
 * Task 15.13: OrderConfirmationPage with useOrderDetail mock returning 403
 * → router navigates to /403.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { createElement } from 'react'

// ---------------------------------------------------------------------------
// Mock useOrderDetail to return 403
// ---------------------------------------------------------------------------

const mockOrderDetailResult = {
  data: undefined as unknown,
  isLoading: false,
  isError: false,
  error: null as unknown,
}

vi.mock('@/features/orders', () => ({
  useOrderDetail: vi.fn(() => mockOrderDetailResult),
  OrderHistoryTimeline: vi.fn(() => null),
}))

// Sentinel so we can assert whether PayWithMercadoPagoButton is rendered or not.
const PayButtonSpy = vi.fn((_props: unknown) => null)
vi.mock('@/features/checkout-payment', () => ({
  PayWithMercadoPagoButton: (props: unknown) => {
    PayButtonSpy(props)
    return null
  },
  usePaymentStatus: vi.fn(() => ({ data: null })),
}))

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('OrderConfirmationPage', () => {
  let queryClient: QueryClient

  beforeEach(() => {
    queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    vi.clearAllMocks()
    PayButtonSpy.mockClear()
    mockOrderDetailResult.data = undefined
    mockOrderDetailResult.isLoading = false
    mockOrderDetailResult.isError = false
    mockOrderDetailResult.error = null
  })

  /** Build a minimal PedidoDetail-shaped object for the page. */
  function buildPedido(formaPago: 'EFECTIVO' | 'MERCADOPAGO'): Record<string, unknown> {
    return {
      id: '11111111-1111-1111-1111-111111111111',
      forma_pago_codigo: formaPago,
      estado_codigo: 'PENDIENTE',
      subtotal: '100.00',
      costo_envio: '10.00',
      total: '110.00',
      items: [
        {
          id: 'item-1',
          nombre_snapshot: 'Pizza',
          precio_snapshot: '50.00',
          cantidad: 2,
        },
      ],
    }
  }

  async function renderOrderConfirmationPage(pedidoId = 'pedido-uuid-1') {
    const { default: OrderConfirmationPage } = await import('@/pages/OrderConfirmationPage')
    return render(
      createElement(
        QueryClientProvider,
        { client: queryClient },
        createElement(
          MemoryRouter,
          { initialEntries: [`/order-confirmation/${pedidoId}`] },
          createElement(
            Routes,
            null,
            createElement(Route, {
              path: '/order-confirmation/:id',
              element: createElement(OrderConfirmationPage),
            }),
            createElement(Route, {
              path: '/403',
              element: createElement('div', null, 'ForbiddenPage'),
            }),
            createElement(Route, {
              path: '/404',
              element: createElement('div', null, 'NotFoundPage'),
            }),
          ),
        ),
      ),
    )
  }

  // Task 15.13: 403 from useOrderDetail → navigate to /403
  it('15.13 — navigates to /403 when useOrderDetail returns 403', async () => {
    // Error with response.status = 403 (matches getHttpStatus utility)
    const error403 = Object.assign(new Error('Forbidden'), {
      response: { status: 403, data: { code: 'ORDER_NOT_OWNED' } },
    })
    mockOrderDetailResult.isError = true
    mockOrderDetailResult.error = error403

    await renderOrderConfirmationPage('other-users-pedido')

    await waitFor(() => {
      expect(screen.queryByText('ForbiddenPage')).not.toBeNull()
    })
  })

  it('shows skeleton when isLoading', async () => {
    mockOrderDetailResult.isLoading = true

    await renderOrderConfirmationPage()

    const skeleton = document.querySelector('[aria-busy="true"]')
    expect(skeleton).not.toBeNull()
  })

  // ---------------------------------------------------------------------------
  // MP-flow fix: EFECTIVO vs MERCADOPAGO branching
  // ---------------------------------------------------------------------------

  it('EFECTIVO pedido → does NOT render PayWithMercadoPagoButton and shows "PENDIENTE" badge', async () => {
    mockOrderDetailResult.data = buildPedido('EFECTIVO')

    await renderOrderConfirmationPage()

    await waitFor(() => {
      expect(screen.queryByText(/Pendiente de confirmación/i)).not.toBeNull()
    })
    expect(PayButtonSpy).not.toHaveBeenCalled()
  })

  it('MERCADOPAGO pedido → renders PayWithMercadoPagoButton', async () => {
    mockOrderDetailResult.data = buildPedido('MERCADOPAGO')

    await renderOrderConfirmationPage()

    await waitFor(() => {
      expect(PayButtonSpy).toHaveBeenCalledTimes(1)
    })
    // "Esperando pago" badge is the MP branch
    expect(screen.queryByText(/Esperando pago/i)).not.toBeNull()
  })
})
