/**
 * ProductosBarChart — recharts horizontal BarChart for top products.
 *
 * Change 23: admin-metrics-dashboard.
 *
 * Layout: horizontal (layout="vertical" in recharts = Y axis has names, X axis has values)
 * Y axis: nombre_snapshot
 * X axis: cantidad_vendida
 * Tooltip: shows ingreso_total formatted as ARS currency
 * Empty state: placeholder when data is empty
 */

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  type TooltipProps,
} from 'recharts'
import { SkeletonRect } from '@/shared/ui/skeleton'
import { EmptyState } from '@/shared/ui/empty-state'
import type { ProductoTopRead } from '../api/metricas.types'

interface ProductosBarChartProps {
  data: ProductoTopRead[]
  loading?: boolean
}

function formatARS(valueStr: string): string {
  const num = parseFloat(valueStr)
  if (isNaN(num)) return valueStr
  return new Intl.NumberFormat('es-AR', {
    style: 'currency',
    currency: 'ARS',
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(num)
}

function CustomTooltip({ active, payload, label }: TooltipProps<number, string>) {
  if (!active || !payload?.length) return null
  const entry = payload[0]?.payload as ProductoTopRead | undefined
  if (!entry) return null
  return (
    <div className="rounded-lg border border-border bg-card px-4 py-3 shadow-lg text-sm">
      <p className="font-semibold text-foreground mb-1 max-w-48 truncate">{label}</p>
      <p className="text-muted-foreground">
        Cantidad vendida: <span className="font-medium text-foreground">{entry.cantidad_vendida}</span>
      </p>
      <p className="text-muted-foreground">
        Ingreso total: <span className="font-medium text-foreground">{formatARS(entry.ingreso_total)}</span>
      </p>
    </div>
  )
}

export function ProductosBarChart({ data, loading = false }: ProductosBarChartProps) {
  if (loading) {
    return <SkeletonRect height="h-64" className="rounded-xl" />
  }

  if (data.length === 0) {
    return (
      <div className="flex h-64 items-center justify-center rounded-xl border border-border bg-card">
        <EmptyState
          title="Sin datos para el período"
          description="Ajusta el rango de fechas para ver métricas."
        />
      </div>
    )
  }

  const chartHeight = Math.max(200, data.length * 36)

  return (
    <div className="rounded-xl border border-border bg-card p-5">
      <h3 className="mb-4 text-sm font-semibold text-foreground">Top Productos Más Vendidos</h3>
      <div className="overflow-x-auto">
        <ResponsiveContainer width="100%" height={chartHeight}>
          <BarChart
            layout="vertical"
            data={data}
            margin={{ top: 4, right: 16, left: 8, bottom: 4 }}
          >
            <CartesianGrid strokeDasharray="3 3" horizontal={false} className="stroke-border" />
            <XAxis
              type="number"
              tick={{ fontSize: 11 }}
              className="fill-muted-foreground"
            />
            <YAxis
              type="category"
              dataKey="nombre_snapshot"
              width={140}
              tick={{ fontSize: 11 }}
              className="fill-muted-foreground"
            />
            <Tooltip content={<CustomTooltip />} />
            <Bar
              dataKey="cantidad_vendida"
              fill="hsl(220, 70%, 50%)"
              radius={[0, 4, 4, 0]}
            />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}
