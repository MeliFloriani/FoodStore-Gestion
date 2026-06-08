/**
 * useMetricasResumen — TanStack Query hook for KPI summary.
 *
 * Change 23: admin-metrics-dashboard.
 *
 * Query key: ['metricas', 'resumen', desde, hasta]
 * staleTime: 30 seconds
 */

import { useQuery } from '@tanstack/react-query'
import { fetchMetricasResumen } from '../api/metricas.api'
import type { DateRangeParams, MetricasResumenRead } from '../api/metricas.types'

export function useMetricasResumen(params: DateRangeParams = {}) {
  const { desde, hasta } = params
  return useQuery<MetricasResumenRead, Error>({
    queryKey: ['metricas', 'resumen', desde, hasta],
    queryFn: () => fetchMetricasResumen(params),
    staleTime: 30_000,
  })
}
