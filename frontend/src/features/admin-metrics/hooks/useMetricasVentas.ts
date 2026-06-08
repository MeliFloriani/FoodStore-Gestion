/**
 * useMetricasVentas — TanStack Query hook for time-series sales data.
 *
 * Change 23: admin-metrics-dashboard.
 *
 * Query key: ['metricas', 'ventas', desde, hasta, granularidad]
 * staleTime: 30 seconds
 */

import { useQuery } from '@tanstack/react-query'
import { fetchMetricasVentas } from '../api/metricas.api'
import type { DateRangeParams, Granularidad, VentasPeriodoRead } from '../api/metricas.types'

interface UseMetricasVentasParams extends DateRangeParams {
  granularidad?: Granularidad
}

export function useMetricasVentas(params: UseMetricasVentasParams = {}) {
  const { desde, hasta, granularidad = 'dia' } = params
  return useQuery<VentasPeriodoRead[], Error>({
    queryKey: ['metricas', 'ventas', desde, hasta, granularidad],
    queryFn: () => fetchMetricasVentas({ desde, hasta, granularidad }),
    staleTime: 30_000,
  })
}
