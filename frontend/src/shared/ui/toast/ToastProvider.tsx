/* eslint-disable react-refresh/only-export-components */
import { createContext, useContext, useReducer, useCallback, useRef, type ReactNode } from 'react'
import type { ToastItem } from './toast.types'
import { Toast } from './Toast'

const MAX_TOASTS = 5

interface ToastContextValue {
  toasts: ToastItem[]
  add: (item: ToastItem) => void
  dismiss: (id: string) => void
  clear: () => void
}

const ToastContext = createContext<ToastContextValue | null>(null)

type Action =
  | { type: 'ADD'; item: ToastItem }
  | { type: 'DISMISS'; id: string }
  | { type: 'CLEAR' }

function reducer(state: ToastItem[], action: Action): ToastItem[] {
  switch (action.type) {
    case 'ADD': {
      const next = [...state, action.item]
      return next.length > MAX_TOASTS ? next.slice(next.length - MAX_TOASTS) : next
    }
    case 'DISMISS':
      return state.filter((t) => t.id !== action.id)
    case 'CLEAR':
      return []
    default:
      return state
  }
}

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, dispatch] = useReducer(reducer, [])
  const timersRef = useRef<Map<string, ReturnType<typeof setTimeout>>>(new Map())

  const dismiss = useCallback((id: string) => {
    const timer = timersRef.current.get(id)
    if (timer) {
      clearTimeout(timer)
      timersRef.current.delete(id)
    }
    dispatch({ type: 'DISMISS', id })
  }, [])

  const add = useCallback((item: ToastItem) => {
    dispatch({ type: 'ADD', item })
    const duration = item.duration ?? 4000
    if (duration > 0) {
      const timer = setTimeout(() => dismiss(item.id), duration)
      timersRef.current.set(item.id, timer)
    }
  }, [dismiss])

  const clear = useCallback(() => {
    timersRef.current.forEach((timer) => clearTimeout(timer))
    timersRef.current.clear()
    dispatch({ type: 'CLEAR' })
  }, [])

  return (
    <ToastContext.Provider value={{ toasts, add, dismiss, clear }}>
      {children}
      <div
        aria-live="polite"
        aria-atomic="true"
        className="fixed bottom-4 right-4 z-[50] flex flex-col gap-2"
      >
        {toasts.map((toast) => (
          <Toast key={toast.id} item={toast} onDismiss={dismiss} />
        ))}
      </div>
    </ToastContext.Provider>
  )
}

export function useToastContext(): ToastContextValue {
  const ctx = useContext(ToastContext)
  if (!ctx) throw new Error('useToastContext must be used inside <ToastProvider>')
  return ctx
}
