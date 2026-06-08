/**
 * Tests for EditUserRolesModal component (Change 21).
 *
 * Covers:
 *   - Pre-checks the user's currently assigned roles.
 *   - Shows all 4 role checkboxes.
 *   - Shows validation error when no roles selected.
 *   - Renders submit and cancel buttons.
 *   - Has accessible dialog.
 */

import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { EditUserRolesModal } from '../ui/EditUserRolesModal'
import type { UsuarioAdminRead } from '../types'

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
    // Deselect all roles
    fireEvent.click(screen.getByRole('checkbox', { name: /ADMIN/i }))
    fireEvent.click(screen.getByRole('checkbox', { name: /CLIENT/i }))

    // Attempt to submit
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
})
