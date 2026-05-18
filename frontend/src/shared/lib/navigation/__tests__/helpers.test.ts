import { describe, it, expect } from 'vitest'
import { filterNavItems, resolveDefaultRoute } from '../helpers'
import { NAVIGATION_ITEMS } from '../items'

describe('filterNavItems', () => {
  it('(a) empty roles returns empty result', () => {
    const result = filterNavItems(NAVIGATION_ITEMS, [])
    expect(result).toHaveLength(0)
  })

  it('(b) CLIENT role returns only CLIENT items', () => {
    const result = filterNavItems(NAVIGATION_ITEMS, ['CLIENT'])
    const paths = result.map(item => item.path)
    // Should contain CLIENT items
    expect(paths).toContain('/catalog')
    expect(paths).toContain('/cart')
    expect(paths).toContain('/orders')
    expect(paths).toContain('/profile')
    expect(paths).toContain('/addresses')
    // Should NOT contain STOCK items
    expect(paths).not.toContain('/stock/products')
    expect(paths).not.toContain('/stock/categories')
    // Should NOT contain PEDIDOS items
    expect(paths).not.toContain('/pedidos-panel')
    // Should NOT contain ADMIN-only items
    expect(paths).not.toContain('/admin/users')
    expect(paths).not.toContain('/admin/metrics')
  })

  it('(c) ADMIN role returns all items', () => {
    const result = filterNavItems(NAVIGATION_ITEMS, ['ADMIN'])
    const paths = result.map(item => item.path)
    // CLIENT items
    expect(paths).toContain('/catalog')
    expect(paths).toContain('/cart')
    // STOCK items
    expect(paths).toContain('/stock/products')
    expect(paths).toContain('/stock/categories')
    // PEDIDOS items
    expect(paths).toContain('/pedidos-panel')
    // ADMIN-only items
    expect(paths).toContain('/admin/users')
    expect(paths).toContain('/admin/metrics')
  })

  it('(d) ADMIN+CLIENT multi-role: union with no duplicate paths', () => {
    const result = filterNavItems(NAVIGATION_ITEMS, ['ADMIN', 'CLIENT'])
    const paths = result.map(item => item.path)
    // No duplicates
    const uniquePaths = new Set(paths)
    expect(uniquePaths.size).toBe(paths.length)
    // Has both CLIENT items and ADMIN-only items
    expect(paths).toContain('/catalog')
    expect(paths).toContain('/admin/users')
  })

  it('(e) unknown role returns no items', () => {
    const result = filterNavItems(NAVIGATION_ITEMS, ['SUPERVISOR'])
    expect(result).toHaveLength(0)
  })

  it('STOCK role returns only STOCK items', () => {
    const result = filterNavItems(NAVIGATION_ITEMS, ['STOCK'])
    const paths = result.map(item => item.path)
    expect(paths).toContain('/stock/products')
    expect(paths).toContain('/stock/categories')
    expect(paths).toContain('/stock/ingredients')
    expect(paths).toContain('/stock/inventory')
    // Should NOT contain CLIENT items
    expect(paths).not.toContain('/cart')
    expect(paths).not.toContain('/admin/users')
  })

  it('PEDIDOS role returns only PEDIDOS items', () => {
    const result = filterNavItems(NAVIGATION_ITEMS, ['PEDIDOS'])
    const paths = result.map(item => item.path)
    expect(paths).toContain('/pedidos-panel')
    expect(paths).not.toContain('/cart')
    expect(paths).not.toContain('/admin/users')
  })
})

describe('resolveDefaultRoute', () => {
  it('ADMIN role returns /admin', () => {
    expect(resolveDefaultRoute(['ADMIN'])).toBe('/admin')
  })

  it('PEDIDOS role returns /pedidos-panel', () => {
    expect(resolveDefaultRoute(['PEDIDOS'])).toBe('/pedidos-panel')
  })

  it('STOCK role returns /stock/products', () => {
    expect(resolveDefaultRoute(['STOCK'])).toBe('/stock/products')
  })

  it('CLIENT role returns /catalog', () => {
    expect(resolveDefaultRoute(['CLIENT'])).toBe('/catalog')
  })

  it('empty roles returns /catalog (fallback)', () => {
    expect(resolveDefaultRoute([])).toBe('/catalog')
  })

  it('unknown role returns /catalog (fallback)', () => {
    expect(resolveDefaultRoute(['SUPERVISOR'])).toBe('/catalog')
  })

  it('multi-role ADMIN+CLIENT returns /admin (ADMIN has highest priority)', () => {
    expect(resolveDefaultRoute(['ADMIN', 'CLIENT'])).toBe('/admin')
  })

  it('multi-role CLIENT+STOCK returns /stock/products (STOCK > CLIENT in priority)', () => {
    // STOCK has higher priority than CLIENT per resolveDefaultRoute
    expect(resolveDefaultRoute(['CLIENT', 'STOCK'])).toBe('/stock/products')
  })
})
