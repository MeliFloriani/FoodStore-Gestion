/**
 * Unit tests for ConfirmDialogProvider and useConfirmContext.
 *
 * The Provider wraps ConfirmDialog in a createPortal so the dialog
 * renders into document.body. All interaction tests work via the
 * openConfirm promise returned by the context.
 */

import { describe, it, expect, vi, type Mock } from 'vitest'
import { render, screen, fireEvent, act, renderHook } from '@testing-library/react'
import { ConfirmDialogProvider, useConfirmContext } from '../ConfirmDialogProvider'

// ── useConfirmContext ──────────────────────────────────────────────────────

describe('useConfirmContext', () => {
  it('throws when used outside ConfirmDialogProvider', () => {
    expect(() => {
      renderHook(() => useConfirmContext())
    }).toThrow('useConfirmContext must be used inside <ConfirmDialogProvider>')
  })

  it('returns openConfirm function when inside provider', () => {
    const { result } = renderHook(() => useConfirmContext(), {
      wrapper: ConfirmDialogProvider,
    })
    expect(result.current.openConfirm).toBeInstanceOf(Function)
  })
})

// ── ConfirmDialogProvider (integration) ────────────────────────────────────

describe('ConfirmDialogProvider', () => {
  it('renders children', () => {
    render(
      <ConfirmDialogProvider>
        <div data-testid="child">Hello</div>
      </ConfirmDialogProvider>,
    )
    expect(screen.getByTestId('child')).toHaveTextContent('Hello')
  })

  it('shows ConfirmDialog when openConfirm is called', async () => {
    function Trigger() {
      const { openConfirm } = useConfirmContext()
      return (
        <button onClick={() => openConfirm({ title: '¿Borrar?' })}>
          Open
        </button>
      )
    }

    render(
      <ConfirmDialogProvider>
        <Trigger />
      </ConfirmDialogProvider>,
    )

    expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument()

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: 'Open' }))
    })

    expect(screen.getByRole('alertdialog')).toBeInTheDocument()
    expect(screen.getByText('¿Borrar?')).toBeInTheDocument()
  })

  it('resolves promise with true when Confirm clicked', async () => {
    let resolvePromise: ((value: boolean) => void) | undefined
    const onResolve = vi.fn()

    function Trigger() {
      const { openConfirm } = useConfirmContext()
      return (
        <button
          onClick={() => {
            const promise = openConfirm({ title: '¿Confirma?' })
            promise.then(onResolve)
            resolvePromise = promise
          }}
        >
          Open
        </button>
      )
    }

    render(
      <ConfirmDialogProvider>
        <Trigger />
      </ConfirmDialogProvider>,
    )

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: 'Open' }))
    })

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: 'Confirmar' }))
    })

    expect(onResolve).toHaveBeenCalledWith(true)
  })

  it('resolves promise with false when Cancel clicked', async () => {
    const onResolve = vi.fn()

    function Trigger() {
      const { openConfirm } = useConfirmContext()
      return (
        <button
          onClick={() => {
            openConfirm({ title: '¿Confirma?' }).then(onResolve)
          }}
        >
          Open
        </button>
      )
    }

    render(
      <ConfirmDialogProvider>
        <Trigger />
      </ConfirmDialogProvider>,
    )

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: 'Open' }))
    })

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: 'Cancelar' }))
    })

    expect(onResolve).toHaveBeenCalledWith(false)
  })

  it('hides dialog after confirm', async () => {
    function Trigger() {
      const { openConfirm } = useConfirmContext()
      return (
        <button onClick={() => openConfirm({ title: '¿Borrar?' })}>
          Open
        </button>
      )
    }

    render(
      <ConfirmDialogProvider>
        <Trigger />
      </ConfirmDialogProvider>,
    )

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: 'Open' }))
    })
    expect(screen.getByRole('alertdialog')).toBeInTheDocument()

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: 'Confirmar' }))
    })
    expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument()
  })

  it('hides dialog after cancel', async () => {
    function Trigger() {
      const { openConfirm } = useConfirmContext()
      return (
        <button onClick={() => openConfirm({ title: '¿Borrar?' })}>
          Open
        </button>
      )
    }

    render(
      <ConfirmDialogProvider>
        <Trigger />
      </ConfirmDialogProvider>,
    )

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: 'Open' }))
    })
    expect(screen.getByRole('alertdialog')).toBeInTheDocument()

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: 'Cancelar' }))
    })
    expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument()
  })
})
