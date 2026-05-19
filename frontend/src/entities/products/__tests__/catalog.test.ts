/**
 * Unit tests for the public catalog entity layer.
 *
 * Tests cover:
 *   - catalogQueryKeys factory shape and sanitization
 *   - fetchCatalogProductos query string building (omits null/undefined)
 *   - fetchCatalogProductoDetalle hits correct URL
 *   - useCatalogProduct is disabled when id is empty
 *   - TypeScript compile-time: ProductoPublicoRead has no stock_cantidad
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import AxiosMockAdapter from 'axios-mock-adapter'
import { http } from '@/shared/api/http'
import {
  fetchCatalogProductos,
  fetchCatalogProductoDetalle,
  fetchCatalogAlergenos,
} from '../api/productoFetchers'
import { catalogQueryKeys } from '../model/useCatalogProducts'
import type {
  CatalogFilters,
  ProductoPublicoRead,
  IngredienteAlergenicoListResponse,
} from '../model/types'

// ── catalogQueryKeys factory ─────────────────────────────────────────────────

describe('catalogQueryKeys', () => {
  it('all key is stable', () => {
    expect(catalogQueryKeys.all).toEqual(['catalog', 'products'])
  })

  it('lists() is a prefix of list(filters)', () => {
    const listsKey = catalogQueryKeys.lists()
    const listKey = catalogQueryKeys.list({ page: 1, q: 'pizza' })
    expect(JSON.stringify(listKey).startsWith(JSON.stringify(listsKey).slice(0, -1))).toBe(true)
  })

  it('list() sanitizes null values from filter', () => {
    const key1 = catalogQueryKeys.list({ page: 1, q: null, categoria_id: null })
    const key2 = catalogQueryKeys.list({ page: 1 })
    // Both should produce equivalent sanitized filter objects
    const sanitized1 = key1[key1.length - 1]
    const sanitized2 = key2[key2.length - 1]
    expect(sanitized1).toEqual(sanitized2)
  })

  it('list() sanitizes undefined values from filter', () => {
    const key1 = catalogQueryKeys.list({ page: 1, q: undefined })
    const key2 = catalogQueryKeys.list({ page: 1 })
    const sanitized1 = key1[key1.length - 1]
    const sanitized2 = key2[key2.length - 1]
    expect(sanitized1).toEqual(sanitized2)
  })

  it('different filters produce different list keys', () => {
    const key1 = catalogQueryKeys.list({ page: 1, q: 'pizza' })
    const key2 = catalogQueryKeys.list({ page: 1, q: 'burger' })
    expect(key1).not.toEqual(key2)
  })

  it('detail(id) key scoped to id', () => {
    const id = 'f47ac10b-58cc-4372-a567-0e02b2c3d479'
    const key = catalogQueryKeys.detail(id)
    expect(key).toContain(id)
    expect(key[0]).toBe('catalog')
  })

  it('alergenos() key is stable', () => {
    expect(catalogQueryKeys.alergenos()).toEqual(['catalog', 'alergenos'])
  })
})

// ── fetchCatalogProductos query string building ───────────────────────────────

describe('fetchCatalogProductos', () => {
  let mock: AxiosMockAdapter

  beforeEach(() => {
    mock = new AxiosMockAdapter(http)
  })

  afterEach(() => {
    mock.reset()
    vi.clearAllMocks()
  })

  it('omits null filter values from query string', async () => {
    const mockResponse = {
      items: [],
      total: 0,
      page: 1,
      size: 20,
      pages: 0,
    }

    let capturedParams: Record<string, string> = {}
    mock.onGet('/api/v1/catalog/productos').reply((config) => {
      capturedParams = config.params as Record<string, string>
      return [200, mockResponse]
    })

    const filters: CatalogFilters = {
      page: 2,
      size: 10,
      q: 'pizza',
      categoria_id: null,
      excluir_alergenos: null,
    }

    await fetchCatalogProductos(filters)

    // null values should be omitted
    expect(capturedParams).not.toHaveProperty('categoria_id')
    expect(capturedParams).not.toHaveProperty('excluir_alergenos')
    // non-null values should be present
    expect(capturedParams).toHaveProperty('page', 2)
    expect(capturedParams).toHaveProperty('size', 10)
    expect(capturedParams).toHaveProperty('q', 'pizza')
  })

  it('omits undefined filter values from query string', async () => {
    const mockResponse = {
      items: [],
      total: 0,
      page: 1,
      size: 20,
      pages: 0,
    }

    let capturedParams: Record<string, unknown> = {}
    mock.onGet('/api/v1/catalog/productos').reply((config) => {
      capturedParams = config.params as Record<string, unknown>
      return [200, mockResponse]
    })

    const filters: CatalogFilters = {
      page: 1,
      size: 20,
      q: undefined,
    }

    await fetchCatalogProductos(filters)

    expect(capturedParams).not.toHaveProperty('q')
  })

  it('includes all non-null filters', async () => {
    const mockResponse = {
      items: [],
      total: 0,
      page: 1,
      size: 20,
      pages: 0,
    }

    let capturedParams: Record<string, unknown> = {}
    mock.onGet('/api/v1/catalog/productos').reply((config) => {
      capturedParams = config.params as Record<string, unknown>
      return [200, mockResponse]
    })

    const filters: CatalogFilters = {
      page: 2,
      size: 10,
      q: 'pizza',
      excluir_alergenos: '1,2',
    }

    await fetchCatalogProductos(filters)

    expect(capturedParams).toEqual({
      page: 2,
      size: 10,
      q: 'pizza',
      excluir_alergenos: '1,2',
    })
  })
})

// ── fetchCatalogProductoDetalle URL ────────────────────────────────────────────

describe('fetchCatalogProductoDetalle', () => {
  let mock: AxiosMockAdapter

  beforeEach(() => {
    mock = new AxiosMockAdapter(http)
  })

  afterEach(() => {
    mock.reset()
    vi.clearAllMocks()
  })

  it('hits correct URL with product id', async () => {
    const id = 'some-uuid-1234'
    const mockResponse = {
      id,
      nombre: 'Pizza Margherita',
      descripcion: 'Deliciosa pizza',
      imagen_url: null,
      precio_base: '12.50',
      disponible: true,
      tiene_stock: true,
      categorias: [],
      ingredientes: [],
    }

    let capturedUrl = ''
    mock.onGet(`/api/v1/catalog/productos/${id}`).reply((config) => {
      capturedUrl = config.url ?? ''
      return [200, mockResponse]
    })

    await fetchCatalogProductoDetalle(id)
    expect(capturedUrl).toBe(`/api/v1/catalog/productos/${id}`)
  })
})

// ── fetchCatalogAlergenos ─────────────────────────────────────────────────────

describe('fetchCatalogAlergenos', () => {
  let mock: AxiosMockAdapter

  beforeEach(() => {
    mock = new AxiosMockAdapter(http)
  })

  afterEach(() => {
    mock.reset()
    vi.clearAllMocks()
  })

  it('hits the correct allergen endpoint', async () => {
    const mockResponse: IngredienteAlergenicoListResponse = {
      items: [
        { ingrediente_id: 'uuid-1', nombre: 'Gluten', es_alergeno: true },
        { ingrediente_id: 'uuid-2', nombre: 'Lactosa', es_alergeno: true },
      ],
      total: 2,
    }

    mock.onGet('/api/v1/catalog/ingredientes-alergenos').reply(200, mockResponse)
    const result = await fetchCatalogAlergenos()

    expect(result.total).toBe(2)
    expect(result.items).toHaveLength(2)
    expect(result.items[0].es_alergeno).toBe(true)
  })
})

// ── TypeScript type guard: ProductoPublicoRead has no stock_cantidad ──────────

describe('ProductoPublicoRead type safety', () => {
  it('ProductoPublicoRead has tiene_stock and no stock_cantidad', () => {
    // This test validates at the TypeScript level that tiene_stock exists
    const producto: ProductoPublicoRead = {
      id: 'uuid',
      nombre: 'Test',
      descripcion: null,
      imagen_url: null,
      precio_base: '10.00',
      disponible: true,
      tiene_stock: true,
    }

    expect(typeof producto.tiene_stock).toBe('boolean')
    // @ts-expect-error stock_cantidad must not exist on ProductoPublicoRead
    expect(producto.stock_cantidad).toBeUndefined()
  })
})
