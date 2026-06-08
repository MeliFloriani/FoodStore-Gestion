/**
 * PedidosTab — embeds PedidosPanelPage content for the admin dashboard.
 *
 * Change 23: admin-metrics-dashboard.
 *
 * Decision D-23-05: Embed, don't duplicate. This tab renders the full
 * PedidosPanelPage component instead of re-implementing order management.
 *
 * PedidosPanelPage is already registered at /pedidos-panel (PEDIDOS/ADMIN guard).
 * Here it is embedded directly as a component within the /admin/pedidos tab.
 */

import { lazy, Suspense } from 'react'

// Lazy-loaded to avoid bundling PedidosPanelPage eagerly in the admin dashboard.
const PedidosPanelPage = lazy(() => import('@/pages/PedidosPanelPage'))

function TabLoader() {
  return (
    <div className="flex h-64 items-center justify-center">
      <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
    </div>
  )
}

export function PedidosTab() {
  return (
    <Suspense fallback={<TabLoader />}>
      <PedidosPanelPage />
    </Suspense>
  )
}
