/* eslint-disable react-refresh/only-export-components */
import { createContext, useContext, useState, useCallback, type ReactNode } from 'react'
import type { ConfirmOptions } from './confirm-dialog.types'
import { ConfirmDialog } from './ConfirmDialog'

interface PendingConfirm {
  options: ConfirmOptions
  resolve: (value: boolean) => void
}

interface ConfirmDialogContextValue {
  openConfirm: (options: ConfirmOptions) => Promise<boolean>
}

const ConfirmDialogContext = createContext<ConfirmDialogContextValue | null>(null)

export function ConfirmDialogProvider({ children }: { children: ReactNode }) {
  const [pending, setPending] = useState<PendingConfirm | null>(null)

  const openConfirm = useCallback((options: ConfirmOptions): Promise<boolean> => {
    return new Promise<boolean>((resolve) => {
      setPending({ options, resolve })
    })
  }, [])

  const handleConfirm = () => {
    pending?.resolve(true)
    setPending(null)
  }

  const handleCancel = () => {
    pending?.resolve(false)
    setPending(null)
  }

  return (
    <ConfirmDialogContext.Provider value={{ openConfirm }}>
      {children}
      {pending && (
        <ConfirmDialog
          {...pending.options}
          onConfirm={handleConfirm}
          onCancel={handleCancel}
        />
      )}
    </ConfirmDialogContext.Provider>
  )
}

export function useConfirmContext(): ConfirmDialogContextValue {
  const ctx = useContext(ConfirmDialogContext)
  if (!ctx) throw new Error('useConfirmContext must be used inside <ConfirmDialogProvider>')
  return ctx
}
