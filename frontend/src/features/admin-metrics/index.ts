/**
 * admin-metrics feature — public API barrel.
 *
 * Change 23: admin-metrics-dashboard.
 *
 * FSD rule: Pages and widgets import from this barrel only.
 * This feature does NOT import from any other feature module.
 */

// API types
export type {
  MetricasResumenRead,
  VentasPeriodoRead,
  ProductoTopRead,
  PedidoEstadoCountRead,
  PedidoEstadoDistribucionRead,
  DateRangeParams,
  Granularidad,
} from './api/metricas.types'

// API functions
export {
  fetchMetricasResumen,
  fetchMetricasVentas,
  fetchMetricasProductosTop,
  fetchMetricasPedidosPorEstado,
} from './api/metricas.api'

// TanStack Query hooks
export { useMetricasResumen } from './hooks/useMetricasResumen'
export { useMetricasVentas } from './hooks/useMetricasVentas'
export { useMetricasProductosTop } from './hooks/useMetricasProductosTop'
export { useMetricasPedidosPorEstado } from './hooks/useMetricasPedidosPorEstado'

// UI Components
export { KpiCard } from './components/KpiCard'
export { KpiGrid } from './components/KpiGrid'
export { VentasLineChart } from './components/VentasLineChart'
export { ProductosBarChart } from './components/ProductosBarChart'
export { PedidosPieChart } from './components/PedidosPieChart'

// Widgets
export { DateRangeFilter } from './widgets/DateRangeFilter'
export { GranularitySelector } from './widgets/GranularitySelector'
