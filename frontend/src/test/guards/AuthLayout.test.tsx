import { describe, it, expect, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { AuthLayout } from '@/app/layouts/AuthLayout'
import { useAuthStore } from '@/entities/auth/model/store'
import type { User } from '@/entities/auth/types'

const mockUser: User = {
  id: 1,
  nombre: 'Test User',
  email: 'test@example.com',
  roles: ['CLIENT'],
}

function renderAuthLayout() {
  return render(
    <MemoryRouter initialEntries={['/login']}>
      <Routes>
        <Route element={<AuthLayout />}>
          <Route path="/login" element={<div>Login Content</div>} />
        </Route>
        <Route path="/" element={<div>Home Page</div>} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('AuthLayout', () => {
  beforeEach(() => {
    useAuthStore.getState().clear()
  })

  it('shows loading spinner when status is idle', () => {
    useAuthStore.setState({ status: 'idle' })
    renderAuthLayout()
    expect(screen.getByRole('status', { name: /loading/i })).toBeInTheDocument()
    expect(screen.queryByText('Login Content')).not.toBeInTheDocument()
  })

  it('renders login content when unauthenticated', () => {
    useAuthStore.setState({ status: 'unauthenticated' })
    renderAuthLayout()
    expect(screen.getByText('Login Content')).toBeInTheDocument()
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
  })

  it('redirects to / when authenticated', () => {
    useAuthStore.getState().login('token', 'refresh', mockUser)
    renderAuthLayout()
    expect(screen.getByText('Home Page')).toBeInTheDocument()
    expect(screen.queryByText('Login Content')).not.toBeInTheDocument()
  })
})
