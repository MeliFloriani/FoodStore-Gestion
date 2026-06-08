/**
 * Unit tests for DateRangeFilter widget — Change 23: admin-metrics-dashboard.
 *
 * Covers:
 *   - Renders two date inputs.
 *   - Calls onChange when desde changes.
 *   - Calls onChange when hasta changes.
 *   - Passes current values to inputs as controlled component.
 */

import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { DateRangeFilter } from '../widgets/DateRangeFilter'

describe('DateRangeFilter', () => {
  it('renders two date inputs', () => {
    render(
      <DateRangeFilter
        desde="2026-01-01"
        hasta="2026-01-31"
        onChange={() => {}}
      />,
    )
    const inputs = screen.getAllByDisplayValue(/2026/)
    expect(inputs.length).toBe(2)
  })

  it('calls onChange when desde changes', () => {
    const onChange = vi.fn()
    render(
      <DateRangeFilter desde="2026-01-01" hasta="2026-01-31" onChange={onChange} />,
    )
    const desdeInput = screen.getByLabelText(/Fecha inicio/i)
    fireEvent.change(desdeInput, { target: { value: '2026-02-01' } })
    expect(onChange).toHaveBeenCalledWith('2026-02-01', '2026-01-31')
  })

  it('calls onChange when hasta changes', () => {
    const onChange = vi.fn()
    render(
      <DateRangeFilter desde="2026-01-01" hasta="2026-01-31" onChange={onChange} />,
    )
    const hastaInput = screen.getByLabelText(/Fecha fin/i)
    fireEvent.change(hastaInput, { target: { value: '2026-02-28' } })
    expect(onChange).toHaveBeenCalledWith('2026-01-01', '2026-02-28')
  })

  it('reflects current values as controlled inputs', () => {
    render(
      <DateRangeFilter desde="2026-03-01" hasta="2026-03-31" onChange={() => {}} />,
    )
    const desdeInput = screen.getByLabelText(/Fecha inicio/i) as HTMLInputElement
    const hastaInput = screen.getByLabelText(/Fecha fin/i) as HTMLInputElement
    expect(desdeInput.value).toBe('2026-03-01')
    expect(hastaInput.value).toBe('2026-03-31')
  })

  it('renders labels for accessibility', () => {
    render(
      <DateRangeFilter desde="2026-01-01" hasta="2026-01-31" onChange={() => {}} />,
    )
    expect(screen.getByText('Desde')).toBeDefined()
    expect(screen.getByText('Hasta')).toBeDefined()
  })
})
