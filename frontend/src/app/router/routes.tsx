/* eslint-disable react-refresh/only-export-components */
import { createBrowserRouter, Navigate } from 'react-router-dom'
import { lazy, Suspense } from 'react'
import { RootLayout } from '@/app/layouts/RootLayout'
import { AuthLayout } from '@/app/layouts/AuthLayout'
import { AppLayout } from '@/app/layouts/AppLayout'
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

function withSuspense(Page: React.ComponentType) {
  return (
    <Suspense fallback={<PageLoader />}>
      <Page />
    </Suspense>
  )
}

export const router = createBrowserRouter([
  {
    element: <RootLayout />,
    children: [
      // Public routes (redirect if already authenticated)
      {
        element: <AuthLayout />,
        children: [
          { path: '/login', element: withSuspense(LoginPage) },
          { path: '/register', element: withSuspense(RegisterPage) },
        ],
      },
      // Protected routes
      {
        element: <ProtectedRoute />,
        children: [
          {
            element: <AppLayout />,
            children: [
              { path: '/', element: withSuspense(HomePage) },
              { path: '/catalog', element: withSuspense(CatalogPage) },
              { path: '/cart', element: withSuspense(CartPage) },
              { path: '/checkout', element: withSuspense(CheckoutPage) },
              { path: '/orders', element: withSuspense(OrdersPage) },
              // Admin routes with RoleGuard
              {
                element: <RoleGuard roles={['ADMIN']} />,
                children: [
                  { path: '/admin', element: withSuspense(AdminPage) },
                ],
              },
            ],
          },
        ],
      },
      // Catch-all redirect
      { path: '*', element: <Navigate to="/" replace /> },
    ],
  },
])
