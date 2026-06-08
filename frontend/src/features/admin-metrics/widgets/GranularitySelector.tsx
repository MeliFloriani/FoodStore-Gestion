/**
 * GranularitySelector — select control for chart time granularity.
 *
 * Change 23: admin-metrics-dashboard.
 *
 * Props:
 *   value    — current granularity ('dia' | 'semana' | 'mes')
 *   onChange — called when selection changes
 */

import type { Granularidad } from '../api/metricas.types'

interface GranularitySelectorProps {
  value: Granularidad
  onChange: (v: Granularidad) => void
}

const OPTIONS: { value: Granularidad; label: string }[] = [
  { value: 'dia', label: 'Día' },
  { value: 'semana', label: 'Semana' },
  { value: 'mes', label: 'Mes' },
]

export function GranularitySelector({ value, onChange }: GranularitySelectorProps) {
  return (
    <div className="flex flex-col gap-1">
      <label
        htmlFor="metricas-granularidad"
        className="text-xs font-medium text-muted-foreground"
      >
        Granularidad
      </label>
      <select
        id="metricas-granularidad"
        value={value}
        onChange={(e) => onChange(e.target.value as Granularidad)}
        className="rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
        aria-label="Granularidad del gráfico de ventas"
      >
        {OPTIONS.map((opt) => (
          <option key={opt.value} value={opt.value}>
            {opt.label}
          </option>
        ))}
      </select>
    </div>
  )
}
