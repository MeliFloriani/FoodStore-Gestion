/**
 * Integration tests for PreCheckoutReview component.
 *
 * Tasks 9.6-9.11:
 *   9.7 - isPending=true → spinner visible, "Continuar al pago" not enabled
 *   9.8 - isSuccess + ok=true → "Continuar al pago" enabled, no error alerts
 *   9.9 - isSuccess + ok=false + STOCK_INSUFICIENTE → button disabled, stock message
 *   9.10 - isSuccess + only PRECIO_CAMBIADO → "Continuar con nuevos precios" + warning
 *   9.11 - isError → error message + "Reintentar" button
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { PreCheckoutReview } from '../PreCheckoutReview'
import type { ValidarPreCheckoutResponse } from '../../model/types'

// ---------------------------------------------------------------------------
// Mock the hook — tests control the hook's return value
// ---------------------------------------------------------------------------
const mockMutateAsync = vi.fn()
const mockHookState = {
  mutateAsync: mockMutateAsync,
  isPending: false,
  isError: false,
  isSuccess: false,
  data: undefined as ValidarPreCheckoutResponse | undefined,
  error: null as Error | null,
}

vi.mock('../../hooks/useValidatePreCheckout', () => ({
  useValidatePreCheckout: () => mockHookState,
}))

// ---------------------------------------------------------------------------
// Setup
// ---------------------------------------------------------------------------

function renderComponent() {
  return render(
    <MemoryRouter>
      <PreCheckoutReview />
    </MemoryRouter>,
  )
}

describe('PreCheckoutReview', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    // Reset hook state to default
    mockHookState.isPending = false
    mockHookState.isError = false
    mockHookState.isSuccess = false
    mockHookState.data = undefined
    mockHookState.error = null
    mockMutateAsync.mockResolvedValue(undefined)
  })

  // -------------------------------------------------------------------------
  // Task 9.7 — isPending=true → spinner visible
  // -------------------------------------------------------------------------
  it('Task 9.7: shows spinner when isPending=true', () => {
    mockHookState.isPending = true

    renderComponent()

    const spinner = screen.getByRole('status')
    expect(spinner).toBeInTheDocument()
    expect(screen.getByText('Verificando tu carrito...')).toBeInTheDocument()
  })

  it('Task 9.7: does not show "Continuar al pago" button when isPending', () => {
    mockHookState.isPending = true

    renderComponent()

    const continueBtn = screen.queryByRole('button', { name: /continuar al pago/i })
    expect(continueBtn).not.toBeInTheDocument()
  })

  // -------------------------------------------------------------------------
  // Task 9.8 — ok=true → "Continuar al pago" enabled
  // -------------------------------------------------------------------------
  it('Task 9.8: shows "Continuar al pago" button enabled when ok=true and cambios=[]', () => {
    mockHookState.isSuccess = true
    mockHookState.data = {
      ok: true,
      items: [
        {
          producto_id: 'prod-1',
          cantidad_solicitada: 1,
          stock_disponible: 5,
          precio_actual: '100.00',
          precio_percibido: '100.00',
          vigente: true,
          disponible: true,
        },
      ],
      cambios: [],
    }

    renderComponent()

    const btn = screen.getByRole('button', { name: /continuar al pago/i })
    expect(btn).toBeInTheDocument()
    expect(btn).not.toBeDisabled()
  })

  it('Task 9.8: no error alerts when ok=true', () => {
    mockHookState.isSuccess = true
    mockHookState.data = { ok: true, items: [], cambios: [] }

    renderComponent()

    const alerts = screen.queryAllByRole('alert')
    // Only the price change or blocking alerts should appear — none for ok=true, cambios=[]
    const errorAlerts = alerts.filter((el) =>
      el.textContent?.includes('requieren tu atención') || false,
    )
    expect(errorAlerts).toHaveLength(0)
  })

  // -------------------------------------------------------------------------
  // Task 9.9 — ok=false + STOCK_INSUFICIENTE → button disabled
  // -------------------------------------------------------------------------
  it('Task 9.9: button is disabled when ok=false with STOCK_INSUFICIENTE', () => {
    mockHookState.isSuccess = true
    mockHookState.data = {
      ok: false,
      items: [
        {
          producto_id: 'prod-1',
          cantidad_solicitada: 5,
          stock_disponible: 2,
          precio_actual: '100.00',
          precio_percibido: '100.00',
          vigente: true,
          disponible: true,
        },
      ],
      cambios: [
        {
          producto_id: 'prod-1',
          tipo: 'STOCK_INSUFICIENTE',
          detalle: { stock_disponible: 2, cantidad_solicitada: 5 },
        },
      ],
    }

    renderComponent()

    // Look for the continue button (any variant)
    const btns = screen.getAllByRole('button')
    const continueBtn = btns.find(
      (b) =>
        b.textContent?.includes('Continuar') && !b.textContent?.includes('Ajustar'),
    )
    expect(continueBtn).toBeInTheDocument()
    expect(continueBtn).toBeDisabled()
  })

  it('Task 9.9: stock message is visible when STOCK_INSUFICIENTE', () => {
    mockHookState.isSuccess = true
    mockHookState.data = {
      ok: false,
      items: [
        {
          producto_id: 'prod-1',
          cantidad_solicitada: 5,
          stock_disponible: 2,
          precio_actual: '100.00',
          precio_percibido: '100.00',
          vigente: true,
          disponible: true,
        },
      ],
      cambios: [
        {
          producto_id: 'prod-1',
          tipo: 'STOCK_INSUFICIENTE',
          detalle: { stock_disponible: 2, cantidad_solicitada: 5 },
        },
      ],
    }

    renderComponent()

    expect(screen.getAllByText(/Stock insuficiente/i).length).toBeGreaterThan(0)
    expect(screen.getAllByText(/2 disponible/i).length).toBeGreaterThan(0)
  })

  // -------------------------------------------------------------------------
  // Task 9.10 — Only PRECIO_CAMBIADO → "Continuar con nuevos precios" + warning
  // -------------------------------------------------------------------------
  it('Task 9.10: shows "Continuar con nuevos precios" when only PRECIO_CAMBIADO', () => {
    mockHookState.isSuccess = true
    mockHookState.data = {
      ok: true,
      items: [
        {
          producto_id: 'prod-1',
          cantidad_solicitada: 1,
          stock_disponible: 5,
          precio_actual: '200.00',
          precio_percibido: '100.00',
          vigente: true,
          disponible: true,
        },
      ],
      cambios: [
        {
          producto_id: 'prod-1',
          tipo: 'PRECIO_CAMBIADO',
          detalle: { precio_anterior: '100.00', precio_actual: '200.00' },
        },
      ],
    }

    renderComponent()

    expect(
      screen.getByRole('button', { name: /continuar con nuevos precios/i }),
    ).toBeInTheDocument()
  })

  it('Task 9.10: shows price change warning text', () => {
    mockHookState.isSuccess = true
    mockHookState.data = {
      ok: true,
      items: [],
      cambios: [
        {
          producto_id: 'prod-1',
          tipo: 'PRECIO_CAMBIADO',
          detalle: { precio_anterior: '100.00', precio_actual: '200.00' },
        },
      ],
    }

    renderComponent()

    const warningText = screen.getByRole('alert')
    expect(warningText).toBeInTheDocument()
    expect(warningText.textContent).toMatch(/cambiaron/i)
    expect(warningText.textContent).toMatch(/nuevos precios/i)
  })

  // -------------------------------------------------------------------------
  // Task 9.11 — isError → error message + "Reintentar" button
  // -------------------------------------------------------------------------
  it('Task 9.11: shows error message when isError=true', () => {
    mockHookState.isError = true

    renderComponent()

    const alert = screen.getByRole('alert')
    expect(alert).toBeInTheDocument()
  })

  it('Task 9.11: shows "Reintentar" button when isError=true', () => {
    mockHookState.isError = true

    renderComponent()

    const retryBtn = screen.getByRole('button', { name: /reintentar/i })
    expect(retryBtn).toBeInTheDocument()
  })
})
