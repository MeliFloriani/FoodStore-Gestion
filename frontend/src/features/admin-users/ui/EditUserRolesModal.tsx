/**
 * EditUserRolesModal — modal for replacing a user's full role set.
 *
 * Change 21: admin-users-management.
 *
 * Semantics: PUT replace (D-02). The checkbox selection IS the complete desired
 * role set. Requires at least 1 role selected (client-side validation).
 *
 * On LAST_ADMIN_PROTECTED error: shows inline message, modal stays open.
 * On success: closes modal and calls onSuccess callback.
 *
 * OQ-02 CLOSED: No "Reactivar" functionality here.
 */

import { useState } from 'react'
import type { UsuarioAdminRead } from '../types'
import { VALID_ROLES } from '../types'
import { useUpdateUserRolesMutation, getErrorCode } from '../api/useUpdateUserRolesMutation'

interface EditUserRolesModalProps {
  user: UsuarioAdminRead
  onClose: () => void
  onSuccess: () => void
}

export function EditUserRolesModal({ user, onClose, onSuccess }: EditUserRolesModalProps) {
  const mutation = useUpdateUserRolesMutation()

  const currentRoleCodes = new Set(user.roles.map((r) => r.codigo))
  const [selectedRoles, setSelectedRoles] = useState<Set<string>>(new Set(currentRoleCodes))
  const [lastAdminError, setLastAdminError] = useState(false)
  const [validationError, setValidationError] = useState<string | null>(null)

  function toggleRole(codigo: string) {
    setSelectedRoles((prev) => {
      const next = new Set(prev)
      if (next.has(codigo)) {
        next.delete(codigo)
      } else {
        next.add(codigo)
      }
      return next
    })
    setLastAdminError(false)
    setValidationError(null)
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (selectedRoles.size === 0) {
      setValidationError('Debe seleccionar al menos un rol')
      return
    }
    setLastAdminError(false)
    setValidationError(null)

    mutation.mutate(
      { id: user.id, data: { roles: Array.from(selectedRoles) } },
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
      aria-labelledby="edit-roles-modal-title"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
    >
      <div className="w-full max-w-sm rounded-lg bg-background shadow-lg">
        <div className="flex items-center justify-between border-b border-border p-4">
          <h2 id="edit-roles-modal-title" className="text-lg font-semibold">
            Editar roles del usuario
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

        <form onSubmit={handleSubmit} noValidate className="p-4 space-y-4">
          <p className="text-sm text-muted-foreground">
            {user.nombre} {user.apellido} — <span className="font-medium">{user.email}</span>
          </p>

          <p className="text-sm font-medium">Seleccioná los roles:</p>

          <div className="space-y-2">
            {VALID_ROLES.map((codigo) => (
              <label
                key={codigo}
                className="flex items-center gap-3 rounded-md border border-border p-2 cursor-pointer hover:bg-muted/20 transition-colors"
              >
                <input
                  type="checkbox"
                  checked={selectedRoles.has(codigo)}
                  onChange={() => toggleRole(codigo)}
                  aria-label={`Rol ${codigo}`}
                  className="h-4 w-4 rounded border-border"
                />
                <span className="text-sm font-medium">{codigo}</span>
              </label>
            ))}
          </div>

          {validationError && (
            <p className="text-sm text-destructive" role="alert">
              {validationError}
            </p>
          )}

          {lastAdminError && (
            <p className="rounded-md bg-destructive/10 p-3 text-sm text-destructive" role="alert">
              No es posible quitar el rol ADMIN al único administrador del sistema.
            </p>
          )}

          <div className="flex justify-end gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="rounded-md border border-border px-4 py-2 text-sm font-medium hover:bg-muted transition-colors"
            >
              Cancelar
            </button>
            <button
              type="submit"
              disabled={mutation.isPending}
              className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {mutation.isPending ? 'Guardando...' : 'Guardar roles'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
