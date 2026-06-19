import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { CancelReasonModal } from '../CancelReasonModal'

describe('CancelReasonModal', () => {
  it('returns null when isOpen is false', () => {
    const { container } = render(
      <CancelReasonModal isOpen={false} onConfirm={vi.fn()} onClose={vi.fn()} />,
    )
    expect(container.innerHTML).toBe('')
  })

  it('renders dialog when isOpen is true', () => {
    render(
      <CancelReasonModal isOpen={true} onConfirm={vi.fn()} onClose={vi.fn()} />,
    )
    expect(screen.getByRole('dialog')).toBeInTheDocument()
    expect(screen.getByText('Cancelar pedido')).toBeInTheDocument()
  })

  it('renders custom title when provided', () => {
    render(
      <CancelReasonModal
        isOpen={true}
        onConfirm={vi.fn()}
        onClose={vi.fn()}
        title="Anular pedido"
      />,
    )
    expect(screen.getByText('Anular pedido')).toBeInTheDocument()
  })

  it('textarea updates motivo value', () => {
    render(
      <CancelReasonModal isOpen={true} onConfirm={vi.fn()} onClose={vi.fn()} />,
    )
    const textarea = screen.getByPlaceholderText(/motivo/i)
    fireEvent.change(textarea, { target: { value: 'Cliente arrepentido' } })
    expect(textarea).toHaveValue('Cliente arrepentido')
  })

  it('confirm button is disabled when motivo is too short', () => {
    render(
      <CancelReasonModal isOpen={true} onConfirm={vi.fn()} onClose={vi.fn()} />,
    )
    const textarea = screen.getByPlaceholderText(/motivo/i)
    fireEvent.change(textarea, { target: { value: 'ab' } })
    expect(screen.getByRole('button', { name: /confirmar/i })).toBeDisabled()
  })

  it('shows validation error when motivo is too short', () => {
    render(
      <CancelReasonModal isOpen={true} onConfirm={vi.fn()} onClose={vi.fn()} />,
    )
    const textarea = screen.getByPlaceholderText(/motivo/i)
    fireEvent.change(textarea, { target: { value: 'ab' } })
    expect(screen.getByText(/al menos 3 caracteres/i)).toBeInTheDocument()
  })

  it('confirm button is enabled when motivo has enough characters', () => {
    render(
      <CancelReasonModal isOpen={true} onConfirm={vi.fn()} onClose={vi.fn()} />,
    )
    const textarea = screen.getByPlaceholderText(/motivo/i)
    fireEvent.change(textarea, { target: { value: 'abc' } })
    expect(screen.getByRole('button', { name: /confirmar/i })).toBeEnabled()
  })

  it('calls onConfirm with trimmed motivo on confirm', () => {
    const onConfirm = vi.fn()
    render(
      <CancelReasonModal isOpen={true} onConfirm={onConfirm} onClose={vi.fn()} />,
    )
    const textarea = screen.getByPlaceholderText(/motivo/i)
    fireEvent.change(textarea, { target: { value: '  Cliente arrepentido  ' } })
    fireEvent.click(screen.getByRole('button', { name: /confirmar/i }))
    expect(onConfirm).toHaveBeenCalledWith('Cliente arrepentido')
  })

  it('resets motivo after confirm', () => {
    const onConfirm = vi.fn()
    render(
      <CancelReasonModal isOpen={true} onConfirm={onConfirm} onClose={vi.fn()} />,
    )
    const textarea = screen.getByPlaceholderText(/motivo/i) as HTMLTextAreaElement
    fireEvent.change(textarea, { target: { value: 'Cliente arrepentido' } })
    fireEvent.click(screen.getByRole('button', { name: /confirmar/i }))
    expect(textarea.value).toBe('')
  })

  it('calls onClose and resets motivo when Volver is clicked', () => {
    const onClose = vi.fn()
    render(
      <CancelReasonModal isOpen={true} onConfirm={vi.fn()} onClose={onClose} />,
    )
    const textarea = screen.getByPlaceholderText(/motivo/i) as HTMLTextAreaElement
    fireEvent.change(textarea, { target: { value: 'test' } })
    fireEvent.click(screen.getByRole('button', { name: /volver/i }))
    expect(onClose).toHaveBeenCalledOnce()
    expect(textarea.value).toBe('')
  })

  it('closes on Escape key', () => {
    const onClose = vi.fn()
    render(
      <CancelReasonModal isOpen={true} onConfirm={vi.fn()} onClose={onClose} />,
    )
    fireEvent.keyDown(screen.getByRole('dialog'), { key: 'Escape' })
    expect(onClose).toHaveBeenCalledOnce()
  })

  it('does not close on other key presses', () => {
    const onClose = vi.fn()
    render(
      <CancelReasonModal isOpen={true} onConfirm={vi.fn()} onClose={onClose} />,
    )
    fireEvent.keyDown(screen.getByRole('dialog'), { key: 'Enter' })
    expect(onClose).not.toHaveBeenCalled()
  })

  it('shows Cancelando... and disables buttons when isLoading', () => {
    render(
      <CancelReasonModal isOpen={true} onConfirm={vi.fn()} onClose={vi.fn()} isLoading={true} />,
    )
    expect(screen.getByText('Cancelando...')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /confirmar/i })).toBeDisabled()
    expect(screen.getByRole('button', { name: /volver/i })).toBeDisabled()
    expect(screen.getByPlaceholderText(/motivo/i)).toBeDisabled()
  })

  it('does not call onConfirm when isLoading', () => {
    const onConfirm = vi.fn()
    render(
      <CancelReasonModal
        isOpen={true}
        onConfirm={onConfirm}
        onClose={vi.fn()}
        isLoading={true}
      />,
    )
    const textarea = screen.getByPlaceholderText(/motivo/i)
    fireEvent.change(textarea, { target: { value: 'motivo válido' } })
    fireEvent.click(screen.getByRole('button', { name: /confirmar/i }))
    expect(onConfirm).not.toHaveBeenCalled()
  })

  it('has accessible aria attributes', () => {
    render(
      <CancelReasonModal isOpen={true} onConfirm={vi.fn()} onClose={vi.fn()} />,
    )
    const dialog = screen.getByRole('dialog')
    expect(dialog).toHaveAttribute('aria-modal', 'true')
    expect(dialog).toHaveAttribute('aria-labelledby', 'cancel-modal-title')
  })
})
