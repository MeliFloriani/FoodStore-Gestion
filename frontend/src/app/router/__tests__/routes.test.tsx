import { describe, it, expect, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { createMemoryRouter, RouterProvider } from 'react-router-dom'
import { useAuthStore } from '@/entities/auth/model/store'
import type { User } from '@/entities/auth/types'

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
const StockPlaceholder = () => <div>Stock Module — Placeholder</div>

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
                  // STOCK routes
                  {
                    element: <RoleGuard roles={['STOCK', 'ADMIN']} />,
                    children: [
                      { path: '/stock/*', element: <StockPlaceholder /> },
                    ],
                  },
                ],
              },
            ],
          },
          // Catch-all
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
    render(<RouterProvider router={router} />)
    await waitFor(() => {
      expect(screen.getByText('Catalog Page')).toBeInTheDocument()
    })
  })

  it('(b) unauthenticated GET /stock/products redirects to /login', async () => {
    useAuthStore.setState({ status: 'unauthenticated' })
    const router = buildTestRouter('/stock/products')
    render(<RouterProvider router={router} />)
    await waitFor(() => {
      expect(screen.getByText('Login Page')).toBeInTheDocument()
    })
  })

  it('(c) CLIENT role GET /stock/products redirects to /403', async () => {
    useAuthStore.setState({ status: 'authenticated', user: mockClientUser })
    const router = buildTestRouter('/stock/products')
    render(<RouterProvider router={router} />)
    await waitFor(() => {
      expect(screen.getByText('Forbidden Page')).toBeInTheDocument()
    })
  })

  it('(d) STOCK role GET /stock/products renders Stock placeholder', async () => {
    useAuthStore.setState({ status: 'authenticated', user: mockStockUser })
    const router = buildTestRouter('/stock/products')
    render(<RouterProvider router={router} />)
    await waitFor(() => {
      expect(screen.getByText('Stock Module — Placeholder')).toBeInTheDocument()
    })
  })
})
