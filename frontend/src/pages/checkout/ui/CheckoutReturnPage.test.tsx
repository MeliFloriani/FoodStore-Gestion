/**
 * Tests for CheckoutReturnPage (MP-flow reconcile bugfix).
 *
 * Verifies:
 *  - status=success → reconcilePayment called once with payment_id, banner shown.
 *  - status=pending → "Estamos confirmando tu pago" banner shown.
 *  - status=failure → reconcilePayment NOT called, rejection banner with link.
 *  - "Ver todos mis pedidos" link is always rendered.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { createElement } from 'react'

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

// Mock reconcilePayment from the pago entity barrel
const reconcilePaymentMock = vi.fn().mockResolvedValue({
  status: 'ok',
  mp_status: 'approved',
  pedido_estado: 'CONFIRMADO',
  already_processed: false,
})

vi.mock('@/entities/pago', () => ({
  reconcilePayment: (...args: unknown[]) => reconcilePaymentMock(...args),
}))

// Mock the PaymentStatusScreen feature so we don't pull TanStack Query.
vi.mock('@/features/checkout-payment', () => ({
  PaymentStatusScreen: () =>
    createElement('div', { 'data-testid': 'payment-status-screen' }),
}))

vi.mock('@/shared/ui/toast', () => ({ useToast: () => ({ toast: vi.fn() }) }))

// Mock the payment store to provide stable noop actions.
vi.mock('@/shared/store/paymentStore', () => {
  const state = {
    startCheckout: vi.fn(),
    setStatus: vi.fn(),
    resetCheckout: vi.fn(),
  }
  return {
    usePaymentStore: (selector: (s: typeof state) => unknown) => selector(state),
  }
})

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

async function renderReturnPage(search: string) {
  const { default: CheckoutReturnPage } = await import('./CheckoutReturnPage')
  return render(
    createElement(
      MemoryRouter,
      { initialEntries: [`/checkout/return${search}`] },
      createElement(
        Routes,
        null,
        createElement(Route, {
          path: '/checkout/return',
          element: createElement(CheckoutReturnPage),
        }),
        createElement(Route, {
          path: '/orders',
          element: createElement('div', null, 'OrdersPage'),
        }),
        createElement(Route, {
          path: '/order-confirmation/:id',
          element: createElement('div', null, 'OrderConfirmationPage'),
        }),
      ),
    ),
  )
}

const PEDIDO_ID = '11111111-1111-1111-1111-111111111111'
const PAYMENT_ID = '987654321'

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('CheckoutReturnPage', () => {
  beforeEach(() => {
    reconcilePaymentMock.mockClear()
  })

  it('status=success → calls reconcilePayment once and shows "Pago aprobado" message', async () => {
    await renderReturnPage(
      `?status=success&pedido_id=${PEDIDO_ID}&payment_id=${PAYMENT_ID}&external_reference=${PEDIDO_ID}`,
    )

    await waitFor(() => {
      expect(reconcilePaymentMock).toHaveBeenCalledTimes(1)
    })
    expect(reconcilePaymentMock).toHaveBeenCalledWith({
      pedido_id: PEDIDO_ID,
      payment_id: Number(PAYMENT_ID),
      external_reference: PEDIDO_ID,
    })
    expect(screen.getByText(/Pago aprobado/i)).toBeInTheDocument()
  })

  it('status=pending → shows "Estamos confirmando tu pago" message', async () => {
    await renderReturnPage(
      `?status=pending&pedido_id=${PEDIDO_ID}&payment_id=${PAYMENT_ID}`,
    )

    expect(screen.getByText(/Estamos confirmando tu pago/i)).toBeInTheDocument()
  })

  it('status=failure → does NOT call reconcile and shows rejection message with link to pedido', async () => {
    await renderReturnPage(`?status=failure&pedido_id=${PEDIDO_ID}`)

    // Give the effect a tick to potentially fire (it should not).
    await new Promise((resolve) => setTimeout(resolve, 10))
    expect(reconcilePaymentMock).not.toHaveBeenCalled()

    expect(screen.getByText(/rechazado/i)).toBeInTheDocument()
    const backLink = screen.getByRole('link', { name: /Volver al pedido/i })
    expect(backLink.getAttribute('href')).toBe(`/order-confirmation/${PEDIDO_ID}`)
  })

  it('always renders a link to "Ver todos mis pedidos"', async () => {
    await renderReturnPage(`?status=pending&pedido_id=${PEDIDO_ID}`)
    const link = screen.getByRole('link', { name: /Ver todos mis pedidos/i })
    expect(link.getAttribute('href')).toBe('/orders')
  })

  it('does NOT call reconcile when payment_id is missing', async () => {
    await renderReturnPage(`?status=success&pedido_id=${PEDIDO_ID}`)

    await new Promise((resolve) => setTimeout(resolve, 10))
    expect(reconcilePaymentMock).not.toHaveBeenCalled()
    // Banner is still shown.
    expect(screen.getByText(/Pago aprobado/i)).toBeInTheDocument()
  })
})
