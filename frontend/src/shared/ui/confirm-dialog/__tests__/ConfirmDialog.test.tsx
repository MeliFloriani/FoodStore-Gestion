import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { ConfirmDialog } from '../ConfirmDialog'

describe('ConfirmDialog', () => {
  it('renders title', () => {
    render(
      <ConfirmDialog
        title="¿Eliminar?"
        onConfirm={() => {}}
        onCancel={() => {}}
      />,
    )
    expect(screen.getByText('¿Eliminar?')).toBeInTheDocument()
  })

  it('renders confirm and cancel buttons with default labels', () => {
    render(
      <ConfirmDialog
        title="Test"
        onConfirm={() => {}}
        onCancel={() => {}}
      />,
    )
    expect(screen.getByRole('button', { name: 'Confirmar' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Cancelar' })).toBeInTheDocument()
  })

  it('renders custom button labels', () => {
    render(
      <ConfirmDialog
        title="Test"
        confirmLabel="Sí, borrar"
        cancelLabel="No, volver"
        onConfirm={() => {}}
        onCancel={() => {}}
      />,
    )
    expect(screen.getByRole('button', { name: 'Sí, borrar' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'No, volver' })).toBeInTheDocument()
  })

  it('renders description when provided', () => {
    render(
      <ConfirmDialog
        title="Test"
        description="Esta acción no se puede deshacer"
        onConfirm={() => {}}
        onCancel={() => {}}
      />,
    )
    expect(
      screen.getByText('Esta acción no se puede deshacer'),
    ).toBeInTheDocument()
  })

  it('does not render description element when not provided', () => {
    render(
      <ConfirmDialog
        title="Test"
        onConfirm={() => {}}
        onCancel={() => {}}
      />,
    )
    // The only paragraph would be in description — should not exist
    expect(screen.queryByRole('paragraph')).not.toBeInTheDocument()
  })

  it('calls onConfirm when confirm button clicked', () => {
    const onConfirm = vi.fn()
    render(
      <ConfirmDialog
        title="Test"
        onConfirm={onConfirm}
        onCancel={() => {}}
      />,
    )
    fireEvent.click(screen.getByRole('button', { name: 'Confirmar' }))
    expect(onConfirm).toHaveBeenCalledOnce()
  })

  it('calls onCancel when cancel button clicked', () => {
    const onCancel = vi.fn()
    render(
      <ConfirmDialog
        title="Test"
        onConfirm={() => {}}
        onCancel={onCancel}
      />,
    )
    fireEvent.click(screen.getByRole('button', { name: 'Cancelar' }))
    expect(onCancel).toHaveBeenCalledOnce()
  })

  it('calls onCancel when overlay is clicked', () => {
    const onCancel = vi.fn()
    render(
      <ConfirmDialog
        title="Test"
        onConfirm={() => {}}
        onCancel={onCancel}
      />,
    )
    const overlay = document.querySelector('[aria-hidden="true"]')
    expect(overlay).toBeInTheDocument()
    fireEvent.click(overlay!)
    expect(onCancel).toHaveBeenCalledOnce()
  })

  it('has alertdialog role with aria-labelledby', () => {
    render(
      <ConfirmDialog
        title="¿Confirma?"
        onConfirm={() => {}}
        onCancel={() => {}}
      />,
    )
    const dialog = screen.getByRole('alertdialog')
    expect(dialog).toBeInTheDocument()
    const labelId = dialog.getAttribute('aria-labelledby')
    expect(labelId).toBe('confirm-dialog-title')
  })

  describe('keyboard handlers', () => {
    it('calls onCancel when Escape key pressed', () => {
      const onCancel = vi.fn()
      render(
        <ConfirmDialog
          title="Test"
          onConfirm={() => {}}
          onCancel={onCancel}
        />,
      )
      fireEvent.keyDown(document, { key: 'Escape' })
      expect(onCancel).toHaveBeenCalledOnce()
    })

    it('calls onConfirm when Enter key pressed', () => {
      const onConfirm = vi.fn()
      render(
        <ConfirmDialog
          title="Test"
          onConfirm={onConfirm}
          onCancel={() => {}}
        />,
      )
      fireEvent.keyDown(document, { key: 'Enter' })
      expect(onConfirm).toHaveBeenCalledOnce()
    })

    it('does not call handlers for other keys', () => {
      const onConfirm = vi.fn()
      const onCancel = vi.fn()
      render(
        <ConfirmDialog
          title="Test"
          onConfirm={onConfirm}
          onCancel={onCancel}
        />,
      )
      fireEvent.keyDown(document, { key: 'Tab' })
      expect(onConfirm).not.toHaveBeenCalled()
      expect(onCancel).not.toHaveBeenCalled()
    })
  })

  describe('variant styling', () => {
    it('applies destructive classes when variant is destructive', () => {
      render(
        <ConfirmDialog
          title="Test"
          variant="destructive"
          onConfirm={() => {}}
          onCancel={() => {}}
        />,
      )
      const confirmBtn = screen.getByRole('button', { name: 'Confirmar' })
      expect(confirmBtn.className).toContain('destructive')
    })

    it('applies primary classes when variant is default', () => {
      render(
        <ConfirmDialog
          title="Test"
          variant="default"
          onConfirm={() => {}}
          onCancel={() => {}}
        />,
      )
      const confirmBtn = screen.getByRole('button', { name: 'Confirmar' })
      expect(confirmBtn.className).toContain('primary')
    })
  })
})
