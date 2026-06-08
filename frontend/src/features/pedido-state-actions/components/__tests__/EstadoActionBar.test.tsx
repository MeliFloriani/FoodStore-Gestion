/**
 * EstadoActionBar — role-visibility tests.
 *
 * Verifies that:
 *  - CLIENT context (showAdminActions=false, the default): only CANCELADO is shown
 *    for states where a CLIENT is allowed to cancel; no staff-only transitions are shown.
 *  - Admin context (showAdminActions=true): full staff transition set is shown,
 *    matching FRONTEND_ALLOWED_TRANSITIONS.
 *  - Terminal states show nothing in both contexts.
 */

import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { EstadoActionBar } from '../EstadoActionBar'

const noop = vi.fn()

// ---------------------------------------------------------------------------
// CLIENT context (default: showAdminActions not passed = false)
// ---------------------------------------------------------------------------

describe('EstadoActionBar — CLIENT context (showAdminActions=false)', () => {
  it('PENDIENTE: shows only Cancelar, NOT Confirmar', () => {
    render(<EstadoActionBar estadoActual="PENDIENTE" onTransition={noop} />)
    expect(screen.queryByRole('button')).not.toBeNull()
    // Cancel button present
    expect(screen.getByRole('button', { name: /cancelado/i })).toBeInTheDocument()
    // Staff-only transitions absent
    expect(screen.queryByRole('button', { name: /confirmado/i })).toBeNull()
    expect(screen.queryByRole('button', { name: /preparaci/i })).toBeNull()
    expect(screen.queryByRole('button', { name: /en camino/i })).toBeNull()
    expect(screen.queryByRole('button', { name: /entregado/i })).toBeNull()
  })

  it('CONFIRMADO: shows only Cancelar, NOT Pasar a preparación', () => {
    render(<EstadoActionBar estadoActual="CONFIRMADO" onTransition={noop} />)
    expect(screen.getByRole('button', { name: /cancelado/i })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /preparaci/i })).toBeNull()
  })

  it('EN_PREP: shows no buttons (CLIENT cannot cancel EN_PREP)', () => {
    render(<EstadoActionBar estadoActual="EN_PREP" onTransition={noop} />)
    expect(screen.queryByRole('button')).toBeNull()
  })

  it('EN_CAMINO: shows no buttons', () => {
    render(<EstadoActionBar estadoActual="EN_CAMINO" onTransition={noop} />)
    expect(screen.queryByRole('button')).toBeNull()
  })

  it('ENTREGADO: shows no buttons (terminal)', () => {
    render(<EstadoActionBar estadoActual="ENTREGADO" onTransition={noop} />)
    expect(screen.queryByRole('button')).toBeNull()
  })

  it('CANCELADO: shows no buttons (terminal)', () => {
    render(<EstadoActionBar estadoActual="CANCELADO" onTransition={noop} />)
    expect(screen.queryByRole('button')).toBeNull()
  })

  it('clicking Cancelar calls onTransition with "CANCELADO"', () => {
    const onTransition = vi.fn()
    render(
      <EstadoActionBar estadoActual="PENDIENTE" onTransition={onTransition} />
    )
    fireEvent.click(screen.getByRole('button', { name: /cancelado/i }))
    expect(onTransition).toHaveBeenCalledWith('CANCELADO')
    expect(onTransition).toHaveBeenCalledTimes(1)
  })
})

// ---------------------------------------------------------------------------
// Admin context (showAdminActions=true)
// ---------------------------------------------------------------------------

describe('EstadoActionBar — admin context (showAdminActions=true)', () => {
  it('PENDIENTE: shows only Cancelar (staff cannot manually confirm MercadoPago; EFECTIVO handled upstream via forma_pago_codigo)', () => {
    // FRONTEND_ALLOWED_TRANSITIONS['PENDIENTE'] = ['CANCELADO']
    // The CONFIRMADO button for EFECTIVO is handled by getAllowedTransitions() in
    // PedidosPanelPage/utils.ts, not by EstadoActionBar directly.
    render(
      <EstadoActionBar estadoActual="PENDIENTE" onTransition={noop} showAdminActions />
    )
    expect(screen.getByRole('button', { name: /cancelado/i })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /confirmado/i })).toBeNull()
  })

  it('CONFIRMADO: shows Pasar a preparación AND Cancelar', () => {
    render(
      <EstadoActionBar estadoActual="CONFIRMADO" onTransition={noop} showAdminActions />
    )
    expect(screen.getByRole('button', { name: /preparaci/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /cancelado/i })).toBeInTheDocument()
  })

  it('EN_PREP: shows Enviar pedido (En Camino) AND Cancelar', () => {
    render(
      <EstadoActionBar estadoActual="EN_PREP" onTransition={noop} showAdminActions />
    )
    expect(screen.getByRole('button', { name: /camino/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /cancelado/i })).toBeInTheDocument()
  })

  it('EN_CAMINO: shows Marcar como entregado only', () => {
    render(
      <EstadoActionBar estadoActual="EN_CAMINO" onTransition={noop} showAdminActions />
    )
    expect(screen.getByRole('button', { name: /entregado/i })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /cancelado/i })).toBeNull()
  })

  it('ENTREGADO: shows no buttons (terminal)', () => {
    render(
      <EstadoActionBar estadoActual="ENTREGADO" onTransition={noop} showAdminActions />
    )
    expect(screen.queryByRole('button')).toBeNull()
  })

  it('CANCELADO: shows no buttons (terminal)', () => {
    render(
      <EstadoActionBar estadoActual="CANCELADO" onTransition={noop} showAdminActions />
    )
    expect(screen.queryByRole('button')).toBeNull()
  })

  it('buttons are disabled while isLoading=true', () => {
    render(
      <EstadoActionBar
        estadoActual="CONFIRMADO"
        onTransition={noop}
        showAdminActions
        isLoading
      />
    )
    const buttons = screen.getAllByRole('button')
    buttons.forEach((btn) => expect(btn).toBeDisabled())
  })
})
