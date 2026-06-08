/*
 * cartStore — FSD entity: entities/cart
 *
 * Slice subscription convention (D-06):
 *
 *   // Preferred: subscribe to one slice to avoid unnecessary re-renders
 *   const items = useCartStore((s) => s.items)
 *   const totalItems = useCartStore((s) => s.totalItems)
 *
 *   // Forbidden: select the whole store object — triggers re-render on every state change
 *   // const store = useCartStore()
 */
import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { CartItem, AddItemResult } from '@/entities/cart/types'
import type { ProductoIngredienteRead } from '@/entities/products/model/types'
import {
  areItemsEquivalent,
  buildItemKey,
  normalizePersonalizacion,
} from './cartUtils'

type CartState = {
  items: CartItem[]
  /**
   * Custom version field for migration. NOT the Zustand middleware `version` config.
   * v1 (Change 05): producto_id: number, personalizacion: number[]
   * v2 (Change 15): producto_id: string, personalizacion: string[] (UUID)
   */
  version: number
}

type CartActions = {
  /**
   * Adds an item to the cart or increments its quantity if an equivalent
   * item already exists (same product + same normalized personalization).
   *
   * Two-layer validation strategy (D-03):
   *  - Caller (UI/feature layer) validates UX constraints (e.g. max quantity,
   *    stock availability, display feedback). The store does NOT duplicate these.
   *  - Store validates defense-in-depth: es_removible check ensures no
   *    non-removable ingredient slips through regardless of caller behavior.
   *    This layer cannot be bypassed by the caller.
   *
   * @param item - CartItem to add; personalizacion = excluded ingredient UUIDs
   * @param availableIngredients - From fetchProductoIngredientes()
   *   (GET /api/v1/productos/{id}/ingredientes); must include es_removible
   */
  addItem: (
    item: CartItem,
    availableIngredients: ProductoIngredienteRead[],
  ) => AddItemResult
  removeItem: (itemKey: string) => void
  incrementQuantity: (itemKey: string) => void
  decrementQuantity: (itemKey: string) => void
  setQuantity: (itemKey: string, n: number) => void
  clearCart: () => void
  // Selectors — NOT included in partialize (recomputed from items)
  totalItems: () => number
  subtotal: () => number
  /** costoEnvio is always 0 — placeholder for future delivery-cost logic (D-05).
   * When delivery pricing is implemented, replace this constant with the actual
   * calculation (e.g. zone-based pricing, order total threshold, promo codes). */
  costoEnvio: () => number
  total: () => number
}

type CartStore = CartState & CartActions

export const initialCartState: CartState = {
  items: [],
  version: 2,
}

export const useCartStore = create<CartStore>()(
  persist(
    (set, get) => ({
      ...initialCartState,

      addItem: (item, availableIngredients) => {
        // Defense-in-depth: validate that all personalizacion IDs are removable
        // Unknown IDs (not in availableIngredients) are also treated as invalid
        const invalidIds = item.personalizacion.filter((id) => {
          const ingredient = availableIngredients.find(
            (i) => i.ingrediente_id === id,
          )
          return !ingredient || !ingredient.es_removible
        })

        if (invalidIds.length > 0) {
          return { ok: false, reason: 'INGREDIENT_NOT_REMOVABLE', invalidIds }
        }

        const normalized = normalizePersonalizacion(item.personalizacion)
        const normalizedItem: CartItem = { ...item, personalizacion: normalized }

        const { items } = get()
        const existingIndex = items.findIndex((i) =>
          areItemsEquivalent(i, normalizedItem),
        )

        if (existingIndex !== -1) {
          set({
            items: items.map((i, idx) =>
              idx === existingIndex
                ? { ...i, cantidad: i.cantidad + normalizedItem.cantidad }
                : i,
            ),
          })
        } else {
          set({ items: [...items, normalizedItem] })
        }

        return { ok: true }
      },

      removeItem: (itemKey) =>
        set({
          items: get().items.filter((i) => buildItemKey(i) !== itemKey),
        }),

      incrementQuantity: (itemKey) =>
        set({
          items: get().items.map((i) =>
            buildItemKey(i) === itemKey ? { ...i, cantidad: i.cantidad + 1 } : i,
          ),
        }),

      decrementQuantity: (itemKey) => {
        const { items } = get()
        const item = items.find((i) => buildItemKey(i) === itemKey)
        if (!item) return
        if (item.cantidad <= 1) {
          set({ items: items.filter((i) => buildItemKey(i) !== itemKey) })
        } else {
          set({
            items: items.map((i) =>
              buildItemKey(i) === itemKey
                ? { ...i, cantidad: i.cantidad - 1 }
                : i,
            ),
          })
        }
      },

      setQuantity: (itemKey, n) => {
        if (n <= 0) {
          set({ items: get().items.filter((i) => buildItemKey(i) !== itemKey) })
          return
        }
        set({
          items: get().items.map((i) =>
            buildItemKey(i) === itemKey ? { ...i, cantidad: n } : i,
          ),
        })
      },

      clearCart: () => set({ items: [] }),

      totalItems: () => get().items.reduce((sum, i) => sum + i.cantidad, 0),

      subtotal: () =>
        get().items.reduce((sum, i) => sum + i.precio * i.cantidad, 0),

      costoEnvio: () => 0,

      total: () => get().subtotal() + get().costoEnvio(),
    }),
    {
      name: 'food-store-cart',
      partialize: (state) => ({
        items: state.items,
        version: state.version,
      }),
      onRehydrateStorage: () => (state) => {
        // Migration v1 → v2: clear items when version doesn't match expected schema.
        // v1 used number IDs (producto_id, personalizacion[]); v2 uses UUID strings.
        // Items from v1 are incompatible — must be cleared rather than migrated.
        if (state && state.version !== 2) {
          state.items = []
          state.version = 2
        }
      },
    },
  ),
)
