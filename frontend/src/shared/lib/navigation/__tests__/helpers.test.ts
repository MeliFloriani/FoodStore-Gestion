import { describe, it, expect } from 'vitest'
import { filterNavItems, resolveDefaultRoute } from '../helpers'
import { NAVIGATION_ITEMS } from '../items'

describe('filterNavItems', () => {
  it('(a) empty roles returns empty result', () => {
    const result = filterNavItems(NAVIGATION_ITEMS, [])
    expect(result).toHaveLength(0)
  })

  it('(b) CLIENT role returns CLIENT items', () => {
    const result = filterNavItems(NAVIGATION_ITEMS, ['CLIENT'])
    const paths = result.map(item => item.path)
    // Should contain CLIENT items (cart/orders/addresses are CLIENT-only)
    expect(paths).toContain('/catalog')
    expect(paths).toContain('/cart')
    expect(paths).toContain('/orders')
    expect(paths).toContain('/profile')
    expect(paths).toContain('/addresses')
    // CLIENT must NOT see stock admin items
    expect(paths).not.toContain('/stock/products')
    expect(paths).not.toContain('/stock/categories')
    expect(paths).not.toContain('/stock/ingredients')
    // Should NOT contain PEDIDOS items
    expect(paths).not.toContain('/pedidos-panel')
    // Should NOT contain ADMIN-only items
    expect(paths).not.toContain('/admin/users')
    expect(paths).not.toContain('/admin/metricas')
  })

  it('(c) ADMIN role: catalog/profile + management items + stock CRUD (no CLIENT purchase flow)', () => {
    const result = filterNavItems(NAVIGATION_ITEMS, ['ADMIN'])
    const paths = result.map(item => item.path)
    // Shared with CLIENT
    expect(paths).toContain('/catalog')
    expect(paths).toContain('/profile')
    // Management
    expect(paths).toContain('/pedidos-panel')
    expect(paths).toContain('/admin/users')
    expect(paths).toContain('/admin/metricas')
    // Stock CRUD restored — three real pages
    expect(paths).toContain('/stock/ingredients')
    expect(paths).toContain('/stock/categories')
    expect(paths).toContain('/stock/products')
    // ADMIN must NOT see CLIENT purchase flow
    expect(paths).not.toContain('/cart')
    expect(paths).not.toContain('/orders')
    expect(paths).not.toContain('/addresses')
    // /stock/inventory must NOT be advertised — no real implementation
    expect(paths).not.toContain('/stock/inventory')
  })

  it('(d) ADMIN+CLIENT multi-role: union with no duplicate paths', () => {
    const result = filterNavItems(NAVIGATION_ITEMS, ['ADMIN', 'CLIENT'])
    const paths = result.map(item => item.path)
    // No duplicates
    const uniquePaths = new Set(paths)
    expect(uniquePaths.size).toBe(paths.length)
    // Has both CLIENT items and ADMIN-only items
    expect(paths).toContain('/catalog')
    expect(paths).toContain('/cart') // CLIENT role grants access
    expect(paths).toContain('/admin/users')
  })

  it('(e) unknown role returns no items', () => {
    const result = filterNavItems(NAVIGATION_ITEMS, ['SUPERVISOR'])
    expect(result).toHaveLength(0)
  })

  it('STOCK role returns the three stock CRUD items (real pages exist now)', () => {
    const result = filterNavItems(NAVIGATION_ITEMS, ['STOCK'])
    const paths = result.map(item => item.path)
    expect(paths).toEqual([
      '/stock/ingredients',
      '/stock/categories',
      '/stock/products',
    ])
    // STOCK must NOT see CLIENT purchase flow or ADMIN/PEDIDOS surfaces
    expect(paths).not.toContain('/cart')
    expect(paths).not.toContain('/orders')
    expect(paths).not.toContain('/addresses')
    expect(paths).not.toContain('/admin/users')
    expect(paths).not.toContain('/pedidos-panel')
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

  it('STOCK role returns /stock/products (real Stock landing)', () => {
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

  it('multi-role CLIENT+STOCK returns /stock/products (STOCK priority over CLIENT)', () => {
    expect(resolveDefaultRoute(['CLIENT', 'STOCK'])).toBe('/stock/products')
  })
})
