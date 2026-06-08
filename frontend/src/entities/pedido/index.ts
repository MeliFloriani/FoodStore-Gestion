/**
 * Barrel export for the pedido entity (FSD entities layer).
 *
 * Change 20: adds PedidoListItem, PedidoPage, PedidoDetail, UsuarioBasic,
 * DireccionBasic, ClientOrdersParams, AdminOrdersParams, pedidoEstadoKeys,
 * and API functions for listing / fetching order detail.
 */

// Types
export type {
  PedidoListItem,
  PedidoPage,
  PedidoDetail,
  UsuarioBasic,
  DireccionBasic,
  ClientOrdersParams,
  AdminOrdersParams,
} from './model/types'

export type { HistorialEstadoPedidoRead } from './model/historialTypes'

// API
export { listPedidos, getPedidoDetail } from './api/pedidosApi'

// Query key factory
export { pedidoEstadoKeys } from './model/pedidoEstadoKeys'
