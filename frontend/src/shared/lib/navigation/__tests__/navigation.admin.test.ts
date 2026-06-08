import { describe, it, expect } from 'vitest'
import { filterNavItems } from '../helpers'
import { NAVIGATION_ITEMS } from '../items'

/**
 * RBAC invariant tests for ADMIN navigation.
 *
 * Updated after the post pre-Change-24 fix correction:
 *
 *  - Stock CRUD items (/stock/ingredients, /stock/categories, /stock/products)
 *    are advertised again to STOCK and ADMIN because real CRUD pages now exist.
 *  - /stock/inventory remains UNADVERTISED — no real implementation exists.
 *  - cart, orders, addresses are still CLIENT-only flows; ADMIN must not see them.
 *
 * Current NAVIGATION_ITEMS surface:
 *   2 CLIENT+ADMIN shared        (/catalog, /profile)
 *   3 CLIENT-only                (/cart, /orders, /addresses)
 *   3 STOCK+ADMIN                (/stock/ingredients, /stock/categories, /stock/products)
 *   1 PEDIDOS+ADMIN              (/pedidos-panel)
 *   2 ADMIN-only                 (/admin/users, /admin/metricas)
 *
 * → ADMIN sees: catalog, profile, stock×3, pedidos-panel, admin-users, admin-metrics = 8
 * → STOCK sees: stock×3 = 3
 * → CLIENT sees: catalog, cart, orders, profile, addresses = 5
 */

describe('ADMIN navigation invariants (post Change-24 fix correction)', () => {
  it('ADMIN role sees exactly 8 navigation items', () => {
    const result = filterNavItems(NAVIGATION_ITEMS, ['ADMIN'])
    expect(result).toHaveLength(8)
  })

  it('ADMIN role does NOT see CLIENT-only purchase-flow items', () => {
    const result = filterNavItems(NAVIGATION_ITEMS, ['ADMIN'])
    const paths = result.map(item => item.path)
    expect(paths).not.toContain('/cart')
    expect(paths).not.toContain('/orders')
    expect(paths).not.toContain('/addresses')
  })

  it('ADMIN role sees the three restored stock CRUD items', () => {
    const result = filterNavItems(NAVIGATION_ITEMS, ['ADMIN'])
    const paths = result.map(item => item.path)
    expect(paths).toContain('/stock/ingredients')
    expect(paths).toContain('/stock/categories')
    expect(paths).toContain('/stock/products')
  })

  it('ADMIN role does NOT see /stock/inventory (no real implementation)', () => {
    const result = filterNavItems(NAVIGATION_ITEMS, ['ADMIN'])
    const paths = result.map(item => item.path)
    expect(paths).not.toContain('/stock/inventory')
  })

  it('ADMIN role sees pedidos panel', () => {
    const result = filterNavItems(NAVIGATION_ITEMS, ['ADMIN'])
    const paths = result.map(item => item.path)
    expect(paths).toContain('/pedidos-panel')
  })

  it('ADMIN role sees admin-only paths', () => {
    const result = filterNavItems(NAVIGATION_ITEMS, ['ADMIN'])
    const paths = result.map(item => item.path)
    expect(paths).toContain('/admin/users')
    expect(paths).toContain('/admin/metricas')
  })

  it('ADMIN role still sees catalog and profile (shared with CLIENT)', () => {
    const result = filterNavItems(NAVIGATION_ITEMS, ['ADMIN'])
    const paths = result.map(item => item.path)
    expect(paths).toContain('/catalog')
    expect(paths).toContain('/profile')
  })

  it('ADMIN nav has no duplicate paths', () => {
    const result = filterNavItems(NAVIGATION_ITEMS, ['ADMIN'])
    const paths = result.map(item => item.path)
    const uniquePaths = new Set(paths)
    expect(uniquePaths.size).toBe(paths.length)
  })

  it('Governance: only the three real stock items exist in NAVIGATION_ITEMS', () => {
    // The real Stock module ships with ingredients/categories/products only.
    // /stock/inventory must NOT appear until it has a real implementation.
    const stockPaths = NAVIGATION_ITEMS.filter(item =>
      item.path.startsWith('/stock/'),
    ).map(item => item.path)
    expect(stockPaths).toEqual([
      '/stock/ingredients',
      '/stock/categories',
      '/stock/products',
    ])
    expect(stockPaths).not.toContain('/stock/inventory')
  })

  it('Governance: stock items must include both STOCK and ADMIN', () => {
    const stockItems = NAVIGATION_ITEMS.filter(item =>
      item.path.startsWith('/stock/'),
    )
    for (const item of stockItems) {
      expect(item.allowedRoles).toContain('STOCK')
      expect(item.allowedRoles).toContain('ADMIN')
    }
  })

  it('Governance: /pedidos-panel still must include ADMIN', () => {
    const pedidosPanel = NAVIGATION_ITEMS.find(item => item.path === '/pedidos-panel')
    expect(pedidosPanel).toBeDefined()
    expect(pedidosPanel?.allowedRoles).toContain('ADMIN')
  })
})
