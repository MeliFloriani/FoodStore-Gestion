/**
 * DateRangeFilter — desde/hasta date range filter widget.
 *
 * Change 23: admin-metrics-dashboard.
 *
 * Props:
 *   desde    — current desde value (YYYY-MM-DD string)
 *   hasta    — current hasta value (YYYY-MM-DD string)
 *   onChange — called when either date changes: (desde, hasta) => void
 *
 * Default values when uncontrolled: last 30 days.
 * The parent (MetricasTab) holds the state and passes it down.
 */

interface DateRangeFilterProps {
  desde: string
  hasta: string
  onChange: (desde: string, hasta: string) => void
}

export function DateRangeFilter({ desde, hasta, onChange }: DateRangeFilterProps) {
  function handleDesdeChange(e: React.ChangeEvent<HTMLInputElement>) {
    onChange(e.target.value, hasta)
  }

  function handleHastaChange(e: React.ChangeEvent<HTMLInputElement>) {
    onChange(desde, e.target.value)
  }

  return (
    <div className="flex flex-wrap items-center gap-3">
      <div className="flex flex-col gap-1">
        <label
          htmlFor="metricas-desde"
          className="text-xs font-medium text-muted-foreground"
        >
          Desde
        </label>
        <input
          id="metricas-desde"
          type="date"
          value={desde}
          onChange={handleDesdeChange}
          className="rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
          aria-label="Fecha inicio del filtro"
        />
      </div>
      <div className="flex flex-col gap-1">
        <label
          htmlFor="metricas-hasta"
          className="text-xs font-medium text-muted-foreground"
        >
          Hasta
        </label>
        <input
          id="metricas-hasta"
          type="date"
          value={hasta}
          onChange={handleHastaChange}
          className="rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
          aria-label="Fecha fin del filtro"
        />
      </div>
    </div>
  )
}
