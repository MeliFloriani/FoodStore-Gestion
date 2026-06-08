/**
 * Barrel export for the orders-panel feature (Change 20).
 *
 * Public API:
 * - useAdminOrders hook (for PedidosPanelPage)
 *
 * FSD rule: imports into this feature must only come from entities/ or shared/.
 */

// Hooks
export { useAdminOrders } from './hooks/useAdminOrders'
