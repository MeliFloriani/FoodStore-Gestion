/**
 * Tests for navigation items related to admin-metrics (Change 23).
 *
 * Verifies the path correction from /admin/metrics (English placeholder)
 * to /admin/metricas (Spanish route) per spec frontend-navigation and
 * frontend-admin-menu-exposure.
 */

import { describe, it, expect } from 'vitest'
import { NAVIGATION_ITEMS } from '@/shared/lib/navigation/items'
import { filterNavItems } from '@/shared/lib/navigation/helpers'

describe('Navigation — admin-metrics path correction (Change 23)', () => {
  it('admin-metrics entry has path /admin/metricas (not /admin/metrics)', () => {
    const metricas = NAVIGATION_ITEMS.find((item) => item.key === 'admin-metrics')
    expect(metricas).toBeDefined()
    expect(metricas?.path).toBe('/admin/metricas')
    expect(metricas?.path).not.toBe('/admin/metrics')
  })

  it('admin-metrics entry has allowedRoles: ["ADMIN"]', () => {
    const metricas = NAVIGATION_ITEMS.find((item) => item.key === 'admin-metrics')
    expect(metricas?.allowedRoles).toContain('ADMIN')
    expect(metricas?.allowedRoles).not.toContain('CLIENT')
    expect(metricas?.allowedRoles).not.toContain('STOCK')
    expect(metricas?.allowedRoles).not.toContain('PEDIDOS')
  })

  it('filterNavItems with ADMIN role includes /admin/metricas', () => {
    const filtered = filterNavItems(NAVIGATION_ITEMS, ['ADMIN'])
    const paths = filtered.map((item) => item.path)
    expect(paths).toContain('/admin/metricas')
  })

  it('filterNavItems with ADMIN role does not include /admin/metrics (old path)', () => {
    const filtered = filterNavItems(NAVIGATION_ITEMS, ['ADMIN'])
    const paths = filtered.map((item) => item.path)
    expect(paths).not.toContain('/admin/metrics')
  })

  it('filterNavItems with CLIENT role excludes /admin/metricas', () => {
    const filtered = filterNavItems(NAVIGATION_ITEMS, ['CLIENT'])
    const paths = filtered.map((item) => item.path)
    expect(paths).not.toContain('/admin/metricas')
  })

  it('filterNavItems with STOCK role excludes /admin/metricas', () => {
    const filtered = filterNavItems(NAVIGATION_ITEMS, ['STOCK'])
    const paths = filtered.map((item) => item.path)
    expect(paths).not.toContain('/admin/metricas')
  })

  it('filterNavItems with ADMIN role returns 5 items (post pre-Change-24 surgical fix)', () => {
    // Stock items removed (placeholder); cart/orders/addresses are now CLIENT-only.
    // ADMIN sees: /catalog, /profile, /pedidos-panel, /admin/users, /admin/metricas.
    const filtered = filterNavItems(NAVIGATION_ITEMS, ['ADMIN'])
    expect(filtered).toHaveLength(5)
  })

  it('filterNavItems with ADMIN role includes /admin/users (unchanged)', () => {
    const filtered = filterNavItems(NAVIGATION_ITEMS, ['ADMIN'])
    const paths = filtered.map((item) => item.path)
    expect(paths).toContain('/admin/users')
  })
})
