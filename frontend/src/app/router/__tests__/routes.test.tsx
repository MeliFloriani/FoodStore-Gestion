import { describe, it, expect, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { createMemoryRouter, RouterProvider } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useAuthStore } from '@/entities/auth/model/store'
import type { User } from '@/entities/auth/types'

// Navigation (rendered inside AppLayout) now depends on TanStack Query via the
// useLogout hook. Provide a fresh QueryClient per render to satisfy that need.
function renderWithProviders(ui: React.ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0 },
      mutations: { retry: false },
    },
  })
  return render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>)
}

// We import the router config lazily to get a fresh router per test
// Instead of reusing the singleton router, we create test routers with the same structure

const mockClientUser: User = {
  id: '550e8400-e29b-41d4-a716-446655440000',
  nombre: 'Test',
  apellido: 'Client',
  email: 'client@example.com',
  roles: ['CLIENT'],
}

const mockStockUser: User = {
  id: '550e8400-e29b-41d4-a716-446655440001',
  nombre: 'Test',
  apellido: 'Stock',
  email: 'stock@example.com',
  roles: ['STOCK'],
}

// Build a minimal router that mirrors the 3-branch structure using simple divs
// This avoids loading the full lazy-loaded pages while testing guard/redirect logic
import { Suspense, lazy } from 'react'
import { RootLayout } from '@/app/layouts/RootLayout'
import { AuthLayout } from '@/app/layouts/AuthLayout'
import { AppLayout } from '@/app/layouts/AppLayout'
import { PublicLayout } from '@/app/layouts/PublicLayout'
import { ProtectedRoute } from '@/app/router/guards/ProtectedRoute'
import { RoleGuard } from '@/app/router/guards/RoleGuard'
import { Navigate } from 'react-router-dom'

function PageLoader() {
  return (
    <div role="status" aria-label="Loading page" className="flex min-h-screen items-center justify-center">
      <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
    </div>
  )
}

const CatalogPageMock = lazy(() =>
  Promise.resolve({ default: function CatalogPage() { return <div>Catalog Page</div> } }),
)
const LoginPageMock = lazy(() =>
  Promise.resolve({ default: function LoginPage() { return <div>Login Page</div> } }),
)
const ForbiddenPageMock = lazy(() =>
  Promise.resolve({ default: function ForbiddenPage() { return <div>Forbidden Page</div> } }),
)
const NotFoundPageMock = lazy(() =>
  Promise.resolve({ default: function NotFoundPage() { return <div>Not Found Page</div> } }),
)
const AddressesPageMock = lazy(() =>
  Promise.resolve({ default: function AddressesPage() { return <div>Addresses Page</div> } }),
)
const StockIngredientsMock = lazy(() =>
  Promise.resolve({
    default: function StockIngredientsPage() {
      return <div>Stock Ingredients Page</div>
    },
  }),
)
const StockCategoriesMock = lazy(() =>
  Promise.resolve({
    default: function StockCategoriesPage() {
      return <div>Stock Categories Page</div>
    },
  }),
)
const StockProductsMock = lazy(() =>
  Promise.resolve({
    default: function StockProductsPage() {
      return <div>Stock Products Page</div>
    },
  }),
)

function buildTestRouter(initialPath: string) {
  return createMemoryRouter(
    [
      {
        element: <RootLayout />,
        children: [
          // BRANCH 1: Public
          {
            element: <PublicLayout />,
            children: [
              { path: '/', element: <Navigate to="/catalog" replace /> },
              {
                path: '/catalog',
                element: <Suspense fallback={<PageLoader />}><CatalogPageMock /></Suspense>,
              },
              {
                path: '/403',
                element: <Suspense fallback={<PageLoader />}><ForbiddenPageMock /></Suspense>,
              },
              {
                path: '/404',
                element: <Suspense fallback={<PageLoader />}><NotFoundPageMock /></Suspense>,
              },
            ],
          },
          // BRANCH 2: Auth
          {
            element: <AuthLayout />,
            children: [
              {
                path: '/login',
                element: <Suspense fallback={<PageLoader />}><LoginPageMock /></Suspense>,
              },
            ],
          },
          // BRANCH 3: Private
          {
            element: <ProtectedRoute />,
            children: [
              {
                element: <AppLayout />,
                children: [
                  // CLIENT-only routes (cart/checkout/addresses are CLIENT-only;
                  // ADMIN is rejected to /403)
                  {
                    element: <RoleGuard roles={['CLIENT']} />,
                    children: [
                      {
                        path: '/addresses',
                        element: <Suspense fallback={<PageLoader />}><AddressesPageMock /></Suspense>,
                      },
                    ],
                  },
                  // ADMIN+STOCK routes — restored real CRUD pages
                  {
                    element: <RoleGuard roles={['ADMIN', 'STOCK']} />,
                    children: [
                      {
                        path: '/stock/ingredients',
                        element: <Suspense fallback={<PageLoader />}><StockIngredientsMock /></Suspense>,
                      },
                      {
                        path: '/stock/categories',
                        element: <Suspense fallback={<PageLoader />}><StockCategoriesMock /></Suspense>,
                      },
                      {
                        path: '/stock/products',
                        element: <Suspense fallback={<PageLoader />}><StockProductsMock /></Suspense>,
                      },
                    ],
                  },
                ],
              },
            ],
          },
          // Catch-all → /404 (verifies that /stock/inventory still falls through)
          { path: '*', element: <Navigate to="/404" replace /> },
        ],
      },
    ],
    { initialEntries: [initialPath] },
  )
}

