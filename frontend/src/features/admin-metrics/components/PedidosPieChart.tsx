/**
 * PedidosPieChart — recharts PieChart for order state distribution.
 *
 * Change 23: admin-metrics-dashboard.
 *
 * One slice per estado_codigo with a color mapping per state.
 * Renders Legend and Tooltip.
 * Empty state: placeholder when data is empty.
 */

import {
  PieChart,
  Pie,
  Cell,
  Legend,
  Tooltip,
  ResponsiveContainer,
  type TooltipProps,
} from 'recharts'
import type { PedidoEstadoDistribucionRead } from '../api/metricas.types'

interface PedidosPieChartProps {
  data: PedidoEstadoDistribucionRead[]
  loading?: boolean
}

// Color mapping per estado_codigo
const ESTADO_COLORS: Record<string, string> = {
  PENDIENTE: '#f59e0b',    // amber-400
  CONFIRMADO: '#3b82f6',   // blue-500
  EN_PREP: '#6366f1',      // indigo-500
  EN_CAMINO: '#8b5cf6',    // violet-500
  ENTREGADO: '#22c55e',    // green-500
  CANCELADO: '#ef4444',    // red-500
}

const DEFAULT_COLOR = '#94a3b8' // slate-400

function getColor(estado: string): string {
  return ESTADO_COLORS[estado] ?? DEFAULT_COLOR
}

function CustomTooltip({ active, payload }: TooltipProps<number, string>) {
  if (!active || !payload?.length) return null
  const item = payload[0]
  if (!item) return null
  return (
    <div className="rounded-lg border border-border bg-card px-4 py-3 shadow-lg text-sm">
      <p className="font-semibold text-foreground">{item.name}</p>
      <p className="text-muted-foreground">
        Cantidad: <span className="font-medium text-foreground">{item.value}</span>
      </p>
    </div>
  )
}

export function PedidosPieChart({ data, loading = false }: PedidosPieChartProps) {
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
    name: d.estado_codigo,
    value: d.cantidad,
  }))

  return (
    <div className="rounded-xl border border-border bg-card p-5">
      <h3 className="mb-4 text-sm font-semibold text-foreground">Distribución por Estado</h3>
      <ResponsiveContainer width="100%" height={260}>
        <PieChart>
          <Pie
            data={chartData}
            cx="50%"
            cy="45%"
            outerRadius={90}
            dataKey="value"
            nameKey="name"
            label={({ name, percent }) =>
              `${name} ${((percent as number) * 100).toFixed(0)}%`
            }
            labelLine={false}
          >
            {chartData.map((entry) => (
              <Cell key={entry.name} fill={getColor(entry.name)} />
            ))}
          </Pie>
          <Tooltip content={<CustomTooltip />} />
          <Legend
            iconType="circle"
            iconSize={10}
            wrapperStyle={{ fontSize: '12px' }}
          />
        </PieChart>
      </ResponsiveContainer>
    </div>
  )
}
