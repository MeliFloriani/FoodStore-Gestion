import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { EditUserRolesModal } from '../ui/EditUserRolesModal'
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

const adminUser: UsuarioAdminRead = {
  id: 'user-admin-1',
  email: 'admin@foodstore.com',
  nombre: 'Carlos',
  apellido: 'López',
  created_at: '2024-01-01T00:00:00Z',
  deleted_at: null,
  roles: [
    { id: 'rol-admin', codigo: 'ADMIN', nombre: 'Admin' },
    { id: 'rol-client', codigo: 'CLIENT', nombre: 'Client' },
  ],
}

function renderWithQuery(component: React.ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  return render(
    <QueryClientProvider client={queryClient}>{component}</QueryClientProvider>,
  )
}

describe('EditUserRolesModal', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('pre-checks current user roles', () => {
    renderWithQuery(
      <EditUserRolesModal user={adminUser} onClose={vi.fn()} onSuccess={vi.fn()} />,
    )
    const adminCheckbox = screen.getByRole('checkbox', { name: /ADMIN/i })
    const clientCheckbox = screen.getByRole('checkbox', { name: /CLIENT/i })
    const stockCheckbox = screen.getByRole('checkbox', { name: /STOCK/i })

    expect(adminCheckbox).toBeChecked()
    expect(clientCheckbox).toBeChecked()
    expect(stockCheckbox).not.toBeChecked()
  })

  it('renders checkboxes for all 4 roles', () => {
    renderWithQuery(
      <EditUserRolesModal user={adminUser} onClose={vi.fn()} onSuccess={vi.fn()} />,
    )
    expect(screen.getByRole('checkbox', { name: /ADMIN/i })).toBeInTheDocument()
    expect(screen.getByRole('checkbox', { name: /STOCK/i })).toBeInTheDocument()
    expect(screen.getByRole('checkbox', { name: /PEDIDOS/i })).toBeInTheDocument()
    expect(screen.getByRole('checkbox', { name: /CLIENT/i })).toBeInTheDocument()
  })

  it('shows validation error when all roles are deselected', () => {
    renderWithQuery(
      <EditUserRolesModal user={adminUser} onClose={vi.fn()} onSuccess={vi.fn()} />,
    )
    fireEvent.click(screen.getByRole('checkbox', { name: /ADMIN/i }))
    fireEvent.click(screen.getByRole('checkbox', { name: /CLIENT/i }))

    fireEvent.click(screen.getByRole('button', { name: /guardar roles/i }))

    expect(screen.getByText(/debe seleccionar al menos un rol/i)).toBeInTheDocument()
  })

  it('renders submit and cancel buttons', () => {
    renderWithQuery(
      <EditUserRolesModal user={adminUser} onClose={vi.fn()} onSuccess={vi.fn()} />,
    )
    expect(screen.getByRole('button', { name: /guardar roles/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /cancelar/i })).toBeInTheDocument()
  })

  it('has accessible dialog role', () => {
    renderWithQuery(
      <EditUserRolesModal user={adminUser} onClose={vi.fn()} onSuccess={vi.fn()} />,
    )
    expect(screen.getByRole('dialog')).toBeInTheDocument()
  })

  it('calls onClose when Cancelar is clicked', () => {
    const onClose = vi.fn()
    renderWithQuery(
      <EditUserRolesModal user={adminUser} onClose={onClose} onSuccess={vi.fn()} />,
    )
    fireEvent.click(screen.getByRole('button', { name: /cancelar/i }))
    expect(onClose).toHaveBeenCalledOnce()
  })

  it('toggles a role on and off', () => {
    renderWithQuery(
      <EditUserRolesModal user={adminUser} onClose={vi.fn()} onSuccess={vi.fn()} />,
    )
    const stockCheckbox = screen.getByRole('checkbox', { name: /STOCK/i })
    expect(stockCheckbox).not.toBeChecked()

    fireEvent.click(stockCheckbox)
    expect(stockCheckbox).toBeChecked()

    fireEvent.click(stockCheckbox)
    expect(stockCheckbox).not.toBeChecked()
  })

  it('submits valid roles and calls onSuccess', async () => {
    vi.mocked(http.put).mockResolvedValue({ data: adminUser })
    const onClose = vi.fn()
    const onSuccess = vi.fn()
    renderWithQuery(
      <EditUserRolesModal user={adminUser} onClose={onClose} onSuccess={onSuccess} />,
    )

    fireEvent.click(screen.getByRole('button', { name: /guardar roles/i }))

    await waitFor(() => {
      expect(onSuccess).toHaveBeenCalledOnce()
    })
    expect(onClose).toHaveBeenCalledOnce()
  })

  it('shows LAST_ADMIN_PROTECTED error inline', async () => {
    vi.mocked(http.put).mockRejectedValue({
      response: { data: { code: 'LAST_ADMIN_PROTECTED' } },
    })
    const onClose = vi.fn()
    const onSuccess = vi.fn()
    renderWithQuery(
      <EditUserRolesModal user={adminUser} onClose={onClose} onSuccess={onSuccess} />,
    )

    fireEvent.click(screen.getByRole('button', { name: /guardar roles/i }))

    await waitFor(() => {
      expect(screen.getByText(/único administrador/i)).toBeInTheDocument()
    })
    expect(onSuccess).not.toHaveBeenCalled()
    expect(onClose).not.toHaveBeenCalled()
  })

  it('shows Guardando... when mutation is pending', async () => {
    vi.mocked(http.put).mockImplementation(() => new Promise(() => {}))
    renderWithQuery(
      <EditUserRolesModal user={adminUser} onClose={vi.fn()} onSuccess={vi.fn()} />,
    )

    fireEvent.click(screen.getByRole('button', { name: /guardar roles/i }))

    expect(await screen.findByText('Guardando...')).toBeInTheDocument()
    const submitBtn = screen.getByText('Guardando...').closest('button')
    expect(submitBtn).toBeDisabled()
  })

  it('clears validation error when a role is toggled', () => {
    renderWithQuery(
      <EditUserRolesModal user={adminUser} onClose={vi.fn()} onSuccess={vi.fn()} />,
    )
    fireEvent.click(screen.getByRole('checkbox', { name: /ADMIN/i }))
    fireEvent.click(screen.getByRole('checkbox', { name: /CLIENT/i }))
    fireEvent.click(screen.getByRole('button', { name: /guardar roles/i }))
    expect(screen.getByText(/debe seleccionar al menos un rol/i)).toBeInTheDocument()

    fireEvent.click(screen.getByRole('checkbox', { name: /STOCK/i }))
    expect(screen.queryByText(/debe seleccionar al menos un rol/i)).not.toBeInTheDocument()
  })
})