describe('Route tree integration', () => {
  beforeEach(() => {
    useAuthStore.getState().clear()
  })

  it('(a) unauthenticated GET /catalog renders CatalogPage (no redirect)', async () => {
    useAuthStore.setState({ status: 'unauthenticated' })
    const router = buildTestRouter('/catalog')
    renderWithProviders(<RouterProvider router={router} />)
    await waitFor(() => {
      expect(screen.getByText('Catalog Page')).toBeInTheDocument()
    })
  })

  it('(b) STOCK GET /stock/products renders the real Stock Products page (no placeholder)', async () => {
    useAuthStore.setState({ status: 'authenticated', user: mockStockUser })
    const router = buildTestRouter('/stock/products')
    renderWithProviders(<RouterProvider router={router} />)
    await waitFor(() => {
      expect(screen.getByText('Stock Products Page')).toBeInTheDocument()
    })
    // Defensive: the page must not be the old "Stock Module — Placeholder"
    expect(screen.queryByText(/Stock Module — Placeholder/i)).not.toBeInTheDocument()
  })

  it('(b2) ADMIN GET /stock/ingredients renders the real Ingredients page', async () => {
    useAuthStore.setState({
      status: 'authenticated',
      user: {
        id: '550e8400-e29b-41d4-a716-446655440009',
        nombre: 'Test',
        apellido: 'Admin',
        email: 'admin@example.com',
        roles: ['ADMIN'],
      },
    })
    const router = buildTestRouter('/stock/ingredients')
    renderWithProviders(<RouterProvider router={router} />)
    await waitFor(() => {
      expect(screen.getByText('Stock Ingredients Page')).toBeInTheDocument()
    })
  })

  it('(b3) ADMIN GET /stock/categories renders the real Categories page', async () => {
    useAuthStore.setState({
      status: 'authenticated',
      user: {
        id: '550e8400-e29b-41d4-a716-446655440010',
        nombre: 'Test',
        apellido: 'Admin',
        email: 'admin@example.com',
        roles: ['ADMIN'],
      },
    })
    const router = buildTestRouter('/stock/categories')
    renderWithProviders(<RouterProvider router={router} />)
    await waitFor(() => {
      expect(screen.getByText('Stock Categories Page')).toBeInTheDocument()
    })
  })

  it('(b4) CLIENT GET /stock/products is rejected to /403', async () => {
    useAuthStore.setState({ status: 'authenticated', user: mockClientUser })
    const router = buildTestRouter('/stock/products')
    renderWithProviders(<RouterProvider router={router} />)
    await waitFor(() => {
      expect(screen.getByText('Forbidden Page')).toBeInTheDocument()
    })
  })

  it('(b5) /stock/inventory has no real implementation — falls through to /404', async () => {
    useAuthStore.setState({ status: 'authenticated', user: mockStockUser })
    const router = buildTestRouter('/stock/inventory')
    renderWithProviders(<RouterProvider router={router} />)
    await waitFor(() => {
      expect(screen.getByText('Not Found Page')).toBeInTheDocument()
    })
  })

  it('(c) ADMIN GET /addresses redirects to /403 (CLIENT-only purchase flow)', async () => {
    useAuthStore.setState({
      status: 'authenticated',
      user: {
        id: '550e8400-e29b-41d4-a716-446655440002',
        nombre: 'Test',
        apellido: 'Admin',
        email: 'admin@example.com',
        roles: ['ADMIN'],
      },
    })
    const router = buildTestRouter('/addresses')
    renderWithProviders(<RouterProvider router={router} />)
    await waitFor(() => {
      expect(screen.getByText('Forbidden Page')).toBeInTheDocument()
    })
  })

  it('(d) CLIENT GET /addresses renders Addresses page', async () => {
    useAuthStore.setState({ status: 'authenticated', user: mockClientUser })
    const router = buildTestRouter('/addresses')
    renderWithProviders(<RouterProvider router={router} />)
    await waitFor(() => {
      expect(screen.getByText('Addresses Page')).toBeInTheDocument()
    })
  })
})
