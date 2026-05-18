import { describe, it, expect, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { AuthLayout } from '../AuthLayout'
import { useAuthStore } from '@/entities/auth/model/store'
import type { User } from '@/entities/auth/types'

function makeUser(roles: string[]): User {
  return {
    id: '550e8400-e29b-41d4-a716-446655440000',
    nombre: 'Test',
    apellido: 'User',
    email: 'test@example.com',
    roles,
  }
}

function renderAuthLayout(initialPath = '/login') {
  return render(
    <MemoryRouter initialEntries={[initialPath]}>
      <Routes>
        <Route element={<AuthLayout />}>
          <Route path="/login" element={<div>Login Content</div>} />
        </Route>
        <Route path="/catalog" element={<div>Catalog Page</div>} />
        <Route path="/admin" element={<div>Admin Page</div>} />
        <Route path="/stock/products" element={<div>Stock Page</div>} />
        <Route path="/pedidos-panel" element={<div>Pedidos Page</div>} />
      </Routes>
    </MemoryRouter>,
  )
}

function renderAuthLayoutWithFrom(from: string) {
  return render(
    <MemoryRouter initialEntries={[{ pathname: '/login', state: { from } }]}>
      <Routes>
        <Route element={<AuthLayout />}>
          <Route path="/login" element={<div>Login Content</div>} />
        </Route>
        <Route path="/catalog" element={<div>Catalog Page</div>} />
        <Route path="/stock/products" element={<div>Stock Page</div>} />
        <Route path="/admin" element={<div>Admin Page</div>} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('AuthLayout — post-login redirects', () => {
  beforeEach(() => {
    useAuthStore.getState().clear()
  })

  it('(a) CLIENT login redirects to /catalog', () => {
    useAuthStore.setState({ status: 'authenticated', user: makeUser(['CLIENT']) })
    renderAuthLayout()
    expect(screen.getByText('Catalog Page')).toBeInTheDocument()
    expect(screen.queryByText('Login Content')).not.toBeInTheDocument()
  })

  it('(b) ADMIN login redirects to /admin', () => {
    useAuthStore.setState({ status: 'authenticated', user: makeUser(['ADMIN']) })
    renderAuthLayout()
    expect(screen.getByText('Admin Page')).toBeInTheDocument()
    expect(screen.queryByText('Login Content')).not.toBeInTheDocument()
  })

  it('(c) STOCK login redirects to /stock/products', () => {
    useAuthStore.setState({ status: 'authenticated', user: makeUser(['STOCK']) })
    renderAuthLayout()
    expect(screen.getByText('Stock Page')).toBeInTheDocument()
    expect(screen.queryByText('Login Content')).not.toBeInTheDocument()
  })

  it('(d) PEDIDOS login redirects to /pedidos-panel', () => {
    useAuthStore.setState({ status: 'authenticated', user: makeUser(['PEDIDOS']) })
    render(
      <MemoryRouter initialEntries={['/login']}>
        <Routes>
          <Route element={<AuthLayout />}>
            <Route path="/login" element={<div>Login Content</div>} />
          </Route>
          <Route path="/pedidos-panel" element={<div>Pedidos Page</div>} />
        </Routes>
      </MemoryRouter>,
    )
    expect(screen.getByText('Pedidos Page')).toBeInTheDocument()
  })

  it('(e) deep-link preserved: STOCK user with from=/stock/products redirects there', () => {
    useAuthStore.setState({ status: 'authenticated', user: makeUser(['STOCK']) })
    renderAuthLayoutWithFrom('/stock/products')
    expect(screen.getByText('Stock Page')).toBeInTheDocument()
  })

  it('shows loading spinner when status is idle', () => {
    useAuthStore.setState({ status: 'idle' })
    renderAuthLayout()
    expect(screen.getByRole('status', { name: /loading/i })).toBeInTheDocument()
  })

  it('renders login content when unauthenticated', () => {
    useAuthStore.setState({ status: 'unauthenticated' })
    renderAuthLayout()
    expect(screen.getByText('Login Content')).toBeInTheDocument()
  })
})
