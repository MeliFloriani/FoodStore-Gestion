/**
 * KpiCard — single KPI metric card.
 *
 * Change 23: admin-metrics-dashboard.
 *
 * Props:
 *   label    — metric label (e.g. "Ventas Totales")
 *   value    — formatted metric value (string or number)
 *   subtitle — optional secondary line (e.g. trend or unit)
 *   loading  — show skeleton when true
 */

interface KpiCardProps {
  label: string
  value: string | number
  subtitle?: string
  loading?: boolean
}

export function KpiCard({ label, value, subtitle, loading = false }: KpiCardProps) {
  return (
    <div className="rounded-xl border border-border bg-card p-5 shadow-sm transition-shadow hover:shadow-md">
      <p className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">
        {label}
      </p>
      {loading ? (
        <div className="mt-2 space-y-2">
          <div className="h-8 w-3/4 animate-pulse rounded-md bg-muted" />
          {subtitle !== undefined && (
            <div className="h-3 w-1/2 animate-pulse rounded-md bg-muted" />
          )}
        </div>
      ) : (
        <>
          <p className="mt-2 text-3xl font-bold tracking-tight text-foreground">{value}</p>
          {subtitle && (
            <p className="mt-1 text-sm text-muted-foreground">{subtitle}</p>
          )}
        </>
      )}
    </div>
  )
}
