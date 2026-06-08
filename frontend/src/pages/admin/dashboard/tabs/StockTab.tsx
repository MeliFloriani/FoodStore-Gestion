/**
 * StockTab — stock management placeholder for the admin dashboard.
 *
 * Change 23: admin-metrics-dashboard.
 *
 * Full stock management is outside the scope of Change 23.
 * Renders an informational message directing to the stock panel.
 * This tab will be replaced when the stock admin page is implemented.
 */

export function StockTab() {
  return (
    <div className="flex min-h-48 items-center justify-center rounded-xl border border-border bg-card p-8 text-center">
      <div>
        <p className="text-base font-medium text-foreground">Gestión de Stock</p>
        <p className="mt-2 text-sm text-muted-foreground">
          Gestión de stock disponible via el panel STOCK.
        </p>
      </div>
    </div>
  )
}
