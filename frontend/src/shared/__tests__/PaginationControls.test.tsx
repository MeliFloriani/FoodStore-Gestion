/**
 * Unit tests for PaginationControls component.
 */

import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { PaginationControls } from '../ui/PaginationControls'

describe('PaginationControls', () => {
  it('renders nothing when pages is 0', () => {
    const { container } = render(
      <PaginationControls page={1} pages={0} onPageChange={() => {}} />,
    )
    expect(container.firstChild).toBeNull()
  })

  it('renders a nav with accessible label', () => {
    render(<PaginationControls page={1} pages={5} onPageChange={() => {}} />)
    expect(
      screen.getByRole('navigation', { name: 'Paginación del catálogo' }),
    ).toBeInTheDocument()
  })

  it('disables Previous button on first page', () => {
    render(<PaginationControls page={1} pages={5} onPageChange={() => {}} />)
    const prevBtn = screen.getByRole('button', { name: 'Página anterior' })
    expect(prevBtn).toBeDisabled()
  })

  it('does not disable Next button on first page', () => {
    render(<PaginationControls page={1} pages={5} onPageChange={() => {}} />)
    const nextBtn = screen.getByRole('button', { name: 'Página siguiente' })
    expect(nextBtn).not.toBeDisabled()
  })

  it('disables Next button on last page', () => {
    render(<PaginationControls page={5} pages={5} onPageChange={() => {}} />)
    const nextBtn = screen.getByRole('button', { name: 'Página siguiente' })
    expect(nextBtn).toBeDisabled()
  })

  it('does not disable Previous button on last page', () => {
    render(<PaginationControls page={5} pages={5} onPageChange={() => {}} />)
    const prevBtn = screen.getByRole('button', { name: 'Página anterior' })
    expect(prevBtn).not.toBeDisabled()
  })

  it('sets aria-current="page" on active page button', () => {
    render(<PaginationControls page={3} pages={10} onPageChange={() => {}} />)
    const activeBtn = screen.getByRole('button', { name: 'Página 3' })
    expect(activeBtn).toHaveAttribute('aria-current', 'page')
  })

  it('does not set aria-current on inactive page buttons', () => {
    render(<PaginationControls page={3} pages={5} onPageChange={() => {}} />)
    const btn1 = screen.getByRole('button', { name: 'Página 1' })
    expect(btn1).not.toHaveAttribute('aria-current')
  })

  it('calls onPageChange with correct page when page button clicked', () => {
    const onPageChange = vi.fn()
    render(<PaginationControls page={2} pages={5} onPageChange={onPageChange} />)

    fireEvent.click(screen.getByRole('button', { name: 'Página 4' }))
    expect(onPageChange).toHaveBeenCalledWith(4)
  })

  it('calls onPageChange with page-1 when Previous clicked', () => {
    const onPageChange = vi.fn()
    render(<PaginationControls page={3} pages={5} onPageChange={onPageChange} />)

    fireEvent.click(screen.getByRole('button', { name: 'Página anterior' }))
    expect(onPageChange).toHaveBeenCalledWith(2)
  })

  it('calls onPageChange with page+1 when Next clicked', () => {
    const onPageChange = vi.fn()
    render(<PaginationControls page={3} pages={5} onPageChange={onPageChange} />)

    fireEvent.click(screen.getByRole('button', { name: 'Página siguiente' }))
    expect(onPageChange).toHaveBeenCalledWith(4)
  })

  it('renders all page buttons for small page count (<=7)', () => {
    render(<PaginationControls page={1} pages={5} onPageChange={() => {}} />)
    for (let i = 1; i <= 5; i++) {
      expect(screen.getByRole('button', { name: `Página ${i}` })).toBeInTheDocument()
    }
  })

  it('disables all buttons when disabled prop is true', () => {
    render(
      <PaginationControls page={3} pages={5} onPageChange={() => {}} disabled />,
    )
    const buttons = screen.getAllByRole('button')
    buttons.forEach((btn) => {
      expect(btn).toBeDisabled()
    })
  })
})
