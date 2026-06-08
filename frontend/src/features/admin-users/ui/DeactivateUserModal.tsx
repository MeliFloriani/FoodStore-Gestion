/**
 * DeactivateUserModal — destructive confirmation modal for deactivating a user.
 *
 * Change 21: admin-users-management.
 *
 * OQ-02 CLOSED: Frontend does NOT expose reactivation. Only activo=false is sent.
 *
 * On LAST_ADMIN_PROTECTED error: shows inline error, modal stays open.
 * On success: closes modal and calls onSuccess callback.
 */

import { useState } from 'react'
import type { UsuarioAdminRead } from '../types'
import { useDeactivateUserMutation } from '../api/useDeactivateUserMutation'

interface DeactivateUserModalProps {
  user: UsuarioAdminRead
  onClose: () => void
  onSuccess: () => void
}

function getErrorCode(error: unknown): string | undefined {
  if (error && typeof error === 'object' && 'response' in error) {
    const response = (error as { response?: { data?: { code?: string } } }).response
    return response?.data?.code
  }
  return undefined
}

export function DeactivateUserModal({ user, onClose, onSuccess }: DeactivateUserModalProps) {
  const mutation = useDeactivateUserMutation()
  const [lastAdminError, setLastAdminError] = useState(false)

  function handleConfirm() {
    setLastAdminError(false)
    mutation.mutate(
      { id: user.id, data: { activo: false } },
      {
        onSuccess: () => {
          onSuccess()
          onClose()
        },
        onError: (error) => {
          const code = getErrorCode(error)
          if (code === 'LAST_ADMIN_PROTECTED') {
            setLastAdminError(true)
          }
        },
      },
    )
  }

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="deactivate-modal-title"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
    >
      <div className="w-full max-w-md rounded-lg bg-background shadow-lg">
        <div className="flex items-center justify-between border-b border-border p-4">
          <h2 id="deactivate-modal-title" className="text-lg font-semibold text-destructive">
            Desactivar usuario
          </h2>
          <button
            type="button"
            onClick={onClose}
            aria-label="Cerrar modal"
            className="rounded p-1 hover:bg-muted transition-colors"
          >
            ✕
          </button>
        </div>

        <div className="p-4 space-y-4">
          <div className="space-y-1">
            <p className="font-medium">
              {user.nombre} {user.apellido}
            </p>
            <p className="text-sm text-muted-foreground">{user.email}</p>
          </div>

          <div className="rounded-md border border-destructive/30 bg-destructive/5 p-3">
            <p className="text-sm text-destructive">
              Esta acción cerrará todas las sesiones activas de{' '}
              <span className="font-medium">{user.nombre}</span> e impedirá su
              acceso al sistema. Los pedidos históricos no serán afectados.
            </p>
          </div>

          {lastAdminError && (
            <p className="rounded-md bg-destructive/10 p-3 text-sm text-destructive" role="alert">
              No se puede desactivar al último administrador del sistema.
            </p>
          )}

          <div className="flex justify-end gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              disabled={mutation.isPending}
              className="rounded-md border border-border px-4 py-2 text-sm font-medium hover:bg-muted transition-colors disabled:opacity-50"
            >
              Cancelar
            </button>
            <button
              type="button"
              onClick={handleConfirm}
              disabled={mutation.isPending}
              aria-label={`Confirmar desactivación de ${user.nombre} ${user.apellido}`}
              className="rounded-md bg-destructive px-4 py-2 text-sm font-medium text-destructive-foreground hover:bg-destructive/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {mutation.isPending ? 'Desactivando...' : 'Desactivar'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
