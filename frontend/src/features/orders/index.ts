/**
 * Barrel export for the orders feature (Change 20).
 *
 * Public API:
 * - useClientOrders hook (for OrdersPage)
 * - useOrderDetail hook (for OrderDetailPage, OrderConfirmationPage)
 * - OrderHistoryTimeline component
 *
 * FSD rule: imports into this feature must only come from entities/ or shared/,
 * or from features/pedido-state-actions (reusing useHistorialPedido — D-07).
 */

// Hooks
export { useClientOrders } from './hooks/useClientOrders'
export { useOrderDetail } from './hooks/useOrderDetail'

// Components
export { OrderHistoryTimeline } from './ui/OrderHistoryTimeline'
export type { OrderHistoryTimelineProps } from './ui/OrderHistoryTimeline'
