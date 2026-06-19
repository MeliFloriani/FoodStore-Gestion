/**
 * Tests for CheckoutSubmit component (Change 17).
 *
 * Tasks 13.5-13.9:
 *   13.6 — isPending=true → skeleton overlay visible, no button
 *   13.7 — isSuccess=true → confirmation message shown
 *   13.8 — isError=true with INSUFFICIENT_STOCK → readable error message
 *   13.9 — isError=true with PAYMENT_METHOD_INVALID → readable error message
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { createElement } from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

// Mock toast to avoid context requirement
vi.mock('@/shared/ui/toast', () => ({
  useToast: () => ({ toast: vi.fn() }),
}))

// ---------------------------------------------------------------------------
// Mock useCreateOrder hook
// ---------------------------------------------------------------------------

const mockMutateAsync = vi.fn()
let mockIsPending = false
let mockIsError = false
let mockIsSuccess = false
let mockData: unknown = undefined
let mockError: unknown = null

vi.mock('../../hooks/useCreateOrder', () => ({
  useCreateOrder: () => ({
    mutateAsync: mockMutateAsync,
    isPending: mockIsPending,
    isError: mockIsError,
    isSuccess: mockIsSuccess,
    data: mockData,
    error: mockError,
  }),
}))

// ---------------------------------------------------------------------------
// Setup
// ---------------------------------------------------------------------------

describe('CheckoutSubmit', () => {
  let queryClient: QueryClient

  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: { mutations: { retry: false } },
    })
    vi.clearAllMocks()
    mockIsPending = false
    mockIsError = false
    mockIsSuccess = false
    mockData = undefined
    mockError = null
    mockMutateAsync.mockResolvedValue({})
  })

  function wrapper(props: { children: React.ReactNode }) {
    return createElement(QueryClientProvider, { client: queryClient }, props.children)
  }

  async function renderComponent(props = {}) {
    const { CheckoutSubmit } = await import('../CheckoutSubmit')
    return render(
      createElement(CheckoutSubmit, {
        formaPagoCodigo: 'EFECTIVO',
        direccionId: null,
        ...props,
      }),
      { wrapper },
    )
  }

  // -------------------------------------------------------------------------
  // Task 13.6: isPending → skeleton overlay, no button
  // -------------------------------------------------------------------------
  it('Task 13.6: shows skeleton overlay when isPending=true', async () => {
    mockIsPending = true
    await renderComponent()

    // Skeleton overlay with aria-busy
    const overlay = screen.getByRole('generic', { busy: true })
    expect(overlay).toBeInTheDocument()
    expect(overlay).toHaveAttribute('aria-busy', 'true')

    // Skeleton text
    expect(screen.getByText('Procesando pedido...')).toBeTruthy()

    // No button rendered when pending
    expect(screen.queryByRole('button')).not.toBeInTheDocument()
  })

  it('Task 13.6b: button is enabled and shows "Confirmar pedido" when not pending', async () => {
    mockIsPending = false
    await renderComponent()

    const button = screen.getByRole('button', { name: 'Confirmar pedido' })
    expect(button).not.toBeDisabled()
    expect(button).toHaveAttribute('aria-busy', 'false')
  })

  // -------------------------------------------------------------------------
  // Task 13.7: isSuccess → confirmation message
  // -------------------------------------------------------------------------
  it('Task 13.7: shows confirmation message on success (no onSuccess prop)', async () => {
    mockIsSuccess = true
    mockData = {
      id: 'order-uuid-123',
      estado_codigo: 'PENDIENTE',
      historial: [],
      items: [],
    }
    await renderComponent()

    const statusEl = screen.getByRole('status')
    expect(statusEl).toBeTruthy()
    expect(statusEl.textContent).toContain('¡Pedido confirmado!')
  })

  // -------------------------------------------------------------------------
  // Task 13.8: INSUFFICIENT_STOCK → legible error message
  // -------------------------------------------------------------------------
  it('Task 13.8: shows readable message on INSUFFICIENT_STOCK error', async () => {
    mockIsError = true
    mockError = Object.assign(new Error('Conflict'), {
      response: {
        status: 409,
        data: { code: 'INSUFFICIENT_STOCK', detail: {} },
      },
      isAxiosError: true,
    })
    await renderComponent()

    const alertEl = screen.getByRole('alert')
    expect(alertEl).toBeTruthy()
    expect(alertEl.textContent).toContain('stock suficiente')
  })

  // -------------------------------------------------------------------------
  // Task 13.9: PAYMENT_METHOD_INVALID → legible error message
  // -------------------------------------------------------------------------
  it('Task 13.9: shows readable message on PAYMENT_METHOD_INVALID error', async () => {
    mockIsError = true
    mockError = Object.assign(new Error('Bad Request'), {
      response: {
        status: 400,
        data: { code: 'PAYMENT_METHOD_INVALID', detail: 'disabled' },
      },
      isAxiosError: true,
    })
    await renderComponent()

    const alertEl = screen.getByRole('alert')
    expect(alertEl.textContent).toContain('forma de pago')
  })

  // -------------------------------------------------------------------------
  // Clicking "Confirmar pedido" calls mutateAsync
  // -------------------------------------------------------------------------
  it('Clicking the button calls mutateAsync with correct args', async () => {
    await renderComponent({ formaPagoCodigo: 'MERCADOPAGO', direccionId: 'dir-uuid' })

    const button = screen.getByRole('button', { name: 'Confirmar pedido' })
    fireEvent.click(button)

    await waitFor(() => {
      expect(mockMutateAsync).toHaveBeenCalledWith({
        forma_pago_codigo: 'MERCADOPAGO',
        direccion_id: 'dir-uuid',
        notas: undefined,
      })
    })
  })
})
