/**
 * MetricasTab — KPI + charts composition for the admin dashboard.
 *
 * Change 23: admin-metrics-dashboard.
 *
 * Manages desde, hasta, granularidad state.
 * Composes: DateRangeFilter, GranularitySelector, KpiGrid, VentasLineChart,
 *           ProductosBarChart, PedidosPieChart.
 *
 * Defaults: desde = today - 30 days, hasta = today, granularidad = 'dia'.
 */

import { useState } from 'react'
import {
  DateRangeFilter,
  GranularitySelector,
  KpiGrid,
  VentasLineChart,
  ProductosBarChart,
  PedidosPieChart,
  useMetricasResumen,
  useMetricasVentas,
  useMetricasProductosTop,
  useMetricasPedidosPorEstado,
} from '@/features/admin-metrics'
import type { Granularidad } from '@/features/admin-metrics'

function getDefaultDesde(): string {
  const d = new Date()
  d.setDate(d.getDate() - 30)
  return d.toISOString().slice(0, 10)
}

function getDefaultHasta(): string {
  return new Date().toISOString().slice(0, 10)
}

export function MetricasTab() {
  const [desde, setDesde] = useState<string>(getDefaultDesde)
  const [hasta, setHasta] = useState<string>(getDefaultHasta)
  const [granularidad, setGranularidad] = useState<Granularidad>('dia')

  const dateParams = {
    desde: desde || undefined,
    hasta: hasta || undefined,
  }

  const resumen = useMetricasResumen(dateParams)
  const ventas = useMetricasVentas({ ...dateParams, granularidad })
  const productosTop = useMetricasProductosTop({ ...dateParams, top: 10 })
  const pedidosPorEstado = useMetricasPedidosPorEstado(dateParams)

  function handleDateChange(newDesde: string, newHasta: string) {
    setDesde(newDesde)
    setHasta(newHasta)
  }

  return (
    <div className="space-y-6">
      {/* Filters */}
      <div className="flex flex-wrap items-end gap-4 rounded-xl border border-border bg-card p-4">
        <DateRangeFilter desde={desde} hasta={hasta} onChange={handleDateChange} />
        <GranularitySelector value={granularidad} onChange={setGranularidad} />
      </div>

      {/* KPI Cards */}
      <KpiGrid data={resumen.data} loading={resumen.isLoading} />

      {/* Charts grid */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <VentasLineChart
          data={ventas.data ?? []}
          loading={ventas.isLoading}
        />
        <PedidosPieChart
          data={pedidosPorEstado.data ?? []}
          loading={pedidosPorEstado.isLoading}
        />
      </div>

      {/* Top products — full width */}
      <ProductosBarChart
        data={productosTop.data ?? []}
        loading={productosTop.isLoading}
      />
    </div>
  )
}
