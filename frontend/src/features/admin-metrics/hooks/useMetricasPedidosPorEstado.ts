/**
 * useMetricasPedidosPorEstado — TanStack Query hook for order state distribution.
 *
 * Change 23: admin-metrics-dashboard.
 *
 * Query key: ['metricas', 'pedidos-por-estado', desde, hasta]
 * staleTime: 30 seconds
 */

import { useQuery } from '@tanstack/react-query'
import { fetchMetricasPedidosPorEstado } from '../api/metricas.api'
import type { DateRangeParams, PedidoEstadoDistribucionRead } from '../api/metricas.types'

export function useMetricasPedidosPorEstado(params: DateRangeParams = {}) {
  const { desde, hasta } = params
  return useQuery<PedidoEstadoDistribucionRead[], Error>({
    queryKey: ['metricas', 'pedidos-por-estado', desde, hasta],
    queryFn: () => fetchMetricasPedidosPorEstado(params),
    staleTime: 30_000,
  })
}
