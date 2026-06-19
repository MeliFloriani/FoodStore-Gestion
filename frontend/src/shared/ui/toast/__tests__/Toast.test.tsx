import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { Toast } from '../Toast'
import type { ToastItem } from '../toast.types'

function createItem(overrides: Partial<ToastItem> = {}): ToastItem {
  return {
    id: 't1',
    variant: 'success',
    title: 'Éxito',
    ...overrides,
  }
}

describe('Toast', () => {
  it('renders title', () => {
    render(<Toast item={createItem()} onDismiss={() => {}} />)
    expect(screen.getByText('Éxito')).toBeInTheDocument()
  })

  it('renders description when provided', () => {
    render(
      <Toast
        item={createItem({ description: 'Operación completada' })}
        onDismiss={() => {}}
      />,
    )
    expect(screen.getByText('Operación completada')).toBeInTheDocument()
  })

  it('does not render description when not provided', () => {
    render(<Toast item={createItem()} onDismiss={() => {}} />)
    expect(screen.queryByText('description')).not.toBeInTheDocument()
  })

  it('calls onDismiss with item id when dismiss button clicked', () => {
    const onDismiss = vi.fn()
    render(<Toast item={createItem({ id: 'abc-123' })} onDismiss={onDismiss} />)
    fireEvent.click(screen.getByRole('button', { name: 'Cerrar notificación' }))
    expect(onDismiss).toHaveBeenCalledWith('abc-123')
  })

  it('has role="status" for accessibility', () => {
    render(<Toast item={createItem()} onDismiss={() => {}} />)
    expect(screen.getByRole('status')).toBeInTheDocument()
  })

  it('renders success variant with checkmark icon', () => {
    render(<Toast item={createItem({ variant: 'success' })} onDismiss={() => {}} />)
    expect(screen.getByText('✓')).toBeInTheDocument()
  })

  it('renders error variant with cross icon', () => {
    render(<Toast item={createItem({ variant: 'error' })} onDismiss={() => {}} />)
    expect(screen.getByText('✕')).toBeInTheDocument()
  })

  it('renders warning variant with warning icon', () => {
    render(<Toast item={createItem({ variant: 'warning' })} onDismiss={() => {}} />)
    expect(screen.getByText('⚠')).toBeInTheDocument()
  })

  it('renders info variant with info icon', () => {
    render(<Toast item={createItem({ variant: 'info' })} onDismiss={() => {}} />)
    expect(screen.getByText('ℹ')).toBeInTheDocument()
  })

  it('renders unknown variant without crashing (fallback classes)', () => {
    render(
      <Toast
        item={createItem({ variant: 'unknown' as ToastItem['variant'] })}
        onDismiss={() => {}}
      />,
    )
    expect(screen.getByRole('status')).toBeInTheDocument()
    expect(screen.getByText('Éxito')).toBeInTheDocument()
  })
})
