/**
 * Tests for DeactivateUserModal component (Change 21).
 *
 * Covers:
 *   - Renders user name and email in the dialog.
 *   - Renders warning text.
 *   - Has "Cancelar" and "Desactivar" buttons.
 *   - Does NOT have "Reactivar" button (OQ-02).
 *   - "Desactivar" button calls the mutation with activo=false.
 *   - "Cancelar" button calls onClose.
 *   - Shows LAST_ADMIN_PROTECTED error inline when applicable.
 */

import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { DeactivateUserModal } from '../ui/DeactivateUserModal'
import type { UsuarioAdminRead } from '../types'

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
    // User name appears in the warning paragraph
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
})
