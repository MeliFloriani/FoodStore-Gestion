/**
 * Barrel export for the Cart entity (FSD entities layer).
 *
 * Public API surface — import from '@/entities/cart' in features/widgets/pages.
 *
 * Exports:
 *  - Types (CartItem, AddItemResult)
 *  - Store hook (useCartStore)
 *  - Utilities (buildItemKey, normalizePersonalizacion, areItemsEquivalent)
 */

// Types
export type { CartItem, AddItemResult } from './types'

// Store
export { useCartStore, initialCartState } from './model/store'

// Utilities
export {
  buildItemKey,
  normalizePersonalizacion,
  areItemsEquivalent,
} from './model/cartUtils'
