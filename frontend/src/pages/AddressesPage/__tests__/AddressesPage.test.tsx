/**
 * Tests for AddressesPage component.
 *
 * Change 14: delivery-addresses-management.
 *
 * Tests:
 *   - Renders loading skeleton while query is pending
 *   - Renders empty state with CTA when no addresses
 *   - Renders address list with "Principal" badge
 *   - "Establecer como principal" button is hidden for principal address
 *   - Delete confirmation dialog appears before mutation fires
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { createElement } from 'react'
import { MemoryRouter } from 'react-router-dom'
import AxiosMockAdapter from 'axios-mock-adapter'
import { http } from '@/shared/api/http'
import type { DireccionEntrega } from '@/entities/direccion-entrega'

// ---------------------------------------------------------------------------
// Auth store mock
// ---------------------------------------------------------------------------

let mockUser: { id: string } | null = { id: 'user-uuid-001' }

vi.mock('@/entities/auth/model/store', () => {
  const useAuthStore = (selector: (state: { user: typeof mockUser }) => unknown) =>
    selector({ user: mockUser })
  // Provide getState so the http interceptor (useAuthStore.getState().accessToken) doesn't throw
  useAuthStore.getState = () => ({ user: mockUser, accessToken: null, refreshToken: null })
  return { useAuthStore }
})

// ---------------------------------------------------------------------------
// Sample data
// ---------------------------------------------------------------------------

const principalAddress: DireccionEntrega = {
  id: 'addr-001',
  usuario_id: 'user-uuid-001',
  alias: 'Casa',
  linea1: 'Av. Siempre Viva 742',
  linea2: null,
  ciudad: 'Springfield',
  provincia: null,
  codigo_postal: null,
  referencia: null,
  es_principal: true,
  created_at: '2026-05-20T00:00:00Z',
  updated_at: '2026-05-20T00:00:00Z',
}

const secondaryAddress: DireccionEntrega = {
  ...principalAddress,
  id: 'addr-002',
  alias: 'Trabajo',
  linea1: 'Calle Falsa 123',
  es_principal: false,
}

// ---------------------------------------------------------------------------
// Test helpers
// ---------------------------------------------------------------------------

function makeWrapper(queryClient: QueryClient) {
  return ({ children }: { children: React.ReactNode }) =>
    createElement(
      MemoryRouter,
      {},
      createElement(QueryClientProvider, { client: queryClient }, children),
    )
}

function makeQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0 },
      mutations: { retry: false },
    },
  })
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('AddressesPage', () => {
  let axiosMock: AxiosMockAdapter
  let queryClient: QueryClient

  beforeEach(() => {
    axiosMock = new AxiosMockAdapter(http)
    queryClient = makeQueryClient()
    mockUser = { id: 'user-uuid-001' }
    vi.clearAllMocks()
  })

  afterEach(() => {
    axiosMock.restore()
    queryClient.clear()
  })

  // Task 10.4 — Render loading skeleton
  it('shows loading skeleton while query is pending', async () => {
    // Never resolves — stays loading
    axiosMock.onGet('/api/v1/direcciones').reply(() => new Promise(() => {}))

    const { default: AddressesPage } = await import('../AddressesPage')
    render(createElement(AddressesPage), { wrapper: makeWrapper(queryClient) })

    expect(screen.getByRole('status', { name: /cargando direcciones/i })).toBeInTheDocument()
  })

  // Task 10.4 — Render empty state
  it('shows empty state with CTA when no addresses', async () => {
    axiosMock.onGet('/api/v1/direcciones').reply(200, [])

    const { default: AddressesPage } = await import('../AddressesPage')
    render(createElement(AddressesPage), { wrapper: makeWrapper(queryClient) })

    await waitFor(() => {
      expect(screen.getByText(/no tenés direcciones guardadas/i)).toBeInTheDocument()
    })
    // There are two "Agregar dirección" buttons (header + empty state CTA) — verify at least one exists
    expect(screen.getAllByText(/agregar dirección/i).length).toBeGreaterThanOrEqual(1)
  })

  // Task 10.4 — Render list with badge
  it('renders address list with "Principal" badge on principal address', async () => {
    axiosMock.onGet('/api/v1/direcciones').reply(200, [principalAddress, secondaryAddress])

    const { default: AddressesPage } = await import('../AddressesPage')
    render(createElement(AddressesPage), { wrapper: makeWrapper(queryClient) })

    await waitFor(() => {
      expect(screen.getByText(/av\. siempre viva 742/i)).toBeInTheDocument()
    })

    // "Principal" badge should appear
    expect(screen.getByText('Principal')).toBeInTheDocument()
    // Both addresses appear
    expect(screen.getByText(/calle falsa 123/i)).toBeInTheDocument()
  })

  // Task 10.6 — "Establecer como principal" hidden for principal address
  it('does not show "Establecer como principal" button for the principal address', async () => {
    axiosMock.onGet('/api/v1/direcciones').reply(200, [principalAddress, secondaryAddress])

    const { default: AddressesPage } = await import('../AddressesPage')
    render(createElement(AddressesPage), { wrapper: makeWrapper(queryClient) })

    await waitFor(() => {
      expect(screen.getByText(/av\. siempre viva 742/i)).toBeInTheDocument()
    })

    // "Establecer como principal" should appear only for non-principal (secondaryAddress)
    const setMainButtons = screen.getAllByText(/establecer como principal/i)
    // There should be exactly one (for the secondary address)
    expect(setMainButtons).toHaveLength(1)
  })

  // Task 10.5 — Delete confirmation dialog
  it('shows confirmation dialog before calling delete mutation', async () => {
    axiosMock.onGet('/api/v1/direcciones').reply(200, [principalAddress])
    axiosMock.onDelete('/api/v1/direcciones/addr-001').reply(204)

    const { default: AddressesPage } = await import('../AddressesPage')
    render(createElement(AddressesPage), { wrapper: makeWrapper(queryClient) })

    // Wait for address to appear
    await waitFor(() => {
      expect(screen.getByText(/av\. siempre viva 742/i)).toBeInTheDocument()
    })

    // Click delete button (aria-label)
    const deleteButton = screen.getByRole('button', { name: /eliminar casa/i })
    fireEvent.click(deleteButton)

    // Dialog should appear
    let dialog: HTMLElement
    await waitFor(() => {
      dialog = screen.getByRole('dialog', { name: /confirmar eliminación/i })
      expect(dialog).toBeInTheDocument()
    })
    expect(screen.getByText(/esta acción no se puede deshacer/i)).toBeInTheDocument()
    // Scope button queries to the dialog to avoid ambiguity with background buttons
    expect(within(dialog!).getByRole('button', { name: /cancelar/i })).toBeInTheDocument()
    expect(within(dialog!).getByRole('button', { name: /eliminar/i })).toBeInTheDocument()

    // axios.delete should NOT have been called yet
    expect(axiosMock.history.delete.length).toBe(0)
  })

  // Task 10.5 — Cancel delete does not call mutation
  it('cancels delete without calling mutation', async () => {
    axiosMock.onGet('/api/v1/direcciones').reply(200, [principalAddress])

    const { default: AddressesPage } = await import('../AddressesPage')
    render(createElement(AddressesPage), { wrapper: makeWrapper(queryClient) })

    await waitFor(() => {
      expect(screen.getByText(/av\. siempre viva 742/i)).toBeInTheDocument()
    })

    // Click delete
    const deleteButton = screen.getByRole('button', { name: /eliminar casa/i })
    fireEvent.click(deleteButton)

    await waitFor(() => {
      expect(screen.getByRole('dialog', { name: /confirmar eliminación/i })).toBeInTheDocument()
    })

    // Click cancel
    const cancelButton = screen.getByRole('button', { name: /cancelar/i })
    fireEvent.click(cancelButton)

    // Dialog closed
    await waitFor(() => {
      expect(screen.queryByRole('dialog', { name: /confirmar eliminación/i })).not.toBeInTheDocument()
    })

    // No delete API call made
    expect(axiosMock.history.delete.length).toBe(0)
  })
})
