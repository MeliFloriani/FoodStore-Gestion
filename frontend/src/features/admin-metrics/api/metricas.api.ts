/**
 * Axios API functions for admin metrics endpoints.
 *
 * Change 23: admin-metrics-dashboard.
 *
 * All functions call the shared Axios instance (http) with the JWT interceptor.
 * Base paths: /api/v1/admin/metricas/*
 */

import { http } from '@/shared/api/http'
import type {
  DateRangeParams,
  Granularidad,
  MetricasResumenRead,
  PedidoEstadoDistribucionRead,
  ProductoTopRead,
  VentasPeriodoRead,
} from './metricas.types'

const BASE = '/api/v1/admin/metricas'

/**
 * GET /api/v1/admin/metricas/resumen
 * Returns KPI summary: sales totals, orders per state, user counts.
 */
export async function fetchMetricasResumen(
  params: DateRangeParams = {},
): Promise<MetricasResumenRead> {
  const response = await http.get<MetricasResumenRead>(`${BASE}/resumen`, { params })
  return response.data
}

/**
 * GET /api/v1/admin/metricas/ventas
 * Returns time-series sales data grouped by granularity.
 */
export async function fetchMetricasVentas(
  params: DateRangeParams & { granularidad?: Granularidad } = {},
): Promise<VentasPeriodoRead[]> {
  const response = await http.get<VentasPeriodoRead[]>(`${BASE}/ventas`, { params })
  return response.data
}

/**
 * GET /api/v1/admin/metricas/productos-top
 * Returns top N products by quantity sold.
 */
export async function fetchMetricasProductosTop(
  params: DateRangeParams & { top?: number } = {},
): Promise<ProductoTopRead[]> {
  const response = await http.get<ProductoTopRead[]>(`${BASE}/productos-top`, { params })
  return response.data
}

/**
 * GET /api/v1/admin/metricas/pedidos-por-estado
 * Returns order count per state for all states in the period.
 */
export async function fetchMetricasPedidosPorEstado(
  params: DateRangeParams = {},
): Promise<PedidoEstadoDistribucionRead[]> {
  const response = await http.get<PedidoEstadoDistribucionRead[]>(
    `${BASE}/pedidos-por-estado`,
    { params },
  )
  return response.data
}
