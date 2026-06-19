import { describe, it, expect, beforeEach } from 'vitest'
import { useCartStore } from '@/entities/cart/model/store'
import { buildItemKey } from '@/entities/cart/model/cartUtils'
import type { CartItem } from '@/entities/cart/types'

const mockItem: CartItem = {
  producto_id: 'prod-1',
  nombre: 'Burger',
  precio: 10.5,
  cantidad: 1,
  imagen_url: 'http://example.com/burger.jpg',
  personalizacion: [],
}

const mockItem2: CartItem = {
  producto_id: 'prod-2',
  nombre: 'Pizza',
  precio: 15.0,
  cantidad: 2,
  imagen_url: 'http://example.com/pizza.jpg',
  personalizacion: [],
}

describe('cartStore', () => {
  beforeEach(() => {
    useCartStore.getState().clearCart()
  })

  it('starts with empty items', () => {
    expect(useCartStore.getState().items).toHaveLength(0)
  })

  it('addItem adds a new item', () => {
    useCartStore.getState().addItem(mockItem, [])
    expect(useCartStore.getState().items).toHaveLength(1)
  })

  it('addItem merges quantity on duplicate producto_id', () => {
    useCartStore.getState().addItem(mockItem, [])
    useCartStore.getState().addItem({ ...mockItem, cantidad: 3 }, [])
    expect(useCartStore.getState().items).toHaveLength(1)
    expect(useCartStore.getState().items[0]?.cantidad).toBe(4)
  })

  it('addItem does not merge different producto_id', () => {
    useCartStore.getState().addItem(mockItem, [])
    useCartStore.getState().addItem(mockItem2, [])
    expect(useCartStore.getState().items).toHaveLength(2)
  })

  it('removeItem removes item by itemKey', () => {
    useCartStore.getState().addItem(mockItem, [])
    useCartStore.getState().addItem(mockItem2, [])
    const key = buildItemKey(mockItem)
    useCartStore.getState().removeItem(key)
    expect(useCartStore.getState().items).toHaveLength(1)
  })

  it('setQuantity updates item quantity', () => {
    useCartStore.getState().addItem(mockItem, [])
    const key = buildItemKey(mockItem)
    useCartStore.getState().setQuantity(key, 5)
    expect(useCartStore.getState().items[0]?.cantidad).toBe(5)
  })

  it('setQuantity removes item when quantity is 0 or less', () => {
    useCartStore.getState().addItem(mockItem, [])
    const key = buildItemKey(mockItem)
    useCartStore.getState().setQuantity(key, 0)
    expect(useCartStore.getState().items).toHaveLength(0)
  })

  it('clearCart removes all items', () => {
    useCartStore.getState().addItem(mockItem, [])
    useCartStore.getState().addItem(mockItem2, [])
    useCartStore.getState().clearCart()
    expect(useCartStore.getState().items).toHaveLength(0)
  })

  it('totalItems sums all quantities', () => {
    useCartStore.getState().addItem(mockItem, [])
    useCartStore.getState().addItem(mockItem2, [])
    expect(useCartStore.getState().totalItems()).toBe(3)
  })

  it('total calculates correct total', () => {
    useCartStore.getState().addItem(mockItem, [])
    useCartStore.getState().addItem(mockItem2, [])
    expect(useCartStore.getState().total()).toBeCloseTo(40.5)
  })

  it('partialize persists only items and version', () => {
    useCartStore.getState().addItem(mockItem, [])
    const partial = useCartStore.persist.getOptions().partialize?.(useCartStore.getState())
    expect(partial).toHaveProperty('items')
    expect(partial).toHaveProperty('version')
  })
})
