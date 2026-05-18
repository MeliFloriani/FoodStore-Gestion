import { describe, it, expect, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { RoleGuard } from '../RoleGuard'
import { useAuthStore } from '@/entities/auth/model/store'
import type { User } from '@/entities/auth/types'

const mockClientUser: User = {
  id: '550e8400-e29b-41d4-a716-446655440000',
  nombre: 'Test',
  apellido: 'User',
  email: 'test@example.com',
  roles: ['CLIENT'],
}

const mockAdminUser: User = {
  id: '550e8400-e29b-41d4-a716-446655440001',
  nombre: 'Admin',
  apellido: 'User',
  email: 'admin@example.com',
  roles: ['ADMIN'],
}

function renderRoleGuard(initialPath: string = '/admin') {
  return render(
    <MemoryRouter initialEntries={[initialPath]}>
      <Routes>
        <Route element={<RoleGuard roles={['ADMIN']} />}>
          <Route path="/admin" element={<div>Admin Content</div>} />
        </Route>
        <Route path="/login" element={<div>Login Page</div>} />
        <Route path="/403" element={<div>Forbidden Page</div>} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('RoleGuard', () => {
  beforeEach(() => {
    useAuthStore.getState().clear()
  })

  it('shows loading spinner when status is idle', () => {
    useAuthStore.setState({ status: 'idle' })
    renderRoleGuard()
    expect(screen.getByRole('status', { name: /loading/i })).toBeInTheDocument()
    expect(screen.queryByText('Admin Content')).not.toBeInTheDocument()
  })

  it('redirects unauthenticated user to /login', () => {
    useAuthStore.setState({ status: 'unauthenticated' })
    renderRoleGuard()
    expect(screen.getByText('Login Page')).toBeInTheDocument()
    expect(screen.queryByText('Admin Content')).not.toBeInTheDocument()
  })

  it('redirects authenticated user with wrong role to /403', () => {
    useAuthStore.setState({ status: 'authenticated', user: mockClientUser })
    renderRoleGuard()
    expect(screen.getByText('Forbidden Page')).toBeInTheDocument()
    expect(screen.queryByText('Admin Content')).not.toBeInTheDocument()
  })

  it('renders outlet when authenticated user has correct role', () => {
    useAuthStore.setState({ status: 'authenticated', user: mockAdminUser })
    renderRoleGuard()
    expect(screen.getByText('Admin Content')).toBeInTheDocument()
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
  })
})
