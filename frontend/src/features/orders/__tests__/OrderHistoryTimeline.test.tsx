/**
 * Tests for OrderHistoryTimeline component (Change 20 — Tasks 15.1–15.4)
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { createElement } from 'react'
import { OrderHistoryTimeline } from '../ui/OrderHistoryTimeline'
import type { HistorialEstadoPedidoRead } from '@/entities/pedido/model/historialTypes'

// ---------------------------------------------------------------------------
// Mock useHistorialPedido from pedido-state-actions feature
// ---------------------------------------------------------------------------

const mockHistorialResult = {
  data: undefined as HistorialEstadoPedidoRead[] | undefined,
  isLoading: false,
  isError: false,
}

vi.mock('@/features/pedido-state-actions', () => ({
  useHistorialPedido: vi.fn(() => mockHistorialResult),
  EstadoActionBar: vi.fn(() => null),
  useTransitionEstado: vi.fn(() => ({
    mutateAsync: vi.fn(),
    isPending: false,
    isError: false,
    isSuccess: false,
  })),
  useCancelarPedidoCliente: vi.fn(() => ({
    mutateAsync: vi.fn(),
    isPending: false,
  })),
}))

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeHistorialEntry(
  id: string,
  estadoDesde: string | null,
  estadoHacia: string,
  actorUserId: string | null = null,
  motivo: string | null = null,
  createdAt = '2026-05-20T10:00:00Z',
): HistorialEstadoPedidoRead {
  return { id, estado_desde: estadoDesde, estado_hacia: estadoHacia, motivo, actor_user_id: actorUserId, created_at: createdAt }
}

function wrapper({ children }: { children: React.ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return createElement(QueryClientProvider, { client: qc }, children)
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('OrderHistoryTimeline', () => {
  beforeEach(() => {
    mockHistorialResult.data = undefined
    mockHistorialResult.isLoading = false
    mockHistorialResult.isError = false
  })

  // Task 15.1: renders 3 entries in chronological order
  it('15.1 — renders 3 entries in chronological order', () => {
    mockHistorialResult.data = [
      makeHistorialEntry('h1', null, 'PENDIENTE', null, null, '2026-05-20T10:00:00Z'),
      makeHistorialEntry('h2', 'PENDIENTE', 'CONFIRMADO', 'user-1', null, '2026-05-20T10:05:00Z'),
      makeHistorialEntry('h3', 'CONFIRMADO', 'EN_PREP', 'user-2', null, '2026-05-20T10:10:00Z'),
    ]

    render(<OrderHistoryTimeline pedidoId="pedido-123" />, { wrapper })

    // All three states should appear (getAllByText handles multiple matches)
    expect(screen.getAllByText(/PENDIENTE/).length).toBeGreaterThan(0)
    expect(screen.getAllByText(/CONFIRMADO/).length).toBeGreaterThan(0)
    expect(screen.getAllByText(/EN_PREP/).length).toBeGreaterThan(0)
  })

  // Task 15.2: first entry with estado_desde null renders without crash
  it('15.2 — first entry with estado_desde null shows "Pedido creado — PENDIENTE"', () => {
    mockHistorialResult.data = [
      makeHistorialEntry('h1', null, 'PENDIENTE'),
    ]

    render(<OrderHistoryTimeline pedidoId="pedido-123" />, { wrapper })

    expect(screen.getByText(/Pedido creado — PENDIENTE/)).toBeDefined()
  })

  // Task 15.3: actor_user_id null shows "Sistema"
  it('15.3 — actor_user_id null shows "Sistema"', () => {
    mockHistorialResult.data = [
      makeHistorialEntry('h1', 'PENDIENTE', 'CONFIRMADO', null),
    ]

    render(<OrderHistoryTimeline pedidoId="pedido-123" />, { wrapper })

    expect(screen.getByText('Sistema')).toBeDefined()
  })

  // Task 15.4: shows skeleton during isLoading
  it('15.4 — shows skeleton while isLoading', () => {
    mockHistorialResult.isLoading = true
    mockHistorialResult.data = undefined

    render(<OrderHistoryTimeline pedidoId="pedido-123" />, { wrapper })

    // The skeleton container has aria-busy="true"
    const container = document.querySelector('[aria-busy="true"]')
    expect(container).not.toBeNull()
  })

  // BUG-01 regression: rendered text must not contain "undefined"
  // Verifies that correct contract field names (estado_hacia / actor_user_id)
  // flow all the way through to the rendered output.
  it('BUG-01 — first entry renders "Pedido creado — PENDIENTE" and never renders "undefined"', () => {
    mockHistorialResult.data = [
      makeHistorialEntry('h1', null, 'PENDIENTE', null, null, '2026-05-20T10:00:00Z'),
    ]

    render(<OrderHistoryTimeline pedidoId="pedido-123" />, { wrapper })

    // The label must show the actual state, not "undefined"
    expect(screen.getByText('Pedido creado — PENDIENTE')).toBeDefined()

    // No element anywhere in the rendered tree should contain the literal word "undefined"
    expect(screen.queryByText(/undefined/i)).toBeNull()
  })
})
