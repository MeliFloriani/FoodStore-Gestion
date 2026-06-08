/**
 * useMetricasProductosTop — TanStack Query hook for top products ranking.
 *
 * Change 23: admin-metrics-dashboard.
 *
 * Query key: ['metricas', 'productos-top', desde, hasta, top]
 * staleTime: 30 seconds
 */

import { useQuery } from '@tanstack/react-query'
import { fetchMetricasProductosTop } from '../api/metricas.api'
import type { DateRangeParams, ProductoTopRead } from '../api/metricas.types'

interface UseMetricasProductosTopParams extends DateRangeParams {
  top?: number
}

export function useMetricasProductosTop(params: UseMetricasProductosTopParams = {}) {
  const { desde, hasta, top = 10 } = params
  return useQuery<ProductoTopRead[], Error>({
    queryKey: ['metricas', 'productos-top', desde, hasta, top],
    queryFn: () => fetchMetricasProductosTop({ desde, hasta, top }),
    staleTime: 30_000,
  })
}
