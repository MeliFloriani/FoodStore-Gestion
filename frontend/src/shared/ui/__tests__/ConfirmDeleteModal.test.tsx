import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { ConfirmDeleteModal } from '../ConfirmDeleteModal'

describe('ConfirmDeleteModal', () => {
  const defaultProps = {
    title: 'Eliminar producto',
    description: '¿Estás seguro?',
    isPending: false,
    onConfirm: vi.fn(),
    onClose: vi.fn(),
  }

  it('renders title and description', () => {
    render(<ConfirmDeleteModal {...defaultProps} />)
    expect(screen.getByText('Eliminar producto')).toBeInTheDocument()
    expect(screen.getByText('¿Estás seguro?')).toBeInTheDocument()
  })

  it('renders "Eliminar" button and "Cancelar" button', () => {
    render(<ConfirmDeleteModal {...defaultProps} />)
    expect(screen.getByRole('button', { name: 'Eliminar' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Cancelar' })).toBeInTheDocument()
  })

  it('calls onConfirm when Eliminar button clicked', () => {
    const onConfirm = vi.fn()
    render(<ConfirmDeleteModal {...defaultProps} onConfirm={onConfirm} />)
    fireEvent.click(screen.getByRole('button', { name: 'Eliminar' }))
    expect(onConfirm).toHaveBeenCalledOnce()
  })

  it('calls onClose when Cancelar button clicked', () => {
    const onClose = vi.fn()
    render(<ConfirmDeleteModal {...defaultProps} onClose={onClose} />)
    fireEvent.click(screen.getByRole('button', { name: 'Cancelar' }))
    expect(onClose).toHaveBeenCalledOnce()
  })

  it('calls onClose when close button (✕) clicked', () => {
    const onClose = vi.fn()
    render(<ConfirmDeleteModal {...defaultProps} onClose={onClose} />)
    fireEvent.click(screen.getByRole('button', { name: 'Cerrar' }))
    expect(onClose).toHaveBeenCalledOnce()
  })

  it('disables buttons when isPending is true', () => {
    render(<ConfirmDeleteModal {...defaultProps} isPending />)
    const buttons = screen.getAllByRole('button')
    buttons.forEach((btn) => {
      expect(btn).toBeDisabled()
    })
  })

  it('shows "Eliminando…" when isPending is true', () => {
    render(<ConfirmDeleteModal {...defaultProps} isPending />)
    expect(screen.getByText('Eliminando…')).toBeInTheDocument()
  })

  it('has dialog role with aria-modal', () => {
    render(<ConfirmDeleteModal {...defaultProps} />)
    const dialog = screen.getByRole('dialog')
    expect(dialog).toHaveAttribute('aria-modal', 'true')
    expect(dialog).toHaveAttribute('aria-labelledby', 'confirm-delete-title')
  })
})
