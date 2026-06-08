/**
 * Tests for PedidosPanelPage Kanban view.
 *
 * Tests:
 *   1.  Renders a column for each order state
 *   2.  Groups pedidos in the correct column
 *   3.  Shows correct count badge per column
 *   4.  Shows state-change action buttons for non-terminal states
 *   4b. CONFIRMADO card shows advance and cancel buttons
 *   4c. PENDIENTE+EFECTIVO card shows "Confirmar pedido" and "Cancelar pedido" buttons
 *   4d. PENDIENTE+MERCADOPAGO card shows ONLY "Cancelar pedido" (no confirm button)
 *   5.  Does NOT show advance action for ENTREGADO (terminal)
 *   6.  Does NOT show advance action for CANCELADO (terminal)
 *   7.  Calls transition mutation with correct args when action button clicked
 *   7b. Clicking Cancelar opens cancel modal and submits with motivo
 *   7c. Clicking Confirmar on PENDIENTE+EFECTIVO card calls mutateAsync with CONFIRMADO
 *   8.  Shows success toast on successful transition
 *   9.  Shows error toast on failed transition
 *   9b. Pedido remains in original column after failed transition
 *   10. Click on card opens the detail modal
 *   11. Detail modal shows order data
 *   12. Detail modal shows action buttons for non-terminal states
 *   13. Detail modal shows action button for CANCELADO (cancel action)
 *   14. Detail modal does NOT show action buttons for terminal ENTREGADO
 *   15. Clicking action button on card does NOT open the detail modal
 *   16. Detail modal action button calls transition mutation correctly
 *   17. Detail modal shows "Confirmar pedido" for PENDIENTE+EFECTIVO
 *   18. Detail modal does NOT show "Confirmar pedido" for PENDIENTE+MERCADOPAGO
 *   19. Detail modal shows MP info badge for PENDIENTE+MERCADOPAGO
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent, within, act } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import PedidosPanelPage from '../index'

// ---------------------------------------------------------------------------
// Mock data — list items
// ---------------------------------------------------------------------------

const mockPedidos = [
  {
    id: 'p-1',
    estado_codigo: 'PENDIENTE',
    total: '1500.00',
    created_at: '2024-01-01T00:00:00Z',
    forma_pago_codigo: 'EFECTIVO',  // EFECTIVO — staff can manually confirm
    items_count: 2,
    usuario_nombre: 'Ana García',
    usuario_email: 'ana@example.com',
  },
  {
    id: 'p-2',
    estado_codigo: 'CONFIRMADO',
    total: '2800.00',
    created_at: '2024-01-01T00:00:00Z',
    forma_pago_codigo: 'EFECTIVO',
    items_count: 3,
    usuario_nombre: 'Carlos López',
    usuario_email: 'carlos@example.com',
  },
  {
    id: 'p-3',
    estado_codigo: 'ENTREGADO',
    total: '900.00',
    created_at: '2024-01-01T00:00:00Z',
    forma_pago_codigo: 'EFECTIVO',
    items_count: 1,
    usuario_nombre: 'María Torres',
    usuario_email: 'maria@example.com',
  },
  {
    id: 'p-4',
    estado_codigo: 'CANCELADO',
    total: '300.00',
    created_at: '2024-01-01T00:00:00Z',
    forma_pago_codigo: 'EFECTIVO',
    items_count: 1,
    usuario_nombre: 'José Pérez',
    usuario_email: 'jose@example.com',
  },
  {
    id: 'p-5',
    estado_codigo: 'PENDIENTE',
    total: '500.00',
    created_at: '2024-01-01T00:00:00Z',
    forma_pago_codigo: 'MERCADOPAGO',  // MERCADOPAGO — auto-confirmed, no manual confirm
    items_count: 1,
    usuario_nombre: 'Luis Fernández',
    usuario_email: 'luis@example.com',
  },
]

// Mock detail for p-2 (CONFIRMADO)
const mockPedidoDetail = {
  id: 'p-2',
  usuario_id: 'u-1',
  usuario: { id: 'u-1', nombre: 'Carlos', apellido: 'López', email: 'carlos@example.com' },
  estado_codigo: 'CONFIRMADO',
  forma_pago_codigo: 'EFECTIVO',
  subtotal: '2700.00',
  costo_envio: '100.00',
  total: '2800.00',
  notas: 'Sin cebolla por favor',
  direccion_id: 'd-1',
  direccion: {
    alias: 'Casa',
    linea1: 'Av. Corrientes 1234',
    linea2: 'Piso 3, Depto B',
    ciudad: 'Buenos Aires',
    provincia: 'CABA',
    codigo_postal: '1043',
    referencia: 'Portón negro, timbre 3B',
  },
  items: [
    {
      id: 'i-1',
      producto_id: 'prod-1',
      nombre_snapshot: 'Hamburguesa Clásica',
      precio_snapshot: '900.00',
      cantidad: 3,
      personalizacion: [],
    },
  ],
  historial: [
    {
      id: 'h-1',
      estado_desde: null,
      estado_hacia: 'PENDIENTE',
      motivo: null,
      actor_user_id: null,
      created_at: '2024-01-01T00:00:00Z',
    },
    {
      id: 'h-2',
      estado_desde: 'PENDIENTE',
      estado_hacia: 'CONFIRMADO',
      motivo: null,
      actor_user_id: null,
      created_at: '2024-01-01T01:00:00Z',
    },
  ],
  pago: null,
  created_at: '2024-01-01T00:00:00Z',
}

// Mock detail for p-1 (PENDIENTE + EFECTIVO)
const mockPedidoDetailPendienteEfectivo = {
  ...mockPedidoDetail,
  id: 'p-1',
  estado_codigo: 'PENDIENTE',
  forma_pago_codigo: 'EFECTIVO',
  total: '1500.00',
  subtotal: '1400.00',
  costo_envio: '100.00',
  usuario: { id: 'u-2', nombre: 'Ana', apellido: 'García', email: 'ana@example.com' },
  historial: [],
  items: [
    {
      id: 'i-3',
      producto_id: 'prod-3',
      nombre_snapshot: 'Empanada',
      precio_snapshot: '700.00',
      cantidad: 2,
      personalizacion: [],
    },
  ],
}

// Mock detail for p-5 (PENDIENTE + MERCADOPAGO)
const mockPedidoDetailPendienteMercadopago = {
  ...mockPedidoDetail,
  id: 'p-5',
  estado_codigo: 'PENDIENTE',
  forma_pago_codigo: 'MERCADOPAGO',
  total: '500.00',
  subtotal: '450.00',
  costo_envio: '50.00',
  usuario: { id: 'u-5', nombre: 'Luis', apellido: 'Fernández', email: 'luis@example.com' },
  historial: [],
  items: [
    {
      id: 'i-5',
      producto_id: 'prod-5',
      nombre_snapshot: 'Sándwich',
      precio_snapshot: '450.00',
      cantidad: 1,
      personalizacion: [],
    },
  ],
}

// Mock detail for p-3 (ENTREGADO — terminal)
const mockPedidoDetailEntregado = {
  ...mockPedidoDetail,
  id: 'p-3',
  estado_codigo: 'ENTREGADO',
  forma_pago_codigo: 'EFECTIVO',
  total: '900.00',
  subtotal: '850.00',
  costo_envio: '50.00',
  items: [
    {
      id: 'i-2',
      producto_id: 'prod-2',
      nombre_snapshot: 'Pizza Margherita',
      precio_snapshot: '850.00',
      cantidad: 1,
      personalizacion: [],
    },
  ],
}

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

const mockMutateAsync = vi.fn()
let mockIsPending = false
const mockUseOrderDetail = vi.fn()

vi.mock('@/features/orders-panel', () => ({
  useAdminOrders: vi.fn(() => ({
    data: {
      items: mockPedidos,
      total: mockPedidos.length,
      page: 1,
      size: 100,
      pages: 1,
    },
    isLoading: false,
    isError: false,
    error: null,
    refetch: vi.fn(),
  })),
}))

vi.mock('@/features/pedido-state-actions', () => ({
  useTransitionEstado: vi.fn(() => ({
    mutateAsync: mockMutateAsync,
    isPending: mockIsPending,
  })),
  FRONTEND_ALLOWED_TRANSITIONS: {
    PENDIENTE:  ['CANCELADO'],
    CONFIRMADO: ['EN_PREP', 'CANCELADO'],
    EN_PREP:    ['EN_CAMINO', 'CANCELADO'],
    EN_CAMINO:  ['ENTREGADO'],
    ENTREGADO:  [],
    CANCELADO:  [],
  },
  CancelReasonModal: vi.fn(({ isOpen, onConfirm, onClose }: {
    isOpen: boolean
    onConfirm: (motivo: string) => void
    onClose: () => void
  }) => {
    if (!isOpen) return null
    return (
      <div role="dialog" aria-label="Cancelar pedido">
        <button onClick={() => onConfirm('Motivo de prueba')}>
          Confirmar cancelación
        </button>
        <button onClick={onClose}>Volver</button>
      </div>
    )
  }),
}))

vi.mock('@/features/orders', () => ({
  useOrderDetail: (pedidoId: string | null) => mockUseOrderDetail(pedidoId),
}))

// ---------------------------------------------------------------------------
// Setup
// ---------------------------------------------------------------------------

function makeQC() {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  })
}

function renderPage() {
  return render(
    <QueryClientProvider client={makeQC()}>
      <MemoryRouter>
        <PedidosPanelPage />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  mockIsPending = false
  mockMutateAsync.mockReset()
  // Default: return loading state (modal not open yet, no detail needed)
  mockUseOrderDetail.mockReturnValue({
    data: undefined,
    isLoading: true,
    isError: false,
    error: null,
  })
})

// ---------------------------------------------------------------------------
// Tests — Kanban columns
// ---------------------------------------------------------------------------

describe('PedidosPanelPage — Kanban view', () => {

  it('1 — renders a column for each of the 6 order states', () => {
    renderPage()
    expect(screen.getByLabelText('Columna Pendiente')).toBeDefined()
    expect(screen.getByLabelText('Columna Confirmado')).toBeDefined()
    expect(screen.getByLabelText('Columna En Preparación')).toBeDefined()
    expect(screen.getByLabelText('Columna En Camino')).toBeDefined()
    expect(screen.getByLabelText('Columna Entregado')).toBeDefined()
    expect(screen.getByLabelText('Columna Cancelado')).toBeDefined()
  })

  it('2 — groups p-1 under PENDIENTE and p-2 under CONFIRMADO', () => {
    renderPage()
    const p1Id = 'p-1'.slice(-8).toUpperCase()
    const p2Id = 'p-2'.slice(-8).toUpperCase()
    expect(screen.getByText(`#${p1Id}`)).toBeDefined()
    expect(screen.getByText(`#${p2Id}`)).toBeDefined()

    const pendienteCol = screen.getByRole('generic', { name: /columna pendiente/i })
    const p1Card = screen.getByLabelText(`Pedido ${p1Id}`)
    expect(pendienteCol.contains(p1Card)).toBe(true)
  })

  it('3 — shows count badge of 2 for PENDIENTE (has p-1 and p-5)', () => {
    renderPage()
    const pendienteCol = screen.getByLabelText('Columna Pendiente')
    expect(pendienteCol.querySelector('[aria-label="2 pedidos"]')).not.toBeNull()
  })

  it('3b — ENTREGADO column badge shows 1', () => {
    renderPage()
    const entregadoCol = screen.getByLabelText('Columna Entregado')
    expect(entregadoCol.querySelector('[aria-label="1 pedidos"]')).not.toBeNull()
  })

  it('4 — PENDIENTE+EFECTIVO card shows "Cancelar pedido" button', () => {
    renderPage()
    const p1Id = 'p-1'.slice(-8).toUpperCase()
    const card = screen.getByLabelText(`Pedido ${p1Id}`)
    expect(card.querySelector('[aria-label="Cancelar pedido"]')).not.toBeNull()
  })

  it('4c — PENDIENTE+EFECTIVO card shows "Confirmar pedido" and "Cancelar pedido" buttons', () => {
    renderPage()
    const p1Id = 'p-1'.slice(-8).toUpperCase()
    const card = screen.getByLabelText(`Pedido ${p1Id}`)
    expect(card.querySelector('[aria-label="Cancelar pedido"]')).not.toBeNull()
    // EFECTIVO: staff can manually confirm
    expect(card.querySelector('[aria-label="Avanzar a Confirmado"]')).not.toBeNull()
  })

  it('4d — PENDIENTE+MERCADOPAGO card shows ONLY "Cancelar pedido" (no confirm button)', () => {
    renderPage()
    const p5Id = 'p-5'.slice(-8).toUpperCase()
    const card = screen.getByLabelText(`Pedido ${p5Id}`)
    expect(card.querySelector('[aria-label="Cancelar pedido"]')).not.toBeNull()
    // MERCADOPAGO: auto-confirmed via webhook — no manual confirm button
    expect(card.querySelector('[aria-label="Avanzar a Confirmado"]')).toBeNull()
  })

  it('4b — CONFIRMADO card shows "Avanzar a En Preparación" and "Cancelar pedido" buttons', () => {
    renderPage()
    const p2Id = 'p-2'.slice(-8).toUpperCase()
    const card = screen.getByLabelText(`Pedido ${p2Id}`)
    expect(card.querySelector('[aria-label="Avanzar a En Preparación"]')).not.toBeNull()
    expect(card.querySelector('[aria-label="Cancelar pedido"]')).not.toBeNull()
  })

  it('5 — ENTREGADO card has NO action buttons', () => {
    renderPage()
    const p3Id = 'p-3'.slice(-8).toUpperCase()
    const card = screen.getByLabelText(`Pedido ${p3Id}`)
    expect(card.querySelectorAll('button').length).toBe(0)
  })

  it('6 — CANCELADO card has NO action buttons', () => {
    renderPage()
    const p4Id = 'p-4'.slice(-8).toUpperCase()
    const card = screen.getByLabelText(`Pedido ${p4Id}`)
    expect(card.querySelectorAll('button').length).toBe(0)
  })

  it('7 — clicking advance button on CONFIRMADO card calls mutateAsync correctly', async () => {
    mockMutateAsync.mockResolvedValueOnce({ id: 'p-2', estado_codigo: 'EN_PREP' })
    renderPage()

    const p2Id = 'p-2'.slice(-8).toUpperCase()
    const card = screen.getByLabelText(`Pedido ${p2Id}`)
    const enPrepBtn = card.querySelector('[aria-label="Avanzar a En Preparación"]') as HTMLButtonElement
    fireEvent.click(enPrepBtn)

    await waitFor(() => {
      expect(mockMutateAsync).toHaveBeenCalledWith({
        pedidoId: 'p-2',
        request: { nuevo_estado: 'EN_PREP', motivo: null },
      })
    })
  })

  it('7b — clicking Cancelar on PENDIENTE card opens cancel modal and submits with motivo', async () => {
    mockMutateAsync.mockResolvedValueOnce({ id: 'p-1', estado_codigo: 'CANCELADO' })
    renderPage()

    const p1Id = 'p-1'.slice(-8).toUpperCase()
    const card = screen.getByLabelText(`Pedido ${p1Id}`)
    const cancelBtn = card.querySelector('[aria-label="Cancelar pedido"]') as HTMLButtonElement
    fireEvent.click(cancelBtn)

    const modal = screen.getByRole('dialog', { name: /cancelar pedido/i })
    expect(modal).toBeDefined()

    fireEvent.click(screen.getByText('Confirmar cancelación'))

    await waitFor(() => {
      expect(mockMutateAsync).toHaveBeenCalledWith({
        pedidoId: 'p-1',
        request: { nuevo_estado: 'CANCELADO', motivo: 'Motivo de prueba' },
      })
    })
  })

  it('7c — clicking Confirmar on PENDIENTE+EFECTIVO card calls mutateAsync with CONFIRMADO', async () => {
    mockMutateAsync.mockResolvedValueOnce({ id: 'p-1', estado_codigo: 'CONFIRMADO' })
    renderPage()

    const p1Id = 'p-1'.slice(-8).toUpperCase()
    const card = screen.getByLabelText(`Pedido ${p1Id}`)
    const confirmBtn = card.querySelector('[aria-label="Avanzar a Confirmado"]') as HTMLButtonElement
    fireEvent.click(confirmBtn)

    await waitFor(() => {
      expect(mockMutateAsync).toHaveBeenCalledWith({
        pedidoId: 'p-1',
        request: { nuevo_estado: 'CONFIRMADO', motivo: null },
      })
    })
  })

  it('8 — shows success toast after successful state transition', async () => {
    mockMutateAsync.mockResolvedValueOnce({ id: 'p-2', estado_codigo: 'EN_PREP' })
    renderPage()

    const p2Id = 'p-2'.slice(-8).toUpperCase()
    const card = screen.getByLabelText(`Pedido ${p2Id}`)
    const btn = card.querySelector('[aria-label="Avanzar a En Preparación"]') as HTMLButtonElement
    fireEvent.click(btn)

    await waitFor(() => {
      expect(screen.getByText(/pedido actualizado a en preparación/i)).toBeDefined()
    })
  })

  it('9 — shows error toast when transition mutation fails', async () => {
    mockMutateAsync.mockRejectedValueOnce({
      response: { data: { code: 'INVALID_TRANSITION', detail: 'La transición no es válida.' } },
    })
    renderPage()

    const p2Id = 'p-2'.slice(-8).toUpperCase()
    const card = screen.getByLabelText(`Pedido ${p2Id}`)
    const btn = card.querySelector('[aria-label="Avanzar a En Preparación"]') as HTMLButtonElement
    fireEvent.click(btn)

    await waitFor(() => {
      expect(screen.getByText('Transición de estado no permitida desde el estado actual.')).toBeDefined()
    })
  })

  it('9b — pedido remains in CONFIRMADO column after failed transition', async () => {
    mockMutateAsync.mockRejectedValueOnce({
      response: { data: { code: 'INVALID_TRANSITION', detail: 'La transición no es válida.' } },
    })
    renderPage()

    const p2Id = 'p-2'.slice(-8).toUpperCase()
    const card = screen.getByLabelText(`Pedido ${p2Id}`)
    const btn = card.querySelector('[aria-label="Avanzar a En Preparación"]') as HTMLButtonElement
    fireEvent.click(btn)

    await waitFor(() => {
      expect(screen.getByText('Transición de estado no permitida desde el estado actual.')).toBeDefined()
    })

    const confirmadoCol = screen.getByLabelText('Columna Confirmado')
    const p2Card = screen.getByLabelText(`Pedido ${p2Id}`)
    expect(confirmadoCol.contains(p2Card)).toBe(true)
  })

})

// ---------------------------------------------------------------------------
// Tests — Detail modal
// ---------------------------------------------------------------------------

describe('PedidosPanelPage — Detail modal', () => {

  it('10 — clicking on a card opens the detail modal', async () => {
    mockUseOrderDetail.mockReturnValue({
      data: mockPedidoDetail,
      isLoading: false,
      isError: false,
      error: null,
    })
    renderPage()

    const p2Id = 'p-2'.slice(-8).toUpperCase()
    const card = screen.getByLabelText(`Pedido ${p2Id}`)
    fireEvent.click(card)

    await waitFor(() => {
      expect(screen.getByRole('dialog', { name: /pedido #/i })).toBeDefined()
    })
  })

  it('11 — detail modal shows order data (total, cliente, notas, items, full address)', async () => {
    mockUseOrderDetail.mockReturnValue({
      data: mockPedidoDetail,
      isLoading: false,
      isError: false,
      error: null,
    })
    renderPage()

    const p2Id = 'p-2'.slice(-8).toUpperCase()
    fireEvent.click(screen.getByLabelText(`Pedido ${p2Id}`))

    const dialog = await screen.findByRole('dialog', { name: /pedido #/i })
    // Cliente
    expect(within(dialog).getByText(/Carlos López/)).toBeDefined()
    // Notas
    expect(within(dialog).getByText('Sin cebolla por favor')).toBeDefined()
    // Dirección — linea1
    expect(within(dialog).getByText('Av. Corrientes 1234')).toBeDefined()
    // Dirección — linea2
    expect(within(dialog).getByText('Piso 3, Depto B')).toBeDefined()
    // Dirección — ciudad + provincia
    expect(within(dialog).getByText(/Buenos Aires.*CABA/)).toBeDefined()
    // Dirección — referencia
    expect(within(dialog).getByText(/Portón negro, timbre 3B/)).toBeDefined()
    // Item
    expect(within(dialog).getByText('Hamburguesa Clásica')).toBeDefined()
  })

  it('11b — detail modal shows listItem client name as fallback when usuario is null', async () => {
    // Detail has usuario: null but listItem has usuario_nombre
    mockUseOrderDetail.mockReturnValue({
      data: {
        ...mockPedidoDetail,
        id: 'p-1',
        estado_codigo: 'PENDIENTE',
        usuario: null,
        historial: [],
        items: [],
        direccion: null,
        direccion_id: null,
        notas: null,
      },
      isLoading: false,
      isError: false,
      error: null,
    })
    renderPage()

    // p-1 has usuario_nombre: 'Ana García' in the list item
    const p1Id = 'p-1'.slice(-8).toUpperCase()
    const card = screen.getByLabelText(`Pedido ${p1Id}`)
    // Click card body (not the button)
    fireEvent.click(card)

    const dialog = await screen.findByRole('dialog', { name: /pedido #/i })
    // listItem fallback shows nombre from the list item
    expect(within(dialog).getByText('Ana García')).toBeDefined()
    expect(within(dialog).getByText('ana@example.com')).toBeDefined()
  })

  it('12 — detail modal shows action buttons for CONFIRMADO state', async () => {
    mockUseOrderDetail.mockReturnValue({
      data: mockPedidoDetail,
      isLoading: false,
      isError: false,
      error: null,
    })
    renderPage()

    const p2Id = 'p-2'.slice(-8).toUpperCase()
    fireEvent.click(screen.getByLabelText(`Pedido ${p2Id}`))

    const dialog = await screen.findByRole('dialog', { name: /pedido #/i })
    expect(within(dialog).getByLabelText('Avanzar a En Preparación')).toBeDefined()
    expect(within(dialog).getByLabelText('Cancelar pedido')).toBeDefined()
  })

  it('14 — detail modal does NOT show action buttons for ENTREGADO (terminal)', async () => {
    mockUseOrderDetail.mockReturnValue({
      data: mockPedidoDetailEntregado,
      isLoading: false,
      isError: false,
      error: null,
    })
    renderPage()

    const p3Id = 'p-3'.slice(-8).toUpperCase()
    fireEvent.click(screen.getByLabelText(`Pedido ${p3Id}`))

    const dialog = await screen.findByRole('dialog', { name: /pedido #/i })
    const actionButtons = within(dialog).queryAllByRole('button').filter(
      (b) => b.getAttribute('aria-label') !== 'Cerrar modal',
    )
    expect(actionButtons.length).toBe(0)
  })

  it('15 — clicking action button on card does NOT open the detail modal', () => {
    mockUseOrderDetail.mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: false,
      error: null,
    })
    renderPage()

    const p2Id = 'p-2'.slice(-8).toUpperCase()
    const card = screen.getByLabelText(`Pedido ${p2Id}`)
    const btn = card.querySelector('[aria-label="Avanzar a En Preparación"]') as HTMLButtonElement
    fireEvent.click(btn)

    // Detail modal should NOT open (no dialog with pedido # title)
    expect(screen.queryByRole('dialog', { name: /pedido #/i })).toBeNull()
  })

  it('16 — clicking advance button in modal calls transition mutation correctly', async () => {
    mockUseOrderDetail.mockReturnValue({
      data: mockPedidoDetail,
      isLoading: false,
      isError: false,
      error: null,
    })
    mockMutateAsync.mockResolvedValueOnce({ id: 'p-2', estado_codigo: 'EN_PREP' })
    renderPage()

    const p2Id = 'p-2'.slice(-8).toUpperCase()
    fireEvent.click(screen.getByLabelText(`Pedido ${p2Id}`))

    const dialog = await screen.findByRole('dialog', { name: /pedido #/i })
    await act(async () => {
      fireEvent.click(within(dialog).getByLabelText('Avanzar a En Preparación'))
    })

    await waitFor(() => {
      expect(mockMutateAsync).toHaveBeenCalledWith({
        pedidoId: 'p-2',
        request: { nuevo_estado: 'EN_PREP', motivo: null },
      })
    })
  })

  it('17 — detail modal shows "Confirmar pedido" button for PENDIENTE+EFECTIVO', async () => {
    mockUseOrderDetail.mockReturnValue({
      data: mockPedidoDetailPendienteEfectivo,
      isLoading: false,
      isError: false,
      error: null,
    })
    renderPage()

    const p1Id = 'p-1'.slice(-8).toUpperCase()
    fireEvent.click(screen.getByLabelText(`Pedido ${p1Id}`))

    const dialog = await screen.findByRole('dialog', { name: /pedido #/i })
    // EFECTIVO: staff can manually confirm
    expect(within(dialog).getByLabelText('Avanzar a Confirmado')).toBeDefined()
    expect(within(dialog).getByLabelText('Cancelar pedido')).toBeDefined()
  })

  it('18 — detail modal does NOT show "Confirmar pedido" button for PENDIENTE+MERCADOPAGO', async () => {
    mockUseOrderDetail.mockReturnValue({
      data: mockPedidoDetailPendienteMercadopago,
      isLoading: false,
      isError: false,
      error: null,
    })
    renderPage()

    const p5Id = 'p-5'.slice(-8).toUpperCase()
    fireEvent.click(screen.getByLabelText(`Pedido ${p5Id}`))

    const dialog = await screen.findByRole('dialog', { name: /pedido #/i })
    // MERCADOPAGO: no manual confirm button
    expect(within(dialog).queryByLabelText('Avanzar a Confirmado')).toBeNull()
    // Cancel is still shown
    expect(within(dialog).getByLabelText('Cancelar pedido')).toBeDefined()
  })

  it('19 — detail modal shows MP info badge for PENDIENTE+MERCADOPAGO', async () => {
    mockUseOrderDetail.mockReturnValue({
      data: mockPedidoDetailPendienteMercadopago,
      isLoading: false,
      isError: false,
      error: null,
    })
    renderPage()

    const p5Id = 'p-5'.slice(-8).toUpperCase()
    fireEvent.click(screen.getByLabelText(`Pedido ${p5Id}`))

    const dialog = await screen.findByRole('dialog', { name: /pedido #/i })
    // Should show the MercadoPago info badge
    expect(within(dialog).getByText(/Esperando confirmación de pago.*MercadoPago/i)).toBeDefined()
  })

})

// ---------------------------------------------------------------------------
// getAllowedTransitions unit tests
// ---------------------------------------------------------------------------

describe('getAllowedTransitions utility', () => {
  it('PENDIENTE (no payment method) → [CANCELADO]', async () => {
    const { getAllowedTransitions } = await import('../utils')
    expect(getAllowedTransitions('PENDIENTE')).toEqual(['CANCELADO'])
  })

  it('PENDIENTE + MERCADOPAGO → [CANCELADO] only (no manual confirm)', async () => {
    const { getAllowedTransitions } = await import('../utils')
    expect(getAllowedTransitions('PENDIENTE', 'MERCADOPAGO')).toEqual(['CANCELADO'])
  })

  it('PENDIENTE + EFECTIVO → [CONFIRMADO, CANCELADO] (manual confirm allowed)', async () => {
    const { getAllowedTransitions } = await import('../utils')
    expect(getAllowedTransitions('PENDIENTE', 'EFECTIVO')).toEqual(['CONFIRMADO', 'CANCELADO'])
  })

  it('CONFIRMADO → [EN_PREP, CANCELADO]', async () => {
    const { getAllowedTransitions } = await import('../utils')
    expect(getAllowedTransitions('CONFIRMADO')).toEqual(['EN_PREP', 'CANCELADO'])
  })

  it('ENTREGADO → [] (terminal)', async () => {
    const { getAllowedTransitions } = await import('../utils')
    expect(getAllowedTransitions('ENTREGADO')).toEqual([])
  })

  it('CANCELADO → [] (terminal)', async () => {
    const { getAllowedTransitions } = await import('../utils')
    expect(getAllowedTransitions('CANCELADO')).toEqual([])
  })
})
