/**
 * KpiGrid — 4-card KPI grid for the admin metrics dashboard.
 *
 * Change 23: admin-metrics-dashboard.
 *
 * Cards rendered:
 *   1. Ventas Totales      — MetricasResumenRead.ventas_totales (ARS formatted)
 *   2. Pedidos Pendientes  — count of PENDIENTE from pedidos_por_estado
 *   3. Pedidos En Curso    — sum of CONFIRMADO + EN_PREP + EN_CAMINO
 *   4. Usuarios Activos    — MetricasResumenRead.usuarios_activos
 *
 * Spec: frontend-admin-metrics-dashboard — "KpiGrid SHALL render exactly 4 KPI cards"
 *
 * Money formatting: ventas_totales arrives as a string (Decimal serialized).
 * Formatted with Intl.NumberFormat locale 'es-AR', currency 'ARS' (spec requirement).
 * No floating-point arithmetic on this value.
 */

import type { MetricasResumenRead } from '../api/metricas.types'
import { KpiCard } from './KpiCard'

interface KpiGridProps {
  data?: MetricasResumenRead
  loading?: boolean
}

const IN_CURSO_STATES = new Set(['CONFIRMADO', 'EN_PREP', 'EN_CAMINO'])

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

export function KpiGrid({ data, loading = false }: KpiGridProps) {
  const pedidosPendientes =
    data?.pedidos_por_estado.find((p) => p.estado_codigo === 'PENDIENTE')?.cantidad ?? 0

  const pedidosEnCurso =
    data?.pedidos_por_estado
      .filter((p) => IN_CURSO_STATES.has(p.estado_codigo))
      .reduce((sum, p) => sum + p.cantidad, 0) ?? 0

  const ventasTotales = data ? formatARS(data.ventas_totales) : '—'
  const usuariosActivos = data?.usuarios_activos ?? 0

  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
      <KpiCard
        label="Ventas Totales"
        value={loading ? '—' : ventasTotales}
        loading={loading}
      />
      <KpiCard
        label="Pedidos Pendientes"
        value={loading ? '—' : pedidosPendientes}
        loading={loading}
      />
      <KpiCard
        label="Pedidos En Curso"
        value={loading ? '—' : pedidosEnCurso}
        subtitle="Confirmado + En prep + En camino"
        loading={loading}
      />
      <KpiCard
        label="Usuarios Activos"
        value={loading ? '—' : usuariosActivos}
        loading={loading}
      />
    </div>
  )
}
