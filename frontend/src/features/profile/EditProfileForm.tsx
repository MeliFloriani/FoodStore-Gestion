/**
 * EditProfileForm — profile data mutation form.
 *
 * Change 13: customer-profile-management.
 *
 * Uses TanStack Form to manage state.
 * Submits PATCH /api/v1/profile/me with { nombre, apellido } only.
 * The email field is shown as disabled/read-only and NEVER included in the payload.
 *
 * On success: shows a success message inline.
 * On error: shows inline error message.
 */

import { useState } from 'react'
import { useForm } from '@tanstack/react-form'
import type { User } from '@/entities/auth/types'
import { useUpdateProfile } from './hooks/useUpdateProfile'

type EditProfileFormProps = {
  user: User
}

export function EditProfileForm({ user }: EditProfileFormProps) {
  const mutation = useUpdateProfile()
  const [successMessage, setSuccessMessage] = useState<string | null>(null)

  const form = useForm({
    defaultValues: {
      nombre: user.nombre,
      apellido: user.apellido,
    },
    onSubmit: async ({ value }) => {
      setSuccessMessage(null)
      mutation.mutate(
        { nombre: value.nombre, apellido: value.apellido },
        {
          onSuccess: () => {
            setSuccessMessage('Perfil actualizado exitosamente')
          },
          onError: () => {
            setSuccessMessage(null)
          },
        }
      )
    },
  })

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault()
        e.stopPropagation()
        void form.handleSubmit()
      }}
      noValidate
    >
      <h2 className="text-xl font-semibold mb-4">Editar Perfil</h2>

      {/* Email — disabled read-only, never in payload */}
      <div className="mb-4">
        <label htmlFor="email" className="block text-sm font-medium mb-1">
          Email
        </label>
        <input
          id="email"
          type="email"
          value={user.email}
          disabled
          aria-label="Email"
          className="w-full px-3 py-2 border rounded bg-gray-100 text-gray-500 cursor-not-allowed"
          readOnly
        />
        <p className="text-xs text-gray-500 mt-1">El email no puede modificarse.</p>
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
          <div className="mb-4">
            <label htmlFor="nombre" className="block text-sm font-medium mb-1">
              Nombre
            </label>
            <input
              id="nombre"
              type="text"
              aria-label="Nombre"
              value={field.state.value}
              onChange={(e) => field.handleChange(e.target.value)}
              onBlur={field.handleBlur}
              maxLength={80}
              className="w-full px-3 py-2 border rounded"
            />
            {field.state.meta.errors.length > 0 && (
              <p className="text-red-500 text-sm mt-1" role="alert">
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
          <div className="mb-4">
            <label htmlFor="apellido" className="block text-sm font-medium mb-1">
              Apellido
            </label>
            <input
              id="apellido"
              type="text"
              aria-label="Apellido"
              value={field.state.value}
              onChange={(e) => field.handleChange(e.target.value)}
              onBlur={field.handleBlur}
              maxLength={80}
              className="w-full px-3 py-2 border rounded"
            />
            {field.state.meta.errors.length > 0 && (
              <p className="text-red-500 text-sm mt-1" role="alert">
                {field.state.meta.errors[0]}
              </p>
            )}
          </div>
        )}
      </form.Field>

      {/* Success message */}
      {successMessage && (
        <p className="text-green-600 text-sm mb-4" role="status">
          {successMessage}
        </p>
      )}

      {/* Error message */}
      {mutation.isError && !successMessage && (
        <p className="text-red-500 text-sm mb-4" role="alert">
          Error al actualizar el perfil. Intenta nuevamente.
        </p>
      )}

      {/* Submit button */}
      <button
        type="submit"
        disabled={mutation.isPending}
        className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
        aria-label="Guardar cambios"
      >
        {mutation.isPending ? 'Guardando...' : 'Guardar cambios'}
      </button>
    </form>
  )
}
