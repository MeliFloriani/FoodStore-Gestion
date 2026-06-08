import { describe, it, expect } from 'vitest'
import {
  normalizePersonalizacion,
  buildItemKey,
  areItemsEquivalent,
} from './cartUtils'
import type { CartItem } from '@/entities/cart/types'

// ── normalizePersonalizacion ────────────────────────────────────────────────

describe('normalizePersonalizacion', () => {
  it('deduplicates and sorts lexicographically', () => {
    expect(normalizePersonalizacion(['ing-3', 'ing-1', 'ing-3'])).toEqual([
      'ing-1',
      'ing-3',
    ])
  })

  it('returns empty array unchanged', () => {
    expect(normalizePersonalizacion([])).toEqual([])
  })

  it('handles single element', () => {
    expect(normalizePersonalizacion(['ing-5'])).toEqual(['ing-5'])
  })

  it('sorts lexicographically (not numerically)', () => {
    // Lexicographic: "ing-10" < "ing-2" alphabetically
    expect(normalizePersonalizacion(['ing-2', 'ing-10'])).toEqual([
      'ing-10',
      'ing-2',
    ])
  })

  it('deduplicates correctly with more than 2 duplicates', () => {
    expect(
      normalizePersonalizacion(['ing-a', 'ing-b', 'ing-a', 'ing-c', 'ing-b']),
    ).toEqual(['ing-a', 'ing-b', 'ing-c'])
  })
})

// ── buildItemKey ────────────────────────────────────────────────────────────

describe('buildItemKey', () => {
  it('returns product::sorted-personalizacion format', () => {
    expect(
      buildItemKey({
        producto_id: 'prod-uuid',
        personalizacion: ['ing-3', 'ing-1'],
      }),
    ).toBe('prod-uuid::ing-1,ing-3')
  })

  it('returns product:: when personalizacion is empty', () => {
    expect(
      buildItemKey({ producto_id: 'prod-uuid', personalizacion: [] }),
    ).toBe('prod-uuid::')
  })

  it('is order-independent — same key for different insertion orders', () => {
    const key1 = buildItemKey({
      producto_id: 'prod-5',
      personalizacion: ['ing-1', 'ing-3'],
    })
    const key2 = buildItemKey({
      producto_id: 'prod-5',
      personalizacion: ['ing-3', 'ing-1'],
    })
    expect(key1).toBe(key2)
  })

  it('different personalizacion produces different key', () => {
    const key1 = buildItemKey({
      producto_id: 'prod-5',
      personalizacion: [],
    })
    const key2 = buildItemKey({
      producto_id: 'prod-5',
      personalizacion: ['ing-1'],
    })
    expect(key1).not.toBe(key2)
  })

  it('different producto_id produces different key', () => {
    const key1 = buildItemKey({
      producto_id: 'prod-1',
      personalizacion: ['ing-1'],
    })
    const key2 = buildItemKey({
      producto_id: 'prod-2',
      personalizacion: ['ing-1'],
    })
    expect(key1).not.toBe(key2)
  })

  it('key is stable — recomputable from persisted CartItem fields', () => {
    const item: CartItem = {
      producto_id: 'prod-uuid',
      nombre: 'Hamburguesa',
      precio: 10,
      cantidad: 1,
      imagen_url: 'img.jpg',
      personalizacion: ['ing-1', 'ing-3'],
    }
    const keyBefore = buildItemKey(item)
    // Simulate rehydration by using the same fields
    const keyAfter = buildItemKey({
      producto_id: item.producto_id,
      personalizacion: item.personalizacion,
    })
    expect(keyBefore).toBe(keyAfter)
  })
})

// ── areItemsEquivalent ──────────────────────────────────────────────────────

describe('areItemsEquivalent', () => {
  const base: CartItem = {
    producto_id: 'prod-1',
    nombre: 'Burger',
    precio: 10,
    cantidad: 1,
    imagen_url: 'img.jpg',
    personalizacion: ['ing-1', 'ing-3'],
  }

  it('returns true for same product and same personalizacion (same order)', () => {
    const b: CartItem = { ...base }
    expect(areItemsEquivalent(base, b)).toBe(true)
  })

  it('returns true for same product and same personalizacion in different order', () => {
    const b: CartItem = { ...base, personalizacion: ['ing-3', 'ing-1'] }
    expect(areItemsEquivalent(base, b)).toBe(true)
  })

  it('returns false for different producto_id', () => {
    const b: CartItem = { ...base, producto_id: 'prod-2' }
    expect(areItemsEquivalent(base, b)).toBe(false)
  })

  it('returns false for same product but different personalizacion', () => {
    const b: CartItem = { ...base, personalizacion: ['ing-2'] }
    expect(areItemsEquivalent(base, b)).toBe(false)
  })

  it('returns false when one has empty personalizacion and other does not', () => {
    const b: CartItem = { ...base, personalizacion: [] }
    expect(areItemsEquivalent(base, b)).toBe(false)
  })

  it('returns true for both empty personalizacion', () => {
    const a: CartItem = { ...base, personalizacion: [] }
    const b: CartItem = { ...base, personalizacion: [] }
    expect(areItemsEquivalent(a, b)).toBe(true)
  })
})
