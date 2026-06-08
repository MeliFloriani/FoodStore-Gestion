import { describe, it, expect, beforeEach } from 'vitest'
import { useCartStore, initialCartState } from './store'
import { useAuthStore } from '@/entities/auth/model/store'
import type { CartItem } from '@/entities/cart/types'
import type { ProductoIngredienteRead } from '@/entities/products/model/types'
import { buildItemKey } from './cartUtils'

// ── Test helpers ──────────────────────────────────────────────────────────────

const makeItem = (overrides: Partial<CartItem> = {}): CartItem => ({
  producto_id: 'prod-uuid',
  nombre: 'Hamburguesa',
  precio: 10,
  cantidad: 1,
  imagen_url: 'img.jpg',
  personalizacion: [],
  ...overrides,
})

const makeIngredient = (
  overrides: Partial<ProductoIngredienteRead> = {},
): ProductoIngredienteRead => ({
  ingrediente_id: 'ing-uuid-1',
  nombre: 'Lechuga',
  es_alergeno: false,
  es_removible: true,
  ...overrides,
})

beforeEach(() => {
  useCartStore.setState(initialCartState)
})

// ── addItem ───────────────────────────────────────────────────────────────────

describe('addItem', () => {
  it('adds a new item to items', () => {
    const result = useCartStore.getState().addItem(makeItem(), [])
    expect(result).toEqual({ ok: true })
    expect(useCartStore.getState().items).toHaveLength(1)
    expect(useCartStore.getState().items[0].producto_id).toBe('prod-uuid')
  })

  it('increments cantidad for equivalent item (same product + same personalization)', () => {
    const ingredient = makeIngredient({ ingrediente_id: 'ing-uuid-1' })
    useCartStore.getState().addItem(
      makeItem({ personalizacion: ['ing-uuid-1'], cantidad: 1 }),
      [ingredient],
    )
    const result = useCartStore.getState().addItem(
      makeItem({ personalizacion: ['ing-uuid-1'], cantidad: 2 }),
      [ingredient],
    )
    expect(result).toEqual({ ok: true })
    const items = useCartStore.getState().items
    expect(items).toHaveLength(1)
    expect(items[0].cantidad).toBe(3)
  })

  it('same product + different personalization creates new slot', () => {
    const ing1 = makeIngredient({ ingrediente_id: 'ing-uuid-1' })
    const ing2 = makeIngredient({ ingrediente_id: 'ing-uuid-2', nombre: 'Tomate' })
    useCartStore.getState().addItem(
      makeItem({ personalizacion: ['ing-uuid-1'] }),
      [ing1, ing2],
    )
    const result = useCartStore.getState().addItem(
      makeItem({ personalizacion: ['ing-uuid-2'] }),
      [ing1, ing2],
    )
    expect(result).toEqual({ ok: true })
    expect(useCartStore.getState().items).toHaveLength(2)
  })

  it('returns ok:false for non-removable ingredient and does not mutate', () => {
    const nonRemovable = makeIngredient({
      ingrediente_id: 'ing-uuid-1',
      es_removible: false,
    })
    const result = useCartStore
      .getState()
      .addItem(makeItem({ personalizacion: ['ing-uuid-1'] }), [nonRemovable])
    expect(result).toEqual({
      ok: false,
      reason: 'INGREDIENT_NOT_REMOVABLE',
      invalidIds: ['ing-uuid-1'],
    })
    expect(useCartStore.getState().items).toHaveLength(0)
  })

  it('returns ok:false for unknown ingredient ID and does not mutate', () => {
    const result = useCartStore
      .getState()
      .addItem(makeItem({ personalizacion: ['ing-unknown'] }), [])
    expect(result).toEqual({
      ok: false,
      reason: 'INGREDIENT_NOT_REMOVABLE',
      invalidIds: ['ing-unknown'],
    })
    expect(useCartStore.getState().items).toHaveLength(0)
  })

  it('returns ok:true for empty personalizacion', () => {
    const result = useCartStore
      .getState()
      .addItem(makeItem({ personalizacion: [] }), [])
    expect(result).toEqual({ ok: true })
    expect(useCartStore.getState().items).toHaveLength(1)
  })

  it('normalizes personalizacion before storing (dedup + sort)', () => {
    const ing1 = makeIngredient({ ingrediente_id: 'ing-1' })
    const ing3 = makeIngredient({ ingrediente_id: 'ing-3', nombre: 'Cebolla' })
    useCartStore
      .getState()
      .addItem(makeItem({ personalizacion: ['ing-3', 'ing-1', 'ing-3'] }), [ing1, ing3])
    const stored = useCartStore.getState().items[0]
    expect(stored.personalizacion).toEqual(['ing-1', 'ing-3'])
  })

  it('treats same personalizacion in different order as equivalent (increments cantidad)', () => {
    const ing1 = makeIngredient({ ingrediente_id: 'ing-uuid-1' })
    const ing3 = makeIngredient({ ingrediente_id: 'ing-uuid-3', nombre: 'Cebolla' })
    useCartStore.getState().addItem(
      makeItem({ personalizacion: ['ing-uuid-1', 'ing-uuid-3'] }),
      [ing1, ing3],
    )
    useCartStore.getState().addItem(
      makeItem({ personalizacion: ['ing-uuid-3', 'ing-uuid-1'] }),
      [ing1, ing3],
    )
    const items = useCartStore.getState().items
    expect(items).toHaveLength(1)
    expect(items[0].cantidad).toBe(2)
  })
})

