/**
 * Tests for PedidosPanelPage (Change 20 — Task 15.9)
 *
 * Task 15.9: RoleGuard blocks STOCK users with redirect to /403.
 *
 * This test verifies the RoleGuard config in routes.tsx: roles={['PEDIDOS','ADMIN']}.
 * STOCK is not in that list, so RoleGuard should redirect to /403.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { createElement } from 'react'

// ---------------------------------------------------------------------------
// Mock auth store to simulate STOCK role
// ---------------------------------------------------------------------------

vi.mock('@/entities/auth/model/store', () => ({
  useAuthStore: vi.fn((selector: (s: {
    user: { roles: string[] } | null;
    accessToken: string | null;
    isHydrated: boolean;
  }) => unknown) =>
    selector({
      user: { roles: ['STOCK'] },
      accessToken: 'test-token',
      isHydrated: true,
    }),
  ),
}))

vi.mock('@/features/orders-panel', () => ({
  useAdminOrders: vi.fn(() => ({
    data: { items: [], total: 0, page: 1, size: 20, pages: 0 },
    isLoading: false,
    isError: false,
    error: null,
    refetch: vi.fn(),
  })),
}))

vi.mock('@/shared/hooks/useDebounce', () => ({
  useDebounce: vi.fn((v: unknown) => v),
}))

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('PedidosPanelPage — RoleGuard', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  // Task 15.9: STOCK user navigating to /pedidos-panel is redirected to /403
  it('15.9 — STOCK user is redirected to /403 by RoleGuard', async () => {
    const { RoleGuard } = await import('@/app/router/guards/RoleGuard')
    const { default: PedidosPanelPage } = await import('@/pages/PedidosPanelPage')

    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })

    render(
      createElement(
        QueryClientProvider,
        { client: qc },
        createElement(
          MemoryRouter,
          { initialEntries: ['/pedidos-panel'] },
          createElement(
            Routes,
            null,
            createElement(
              Route,
              { element: createElement(RoleGuard, { roles: ['PEDIDOS', 'ADMIN'] }) },
              createElement(Route, {
                path: '/pedidos-panel',
                element: createElement(PedidosPanelPage),
              }),
            ),
            createElement(Route, {
              path: '/403',
              element: createElement('div', null, 'ForbiddenPage'),
            }),
          ),
        ),
      ),
    )

    // STOCK is not in ['PEDIDOS', 'ADMIN'] → RoleGuard should redirect to /403
    expect(screen.getByText('ForbiddenPage')).toBeDefined()
  })
})
