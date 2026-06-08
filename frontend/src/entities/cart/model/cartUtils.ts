import type { CartItem } from '@/entities/cart/types'

/**
 * Returns a sorted, deduplicated copy of the ingredient ID array.
 * Sorting is lexicographic — correct for UUID strings.
 */
export function normalizePersonalizacion(ids: string[]): string[] {
  return [...new Set(ids)].sort()
}

/**
 * Derives a stable string key for a cart item from its product ID and
 * normalized personalization. NOT persisted — always recomputed on demand.
 *
 * Format: "<producto_id>::<ing-1>,<ing-2>,..."
 * Example: buildItemKey({ producto_id: "prod-uuid", personalizacion: ["ing-3","ing-1"] })
 *          → "prod-uuid::ing-1,ing-3"
 */
export function buildItemKey(
  item: Pick<CartItem, 'producto_id' | 'personalizacion'>,
): string {
  const sorted = normalizePersonalizacion(item.personalizacion)
  return `${item.producto_id}::${sorted.join(',')}`
}

/**
 * Returns true when two CartItems represent the same "slot" in the cart:
 * same product AND same (order-independent) personalization.
 */
export function areItemsEquivalent(a: CartItem, b: CartItem): boolean {
  if (a.producto_id !== b.producto_id) return false
  const na = normalizePersonalizacion(a.personalizacion)
  const nb = normalizePersonalizacion(b.personalizacion)
  return na.length === nb.length && na.every((v, i) => v === nb[i])
}
