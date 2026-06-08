/**
 * Tests for OrdersPage (Change 20 — Task 15.10)
 *
 * Task 15.10: Filtering by estado calls the API with ?estado=<value>.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { createElement } from 'react'

// ---------------------------------------------------------------------------
// Mock useClientOrders
// ---------------------------------------------------------------------------

const mockUseClientOrders = vi.fn()

vi.mock('@/features/orders', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/features/orders')>()
  return {
    ...actual,
    useClientOrders: mockUseClientOrders,
    OrderHistoryTimeline: vi.fn(() => null),
  }
})

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('OrdersPage', () => {
  let queryClient: QueryClient

  beforeEach(() => {
    queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    vi.clearAllMocks()

    // Default: empty state
    mockUseClientOrders.mockReturnValue({
      data: { items: [], total: 0, page: 1, size: 10, pages: 0 },
      isLoading: false,
      isError: false,
      error: null,
      refetch: vi.fn(),
    })
  })

  async function renderOrdersPage() {
    const { default: OrdersPage } = await import('@/pages/OrdersPage')
    return render(
      createElement(
        QueryClientProvider,
        { client: queryClient },
        createElement(
          MemoryRouter,
          null,
          createElement(OrdersPage),
        ),
      ),
    )
  }

  // Task 15.10: selecting estado filter calls hook with correct params
  it('15.10 — selecting "PENDIENTE" in estado filter calls hook with estado=PENDIENTE', async () => {
    await renderOrdersPage()

    const select = screen.getByLabelText('Filtrar por estado') as HTMLSelectElement
    fireEvent.change(select, { target: { value: 'PENDIENTE' } })

    await waitFor(() => {
      // Find the most recent call — after state update
      const calls = mockUseClientOrders.mock.calls
      const lastCall = calls[calls.length - 1]
      const params = lastCall[0] as { estado?: string }
      expect(params.estado).toBe('PENDIENTE')
    })
  })

  it('shows empty state when items is empty', async () => {
    await renderOrdersPage()
    expect(screen.getByText(/Todavía no realizaste ningún pedido/)).toBeDefined()
  })

  it('shows skeleton while loading', async () => {
    mockUseClientOrders.mockReturnValue({
      data: undefined,
      isLoading: true,
      isError: false,
      error: null,
      refetch: vi.fn(),
    })

    await renderOrdersPage()

    const container = document.querySelector('[aria-busy="true"]')
    expect(container).not.toBeNull()
  })
})
