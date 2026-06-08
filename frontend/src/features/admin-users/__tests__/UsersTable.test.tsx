/**
 * Unit tests for UsersTable component (Change 21).
 *
 * Covers:
 *   - Renders skeleton rows when isLoading=true.
 *   - Renders users when isLoading=false.
 *   - Active user shows "Activo" badge and "Desactivar" button.
 *   - Inactive user shows "Inactivo" badge and no "Desactivar" button.
 *   - Action handlers are called with the correct user.
 *   - OQ-02: No "Reactivar" button anywhere.
 */

import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { UsersTable } from '../ui/UsersTable'
import type { UsuarioAdminRead } from '../types'

const activeUser: UsuarioAdminRead = {
  id: 'user-1',
  email: 'active@example.com',
  nombre: 'Ana',
  apellido: 'García',
  created_at: '2024-01-15T10:00:00Z',
  deleted_at: null,
  roles: [{ id: 'rol-1', codigo: 'ADMIN', nombre: 'Admin' }],
}

const inactiveUser: UsuarioAdminRead = {
  id: 'user-2',
  email: 'inactive@example.com',
  nombre: 'Juan',
  apellido: 'Pérez',
  created_at: '2024-01-10T08:00:00Z',
  deleted_at: '2024-06-01T12:00:00Z',
  roles: [{ id: 'rol-2', codigo: 'CLIENT', nombre: 'Client' }],
}

describe('UsersTable', () => {
  it('renders skeleton rows when isLoading=true', () => {
    const { container } = render(
      <UsersTable
        users={[]}
        isLoading={true}
        onEditData={vi.fn()}
        onEditRoles={vi.fn()}
        onDeactivate={vi.fn()}
      />,
    )
    // animate-pulse elements indicate skeletons
    const pulseElements = container.querySelectorAll('.animate-pulse')
    expect(pulseElements.length).toBeGreaterThan(0)
  })

  it('shows no actual data rows when isLoading=true', () => {
    render(
      <UsersTable
        users={[activeUser]}
        isLoading={true}
        onEditData={vi.fn()}
        onEditRoles={vi.fn()}
        onDeactivate={vi.fn()}
      />,
    )
    // The user's email should not appear during loading
    expect(screen.queryByText('active@example.com')).not.toBeInTheDocument()
  })

  it('renders user data when isLoading=false', () => {
    render(
      <UsersTable
        users={[activeUser]}
        isLoading={false}
        onEditData={vi.fn()}
        onEditRoles={vi.fn()}
        onDeactivate={vi.fn()}
      />,
    )
    expect(screen.getByText('active@example.com')).toBeInTheDocument()
    expect(screen.getByText('Ana García')).toBeInTheDocument()
  })

  it('shows "Activo" badge for active user', () => {
    render(
      <UsersTable
        users={[activeUser]}
        isLoading={false}
        onEditData={vi.fn()}
        onEditRoles={vi.fn()}
        onDeactivate={vi.fn()}
      />,
    )
    expect(screen.getByText('Activo')).toBeInTheDocument()
  })

  it('shows "Inactivo" badge for inactive user', () => {
    render(
      <UsersTable
        users={[inactiveUser]}
        isLoading={false}
        onEditData={vi.fn()}
        onEditRoles={vi.fn()}
        onDeactivate={vi.fn()}
      />,
    )
    expect(screen.getByText('Inactivo')).toBeInTheDocument()
  })

  it('shows "Desactivar" button only for active users', () => {
    render(
      <UsersTable
        users={[activeUser]}
        isLoading={false}
        onEditData={vi.fn()}
        onEditRoles={vi.fn()}
        onDeactivate={vi.fn()}
      />,
    )
    expect(screen.getByText('Desactivar')).toBeInTheDocument()
  })

  it('does NOT show "Desactivar" button for inactive users (OQ-02)', () => {
    render(
      <UsersTable
        users={[inactiveUser]}
        isLoading={false}
        onEditData={vi.fn()}
        onEditRoles={vi.fn()}
        onDeactivate={vi.fn()}
      />,
    )
    expect(screen.queryByText('Desactivar')).not.toBeInTheDocument()
  })

  it('does NOT expose any "Reactivar" button (OQ-02 CLOSED)', () => {
    render(
      <UsersTable
        users={[inactiveUser, activeUser]}
        isLoading={false}
        onEditData={vi.fn()}
        onEditRoles={vi.fn()}
        onDeactivate={vi.fn()}
      />,
    )
    expect(screen.queryByText('Reactivar')).not.toBeInTheDocument()
  })

  it('calls onEditData with the correct user', () => {
    const onEditData = vi.fn()
    render(
      <UsersTable
        users={[activeUser]}
        isLoading={false}
        onEditData={onEditData}
        onEditRoles={vi.fn()}
        onDeactivate={vi.fn()}
      />,
    )
    fireEvent.click(screen.getByText('Editar datos'))
    expect(onEditData).toHaveBeenCalledWith(activeUser)
  })

  it('calls onEditRoles with the correct user', () => {
    const onEditRoles = vi.fn()
    render(
      <UsersTable
        users={[activeUser]}
        isLoading={false}
        onEditData={vi.fn()}
        onEditRoles={onEditRoles}
        onDeactivate={vi.fn()}
      />,
    )
    fireEvent.click(screen.getByText('Editar roles'))
    expect(onEditRoles).toHaveBeenCalledWith(activeUser)
  })

  it('calls onDeactivate with the correct user', () => {
    const onDeactivate = vi.fn()
    render(
      <UsersTable
        users={[activeUser]}
        isLoading={false}
        onEditData={vi.fn()}
        onEditRoles={vi.fn()}
        onDeactivate={onDeactivate}
      />,
    )
    fireEvent.click(screen.getByText('Desactivar'))
    expect(onDeactivate).toHaveBeenCalledWith(activeUser)
  })

  it('renders role badges', () => {
    render(
      <UsersTable
        users={[activeUser]}
        isLoading={false}
        onEditData={vi.fn()}
        onEditRoles={vi.fn()}
        onDeactivate={vi.fn()}
      />,
    )
    expect(screen.getByText('ADMIN')).toBeInTheDocument()
  })
})
