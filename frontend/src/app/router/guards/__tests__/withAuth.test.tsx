import { describe, it, expect, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { withAuth } from '../withAuth'
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

type AdminPageProps = { title?: string }

function AdminPageComponent({ title = 'Admin Content' }: AdminPageProps) {
  return <div>{title}</div>
}

const ProtectedAdminPage = withAuth(AdminPageComponent, ['ADMIN'])

function renderWithAuth(initialPath: string = '/admin') {
  return render(
    <MemoryRouter initialEntries={[initialPath]}>
      <Routes>
        <Route path="/admin" element={<ProtectedAdminPage />} />
        <Route path="/login" element={<div>Login Page</div>} />
        <Route path="/403" element={<div>Forbidden Page</div>} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('withAuth HOC', () => {
  beforeEach(() => {
    useAuthStore.getState().clear()
  })

  it('shows loading spinner when status is idle', () => {
    useAuthStore.setState({ status: 'idle' })
    renderWithAuth()
    expect(screen.getByRole('status', { name: /loading/i })).toBeInTheDocument()
    expect(screen.queryByText('Admin Content')).not.toBeInTheDocument()
  })

  it('redirects unauthenticated user to /login', () => {
    useAuthStore.setState({ status: 'unauthenticated' })
    renderWithAuth()
    expect(screen.getByText('Login Page')).toBeInTheDocument()
    expect(screen.queryByText('Admin Content')).not.toBeInTheDocument()
  })

  it('redirects authenticated user with wrong role to /403', () => {
    useAuthStore.setState({ status: 'authenticated', user: mockClientUser })
    renderWithAuth()
    expect(screen.getByText('Forbidden Page')).toBeInTheDocument()
    expect(screen.queryByText('Admin Content')).not.toBeInTheDocument()
  })

  it('renders component when authenticated user has correct role', () => {
    useAuthStore.setState({ status: 'authenticated', user: mockAdminUser })
    renderWithAuth()
    expect(screen.getByText('Admin Content')).toBeInTheDocument()
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
  })

  it('forwards props to the wrapped component', () => {
    useAuthStore.setState({ status: 'authenticated', user: mockAdminUser })
    render(
      <MemoryRouter>
        <Routes>
          <Route path="/" element={<ProtectedAdminPage title="Custom Title" />} />
          <Route path="/login" element={<div>Login Page</div>} />
          <Route path="/403" element={<div>Forbidden Page</div>} />
        </Routes>
      </MemoryRouter>,
    )
    expect(screen.getByText('Custom Title')).toBeInTheDocument()
  })

  it('sets displayName on the wrapped component', () => {
    expect(ProtectedAdminPage.displayName).toBe('withAuth(AdminPageComponent)')
  })
})
