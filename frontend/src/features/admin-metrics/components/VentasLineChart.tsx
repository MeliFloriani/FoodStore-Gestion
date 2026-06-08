/**
 * VentasLineChart — recharts LineChart for sales time series.
 *
 * Change 23: admin-metrics-dashboard.
 *
 * X axis: periodo (formatted as date string)
 * Y axis: monto_total (string → number for chart rendering)
 * Tooltip: shows both monto_total and cantidad_pedidos
 * Empty state: renders a placeholder when data is empty
 */

import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  type TooltipProps,
} from 'recharts'
import type { VentasPeriodoRead } from '../api/metricas.types'

interface VentasLineChartProps {
  data: VentasPeriodoRead[]
  loading?: boolean
}

function formatPeriodo(iso: string): string {
  try {
    return new Date(iso).toLocaleDateString('es-AR', {
      day: '2-digit',
      month: '2-digit',
      year: '2-digit',
    })
  } catch {
    return iso
  }
}

function formatARS(value: number): string {
  return new Intl.NumberFormat('es-AR', {
    style: 'currency',
    currency: 'ARS',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(value)
}

function CustomTooltip({ active, payload, label }: TooltipProps<number, string>) {
  if (!active || !payload?.length) return null
  const entry = payload[0]?.payload as { monto_total: string; cantidad_pedidos: number } | undefined
  if (!entry) return null
  return (
    <div className="rounded-lg border border-border bg-card px-4 py-3 shadow-lg text-sm">
      <p className="font-semibold text-foreground mb-1">{label}</p>
      <p className="text-muted-foreground">
        Ventas: <span className="font-medium text-foreground">{formatARS(parseFloat(entry.monto_total))}</span>
      </p>
      <p className="text-muted-foreground">
        Pedidos: <span className="font-medium text-foreground">{entry.cantidad_pedidos}</span>
      </p>
    </div>
  )
}

export function VentasLineChart({ data, loading = false }: VentasLineChartProps) {
  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center rounded-xl border border-border bg-card">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
      </div>
    )
  }

  if (data.length === 0) {
    return (
      <div className="flex h-64 items-center justify-center rounded-xl border border-border bg-card">
        <p className="text-sm text-muted-foreground">No hay datos para el período seleccionado.</p>
      </div>
    )
  }

  const chartData = data.map((d) => ({
    periodo: formatPeriodo(d.periodo),
    monto_total: d.monto_total,
    cantidad_pedidos: d.cantidad_pedidos,
    monto_num: parseFloat(d.monto_total),
  }))

  return (
    <div className="rounded-xl border border-border bg-card p-5">
      <h3 className="mb-4 text-sm font-semibold text-foreground">Evolución de Ventas</h3>
      <ResponsiveContainer width="100%" height={240}>
        <LineChart data={chartData} margin={{ top: 4, right: 16, left: 0, bottom: 4 }}>
          <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
          <XAxis
            dataKey="periodo"
            tick={{ fontSize: 11 }}
            className="fill-muted-foreground"
          />
          <YAxis
            tickFormatter={(v: number) => formatARS(v)}
            tick={{ fontSize: 11 }}
            className="fill-muted-foreground"
            width={80}
          />
          <Tooltip content={<CustomTooltip />} />
          <Line
            type="monotone"
            dataKey="monto_num"
            stroke="hsl(var(--primary, 222 47% 11%))"
            strokeWidth={2}
            dot={false}
            activeDot={{ r: 4 }}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}
