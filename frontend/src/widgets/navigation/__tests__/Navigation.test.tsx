import { describe, it, expect, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { Navigation } from '../Navigation'
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

function renderNavigation() {
  return render(
    <MemoryRouter>
      <Navigation />
    </MemoryRouter>,
  )
}

describe('Navigation widget', () => {
  beforeEach(() => {
    useAuthStore.getState().clear()
  })

  it('shows anonymous items when unauthenticated', () => {
    useAuthStore.setState({ status: 'unauthenticated' })
    renderNavigation()
    expect(screen.getByText('Catálogo')).toBeInTheDocument()
    expect(screen.getByText('Login')).toBeInTheDocument()
    expect(screen.getByText('Registrarse')).toBeInTheDocument()
    // Should NOT show authenticated items
    expect(screen.queryByText('Mi Carrito')).not.toBeInTheDocument()
    expect(screen.queryByText('Usuarios')).not.toBeInTheDocument()
  })

  it('shows anonymous items when status is idle', () => {
    useAuthStore.setState({ status: 'idle' })
    renderNavigation()
    expect(screen.getByText('Login')).toBeInTheDocument()
    expect(screen.queryByText('Mi Carrito')).not.toBeInTheDocument()
  })

  it('shows CLIENT items for CLIENT role', () => {
    useAuthStore.setState({ status: 'authenticated', user: makeUser(['CLIENT']) })
    renderNavigation()
    expect(screen.getByText('Catálogo')).toBeInTheDocument()
    expect(screen.getByText('Mi Carrito')).toBeInTheDocument()
    expect(screen.getByText('Mis Pedidos')).toBeInTheDocument()
    expect(screen.getByText('Mi Perfil')).toBeInTheDocument()
    expect(screen.getByText('Mis Direcciones')).toBeInTheDocument()
    // Should NOT show STOCK, PEDIDOS, or ADMIN items
    expect(screen.queryByText('Productos')).not.toBeInTheDocument()
    expect(screen.queryByText('Panel de Pedidos')).not.toBeInTheDocument()
    expect(screen.queryByText('Usuarios')).not.toBeInTheDocument()
  })

  it('shows STOCK items for STOCK role', () => {
    useAuthStore.setState({ status: 'authenticated', user: makeUser(['STOCK']) })
    renderNavigation()
    expect(screen.getByText('Productos')).toBeInTheDocument()
    expect(screen.getByText('Categorías')).toBeInTheDocument()
    expect(screen.getByText('Ingredientes')).toBeInTheDocument()
    expect(screen.getByText('Stock')).toBeInTheDocument()
    // Should NOT show CLIENT or ADMIN-only items
    expect(screen.queryByText('Mi Carrito')).not.toBeInTheDocument()
    expect(screen.queryByText('Usuarios')).not.toBeInTheDocument()
  })

  it('shows PEDIDOS items for PEDIDOS role', () => {
    useAuthStore.setState({ status: 'authenticated', user: makeUser(['PEDIDOS']) })
    renderNavigation()
    expect(screen.getByText('Panel de Pedidos')).toBeInTheDocument()
    // Should NOT show CLIENT or ADMIN-only items
    expect(screen.queryByText('Mi Carrito')).not.toBeInTheDocument()
    expect(screen.queryByText('Usuarios')).not.toBeInTheDocument()
  })

  it('shows all items for ADMIN role', () => {
    useAuthStore.setState({ status: 'authenticated', user: makeUser(['ADMIN']) })
    renderNavigation()
    // CLIENT items (ADMIN is in allowedRoles)
    expect(screen.getByText('Catálogo')).toBeInTheDocument()
    expect(screen.getByText('Mi Carrito')).toBeInTheDocument()
    // STOCK items
    expect(screen.getByText('Productos')).toBeInTheDocument()
    // PEDIDOS items
    expect(screen.getByText('Panel de Pedidos')).toBeInTheDocument()
    // ADMIN-only items
    expect(screen.getByText('Usuarios')).toBeInTheDocument()
    expect(screen.getByText('Métricas')).toBeInTheDocument()
  })

  it('shows union of items for ADMIN+CLIENT multi-role user (no duplicate paths)', () => {
    useAuthStore.setState({ status: 'authenticated', user: makeUser(['ADMIN', 'CLIENT']) })
    renderNavigation()
    // Both CLIENT and ADMIN items visible
    expect(screen.getByText('Mi Carrito')).toBeInTheDocument()
    expect(screen.getByText('Usuarios')).toBeInTheDocument()
    // Catálogo appears in both CLIENT and ADMIN — should only appear ONCE
    const catalogLinks = screen.getAllByText('Catálogo')
    expect(catalogLinks).toHaveLength(1)
  })
})