// ── removeItem ────────────────────────────────────────────────────────────────

describe('removeItem', () => {
  it('removes correct item; other items remain', () => {
    const item1 = makeItem({ producto_id: 'prod-1', nombre: 'Burger' })
    const item2 = makeItem({ producto_id: 'prod-2', nombre: 'Pizza' })
    useCartStore.getState().addItem(item1, [])
    useCartStore.getState().addItem(item2, [])
    useCartStore.getState().removeItem(buildItemKey(item1))
    const items = useCartStore.getState().items
    expect(items).toHaveLength(1)
    expect(items[0].producto_id).toBe('prod-2')
  })

  it('is a no-op for unknown itemKey', () => {
    useCartStore.getState().addItem(makeItem(), [])
    useCartStore.getState().removeItem('nonexistent::key')
    expect(useCartStore.getState().items).toHaveLength(1)
  })
})

// ── quantity actions ──────────────────────────────────────────────────────────

describe('quantity actions', () => {
  let key: string

  beforeEach(() => {
    useCartStore.getState().addItem(makeItem({ cantidad: 2 }), [])
    key = buildItemKey(makeItem())
  })

  it('incrementQuantity increments by 1', () => {
    useCartStore.getState().incrementQuantity(key)
    expect(useCartStore.getState().items[0].cantidad).toBe(3)
  })

  it('decrementQuantity decrements by 1', () => {
    useCartStore.getState().decrementQuantity(key)
    expect(useCartStore.getState().items[0].cantidad).toBe(1)
  })

  it('decrementQuantity removes item when cantidad reaches 1', () => {
    useCartStore.getState().setQuantity(key, 1)
    useCartStore.getState().decrementQuantity(key)
    expect(useCartStore.getState().items).toHaveLength(0)
  })

  it('setQuantity sets to given value', () => {
    useCartStore.getState().setQuantity(key, 5)
    expect(useCartStore.getState().items[0].cantidad).toBe(5)
  })

  it('setQuantity(key, 0) removes item', () => {
    useCartStore.getState().setQuantity(key, 0)
    expect(useCartStore.getState().items).toHaveLength(0)
  })

  it('setQuantity(key, -1) removes item', () => {
    useCartStore.getState().setQuantity(key, -1)
    expect(useCartStore.getState().items).toHaveLength(0)
  })
})

// ── clearCart ─────────────────────────────────────────────────────────────────

describe('clearCart', () => {
  it('resets items to []', () => {
    useCartStore.getState().addItem(makeItem(), [])
    useCartStore.getState().clearCart()
    expect(useCartStore.getState().items).toEqual([])
  })

  it('totalItems returns 0 after clearCart', () => {
    useCartStore.getState().addItem(makeItem({ cantidad: 3 }), [])
    useCartStore.getState().clearCart()
    expect(useCartStore.getState().totalItems()).toBe(0)
  })
})

// ── RN-CR02: cart survives authStore.logout() ─────────────────────────────────

describe('RN-CR02: cart survives authStore.logout()', () => {
  it('cart items are unchanged after authStore.logout()', () => {
    useCartStore.getState().addItem(makeItem({ cantidad: 2 }), [])
    const itemsBefore = useCartStore.getState().items

    // authStore.logout() only clears auth state — it must never call clearCart()
    useAuthStore.getState().logout()

    const itemsAfter = useCartStore.getState().items
    expect(itemsAfter).toEqual(itemsBefore)
    expect(itemsAfter).toHaveLength(1)
  })
})

// ── Selectors ─────────────────────────────────────────────────────────────────

describe('selectors', () => {
  it('totalItems returns sum of all cantidad', () => {
    useCartStore.getState().addItem(makeItem({ cantidad: 2 }), [])
    useCartStore
      .getState()
      .addItem(makeItem({ producto_id: 'prod-2', cantidad: 3 }), [])
    expect(useCartStore.getState().totalItems()).toBe(5)
  })

  it('subtotal returns sum of precio * cantidad for all items', () => {
    useCartStore.getState().addItem(makeItem({ precio: 10, cantidad: 2 }), [])
    useCartStore
      .getState()
      .addItem(makeItem({ producto_id: 'prod-2', precio: 5, cantidad: 3 }), [])
    // 10*2 + 5*3 = 35
    expect(useCartStore.getState().subtotal()).toBe(35)
  })

  it('subtotal returns 0 when cart is empty', () => {
    expect(useCartStore.getState().subtotal()).toBe(0)
  })

  it('costoEnvio always returns 0', () => {
    useCartStore.getState().addItem(makeItem({ precio: 100, cantidad: 5 }), [])
    expect(useCartStore.getState().costoEnvio()).toBe(0)
  })

  it('total equals subtotal + costoEnvio', () => {
    useCartStore.getState().addItem(makeItem({ precio: 10, cantidad: 3 }), [])
    const subtotal = useCartStore.getState().subtotal()
    const costoEnvio = useCartStore.getState().costoEnvio()
    expect(useCartStore.getState().total()).toBe(subtotal + costoEnvio)
    expect(useCartStore.getState().total()).toBe(30)
  })
})
