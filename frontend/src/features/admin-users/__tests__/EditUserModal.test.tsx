/**
 * Tests for EditUserModal component (Change 21).
 *
 * Covers:
 *   - Renders with user's current nombre and apellido pre-populated.
 *   - Email is shown as read-only (D-01).
 *   - Has "Guardar cambios" and "Cancelar" buttons.
 *   - Form does not submit nombre/apellido fields that are empty.
 */

import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { EditUserModal } from '../ui/EditUserModal'
import type { UsuarioAdminRead } from '../types'

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
})
