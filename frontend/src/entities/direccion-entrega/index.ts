/**
 * Barrel exports for the direccion-entrega entity (FSD Layer: Entities).
 *
 * Change 14: delivery-addresses-management.
 *
 * Exports all public types and hooks so consumers can import from
 * '@/entities/direccion-entrega' without referencing internal paths.
 */

// Types
export type { DireccionEntrega, DireccionEntregaCreateDto, DireccionEntregaUpdateDto } from './model/types'

// API functions
export {
  getAddresses,
  getAddress,
  createAddress,
  updateAddress,
  setMainAddress,
  deleteAddress,
} from './api/direccion-entrega-api'

// Query hooks
export {
  useAddresses,
  useAddress,
  useCreateAddress,
  useUpdateAddress,
  useSetMainAddress,
  useDeleteAddress,
} from './api/use-direcciones'
