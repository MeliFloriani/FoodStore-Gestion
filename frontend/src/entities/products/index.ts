/**
 * Barrel export for the Producto entity (FSD entities layer).
 *
 * Public API surface — import from '@/entities/products' in features/widgets/pages.
 *
 * Exports:
 *  - Types (ProductoRead, ProductoDetail, PaginatedProductos, payload & filter types)
 *  - Query key factory (productQueryKeys)
 *  - Read hooks (useProductos, useProducto, useProductoIngredientes)
 *  - Mutation hooks (useCreateProducto, useUpdateProducto, useDeleteProducto,
 *                    useUpdateDisponibilidad, useAsociarIngrediente, useRemoverIngrediente)
 *  - Plain async fetchers (for use outside React — e.g. loaders, server utilities)
 */

// Model
export type {
  ProductoRead,
  ProductoIngredienteRead,
  ProductoDetail,
  PaginatedProductos,
  ProductoCreatePayload,
  ProductoUpdatePayload,
  DisponibilidadUpdatePayload,
  AsociarIngredientePayload,
  ProductoListFilters,
} from './model/types'

export { productQueryKeys } from './model/queryKeys'

// Read hooks
export {
  useProductos,
  useProducto,
  useProductoIngredientes,
} from './model/useProductos'

// Mutation hooks
export {
  useCreateProducto,
  useUpdateProducto,
  useDeleteProducto,
  useUpdateDisponibilidad,
  useAsociarIngrediente,
  useRemoverIngrediente,
} from './model/useProductoMutations'

// Plain fetchers (for non-hook usage)
export {
  listProductos,
  getProducto,
  createProducto,
  updateProducto,
  deleteProducto,
  updateDisponibilidad,
  listProductoIngredientes,
  asociarIngrediente,
  removerIngrediente,
} from './api/productoFetchers'
