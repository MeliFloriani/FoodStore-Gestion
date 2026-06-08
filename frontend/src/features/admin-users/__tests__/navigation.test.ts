/**
 * Tests for navigation items related to admin-users (Change 21).
 *
 * Task 7.2 verification:
 *   - filterNavItems(NAVIGATION_ITEMS, ['ADMIN']) includes /admin/users.
 *   - filterNavItems(NAVIGATION_ITEMS, ['CLIENT']) excludes /admin/users.
 */

import { describe, it, expect } from 'vitest'
import { NAVIGATION_ITEMS } from '@/shared/lib/navigation/items'
import { filterNavItems } from '@/shared/lib/navigation/helpers'

describe('Navigation — admin-users entry (Task 7.2)', () => {
  it('NAVIGATION_ITEMS includes admin-users entry', () => {
    const adminUsersEntry = NAVIGATION_ITEMS.find((item) => item.key === 'admin-users')
    expect(adminUsersEntry).toBeDefined()
    expect(adminUsersEntry?.path).toBe('/admin/users')
    expect(adminUsersEntry?.allowedRoles).toContain('ADMIN')
  })

  it('filterNavItems with ADMIN role includes /admin/users', () => {
    const filtered = filterNavItems(NAVIGATION_ITEMS, ['ADMIN'])
    const paths = filtered.map((item) => item.path)
    expect(paths).toContain('/admin/users')
  })

  it('filterNavItems with CLIENT role excludes /admin/users', () => {
    const filtered = filterNavItems(NAVIGATION_ITEMS, ['CLIENT'])
    const paths = filtered.map((item) => item.path)
    expect(paths).not.toContain('/admin/users')
  })

  it('filterNavItems with STOCK role excludes /admin/users', () => {
    const filtered = filterNavItems(NAVIGATION_ITEMS, ['STOCK'])
    const paths = filtered.map((item) => item.path)
    expect(paths).not.toContain('/admin/users')
  })
})
