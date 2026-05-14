import { describe, it, expect, beforeEach } from 'vitest'
import { useCartStore } from '@/entities/cart/model/store'
import type { CartItem } from '@/entities/cart/types'

const mockItem: CartItem = {
  producto_id: 1,
  nombre: 'Burger',
  precio: 10.5,
  cantidad: 1,
  imagen_url: 'http://example.com/burger.jpg',
  personalizacion: [],
}

const mockItem2: CartItem = {
  producto_id: 2,
  nombre: 'Pizza',
  precio: 15.0,
  cantidad: 2,
  imagen_url: 'http://example.com/pizza.jpg',
  personalizacion: [3, 5],
}

describe('cartStore', () => {
  beforeEach(() => {
    useCartStore.getState().clearCart()
  })

  it('starts with empty items', () => {
    expect(useCartStore.getState().items).toHaveLength(0)
  })

  it('addItem adds a new item', () => {
    useCartStore.getState().addItem(mockItem)
    expect(useCartStore.getState().items).toHaveLength(1)
    expect(useCartStore.getState().items[0]).toEqual(mockItem)
  })

  it('addItem merges quantity on duplicate producto_id', () => {
    useCartStore.getState().addItem(mockItem)
    useCartStore.getState().addItem({ ...mockItem, cantidad: 3 })
    const items = useCartStore.getState().items
    expect(items).toHaveLength(1)
    expect(items[0]?.cantidad).toBe(4)
  })

  it('addItem does not merge different producto_id', () => {
    useCartStore.getState().addItem(mockItem)
    useCartStore.getState().addItem(mockItem2)
    expect(useCartStore.getState().items).toHaveLength(2)
  })

  it('removeItem removes item by producto_id', () => {
    useCartStore.getState().addItem(mockItem)
    useCartStore.getState().addItem(mockItem2)
    useCartStore.getState().removeItem(1)
    const items = useCartStore.getState().items
    expect(items).toHaveLength(1)
    expect(items[0]?.producto_id).toBe(2)
  })

  it('updateQuantity updates item quantity', () => {
    useCartStore.getState().addItem(mockItem)
    useCartStore.getState().updateQuantity(1, 5)
    expect(useCartStore.getState().items[0]?.cantidad).toBe(5)
  })

  it('updateQuantity removes item when quantity is 0 or less', () => {
    useCartStore.getState().addItem(mockItem)
    useCartStore.getState().updateQuantity(1, 0)
    expect(useCartStore.getState().items).toHaveLength(0)
  })

  it('clearCart removes all items', () => {
    useCartStore.getState().addItem(mockItem)
    useCartStore.getState().addItem(mockItem2)
    useCartStore.getState().clearCart()
    expect(useCartStore.getState().items).toHaveLength(0)
  })

  it('totalItems sums all quantities', () => {
    useCartStore.getState().addItem(mockItem)
    useCartStore.getState().addItem(mockItem2)
    expect(useCartStore.getState().totalItems()).toBe(3) // 1 + 2
  })

  it('totalPrice calculates correct total', () => {
    useCartStore.getState().addItem(mockItem) // 10.5 * 1
    useCartStore.getState().addItem(mockItem2) // 15.0 * 2
    expect(useCartStore.getState().totalPrice()).toBeCloseTo(40.5)
  })

  it('partialize persists only items and version', () => {
    useCartStore.getState().addItem(mockItem)
    const partial = useCartStore.persist.getOptions().partialize?.(useCartStore.getState())
    expect(partial).toHaveProperty('items')
    expect(partial).toHaveProperty('version')
  })
})
