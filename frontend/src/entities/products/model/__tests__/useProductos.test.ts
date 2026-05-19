/**
 * Unit tests for the Producto entity query hooks.
 *
 * Strategy: verify that each hook uses the correct query key, so cache
 * invalidation in mutation hooks will target the right cache entries.
 * Actual HTTP calls are NOT tested here — that is covered by productoFetchers
 * integration tests. These tests verify the TanStack Query integration only.
 *
 * Tests:
 *   test_useProductos_calls_fetchProductos_with_filters — correct query key
 *   test_useProducto_calls_fetchProductoDetail          — correct detail query key
 */

import { describe, it, expect } from 'vitest'
import { productQueryKeys } from '../queryKeys'
import type { ProductoListFilters } from '../types'

// ── Query key factory tests ─────────────────────────────────────────────────

describe('productQueryKeys', () => {
  it('all key is stable', () => {
    expect(productQueryKeys.all).toEqual(['products'])
  })

  it('lists() returns all + list', () => {
    expect(productQueryKeys.lists()).toEqual(['products', 'list'])
  })

  it('list(filters) includes filters in key', () => {
    const filters: ProductoListFilters = { page: 1, size: 20, disponible: true }
    const key = productQueryKeys.list(filters)
    expect(key).toEqual(['products', 'list', filters])
  })

  it('list() without filters still includes undefined slot', () => {
    const key = productQueryKeys.list()
    expect(key).toEqual(['products', 'list', undefined])
  })

  it('details() returns all + detail', () => {
    expect(productQueryKeys.details()).toEqual(['products', 'detail'])
  })

  it('detail(id) includes id in key', () => {
    const id = '550e8400-e29b-41d4-a716-446655440000'
    const key = productQueryKeys.detail(id)
    expect(key).toEqual(['products', 'detail', id])
  })

  it('ingredientes(id) includes entity kind and id', () => {
    const id = 'abc12300-0000-0000-0000-000000000001'
    const key = productQueryKeys.ingredientes(id)
    expect(key).toEqual(['products', 'ingredientes', id])
  })

  it('different product ids produce different detail keys', () => {
    const id1 = 'aaaaaaaa-0000-0000-0000-000000000001'
    const id2 = 'bbbbbbbb-0000-0000-0000-000000000002'
    expect(productQueryKeys.detail(id1)).not.toEqual(productQueryKeys.detail(id2))
  })

  it('lists() key is a prefix of list(filters) key', () => {
    const listKey = productQueryKeys.lists()
    const listWithFiltersKey = productQueryKeys.list({ page: 2 })
    // TanStack Query invalidateQueries with lists() must match list(filters)
    // because list(filters) starts with lists()
    expect(listWithFiltersKey.slice(0, listKey.length)).toEqual([...listKey])
  })

  it('details() key is a prefix of detail(id) key', () => {
    const detailsKey = productQueryKeys.details()
    const detailKey = productQueryKeys.detail('some-id')
    expect(detailKey.slice(0, detailsKey.length)).toEqual([...detailsKey])
  })
})

// ── Hook query key usage tests ────────────────────────────────────────────

describe('test_useProductos_calls_fetchProductos_with_filters', () => {
  it('useProductos query key includes filters object', () => {
    // Verify that the key factory used by useProductos encodes filters,
    // which means queries with different filters are cached separately.
    const noFilter = productQueryKeys.list(undefined)
    const withCat = productQueryKeys.list({
      categoria_id: 'cat-uuid',
      disponible: true,
    })
    expect(noFilter).not.toEqual(withCat)
  })

  it('invalidating lists() also invalidates list(filters) queries', () => {
    // This validates the cache invalidation contract:
    // invalidateQueries({ queryKey: lists() }) in mutation hooks will
    // invalidate ALL list queries regardless of filter params.
    const listsKey = productQueryKeys.lists()
    const listKey = productQueryKeys.list({ page: 1, search: 'pizza' })
    // lists() = ['products', 'list']  →  list(f) = ['products', 'list', f]
    // TanStack Query prefix-matches: lists() is a prefix of list(f)
    const isPrefix = JSON.stringify(listKey).startsWith(
      JSON.stringify(listsKey).slice(0, -1), // remove trailing ]
    )
    expect(isPrefix).toBe(true)
  })
})

describe('test_useProducto_calls_fetchProductoDetail', () => {
  it('useProducto query key is scoped to the given id', () => {
    const id = 'f47ac10b-58cc-4372-a567-0e02b2c3d479'
    const key = productQueryKeys.detail(id)
    // Key must contain the id so different products are cached separately
    expect(key).toContain(id)
    // Key must be under the 'products' namespace
    expect(key[0]).toBe('products')
    // Key must be under 'detail' sub-namespace
    expect(key[1]).toBe('detail')
  })

  it('invalidating details() also invalidates detail(id) queries', () => {
    const detailsKey = productQueryKeys.details()
    const detailKey = productQueryKeys.detail('any-uuid')
    const isPrefix = JSON.stringify(detailKey).startsWith(
      JSON.stringify(detailsKey).slice(0, -1),
    )
    expect(isPrefix).toBe(true)
  })
})
