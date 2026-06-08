/**
 * AdminDashboardPage — tab-based admin dashboard.
 *
 * Change 23: admin-metrics-dashboard.
 *
 * Route: /admin (index → /admin/metricas)
 *        /admin/metricas  → MetricasTab
 *        /admin/pedidos   → PedidosTab
 *        /admin/usuarios  → AdminUsersPage (existing, Change 21)
 *        /admin/productos → ProductosTab
 *        /admin/stock     → StockTab
 *
 * Tab navigation uses React Router's Outlet + NavLink for URL-based activation.
 * This supports shareable URLs, back-button navigation, and clean deep-linking.
 *
 * RoleGuard roles={['ADMIN']} is applied at the parent route — no additional
 * guard needed here.
 */

import { NavLink, Outlet } from 'react-router-dom'

const TABS = [
  { label: 'Métricas', path: '/admin/metricas' },
  { label: 'Pedidos', path: '/admin/pedidos' },
  { label: 'Usuarios', path: '/admin/usuarios' },
  { label: 'Productos', path: '/admin/productos' },
  { label: 'Stock', path: '/admin/stock' },
] as const

export default function AdminDashboardPage() {
  return (
    <div className="mx-auto max-w-7xl px-4 py-6 sm:px-6">
      {/* Page header */}
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-foreground">Panel de Administración</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Métricas, pedidos, usuarios, productos y stock.
        </p>
      </div>

      {/* Tab navigation */}
      <nav
        className="mb-6 flex gap-1 overflow-x-auto rounded-lg border border-border bg-muted/40 p-1"
        aria-label="Admin dashboard tabs"
        role="tablist"
      >
        {TABS.map((tab) => (
          <NavLink
            key={tab.path}
            to={tab.path}
            role="tab"
            className={({ isActive }) =>
              [
                'whitespace-nowrap rounded-md px-4 py-2 text-sm font-medium transition-colors',
                isActive
                  ? 'bg-card text-foreground shadow-sm'
                  : 'text-muted-foreground hover:bg-card/50 hover:text-foreground',
              ].join(' ')
            }
          >
            {tab.label}
          </NavLink>
        ))}
      </nav>

      {/* Tab content — rendered by nested routes via Outlet */}
      <Outlet />
    </div>
  )
}
