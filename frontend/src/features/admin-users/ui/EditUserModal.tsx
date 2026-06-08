/**
 * EditUserModal — modal form for editing user nombre/apellido.
 *
 * Change 21: admin-users-management.
 *
 * D-01: email is display-only (read-only). NOT sent in the mutation.
 * Fields: nombre (max 80), apellido (max 80).
 * Pre-populates with current user data.
 * On success: closes modal + shows success toast (via onSuccess callback).
 */

import { useState } from 'react'
import { useForm } from '@tanstack/react-form'
import type { UsuarioAdminRead } from '../types'
import { useUpdateUserMutation } from '../api/useUpdateUserMutation'

interface EditUserModalProps {
  user: UsuarioAdminRead
  onClose: () => void
  onSuccess: () => void
}

export function EditUserModal({ user, onClose, onSuccess }: EditUserModalProps) {
  const mutation = useUpdateUserMutation()
  const [serverError, setServerError] = useState<string | null>(null)

  const form = useForm({
    defaultValues: {
      nombre: user.nombre,
      apellido: user.apellido,
    },
    onSubmit: async ({ value }) => {
      setServerError(null)
      mutation.mutate(
        {
          id: user.id,
          data: { nombre: value.nombre, apellido: value.apellido },
        },
        {
          onSuccess: () => {
            onSuccess()
            onClose()
          },
          onError: () => {
            setServerError('Error al actualizar el usuario. Intenta nuevamente.')
          },
        },
      )
    },
  })

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="edit-user-modal-title"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
    >
      <div className="w-full max-w-md rounded-lg bg-background shadow-lg">
        <div className="flex items-center justify-between border-b border-border p-4">
          <h2
            id="edit-user-modal-title"
            className="text-lg font-semibold"
          >
            Editar datos del usuario
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

        <form
          onSubmit={(e) => {
            e.preventDefault()
            e.stopPropagation()
            void form.handleSubmit()
          }}
          noValidate
          className="p-4 space-y-4"
        >
          {/* Email — read-only, never sent (D-01) */}
          <div>
            <label
              htmlFor="edit-user-email"
              className="block text-sm font-medium text-muted-foreground mb-1"
            >
              Email (no editable)
            </label>
            <input
              id="edit-user-email"
              type="email"
              value={user.email}
              disabled
              readOnly
              aria-label="Email del usuario (no editable)"
              className="w-full rounded-md border border-input bg-muted px-3 py-2 text-sm text-muted-foreground cursor-not-allowed"
            />
          </div>

          {/* Nombre */}
          <form.Field
            name="nombre"
            validators={{
              onChange: ({ value }) => {
                if (!value || value.trim() === '') return 'El nombre es requerido'
                if (value.length > 80) return 'El nombre no puede superar 80 caracteres'
                return undefined
              },
            }}
          >
            {(field) => (
              <div>
                <label
                  htmlFor="edit-user-nombre"
                  className="block text-sm font-medium mb-1"
                >
                  Nombre
                </label>
                <input
                  id="edit-user-nombre"
                  type="text"
                  aria-label="Nombre del usuario"
                  value={field.state.value}
                  onChange={(e) => field.handleChange(e.target.value)}
                  onBlur={field.handleBlur}
                  maxLength={80}
                  className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                />
                {field.state.meta.errors.length > 0 && (
                  <p className="mt-1 text-xs text-destructive" role="alert">
                    {field.state.meta.errors[0]}
                  </p>
                )}
              </div>
            )}
          </form.Field>

          {/* Apellido */}
          <form.Field
            name="apellido"
            validators={{
              onChange: ({ value }) => {
                if (!value || value.trim() === '') return 'El apellido es requerido'
                if (value.length > 80) return 'El apellido no puede superar 80 caracteres'
                return undefined
              },
            }}
          >
            {(field) => (
              <div>
                <label
                  htmlFor="edit-user-apellido"
                  className="block text-sm font-medium mb-1"
                >
                  Apellido
                </label>
                <input
                  id="edit-user-apellido"
                  type="text"
                  aria-label="Apellido del usuario"
                  value={field.state.value}
                  onChange={(e) => field.handleChange(e.target.value)}
                  onBlur={field.handleBlur}
                  maxLength={80}
                  className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                />
                {field.state.meta.errors.length > 0 && (
                  <p className="mt-1 text-xs text-destructive" role="alert">
                    {field.state.meta.errors[0]}
                  </p>
                )}
              </div>
            )}
          </form.Field>

          {serverError && (
            <p className="text-sm text-destructive" role="alert">
              {serverError}
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
              {mutation.isPending ? 'Guardando...' : 'Guardar cambios'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
