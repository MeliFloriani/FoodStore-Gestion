/**
 * LoginPage — email + password authentication form.
 *
 * Flow:
 *   1. POST /api/v1/auth/login with { email, password } → TokenResponse
 *   2. setTokens(access, refresh) so the next request carries the Bearer
 *   3. GET /api/v1/auth/me → User
 *   4. authStore.login(access, refresh, user) sets status = 'authenticated'
 *   5. AuthLayout detects 'authenticated' and redirects via resolveDefaultRoute
 *
 * Errors:
 *   401 → "Credenciales inválidas"
 *   422 → field-level message from normalizeError (rare for login)
 *   429 → rate limit notice
 *   network/other → generic fallback
 */

import { useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { useForm } from '@tanstack/react-form'
import { http } from '@/shared/api/http'
import { AUTH_LOGIN, AUTH_ME } from '@/shared/api/endpoints'
import { normalizeError } from '@/shared/lib/errors'
import { resolveDefaultRoute } from '@/shared/lib/navigation'
import { useAuthStore } from '@/entities/auth/model/store'
import { useToast } from '@/shared/ui/toast'
import type { User } from '@/entities/auth/types'

type TokenResponse = {
  access_token: string
  refresh_token: string
  token_type: string
  expires_in: number
}

export default function LoginPage() {
  const navigate = useNavigate()
  const location = useLocation()
  const setTokens = useAuthStore((s) => s.setTokens)
  const loginAction = useAuthStore((s) => s.login)
  const clear = useAuthStore((s) => s.clear)
  const { toast } = useToast()

  const [submitting, setSubmitting] = useState(false)

  const form = useForm({
    defaultValues: {
      email: '',
      password: '',
    },
    onSubmit: async ({ value }) => {
      setSubmitting(true)
      try {
        const tokenRes = await http.post<TokenResponse>(AUTH_LOGIN, {
          email: value.email,
          password: value.password,
        })
        const { access_token, refresh_token } = tokenRes.data

        // Seed tokens BEFORE /me so the request interceptor attaches Bearer.
        setTokens(access_token, refresh_token)

        const meRes = await http.get<User>(AUTH_ME)
        const user = meRes.data

        // Atomic transition to authenticated state.
        loginAction(access_token, refresh_token, user)

        const from = (location.state as { from?: string } | null)?.from
        navigate(from ?? resolveDefaultRoute(user.roles), { replace: true })
      } catch (err) {
        // Roll back partial token seed if /me failed mid-flight.
        clear()
        const norm = normalizeError(err)
        let description = 'No pudimos iniciar sesión. Intentá nuevamente.'
        if (norm.status === 401) {
          description = 'Credenciales inválidas. Verifica tu email y contraseña.'
        } else if (norm.status === 429) {
          description = 'Demasiados intentos. Esperá 15 minutos e intentá de nuevo.'
        } else if (norm.status === 422) {
          description = 'Datos inválidos. Revisá los campos.'
        }
        toast({ variant: 'error', title: 'Error al iniciar sesión', description })
      } finally {
        setSubmitting(false)
      }
    },
  })

  return (
    <div className="flex min-h-screen items-center justify-center bg-gray-50 px-4">
      <div className="w-full max-w-md rounded-lg bg-white p-8 shadow">
        <h1 className="mb-6 text-2xl font-semibold text-gray-900">Iniciar sesión</h1>

        <form
          onSubmit={(e) => {
            e.preventDefault()
            e.stopPropagation()
            void form.handleSubmit()
          }}
          noValidate
        >
          <form.Field
            name="email"
            validators={{
              onChange: ({ value }) => {
                if (!value) return 'El email es obligatorio'
                if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value)) return 'Email inválido'
                return undefined
              },
            }}
          >
            {(field) => (
              <div className="mb-4">
                <label htmlFor="email" className="mb-1 block text-sm font-medium text-gray-700">
                  Email
                </label>
                <input
                  id="email"
                  type="email"
                  autoComplete="email"
                  aria-label="Email"
                  value={field.state.value}
                  onChange={(e) => field.handleChange(e.target.value)}
                  onBlur={field.handleBlur}
                  className="h-11 w-full rounded border border-gray-300 px-3 py-2 focus:border-red-600 focus:outline-none"
                />
                {field.state.meta.errors.length > 0 && (
                  <p className="mt-1 text-sm text-red-500" role="alert">
                    {String(field.state.meta.errors[0])}
                  </p>
                )}
              </div>
            )}
          </form.Field>

          <form.Field
            name="password"
            validators={{
              onChange: ({ value }) => {
                if (!value) return 'La contraseña es obligatoria'
                return undefined
              },
            }}
          >
            {(field) => (
              <div className="mb-6">
                <label htmlFor="password" className="mb-1 block text-sm font-medium text-gray-700">
                  Contraseña
                </label>
                <input
                  id="password"
                  type="password"
                  autoComplete="current-password"
                  aria-label="Contraseña"
                  value={field.state.value}
                  onChange={(e) => field.handleChange(e.target.value)}
                  onBlur={field.handleBlur}
                  className="h-11 w-full rounded border border-gray-300 px-3 py-2 focus:border-red-600 focus:outline-none"
                />
                {field.state.meta.errors.length > 0 && (
                  <p className="mt-1 text-sm text-red-500" role="alert">
                    {String(field.state.meta.errors[0])}
                  </p>
                )}
              </div>
            )}
          </form.Field>

          <button
            type="submit"
            disabled={submitting}
            className="min-h-[44px] w-full rounded bg-red-600 px-4 py-2 font-medium text-white hover:bg-red-700 disabled:cursor-not-allowed disabled:opacity-50"
            aria-label="Iniciar sesión"
          >
            {submitting ? 'Ingresando…' : 'Ingresar'}
          </button>
        </form>

        <p className="mt-6 text-center text-sm text-gray-600">
          ¿No tenés cuenta?{' '}
          <Link to="/register" className="font-medium text-red-600 hover:underline">
            Registrate
          </Link>
        </p>
      </div>
    </div>
  )
}
