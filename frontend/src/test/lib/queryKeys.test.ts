import { describe, it, expect } from 'vitest'
import { queryKeys } from '@/shared/lib/queryKeys'

describe('queryKeys', () => {
  it('auth.all returns tuple identity', () => {
    expect(queryKeys.auth.all()).toEqual(['auth'])
    // Two calls return same value (not same reference, but tuple equality)
    expect(queryKeys.auth.all()).toStrictEqual(['auth'])
  })

  it('auth.me returns auth/me tuple', () => {
    expect(queryKeys.auth.me()).toEqual(['auth', 'me'])
  })

  it('catalog.all returns catalog tuple', () => {
    expect(queryKeys.catalog.all()).toEqual(['catalog'])
  })

  it('catalog.products includes filters in key', () => {
    const filters = { category: 'pizza' }
    const key = queryKeys.catalog.products(filters)
    expect(key[0]).toBe('catalog')
    expect(key[1]).toBe('products')
    expect(key[2]).toEqual(filters)
  })

  it('catalog.product includes id in key', () => {
    expect(queryKeys.catalog.product(42)).toEqual(['catalog', 'product', 42])
  })

  it('cart.all returns cart tuple', () => {
    expect(queryKeys.cart.all()).toEqual(['cart'])
  })

  it('orders.all returns orders tuple', () => {
    expect(queryKeys.orders.all()).toEqual(['orders'])
  })

  it('orders.order includes id in key', () => {
    expect(queryKeys.orders.order(7)).toEqual(['orders', 'order', 7])
  })

  it('payment.all returns payment tuple', () => {
    expect(queryKeys.payment.all()).toEqual(['payment'])
  })

  it('payment.preference includes pedidoId in key', () => {
    expect(queryKeys.payment.preference(3)).toEqual(['payment', 'preference', 3])
  })

  it('different namespaces do not share prefixes', () => {
    expect(queryKeys.auth.all()[0]).not.toBe(queryKeys.catalog.all()[0])
    expect(queryKeys.orders.all()[0]).not.toBe(queryKeys.payment.all()[0])
  })
})
