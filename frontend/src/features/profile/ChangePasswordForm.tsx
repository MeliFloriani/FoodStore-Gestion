/**
 * ChangePasswordForm — password mutation form.
 *
 * Change 13: customer-profile-management.
 *
 * Uses TanStack Form to manage state.
 * Fields: current_password, new_password (min 8), password_confirm (client-only equality check).
 * Submits POST /api/v1/profile/me/password with { current_password, new_password } ONLY.
 * password_confirm is NEVER sent to the backend.
 *
 * On success (204): toast "Contraseña actualizada" + authStore.logout() + navigate('/login')
 * On 409: inline error on current_password field
 * On 429: show rate limit toast message
 */

import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useForm } from '@tanstack/react-form'
import { useAuthStore } from '@/entities/auth/model/store'
import { useChangePassword } from './hooks/useChangePassword'
import type { AxiosError } from 'axios'

type ApiError = {
  detail?: string
  code?: string
}

export function ChangePasswordForm() {
  const navigate = useNavigate()
  const logout = useAuthStore((s) => s.logout)
  const mutation = useChangePassword()
  const [currentPasswordError, setCurrentPasswordError] = useState<string | null>(null)
  const [rateLimitError, setRateLimitError] = useState<string | null>(null)
  const [successMessage, setSuccessMessage] = useState<string | null>(null)

  const form = useForm({
    defaultValues: {
      current_password: '',
      new_password: '',
      password_confirm: '',
    },
    onSubmit: async ({ value }) => {
      setCurrentPasswordError(null)
      setRateLimitError(null)
      setSuccessMessage(null)

      mutation.mutate(
        {
          current_password: value.current_password,
          new_password: value.new_password,
          // password_confirm is NOT sent — client-only field
        },
        {
          onSuccess: () => {
            setSuccessMessage('Contraseña actualizada. Cerrando sesión...')
            // Logout and redirect to login
            logout()
            navigate('/login')
          },
          onError: (error) => {
            const axiosErr = error as AxiosError<ApiError>
            const status = axiosErr?.response?.status
            const code = axiosErr?.response?.data?.code

            if (status === 409 || code === 'CURRENT_PASSWORD_MISMATCH') {
              setCurrentPasswordError('Contraseña actual incorrecta. Verifica e intenta nuevamente.')
            } else if (status === 429) {
              setRateLimitError('Demasiados intentos. Espera 15 minutos.')
            }
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
      <h2 className="text-xl font-semibold mb-4">Cambiar Contraseña</h2>

      {/* Current Password */}
      <form.Field name="current_password">
        {(field) => (
          <div className="mb-4">
            <label htmlFor="current_password" className="block text-sm font-medium mb-1">
              Contraseña actual
            </label>
            <input
              id="current_password"
              type="password"
              aria-label="Contraseña actual"
              value={field.state.value}
              onChange={(e) => {
                field.handleChange(e.target.value)
                setCurrentPasswordError(null) // clear server error on change
              }}
              onBlur={field.handleBlur}
              className="w-full px-3 py-2 border rounded"
            />
            {currentPasswordError && (
              <p className="text-red-500 text-sm mt-1" role="alert">
                {currentPasswordError}
              </p>
            )}
          </div>
        )}
      </form.Field>

      {/* New Password */}
      <form.Field
        name="new_password"
        validators={{
          onChange: ({ value }) => {
            if (!value || value.length < 8) return 'La contraseña debe tener al menos 8 caracteres'
            return undefined
          },
        }}
      >
        {(field) => (
          <div className="mb-4">
            <label htmlFor="new_password" className="block text-sm font-medium mb-1">
              Nueva contraseña (mínimo 8 caracteres)
            </label>
            <input
              id="new_password"
              type="password"
              aria-label="Nueva contraseña"
              value={field.state.value}
              onChange={(e) => field.handleChange(e.target.value)}
              onBlur={field.handleBlur}
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

      {/* Password Confirm — client-only, never sent to backend */}
      <form.Field
        name="password_confirm"
        validators={{
          onChangeListenTo: ['new_password'],
          onChange: ({ value, fieldApi }) => {
            const newPassword = fieldApi.form.getFieldValue('new_password')
            if (value && value !== newPassword) {
              return 'Las contraseñas no coinciden'
            }
            return undefined
          },
        }}
      >
        {(field) => (
          <div className="mb-4">
            <label htmlFor="password_confirm" className="block text-sm font-medium mb-1">
              Confirmar nueva contraseña
            </label>
            <input
              id="password_confirm"
              type="password"
              aria-label="Confirmar nueva contraseña"
              value={field.state.value}
              onChange={(e) => field.handleChange(e.target.value)}
              onBlur={field.handleBlur}
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

      {/* Rate limit error */}
      {rateLimitError && (
        <p className="text-orange-500 text-sm mb-4" role="alert">
          {rateLimitError}
        </p>
      )}

      {/* Success message */}
      {successMessage && (
        <p className="text-green-600 text-sm mb-4" role="status">
          {successMessage}
        </p>
      )}

      {/* General server error */}
      {mutation.isError && !currentPasswordError && !rateLimitError && (
        <p className="text-red-500 text-sm mb-4" role="alert">
          Error al cambiar la contraseña. Intenta nuevamente.
        </p>
      )}

      {/* Submit button */}
      <button
        type="submit"
        disabled={mutation.isPending}
        className="px-4 py-2 bg-red-600 text-white rounded hover:bg-red-700 disabled:opacity-50 disabled:cursor-not-allowed"
        aria-label="Cambiar contraseña"
      >
        {mutation.isPending ? 'Cambiando...' : 'Cambiar contraseña'}
      </button>
    </form>
  )
}
