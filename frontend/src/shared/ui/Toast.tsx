/* eslint-disable react-refresh/only-export-components */
/**
 * Minimal toast notification system — no external dependencies.
 *
 * Usage:
 *   const { toasts, showToast } = useToast()
 *   showToast('Guardado correctamente', 'success')
 *   showToast('Error al guardar', 'error')
 *   <ToastList toasts={toasts} />
 */

import { useState, useCallback } from 'react'

export type ToastVariant = 'success' | 'error'

export interface ToastItem {
  id: number
  message: string
  variant: ToastVariant
}

let _nextId = 0

export function useToast() {
  const [toasts, setToasts] = useState<ToastItem[]>([])

  const dismiss = useCallback((id: number) => {
    setToasts((prev) => prev.filter((t) => t.id !== id))
  }, [])

  const showToast = useCallback(
    (message: string, variant: ToastVariant = 'success') => {
      const id = ++_nextId
      setToasts((prev) => [...prev, { id, message, variant }])
      setTimeout(() => dismiss(id), 4000)
    },
    [dismiss],
  )

  return { toasts, showToast }
}

interface ToastListProps {
  toasts: ToastItem[]
}

export function ToastList({ toasts }: ToastListProps) {
  if (toasts.length === 0) return null
  return (
    <div
      aria-live="polite"
      aria-label="Notificaciones"
      className="fixed bottom-4 right-4 z-[60] flex flex-col gap-2"
    >
      {toasts.map((t) => (
        <div
          key={t.id}
          role="status"
          data-variant={t.variant}
          className={`flex items-center gap-2 rounded-md px-4 py-3 text-sm font-medium shadow-lg ${
            t.variant === 'success'
              ? 'bg-green-600 text-white'
              : 'bg-destructive text-destructive-foreground'
          }`}
        >
          <span aria-hidden="true">{t.variant === 'success' ? '✓' : '✕'}</span>
          {t.message}
        </div>
      ))}
    </div>
  )
}
