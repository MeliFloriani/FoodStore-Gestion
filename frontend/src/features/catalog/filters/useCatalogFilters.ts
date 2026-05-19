/**
 * useCatalogFilters — single source of truth for public catalog filter state.
 *
 * Reads/writes filter state to URL search params (React Router v6).
 * Filters survive page refresh and are shareable via URL.
 *
 * Responsibilities:
 *   - filters: CatalogFilters — derived from URL params (q is debounced 300ms)
 *   - rawQ: string — immediate search input value (for controlled input)
 *   - setRawQ: update the immediate search input value
 *   - setFilter(key, value) — write a single filter to URL, reset page to 1
 *   - resetFilters() — clear all filter params from URL
 *
 * Change 12: catalog-public-browsing
 */

import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useDebounce } from '@/shared/hooks/useDebounce'
import type { CatalogFilters } from '@/entities/products'

export function useCatalogFilters() {
  const [searchParams, setSearchParams] = useSearchParams()

  // Raw (immediate) q for binding to the search input.
  // Initialized from URL so filters survive page refresh.
  const [rawQ, setRawQ] = useState<string>(() => searchParams.get('q') ?? '')

  // Debounced q — only applied to filters after 300ms of inactivity
  const debouncedQ = useDebounce(rawQ, 300)

  // Build CatalogFilters from URL params, using the debounced q value
  const filters: CatalogFilters = {
    page: searchParams.has('page') ? Number(searchParams.get('page')) : undefined,
    size: searchParams.has('size') ? Number(searchParams.get('size')) : undefined,
    q: debouncedQ || null,
    categoria_id: searchParams.get('categoria_id') || null,
    excluir_alergenos: searchParams.get('excluir_alergenos') || null,
    ordenar: searchParams.get('ordenar') || null,
  }

  /**
   * Set a single filter value. Resets page to 1 atomically.
   * Pass null/undefined/''/0 to clear the filter.
   */
  function setFilter(key: keyof CatalogFilters, value: unknown) {
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev)

      // Reset page to 1 whenever a filter changes
      next.set('page', '1')

      if (key === 'q') {
        const strVal = String(value ?? '')
        setRawQ(strVal)
        if (strVal) {
          next.set('q', strVal)
        } else {
          next.delete('q')
        }
        return next
      }

      if (value == null || value === '' || value === false) {
        next.delete(key)
      } else {
        next.set(key, String(value))
      }

      return next
    })
  }

  /** Clear all filter params from the URL. */
  function resetFilters() {
    setRawQ('')
    setSearchParams({})
  }

  return {
    rawQ,
    setRawQ,
    filters,
    setFilter,
    resetFilters,
  }
}
