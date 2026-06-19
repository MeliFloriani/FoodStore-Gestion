import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, act, renderHook } from '@testing-library/react'
import { ToastProvider, useToastContext } from '../ToastProvider'

function TestChild() {
  const { add, dismiss, clear, toasts } = useToastContext()
  return (
    <div>
      <span data-testid="count">{toasts.length}</span>
      <button
        onClick={() =>
          add({ id: 't1', variant: 'info', title: 'Info', description: 'Detail', duration: 0 })
        }
      >
        Add
      </button>
      <button onClick={() => dismiss('t1')}>Dismiss</button>
      <button onClick={clear}>Clear</button>
    </div>
  )
}

describe('ToastProvider', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('renders children', () => {
    render(
      <ToastProvider>
        <div data-testid="child">Hello</div>
      </ToastProvider>,
    )
    expect(screen.getByTestId('child')).toHaveTextContent('Hello')
  })

  it('adds a toast and renders it', () => {
    render(
      <ToastProvider>
        <TestChild />
      </ToastProvider>,
    )

    expect(screen.queryByRole('status')).not.toBeInTheDocument()

    act(() => {
      screen.getByRole('button', { name: 'Add' }).click()
    })

    expect(screen.getByRole('status')).toBeInTheDocument()
    expect(screen.getByText('Info')).toBeInTheDocument()
    expect(screen.getByText('Detail')).toBeInTheDocument()
  })

  it('dismisses a toast when dismiss is called', () => {
    render(
      <ToastProvider>
        <TestChild />
      </ToastProvider>,
    )

    act(() => {
      screen.getByRole('button', { name: 'Add' }).click()
    })
    expect(screen.getByRole('status')).toBeInTheDocument()

    act(() => {
      screen.getByRole('button', { name: 'Dismiss' }).click()
    })
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
  })

  it('clears all toasts when clear is called', () => {
    render(
      <ToastProvider>
        <TestChild />
      </ToastProvider>,
    )

    act(() => {
      screen.getByRole('button', { name: 'Add' }).click()
    })
    expect(screen.getByRole('status')).toBeInTheDocument()

    act(() => {
      screen.getByRole('button', { name: 'Clear' }).click()
    })
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
  })

  it('auto-dismisses a toast after its duration', () => {
    function AutoToast() {
      const { add } = useToastContext()
      return (
        <button
          onClick={() =>
            add({ id: 'auto', variant: 'success', title: 'Auto', duration: 2000 })
          }
        >
          Add auto
        </button>
      )
    }

    render(
      <ToastProvider>
        <AutoToast />
      </ToastProvider>,
    )

    act(() => {
      screen.getByRole('button', { name: 'Add auto' }).click()
    })
    expect(screen.getByRole('status')).toBeInTheDocument()

    act(() => {
      vi.advanceTimersByTime(2000)
    })
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
  })

  it('caps toasts at MAX_TOASTS (5)', () => {
    function AddMany() {
      const { add, toasts } = useToastContext()
      return (
        <div>
          <span data-testid="count">{toasts.length}</span>
          <button onClick={() => add({ id: `t${Date.now()}`, variant: 'info', title: 'T', duration: 0 })}>
            Add
          </button>
        </div>
      )
    }

    render(
      <ToastProvider>
        <AddMany />
      </ToastProvider>,
    )

    for (let i = 0; i < 7; i++) {
      act(() => {
        screen.getByRole('button', { name: 'Add' }).click()
      })
    }

    // Should be capped at 5
    expect(screen.getByTestId('count').textContent).toBe('5')
  })
})

describe('useToastContext', () => {
  it('throws when used outside ToastProvider', () => {
    expect(() => {
      renderHook(() => useToastContext())
    }).toThrow('useToastContext must be used inside <ToastProvider>')
  })
})
