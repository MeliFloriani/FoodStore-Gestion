import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { UserFilters } from '../ui/UserFilters'

describe('UserFilters', () => {
  it('renders both selects with default Todos option', () => {
    render(
      <UserFilters
        rol={undefined}
        activo={undefined}
        onRolChange={vi.fn()}
        onActivoChange={vi.fn()}
      />,
    )
    expect(screen.getByLabelText(/rol/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/estado/i)).toBeInTheDocument()
    const selects = screen.getAllByRole('combobox')
    expect(selects).toHaveLength(2)
  })

  it('rol select calls onRolChange with selected value', () => {
    const onRolChange = vi.fn()
    render(
      <UserFilters
        rol={undefined}
        activo={undefined}
        onRolChange={onRolChange}
        onActivoChange={vi.fn()}
      />,
    )
    const rolSelect = screen.getByLabelText(/rol/i)
    fireEvent.change(rolSelect, { target: { value: 'ADMIN' } })
    expect(onRolChange).toHaveBeenCalledWith('ADMIN')
  })

  it('rol select calls onRolChange with undefined when empty value', () => {
    const onRolChange = vi.fn()
    render(
      <UserFilters
        rol={'ADMIN'}
        activo={undefined}
        onRolChange={onRolChange}
        onActivoChange={vi.fn()}
      />,
    )
    const rolSelect = screen.getByLabelText(/rol/i)
    fireEvent.change(rolSelect, { target: { value: '' } })
    expect(onRolChange).toHaveBeenCalledWith(undefined)
  })

  it('activo select calls onActivoChange with true/false/undefined', () => {
    const onActivoChange = vi.fn()

    const { rerender } = render(
      <UserFilters
        rol={undefined}
        activo={undefined}
        onRolChange={vi.fn()}
        onActivoChange={onActivoChange}
      />,
    )
    const activoSelect = screen.getByLabelText(/estado/i)

    fireEvent.change(activoSelect, { target: { value: 'true' } })
    expect(onActivoChange).toHaveBeenCalledWith(true)

    fireEvent.change(activoSelect, { target: { value: 'false' } })
    expect(onActivoChange).toHaveBeenCalledWith(false)

    fireEvent.change(activoSelect, { target: { value: '' } })
    expect(onActivoChange).toHaveBeenCalledWith(undefined)
  })

  it('disables both selects when disabled prop is true', () => {
    render(
      <UserFilters
        rol={undefined}
        activo={undefined}
        onRolChange={vi.fn()}
        onActivoChange={vi.fn()}
        disabled={true}
      />,
    )
    const selects = screen.getAllByRole('combobox')
    selects.forEach((select) => {
      expect(select).toBeDisabled()
    })
  })

  it('shows current rol and activo values', () => {
    render(
      <UserFilters
        rol={'STOCK'}
        activo={true}
        onRolChange={vi.fn()}
        onActivoChange={vi.fn()}
      />,
    )
    expect(screen.getByLabelText(/rol/i)).toHaveValue('STOCK')
    expect(screen.getByLabelText(/estado/i)).toHaveValue('true')
  })
})
