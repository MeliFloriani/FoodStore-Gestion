/**
 * Query key factory for order-related queries (Change 20).
 *
 * Centralizes query key definitions so that:
 * - useClientOrders uses [...pedidoEstadoKeys.list(), params]
 * - useOrderDetail uses pedidoEstadoKeys.detail(pedidoId) = ['pedido', pedidoId]
 * - useHistorialPedido (Change 18) already uses ['pedido-historial', pedidoId]
 *   (kept separate to avoid over-invalidation)
 *
 * Key structure:
 *   list()        → ['pedidos']           (invalidation prefix for order lists)
 *   detail(id)    → ['pedido', id]        (single order — same as usePaymentStatus)
 *
 * useTransitionEstado.onSuccess already invalidates ['pedidos'] and ['pedido', id],
 * so invalidation works automatically for both list and detail views.
 */

export const pedidoEstadoKeys = {
  /** Base key for all order listings — prefix match invalidates all list variants */
  list: () => ['pedidos'] as const,
  /** Key for a single order detail — compatible with usePaymentStatus query key */
  detail: (pedidoId: string) => ['pedido', pedidoId] as const,
} as const
