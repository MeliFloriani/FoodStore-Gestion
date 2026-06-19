import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { useCatalogFilters } from '../useCatalogFilters'

function wrapper(initialEntries: string[] = ['/catalog']) {
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return <MemoryRouter initialEntries={initialEntries}>{children}</MemoryRouter>
  }
}

describe('useCatalogFilters', () => {
  it('reads initial filters from URL params', () => {
    const { result } = renderHook(() => useCatalogFilters(), {
      wrapper: wrapper(['/catalog?q=pizza&categoria_id=cat-1']),
    })

    expect(result.current.filters.q).toBe('pizza')
    expect(result.current.filters.categoria_id).toBe('cat-1')
  })

  it('initializes rawQ from URL q param', () => {
    const { result } = renderHook(() => useCatalogFilters(), {
      wrapper: wrapper(['/catalog?q=burger']),
    })

    expect(result.current.rawQ).toBe('burger')
  })

  it('returns undefined for missing filters', () => {
    const { result } = renderHook(() => useCatalogFilters(), {
      wrapper: wrapper(),
    })

    expect(result.current.filters.page).toBeUndefined()
    expect(result.current.filters.q).toBeNull()
    expect(result.current.filters.categoria_id).toBeNull()
  })

  it('setFilter updates URL and sets page to 1', () => {
    const { result } = renderHook(() => useCatalogFilters(), {
      wrapper: wrapper(['/catalog?page=3']),
    })

    act(() => {
      result.current.setFilter('categoria_id', 'cat-2')
    })

    expect(result.current.filters.categoria_id).toBe('cat-2')
    expect(result.current.filters.page).toBe(1)
  })

  it('setFilter with q value updates rawQ and URL', () => {
    const { result } = renderHook(() => useCatalogFilters(), {
      wrapper: wrapper(),
    })

    act(() => {
      result.current.setFilter('q', 'pizza')
    })

    expect(result.current.rawQ).toBe('pizza')
  })

  it('setFilter clears q — rawQ is updated immediately (debounce delays filter.q)', () => {
    const { result } = renderHook(() => useCatalogFilters(), {
      wrapper: wrapper(['/catalog?q=pizza']),
    })

    act(() => {
      result.current.setFilter('q', '')
    })

    // rawQ is updated immediately
    expect(result.current.rawQ).toBe('')
    // filters.q is debounced, may still show old value
    expect(result.current.filters.q).toBe('pizza')
  })

  it('setFilter removes param when value is null or empty', () => {
    const { result } = renderHook(() => useCatalogFilters(), {
      wrapper: wrapper(['/catalog?categoria_id=cat-1']),
    })

    act(() => {
      result.current.setFilter('categoria_id', '')
    })

    expect(result.current.filters.categoria_id).toBeNull()
  })

  it('resetFilters clears rawQ immediately', () => {
    const { result } = renderHook(() => useCatalogFilters(), {
      wrapper: wrapper(['/catalog?q=pizza&categoria_id=cat-1&page=2']),
    })

    act(() => {
      result.current.resetFilters()
    })

    expect(result.current.rawQ).toBe('')
    // URL params cleared but debounce delay affects filters.q
    expect(result.current.filters.categoria_id).toBeNull()
  })

  it('setRawQ updates rawQ immediately', () => {
    const { result } = renderHook(() => useCatalogFilters(), {
      wrapper: wrapper(),
    })

    act(() => {
      result.current.setRawQ('test')
    })

    expect(result.current.rawQ).toBe('test')
  })
})
