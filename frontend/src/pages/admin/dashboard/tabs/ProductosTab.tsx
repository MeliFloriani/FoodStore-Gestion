/**
 * ProductosTab — product management placeholder for the admin dashboard.
 *
 * Change 23: admin-metrics-dashboard.
 *
 * Full product CRUD (AdminProductosPage) is outside the scope of Change 23.
 * Renders an informational message directing to the catalog management panel.
 * This tab will be replaced when the products admin page is implemented.
 */

export function ProductosTab() {
  return (
    <div className="flex min-h-48 items-center justify-center rounded-xl border border-border bg-card p-8 text-center">
      <div>
        <p className="text-base font-medium text-foreground">Gestión de Productos</p>
        <p className="mt-2 text-sm text-muted-foreground">
          Gestión de productos disponible en el panel de Catálogo.
        </p>
      </div>
    </div>
  )
}
