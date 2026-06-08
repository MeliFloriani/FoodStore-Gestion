/**
 * Barrel export for the pedido-state-actions feature (Change 18).
 *
 * Public API of src/features/pedido-state-actions/:
 * - API functions
 * - Hooks (useTransitionEstado, useCancelarPedidoCliente, useHistorialPedido)
 * - Components (EstadoActionBar, CancelReasonModal)
 *
 * FSD rule: imports into this feature must only come from entities/ or shared/.
 */

// API
export {
  transitionEstado,
  cancelarPedidoCliente,
  getHistorialPedido,
  FRONTEND_ALLOWED_TRANSITIONS,
  CLIENT_ALLOWED_TRANSITIONS,
} from './api/pedidoEstadoApi'
export type { TransitionEstadoRequest } from './api/pedidoEstadoApi'

// Hooks
export { useTransitionEstado } from './hooks/useTransitionEstado'
export type { TransitionEstadoArgs } from './hooks/useTransitionEstado'

export { useCancelarPedidoCliente } from './hooks/useCancelarPedidoCliente'
export type { CancelarPedidoArgs } from './hooks/useCancelarPedidoCliente'

export { useHistorialPedido } from './hooks/useHistorialPedido'

// Components
export { EstadoActionBar } from './components/EstadoActionBar'
export type { EstadoActionBarProps } from './components/EstadoActionBar'

export { CancelReasonModal } from './components/CancelReasonModal'
export type { CancelReasonModalProps } from './components/CancelReasonModal'
