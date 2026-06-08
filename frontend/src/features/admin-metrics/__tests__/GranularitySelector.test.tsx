/**
 * Unit tests for GranularitySelector widget — Change 23: admin-metrics-dashboard.
 *
 * Covers:
 *   - Renders a select with three options (Día, Semana, Mes).
 *   - Calls onChange with 'dia' when Día is selected.
 *   - Calls onChange with 'semana' when Semana is selected.
 *   - Calls onChange with 'mes' when Mes is selected.
 *   - Current value is reflected in select.
 */

import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { GranularitySelector } from '../widgets/GranularitySelector'

describe('GranularitySelector', () => {
  it('renders three options', () => {
    render(<GranularitySelector value="dia" onChange={() => {}} />)
    expect(screen.getByText('Día')).toBeDefined()
    expect(screen.getByText('Semana')).toBeDefined()
    expect(screen.getByText('Mes')).toBeDefined()
  })

  it('calls onChange with "dia" when Día is selected', () => {
    const onChange = vi.fn()
    render(<GranularitySelector value="mes" onChange={onChange} />)
    const select = screen.getByLabelText(/Granularidad/i)
    fireEvent.change(select, { target: { value: 'dia' } })
    expect(onChange).toHaveBeenCalledWith('dia')
  })

  it('calls onChange with "semana" when Semana is selected', () => {
    const onChange = vi.fn()
    render(<GranularitySelector value="dia" onChange={onChange} />)
    const select = screen.getByLabelText(/Granularidad/i)
    fireEvent.change(select, { target: { value: 'semana' } })
    expect(onChange).toHaveBeenCalledWith('semana')
  })

  it('calls onChange with "mes" when Mes is selected', () => {
    const onChange = vi.fn()
    render(<GranularitySelector value="dia" onChange={onChange} />)
    const select = screen.getByLabelText(/Granularidad/i)
    fireEvent.change(select, { target: { value: 'mes' } })
    expect(onChange).toHaveBeenCalledWith('mes')
  })

  it('reflects current value in select', () => {
    render(<GranularitySelector value="semana" onChange={() => {}} />)
    const select = screen.getByLabelText(/Granularidad/i) as HTMLSelectElement
    expect(select.value).toBe('semana')
  })
})
