/* eslint-disable react-refresh/only-export-components */
import { createBrowserRouter, Navigate, Suspense } from 'react-router-dom'
import { lazy } from 'react'
import { RootLayout } from '@/app/layouts/RootLayout'
import { AuthLayout } from '@/app/layouts/AuthLayout'
import { AppLayout } from '@/app/layouts/AppLayout'
import { PublicLayout } from '@/app/layouts/PublicLayout'
import { ProtectedRoute } from '@/app/router/guards/ProtectedRoute'
import { RoleGuard } from '@/app/router/guards/RoleGuard'

const LoginPage = lazy(() => import('@/pages/login/ui/LoginPage'))
const RegisterPage = lazy(() => import('@/pages/register/ui/RegisterPage'))
const HomePage = lazy(() => import('@/pages/home/ui/HomePage'))
const CatalogPage = lazy(() => import('@/pages/catalog/ui/CatalogPage'))
const CartPage = lazy(() => import('@/pages/cart/ui/CartPage'))
const CheckoutPage = lazy(() => import('@/pages/checkout/ui/CheckoutPage'))
const OrdersPage = lazy(() => import('@/pages/orders/ui/OrdersPage'))
const AdminPage = lazy(() => import('@/pages/admin/ui/AdminPage'))
const ForbiddenPage = lazy(() => import('@/pages/errors/ForbiddenPage'))
const UnauthorizedPage = lazy(() => import('@/pages/errors/UnauthorizedPage'))
const NotFoundPage = lazy(() => import('@/pages/errors/NotFoundPage'))
const ProfilePage = lazy(() => import('@/pages/profile/ui/ProfilePage'))
const AddressesPage = lazy(() => import('@/pages/addresses/ui/AddressesPage'))

function PageLoader() {
  return (
    <div
      role="status"
      aria-label="Loading page"
      className="flex min-h-screen items-center justify-center"
    >
      <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
    </div>
  )
}

export const router = createBrowserRouter([
  {
    element: <RootLayout />,
    children: [
      // BRANCH 1: Public (no auth required)
      {
        element: <PublicLayout />,
        children: [
          { path: '/', element: <Navigate to="/catalog" replace /> },
          {
            path: '/catalog',
            element: (
              <Suspense fallback={<PageLoader />}>
                <CatalogPage />
              </Suspense>
            ),
          },
          {
            path: '/401',
            element: (
              <Suspense fallback={<PageLoader />}>
                <UnauthorizedPage />
              </Suspense>
            ),
          },
          {
            path: '/403',
            element: (
              <Suspense fallback={<PageLoader />}>
                <ForbiddenPage />
              </Suspense>
            ),
          },
          {
            path: '/404',
            element: (
              <Suspense fallback={<PageLoader />}>
                <NotFoundPage />
              </Suspense>
            ),
          },
        ],
      },
      // BRANCH 2: Auth (login/register — redirects away if already authenticated)
      {
        element: <AuthLayout />,
        children: [
          {
            path: '/login',
            element: (
              <Suspense fallback={<PageLoader />}>
                <LoginPage />
              </Suspense>
            ),
          },
          {
            path: '/register',
            element: (
              <Suspense fallback={<PageLoader />}>
                <RegisterPage />
              </Suspense>
            ),
          },
        ],
      },
      // BRANCH 3: Private (requires authentication)
      {
        element: <ProtectedRoute />,
        children: [
          {
            element: <AppLayout />,
            children: [
              {
                path: '/home',
                element: (
                  <Suspense fallback={<PageLoader />}>
                    <HomePage />
                  </Suspense>
                ),
              },
              // CLIENT+ADMIN routes
              {
                element: <RoleGuard roles={['CLIENT', 'ADMIN']} />,
                children: [
                  {
                    path: '/cart',
                    element: (
                      <Suspense fallback={<PageLoader />}>
                        <CartPage />
                      </Suspense>
                    ),
                  },
                  {
                    path: '/checkout',
                    element: (
                      <Suspense fallback={<PageLoader />}>
                        <CheckoutPage />
                      </Suspense>
                    ),
                  },
                  {
                    path: '/orders',
                    element: (
                      <Suspense fallback={<PageLoader />}>
                        <OrdersPage />
                      </Suspense>
                    ),
                  },
                  {
                    path: '/profile',
                    element: (
                      <Suspense fallback={<PageLoader />}>
                        <ProfilePage />
                      </Suspense>
                    ),
                  },
                  {
                    path: '/addresses',
                    element: (
                      <Suspense fallback={<PageLoader />}>
                        <AddressesPage />
                      </Suspense>
                    ),
                  },
                ],
              },
              // ADMIN-only routes
              {
                element: <RoleGuard roles={['ADMIN']} />,
                children: [
                  {
                    path: '/admin',
                    element: (
                      <Suspense fallback={<PageLoader />}>
                        <AdminPage />
                      </Suspense>
                    ),
                  },
                ],
              },
              // STOCK routes (placeholder subtree)
              {
                element: <RoleGuard roles={['STOCK', 'ADMIN']} />,
                children: [
                  {
                    path: '/stock/*',
                    element: (
                      <Suspense fallback={<PageLoader />}>
                        <div>Stock Module — Placeholder</div>
                      </Suspense>
                    ),
                  },
                ],
              },
              // PEDIDOS routes (placeholder subtree)
              {
                element: <RoleGuard roles={['PEDIDOS', 'ADMIN']} />,
                children: [
                  {
                    path: '/pedidos-panel/*',
                    element: (
                      <Suspense fallback={<PageLoader />}>
                        <div>Pedidos Panel — Placeholder</div>
                      </Suspense>
                    ),
                  },
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
])
