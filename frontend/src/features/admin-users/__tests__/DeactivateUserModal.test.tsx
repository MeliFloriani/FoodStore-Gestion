import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { DeactivateUserModal } from '../ui/DeactivateUserModal'
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
  id: 'user-admin-1',
  email: 'admin@foodstore.com',
  nombre: 'Carlos',
  apellido: 'López',
  created_at: '2024-01-01T00:00:00Z',
  deleted_at: null,
  roles: [{ id: 'rol-1', codigo: 'ADMIN', nombre: 'Admin' }],
}

function renderWithQuery(component: React.ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  return render(
    <QueryClientProvider client={queryClient}>{component}</QueryClientProvider>,
  )
}

describe('DeactivateUserModal', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('shows user name and email', () => {
    renderWithQuery(
      <DeactivateUserModal user={testUser} onClose={vi.fn()} onSuccess={vi.fn()} />,
    )
    expect(screen.getByText('Carlos López')).toBeInTheDocument()
    expect(screen.getByText('admin@foodstore.com')).toBeInTheDocument()
  })

  it('shows warning text mentioning the user name', () => {
    renderWithQuery(
      <DeactivateUserModal user={testUser} onClose={vi.fn()} onSuccess={vi.fn()} />,
    )
    expect(screen.getAllByText(/Carlos/).length).toBeGreaterThan(0)
    expect(screen.getByText(/pedidos históricos no serán afectados/i)).toBeInTheDocument()
  })

  it('renders "Cancelar" and "Desactivar" buttons', () => {
    renderWithQuery(
      <DeactivateUserModal user={testUser} onClose={vi.fn()} onSuccess={vi.fn()} />,
    )
    expect(screen.getByRole('button', { name: /cancelar/i })).toBeInTheDocument()
    expect(screen.getByText('Desactivar')).toBeInTheDocument()
  })

  it('does NOT render a "Reactivar" button (OQ-02 CLOSED)', () => {
    renderWithQuery(
      <DeactivateUserModal user={testUser} onClose={vi.fn()} onSuccess={vi.fn()} />,
    )
    expect(screen.queryByRole('button', { name: /reactivar/i })).not.toBeInTheDocument()
    expect(screen.queryByText(/reactivar/i)).not.toBeInTheDocument()
  })

  it('calls onClose when "Cancelar" is clicked', () => {
    const onClose = vi.fn()
    renderWithQuery(
      <DeactivateUserModal user={testUser} onClose={onClose} onSuccess={vi.fn()} />,
    )
    const cancelBtn = screen.getByRole('button', { name: /cancelar/i })
    fireEvent.click(cancelBtn)
    expect(onClose).toHaveBeenCalledOnce()
  })

  it('has accessible dialog role', () => {
    renderWithQuery(
      <DeactivateUserModal user={testUser} onClose={vi.fn()} onSuccess={vi.fn()} />,
    )
    expect(screen.getByRole('dialog')).toBeInTheDocument()
  })

  it('calls mutation with activo=false on confirm and calls onSuccess', async () => {
    vi.mocked(http.patch).mockResolvedValue({ data: testUser })
    const onClose = vi.fn()
    const onSuccess = vi.fn()
    renderWithQuery(
      <DeactivateUserModal user={testUser} onClose={onClose} onSuccess={onSuccess} />,
    )

    fireEvent.click(screen.getByRole('button', { name: /confirmar desactivación/i }))

    await waitFor(() => {
      expect(onSuccess).toHaveBeenCalledOnce()
    })
    expect(onClose).toHaveBeenCalledOnce()
    expect(vi.mocked(http.patch)).toHaveBeenCalledWith(
      expect.stringContaining('/admin/usuarios/user-admin-1/estado'),
      { activo: false },
    )
  })

  it('shows inline error on LAST_ADMIN_PROTECTED', async () => {
    vi.mocked(http.patch).mockRejectedValue({
      response: { data: { code: 'LAST_ADMIN_PROTECTED' } },
    })
    const onClose = vi.fn()
    const onSuccess = vi.fn()
    renderWithQuery(
      <DeactivateUserModal user={testUser} onClose={onClose} onSuccess={onSuccess} />,
    )

    fireEvent.click(screen.getByRole('button', { name: /confirmar desactivación/i }))

    await waitFor(() => {
      expect(screen.getByText(/último administrador/i)).toBeInTheDocument()
    })
    expect(onSuccess).not.toHaveBeenCalled()
    expect(onClose).not.toHaveBeenCalled()
  })

  it('shows Desactivando... when mutation is pending', async () => {
    vi.mocked(http.patch).mockImplementation(() => new Promise(() => {}))
    renderWithQuery(
      <DeactivateUserModal user={testUser} onClose={vi.fn()} onSuccess={vi.fn()} />,
    )

    fireEvent.click(screen.getByRole('button', { name: /confirmar desactivación/i }))

    expect(await screen.findByText('Desactivando...')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /cancelar/i })).toBeDisabled()
  })
})
