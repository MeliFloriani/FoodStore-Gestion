import { useCallback } from 'react'
import { useToastContext } from './ToastProvider'
import type { ToastItem } from './toast.types'

let _nextId = 0

function genId(): string {
  return `toast-${++_nextId}-${Date.now()}`
}

export function useToast() {
  const { add, dismiss, clear } = useToastContext()

  const toast = useCallback(
    (item: Omit<ToastItem, 'id'>): string => {
      const id = genId()
      add({ ...item, id })
      return id
    },
    [add],
  )

  return { toast, dismiss, clear }
}
