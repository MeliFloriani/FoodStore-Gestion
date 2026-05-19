/**
 * Unit tests for CatalogFilters widget sub-components.
 *
 * Tests are scoped to individual sub-components rather than the composite
 * CatalogFilters index to avoid needing full routing + query context setup.
 */

import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { SearchInput } from '../CatalogFilters/SearchInput'
import { AllergenosExclusion } from '../CatalogFilters/AllergenosExclusion'

// ── SearchInput ───────────────────────────────────────────────────────────────

describe('SearchInput', () => {
  it('renders input with correct aria-label', () => {
    render(<SearchInput value="" onChange={() => {}} />)
    const input = screen.getByRole('searchbox', { name: 'Buscar productos por nombre' })
    expect(input).toBeInTheDocument()
  })

  it('displays the current value', () => {
    render(<SearchInput value="pizza" onChange={() => {}} />)
    expect(screen.getByRole('searchbox')).toHaveValue('pizza')
  })

  it('calls onChange when user types', () => {
    const onChange = vi.fn()
    render(<SearchInput value="" onChange={onChange} />)
    const input = screen.getByRole('searchbox')
    fireEvent.change(input, { target: { value: 'burger' } })
    expect(onChange).toHaveBeenCalledWith('burger')
  })
})

// ── AllergenosExclusion ───────────────────────────────────────────────────────

// Mock useCatalogAlergenos
vi.mock('@/entities/products', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/entities/products')>()
  return {
    ...actual,
    useCatalogAlergenos: vi.fn(() => ({
      data: {
        items: [
          { ingrediente_id: 'uuid-1', nombre: 'Gluten', es_alergeno: true },
          { ingrediente_id: 'uuid-2', nombre: 'Lactosa', es_alergeno: true },
        ],
        total: 2,
      },
      isPending: false,
    })),
  }
})

describe('AllergenosExclusion', () => {
  it('renders allergen toggle buttons', () => {
    render(<AllergenosExclusion value={null} onChange={() => {}} />)
    expect(screen.getByRole('button', { name: 'Gluten' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Lactosa' })).toBeInTheDocument()
  })

  it('renders group with aria-labelledby pointing to heading', () => {
    render(<AllergenosExclusion value={null} onChange={() => {}} />)
    const group = screen.getByRole('group')
    const labelId = group.getAttribute('aria-labelledby')
    expect(labelId).toBeTruthy()
    // The label element with that id should contain "Excluir alérgenos"
    const labelEl = document.getElementById(labelId!)
    expect(labelEl).toHaveTextContent('Excluir alérgenos')
  })

  it('sets aria-pressed=false on unselected allergen', () => {
    render(<AllergenosExclusion value={null} onChange={() => {}} />)
    const btn = screen.getByRole('button', { name: 'Gluten' })
    expect(btn).toHaveAttribute('aria-pressed', 'false')
  })

  it('sets aria-pressed=true on selected allergen', () => {
    render(<AllergenosExclusion value="uuid-1" onChange={() => {}} />)
    const btn = screen.getByRole('button', { name: 'Gluten' })
    expect(btn).toHaveAttribute('aria-pressed', 'true')
  })

  it('calls onChange with comma-string when allergen toggled', () => {
    const onChange = vi.fn()
    render(<AllergenosExclusion value={null} onChange={onChange} />)
    fireEvent.click(screen.getByRole('button', { name: 'Gluten' }))
    expect(onChange).toHaveBeenCalledWith('uuid-1')
  })

  it('appends to comma-string when second allergen toggled', () => {
    const onChange = vi.fn()
    render(<AllergenosExclusion value="uuid-1" onChange={onChange} />)
    fireEvent.click(screen.getByRole('button', { name: 'Lactosa' }))
    expect(onChange).toHaveBeenCalledWith('uuid-1,uuid-2')
  })

  it('removes allergen from comma-string when toggled off', () => {
    const onChange = vi.fn()
    render(<AllergenosExclusion value="uuid-1,uuid-2" onChange={onChange} />)
    fireEvent.click(screen.getByRole('button', { name: 'Gluten' }))
    expect(onChange).toHaveBeenCalledWith('uuid-2')
  })

  it('calls onChange with null when last allergen is deselected', () => {
    const onChange = vi.fn()
    render(<AllergenosExclusion value="uuid-1" onChange={onChange} />)
    fireEvent.click(screen.getByRole('button', { name: 'Gluten' }))
    expect(onChange).toHaveBeenCalledWith(null)
  })
})
