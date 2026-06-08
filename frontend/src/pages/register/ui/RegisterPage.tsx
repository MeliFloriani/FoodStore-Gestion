/**
 * RegisterPage — new user signup form.
 *
 * Fields: nombre, apellido, email, password (min 8)
 * Submits POST /api/v1/auth/register with the same body.
 *
 * On 201: navigate to /login with a success notice (auto-login is intentionally
 * NOT done so the user sees the standard credentials flow at least once).
 * On 409: inline error on email field ("Ya existe un usuario con ese email").
 * On 422: surface backend field errors via normalizeError().fieldErrors.
 * On 429: rate limit notice.
 */

import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useForm } from '@tanstack/react-form'
import { http } from '@/shared/api/http'
import { AUTH_REGISTER } from '@/shared/api/endpoints'
import { normalizeError } from '@/shared/lib/errors'
import { useToast } from '@/shared/ui/toast'

type RegisterFieldErrors = {
  nombre?: string
  apellido?: string
  email?: string
  password?: string
}

export default function RegisterPage() {
  const navigate = useNavigate()
  const { toast } = useToast()
  const [fieldErrors, setFieldErrors] = useState<RegisterFieldErrors>({})
  const [submitting, setSubmitting] = useState(false)

  const form = useForm({
    defaultValues: {
      nombre: '',
      apellido: '',
      email: '',
      password: '',
    },
    onSubmit: async ({ value }) => {
      setFieldErrors({})
      setSubmitting(true)
      try {
        await http.post(AUTH_REGISTER, value)
        toast({
          variant: 'success',
          title: 'Cuenta creada',
          description: 'Iniciá sesión para continuar.',
        })
        navigate('/login', {
          replace: true,
          state: { justRegistered: true },
        })
      } catch (err) {
        const norm = normalizeError(err)
        if (norm.status === 409) {
          setFieldErrors({ email: 'Ya existe un usuario con ese email' })
        } else if (norm.status === 422 && norm.fieldErrors) {
          const fe: RegisterFieldErrors = {}
          for (const [k, msgs] of Object.entries(norm.fieldErrors)) {
            const first = msgs[0]
            if (!first) continue
            if (k === 'nombre' || k === 'apellido' || k === 'email' || k === 'password') {
              fe[k] = first
            }
          }
          if (Object.keys(fe).length > 0) {
            setFieldErrors(fe)
          } else {
            toast({ variant: 'error', title: 'Error al crear cuenta', description: 'Datos inválidos. Revisá los campos.' })
          }
        } else if (norm.status === 429) {
          toast({ variant: 'error', title: 'Error al crear cuenta', description: 'Demasiados intentos. Esperá unos minutos.' })
        } else {
          toast({ variant: 'error', title: 'Error al crear cuenta', description: 'No pudimos crear la cuenta. Intentá nuevamente.' })
        }
      } finally {
        setSubmitting(false)
      }
    },
  })

  return (
    <div className="flex min-h-screen items-center justify-center bg-gray-50 px-4 py-8">
      <div className="w-full max-w-md rounded-lg bg-white p-8 shadow">
        <h1 className="mb-6 text-2xl font-semibold text-gray-900">Crear cuenta</h1>

        <form
          onSubmit={(e) => {
            e.preventDefault()
            e.stopPropagation()
            void form.handleSubmit()
          }}
          noValidate
        >
          <form.Field
            name="nombre"
            validators={{
              onChange: ({ value }) => (value.trim() ? undefined : 'El nombre es obligatorio'),
            }}
          >
            {(field) => (
              <div className="mb-4">
                <label htmlFor="nombre" className="mb-1 block text-sm font-medium text-gray-700">
                  Nombre
                </label>
                <input
                  id="nombre"
                  type="text"
                  autoComplete="given-name"
                  aria-label="Nombre"
                  value={field.state.value}
                  onChange={(e) => {
                    field.handleChange(e.target.value)
                    if (fieldErrors.nombre) setFieldErrors((s) => ({ ...s, nombre: undefined }))
                  }}
                  onBlur={field.handleBlur}
                  className="h-11 w-full rounded border border-gray-300 px-3 py-2 focus:border-red-600 focus:outline-none"
                />
                {(field.state.meta.errors[0] || fieldErrors.nombre) && (
                  <p className="mt-1 text-sm text-red-500" role="alert">
                    {String(field.state.meta.errors[0] ?? fieldErrors.nombre)}
                  </p>
                )}
              </div>
            )}
          </form.Field>

          <form.Field
            name="apellido"
            validators={{
              onChange: ({ value }) => (value.trim() ? undefined : 'El apellido es obligatorio'),
            }}
          >
            {(field) => (
              <div className="mb-4">
                <label htmlFor="apellido" className="mb-1 block text-sm font-medium text-gray-700">
                  Apellido
                </label>
                <input
                  id="apellido"
                  type="text"
                  autoComplete="family-name"
                  aria-label="Apellido"
                  value={field.state.value}
                  onChange={(e) => {
                    field.handleChange(e.target.value)
                    if (fieldErrors.apellido) setFieldErrors((s) => ({ ...s, apellido: undefined }))
                  }}
                  onBlur={field.handleBlur}
                  className="h-11 w-full rounded border border-gray-300 px-3 py-2 focus:border-red-600 focus:outline-none"
                />
                {(field.state.meta.errors[0] || fieldErrors.apellido) && (
                  <p className="mt-1 text-sm text-red-500" role="alert">
                    {String(field.state.meta.errors[0] ?? fieldErrors.apellido)}
                  </p>
                )}
              </div>
            )}
          </form.Field>

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
                  onChange={(e) => {
                    field.handleChange(e.target.value)
                    if (fieldErrors.email) setFieldErrors((s) => ({ ...s, email: undefined }))
                  }}
                  onBlur={field.handleBlur}
                  className="h-11 w-full rounded border border-gray-300 px-3 py-2 focus:border-red-600 focus:outline-none"
                />
                {(field.state.meta.errors[0] || fieldErrors.email) && (
                  <p className="mt-1 text-sm text-red-500" role="alert">
                    {String(field.state.meta.errors[0] ?? fieldErrors.email)}
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
                if (value.length < 8) return 'Mínimo 8 caracteres'
                return undefined
              },
            }}
          >
            {(field) => (
              <div className="mb-6">
                <label htmlFor="password" className="mb-1 block text-sm font-medium text-gray-700">
                  Contraseña (mínimo 8 caracteres)
                </label>
                <input
                  id="password"
                  type="password"
                  autoComplete="new-password"
                  aria-label="Contraseña"
                  value={field.state.value}
                  onChange={(e) => {
                    field.handleChange(e.target.value)
                    if (fieldErrors.password) setFieldErrors((s) => ({ ...s, password: undefined }))
                  }}
                  onBlur={field.handleBlur}
                  className="h-11 w-full rounded border border-gray-300 px-3 py-2 focus:border-red-600 focus:outline-none"
                />
                {(field.state.meta.errors[0] || fieldErrors.password) && (
                  <p className="mt-1 text-sm text-red-500" role="alert">
                    {String(field.state.meta.errors[0] ?? fieldErrors.password)}
                  </p>
                )}
              </div>
            )}
          </form.Field>

          <button
            type="submit"
            disabled={submitting}
            className="min-h-[44px] w-full rounded bg-red-600 px-4 py-2 font-medium text-white hover:bg-red-700 disabled:cursor-not-allowed disabled:opacity-50"
            aria-label="Crear cuenta"
          >
            {submitting ? 'Creando cuenta…' : 'Crear cuenta'}
          </button>
        </form>

        <p className="mt-6 text-center text-sm text-gray-600">
          ¿Ya tenés cuenta?{' '}
          <Link to="/login" className="font-medium text-red-600 hover:underline">
            Iniciar sesión
          </Link>
        </p>
      </div>
    </div>
  )
}
