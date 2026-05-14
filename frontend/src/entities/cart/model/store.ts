import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { CartItem } from '@/entities/cart/types'

type CartState = {
  items: CartItem[]
  version: number
}

type CartActions = {
  addItem: (item: CartItem) => void
  removeItem: (producto_id: number) => void
  updateQuantity: (producto_id: number, cantidad: number) => void
  clearCart: () => void
  totalItems: () => number
  totalPrice: () => number
}

type CartStore = CartState & CartActions

export const useCartStore = create<CartStore>()(
  persist(
    (set, get) => ({
      items: [],
      version: 1,

      addItem: (item) => {
        const existing = get().items.find(
          (i) => i.producto_id === item.producto_id,
        )
        if (existing) {
          set({
            items: get().items.map((i) =>
              i.producto_id === item.producto_id
                ? { ...i, cantidad: i.cantidad + item.cantidad }
                : i,
            ),
          })
        } else {
          set({ items: [...get().items, item] })
        }
      },

      removeItem: (producto_id) =>
        set({
          items: get().items.filter((i) => i.producto_id !== producto_id),
        }),

      updateQuantity: (producto_id, cantidad) => {
        if (cantidad <= 0) {
          get().removeItem(producto_id)
          return
        }
        set({
          items: get().items.map((i) =>
            i.producto_id === producto_id ? { ...i, cantidad } : i,
          ),
        })
      },

      clearCart: () => set({ items: [] }),

      totalItems: () =>
        get().items.reduce((sum, item) => sum + item.cantidad, 0),

      totalPrice: () =>
        get().items.reduce(
          (sum, item) => sum + item.precio * item.cantidad,
          0,
        ),
    }),
    {
      name: 'food-store-cart',
      partialize: (state) => ({
        items: state.items,
        version: state.version,
      }),
    },
  ),
)
