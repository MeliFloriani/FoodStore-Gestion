import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { EditUserModal } from '../ui/EditUserModal'
import { http } from '@/shared/api/http'
import type { UsuarioAdminRead } from '../types'

vi.mock('@/shared/api/http', () => ({
  http: {
    patch: vi.fn(),
    put: vi.fn(),
    post: vi.fn(),
    get: vi.fn(),
    delete: vi.fn(),
  },
}))

const testUser: UsuarioAdminRead = {
  id: 'user-1',
  email: 'user@example.com',
  nombre: 'María',
  apellido: 'Fernández',
  created_at: '2024-01-01T00:00:00Z',
  deleted_at: null,
  roles: [{ id: 'rol-1', codigo: 'CLIENT', nombre: 'Client' }],
}

function renderWithQuery(component: React.ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  return render(
    <QueryClientProvider client={queryClient}>{component}</QueryClientProvider>,
  )
}

describe('EditUserModal', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('pre-populates nombre and apellido fields', () => {
    renderWithQuery(
      <EditUserModal user={testUser} onClose={vi.fn()} onSuccess={vi.fn()} />,
    )
    expect(screen.getByDisplayValue('María')).toBeInTheDocument()
    expect(screen.getByDisplayValue('Fernández')).toBeInTheDocument()
  })

  it('displays email as read-only (D-01)', () => {
    renderWithQuery(
      <EditUserModal user={testUser} onClose={vi.fn()} onSuccess={vi.fn()} />,
    )
    const emailInput = screen.getByDisplayValue('user@example.com')
    expect(emailInput).toBeDisabled()
  })

  it('renders submit and cancel buttons', () => {
    renderWithQuery(
      <EditUserModal user={testUser} onClose={vi.fn()} onSuccess={vi.fn()} />,
    )
    expect(screen.getByRole('button', { name: /guardar cambios/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /cancelar/i })).toBeInTheDocument()
  })

  it('has accessible dialog role', () => {
    renderWithQuery(
      <EditUserModal user={testUser} onClose={vi.fn()} onSuccess={vi.fn()} />,
    )
    expect(screen.getByRole('dialog')).toBeInTheDocument()
  })

  it('calls onClose when Cancelar is clicked', () => {
    const onClose = vi.fn()
    renderWithQuery(
      <EditUserModal user={testUser} onClose={onClose} onSuccess={vi.fn()} />,
    )
    screen.getByRole('button', { name: /cancelar/i }).click()
    expect(onClose).toHaveBeenCalledOnce()
  })

  it('submits form and calls onSuccess', async () => {
    vi.mocked(http.put).mockResolvedValue({ data: testUser })
    const onClose = vi.fn()
    const onSuccess = vi.fn()
    renderWithQuery(
      <EditUserModal user={testUser} onClose={onClose} onSuccess={onSuccess} />,
    )

    fireEvent.click(screen.getByRole('button', { name: /guardar cambios/i }))

    await waitFor(() => {
      expect(onSuccess).toHaveBeenCalledOnce()
    })
    expect(onClose).toHaveBeenCalledOnce()
  })

  it('shows validation error when nombre is empty', async () => {
    renderWithQuery(
      <EditUserModal user={testUser} onClose={vi.fn()} onSuccess={vi.fn()} />,
    )

    const nombreInput = screen.getByLabelText(/nombre del usuario/i)
    fireEvent.change(nombreInput, { target: { value: '' } })
    fireEvent.blur(nombreInput)

    expect(await screen.findByText(/el nombre es requerido/i)).toBeInTheDocument()
  })

  it('shows validation error when apellido is too long', async () => {
    renderWithQuery(
      <EditUserModal user={testUser} onClose={vi.fn()} onSuccess={vi.fn()} />,
    )

    const apellidoInput = screen.getByLabelText(/apellido del usuario/i)
    fireEvent.change(apellidoInput, { target: { value: 'a'.repeat(81) } })
    fireEvent.blur(apellidoInput)

    expect(await screen.findByText(/no puede superar 80 caracteres/i)).toBeInTheDocument()
  })

  it('shows serverError on mutation error', async () => {
    vi.mocked(http.put).mockRejectedValue(new Error('Network error'))
    renderWithQuery(
      <EditUserModal user={testUser} onClose={vi.fn()} onSuccess={vi.fn()} />,
    )

    fireEvent.click(screen.getByRole('button', { name: /guardar cambios/i }))

    await waitFor(() => {
      expect(screen.getByText(/error al actualizar/i)).toBeInTheDocument()
    })
  })

  it('shows Guardando... when mutation is pending', async () => {
    vi.mocked(http.put).mockImplementation(() => new Promise(() => {}))
    renderWithQuery(
      <EditUserModal user={testUser} onClose={vi.fn()} onSuccess={vi.fn()} />,
    )

    fireEvent.click(screen.getByRole('button', { name: /guardar cambios/i }))

    expect(await screen.findByText('Guardando...')).toBeInTheDocument()
    const submitBtn = screen.getByText('Guardando...').closest('button')
    expect(submitBtn).toBeDisabled()
  })
})
