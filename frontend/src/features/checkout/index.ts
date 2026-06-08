/**
 * Barrel export for the checkout feature (Change 17).
 *
 * Public API of src/features/checkout/:
 * - useCreateOrder hook
 * - CheckoutSubmit component
 * - Public types (CreateOrderRequest, PedidoRead, etc.)
 *
 * FSD rule: imports into this feature must only come from entities/ or shared/.
 */

export { useCreateOrder } from './hooks/useCreateOrder'
export type { CreateOrderArgs } from './hooks/useCreateOrder'
export { CheckoutSubmit } from './ui/CheckoutSubmit'
export type {
  CreateOrderRequest,
  OrderItemRequest,
  PedidoRead,
  DetallePedidoRead,
  HistorialEstadoPedidoRead,
  OrderErrorResponse,
} from './model/types'
