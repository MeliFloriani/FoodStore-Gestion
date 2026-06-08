/* eslint-disable react-refresh/only-export-components */
import { createBrowserRouter, Navigate } from 'react-router-dom'
import { lazy, Suspense } from 'react'
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
const ProductDetailPage = lazy(() => import('@/pages/catalog/ui/ProductDetailPage'))
const CartPage = lazy(() => import('@/pages/cart/ui/CartPage'))
const CheckoutPage = lazy(() => import('@/pages/checkout/ui/CheckoutPage'))
const CheckoutReturnPage = lazy(() => import('@/pages/checkout/ui/CheckoutReturnPage'))
// Change 20: real implementations — replaces OrdersPage placeholder from old orders/ui path
const OrdersPage = lazy(() => import('@/pages/OrdersPage'))
const OrderDetailPage = lazy(() => import('@/pages/OrderDetailPage'))
const OrderConfirmationPage = lazy(() => import('@/pages/OrderConfirmationPage'))
const ForbiddenPage = lazy(() => import('@/pages/errors/ForbiddenPage'))
const UnauthorizedPage = lazy(() => import('@/pages/errors/UnauthorizedPage'))
const NotFoundPage = lazy(() => import('@/pages/errors/NotFoundPage'))
const ProfilePage = lazy(() => import('@/pages/ProfilePage'))
const AddressesPage = lazy(() => import('@/pages/AddressesPage'))
const PreCheckoutReviewPage = lazy(() => import('@/pages/PreCheckoutReviewPage'))
// Change 20: panel de gestión real — replaces placeholder
const PedidosPanelPage = lazy(() => import('@/pages/PedidosPanelPage'))
const PedidosPanelDetailPage = lazy(() => import('@/pages/PedidosPanelDetailPage'))
// Change 21: Admin user management page
const AdminUsersPage = lazy(() => import('@/pages/AdminUsersPage'))
// Stock admin CRUD pages (restored post pre-Change-24 nav fix correction)
const StockIngredientsPage = lazy(() => import('@/pages/stock/IngredientsPage'))
const StockCategoriesPage = lazy(() => import('@/pages/stock/CategoriesPage'))
const StockProductsPage = lazy(() => import('@/pages/stock/ProductsPage'))
// Change 23: Admin dashboard with nested tabs (admin-metrics-dashboard)
const AdminDashboardPage = lazy(() => import('@/pages/admin/dashboard'))
const MetricasTab = lazy(() =>
  import('@/pages/admin/dashboard/tabs/MetricasTab').then((m) => ({ default: m.MetricasTab })),
)
const PedidosTab = lazy(() =>
  import('@/pages/admin/dashboard/tabs/PedidosTab').then((m) => ({ default: m.PedidosTab })),
)
const ProductosTab = lazy(() =>
  import('@/pages/admin/dashboard/tabs/ProductosTab').then((m) => ({ default: m.ProductosTab })),
)
const StockTab = lazy(() =>
  import('@/pages/admin/dashboard/tabs/StockTab').then((m) => ({ default: m.StockTab })),
)

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
            path: '/catalog/:id',
            element: (
              <Suspense fallback={<PageLoader />}>
                <ProductDetailPage />
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
              // CLIENT+ADMIN routes — only shared pages remain (profile).
              {
                element: <RoleGuard roles={['CLIENT', 'ADMIN']} />,
                children: [
                  {
                    path: '/profile',
                    element: (
                      <Suspense fallback={<PageLoader />}>
                        <ProfilePage />
                      </Suspense>
                    ),
                  },
                ],
              },
              // CLIENT-only routes — purchase flow (cart, checkout, addresses).
              // Pre-Change-24 surgical fix: ADMIN must NOT enter these. RoleGuard
              // redirects ADMIN to /403 if accessed manually.
              {
                element: <RoleGuard roles={['CLIENT']} />,
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
                    path: '/checkout/review',
                    element: (
                      <Suspense fallback={<PageLoader />}>
                        <PreCheckoutReviewPage />
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
              // Change 19 (Checkout Pro): MP back_url redirects here after payment.
              // No additional RoleGuard — protected by ProtectedRoute (auth required).
              {
                path: '/checkout/return',
                element: (
                  <Suspense fallback={<PageLoader />}>
                    <CheckoutReturnPage />
                  </Suspense>
                ),
              },
              // CLIENT-only routes (Change 20 — D-15 strict role separation)
              // PEDIDOS and ADMIN are rejected to /403 — they must use /pedidos-panel.
              {
                element: <RoleGuard roles={['CLIENT']} />,
                children: [
                  {
                    path: '/orders',
                    element: (
                      <Suspense fallback={<PageLoader />}>
                        <OrdersPage />
                      </Suspense>
                    ),
                  },
                  {
                    path: '/orders/:id',
                    element: (
                      <Suspense fallback={<PageLoader />}>
                        <OrderDetailPage />
                      </Suspense>
                    ),
                  },
                  {
                    path: '/order-confirmation/:id',
                    element: (
                      <Suspense fallback={<PageLoader />}>
                        <OrderConfirmationPage />
                      </Suspense>
                    ),
                  },
                ],
              },
              // ADMIN-only routes
              {
                element: <RoleGuard roles={['ADMIN']} />,
                children: [
                  // Change 21: /admin/users kept for backwards compatibility
                  {
                    path: '/admin/users',
                    element: (
                      <Suspense fallback={<PageLoader />}>
                        <AdminUsersPage />
                      </Suspense>
                    ),
                  },
                  // Change 23: Admin dashboard with nested tab routes (admin-metrics-dashboard)
                  {
                    path: '/admin',
                    element: (
                      <Suspense fallback={<PageLoader />}>
                        <AdminDashboardPage />
                      </Suspense>
                    ),
                    children: [
                      // Default: redirect /admin → /admin/metricas
                      {
                        index: true,
                        element: <Navigate to="/admin/metricas" replace />,
                      },
                      {
                        path: 'metricas',
                        element: (
                          <Suspense fallback={<PageLoader />}>
                            <MetricasTab />
                          </Suspense>
                        ),
                      },
                      {
                        path: 'pedidos',
                        element: (
                          <Suspense fallback={<PageLoader />}>
                            <PedidosTab />
                          </Suspense>
                        ),
                      },
                      // /admin/usuarios — AdminUsersPage embedded in dashboard tab
                      {
                        path: 'usuarios',
                        element: (
                          <Suspense fallback={<PageLoader />}>
                            <AdminUsersPage />
                          </Suspense>
                        ),
                      },
                      {
                        path: 'productos',
                        element: (
                          <Suspense fallback={<PageLoader />}>
                            <ProductosTab />
                          </Suspense>
                        ),
                      },
                      {
                        path: 'stock',
                        element: (
                          <Suspense fallback={<PageLoader />}>
                            <StockTab />
                          </Suspense>
                        ),
                      },
                    ],
                  },
                ],
              },
              // ADMIN + STOCK routes — real CRUD for ingredients / categories /
              // products (post pre-Change-24 nav fix correction).
              // /stock/inventory intentionally NOT registered — no real impl yet.
              // Backend write endpoints enforce the finer-grained roles
              // (products POST/PUT/DELETE = ADMIN-only; categorias + ingredientes
              //  write = ADMIN+STOCK). The route guard stays ['ADMIN','STOCK']
              // per the frontend-routing spec; backend remains authoritative.
              {
                element: <RoleGuard roles={['ADMIN', 'STOCK']} />,
                children: [
                  {
                    path: '/stock/ingredients',
                    element: (
                      <Suspense fallback={<PageLoader />}>
                        <StockIngredientsPage />
                      </Suspense>
                    ),
                  },
                  {
                    path: '/stock/categories',
                    element: (
                      <Suspense fallback={<PageLoader />}>
                        <StockCategoriesPage />
                      </Suspense>
                    ),
                  },
                  {
                    path: '/stock/products',
                    element: (
                      <Suspense fallback={<PageLoader />}>
                        <StockProductsPage />
                      </Suspense>
                    ),
                  },
                ],
              },
              // PEDIDOS/ADMIN routes — panel de gestión (Change 20)
              {
                element: <RoleGuard roles={['PEDIDOS', 'ADMIN']} />,
                children: [
                  {
                    path: '/pedidos-panel',
                    element: (
                      <Suspense fallback={<PageLoader />}>
                        <PedidosPanelPage />
                      </Suspense>
                    ),
                  },
                  {
                    path: '/pedidos-panel/:id',
                    element: (
                      <Suspense fallback={<PageLoader />}>
                        <PedidosPanelDetailPage />
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
