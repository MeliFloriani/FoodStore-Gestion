import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import AxiosMockAdapter from 'axios-mock-adapter'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter, Routes, Route, useLocation } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import { Navigation } from '../Navigation'
import { useAuthStore } from '@/entities/auth/model/store'
import { http } from '@/shared/api/http'
import { AUTH_LOGOUT } from '@/shared/api/endpoints'
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

function makeQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0 },
      mutations: { retry: false },
    },
  })
}

type Options = {
  queryClient?: QueryClient
  onLocationChange?: (path: string) => void
  initialPath?: string
}

function renderNavigation(opts: Options = {}) {
  const queryClient = opts.queryClient ?? makeQueryClient()

  function LocationProbe() {
    const location = useLocation()
    opts.onLocationChange?.(location.pathname)
    return null
  }

  function Wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={[opts.initialPath ?? '/']}>
          <LocationProbe />
          <Routes>
            <Route path="*" element={<>{children}</>} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>
    )
  }

  return { queryClient, ...render(<Navigation />, { wrapper: Wrapper }) }
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
    expect(screen.queryByText('Ingredientes')).not.toBeInTheDocument()
    expect(screen.queryByText('Productos')).not.toBeInTheDocument()
    expect(screen.queryByText('Panel de Pedidos')).not.toBeInTheDocument()
    expect(screen.queryByText('Usuarios')).not.toBeInTheDocument()
  })

  it('STOCK role sees the three restored stock CRUD items', () => {
    useAuthStore.setState({ status: 'authenticated', user: makeUser(['STOCK']) })
    renderNavigation()
    expect(screen.getByText('Ingredientes')).toBeInTheDocument()
    expect(screen.getByText('Categorías')).toBeInTheDocument()
    expect(screen.getByText('Productos')).toBeInTheDocument()
    // STOCK must NOT see CLIENT purchase flow or ADMIN-only surfaces
    expect(screen.queryByText('Mi Carrito')).not.toBeInTheDocument()
    expect(screen.queryByText('Mis Pedidos')).not.toBeInTheDocument()
    expect(screen.queryByText('Mis Direcciones')).not.toBeInTheDocument()
    expect(screen.queryByText('Usuarios')).not.toBeInTheDocument()
    expect(screen.queryByText('Panel de Pedidos')).not.toBeInTheDocument()
    expect(screen.queryByText('Métricas')).not.toBeInTheDocument()
  })

  it('shows PEDIDOS items for PEDIDOS role', () => {
    useAuthStore.setState({ status: 'authenticated', user: makeUser(['PEDIDOS']) })
    renderNavigation()
    expect(screen.getByText('Panel de Pedidos')).toBeInTheDocument()
    // Should NOT show CLIENT or ADMIN-only items
    expect(screen.queryByText('Mi Carrito')).not.toBeInTheDocument()
    expect(screen.queryByText('Usuarios')).not.toBeInTheDocument()
  })

  it('ADMIN role sees management items + catalog/profile + restored stock CRUD, but NOT CLIENT purchase flow', () => {
    useAuthStore.setState({ status: 'authenticated', user: makeUser(['ADMIN']) })
    renderNavigation()
    // Shared with CLIENT (ADMIN still listed in allowedRoles)
    expect(screen.getByText('Catálogo')).toBeInTheDocument()
    expect(screen.getByText('Mi Perfil')).toBeInTheDocument()
    // Management items
    expect(screen.getByText('Panel de Pedidos')).toBeInTheDocument()
    expect(screen.getByText('Usuarios')).toBeInTheDocument()
    expect(screen.getByText('Métricas')).toBeInTheDocument()
    // Restored stock CRUD items — real pages now exist
    expect(screen.getByText('Ingredientes')).toBeInTheDocument()
    expect(screen.getByText('Categorías')).toBeInTheDocument()
    expect(screen.getByText('Productos')).toBeInTheDocument()
    // ADMIN must NOT see CLIENT purchase flow
    expect(screen.queryByText('Mi Carrito')).not.toBeInTheDocument()
    expect(screen.queryByText('Mis Pedidos')).not.toBeInTheDocument()
    expect(screen.queryByText('Mis Direcciones')).not.toBeInTheDocument()
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

  // ---------------------------------------------------------------------------
  // "Cerrar sesión" button
  // ---------------------------------------------------------------------------

  describe('Cerrar sesión button', () => {
    let axiosMock: AxiosMockAdapter

    beforeEach(() => {
      axiosMock = new AxiosMockAdapter(http)
    })

    afterEach(() => {
      axiosMock.restore()
    })

    it('renders the button when the user is authenticated', () => {
      useAuthStore.setState({ status: 'authenticated', user: makeUser(['CLIENT']) })
      renderNavigation()
      expect(screen.getByRole('button', { name: /cerrar sesión/i })).toBeInTheDocument()
    })

    it('does NOT render the button when status is unauthenticated', () => {
      useAuthStore.setState({ status: 'unauthenticated' })
      renderNavigation()
      expect(screen.queryByRole('button', { name: /cerrar sesión/i })).not.toBeInTheDocument()
    })

    it('does NOT render the button when status is idle or authenticating', () => {
      useAuthStore.setState({ status: 'idle' })
      const { unmount } = renderNavigation()
      expect(screen.queryByRole('button', { name: /cerrar sesión/i })).not.toBeInTheDocument()
      unmount()

      useAuthStore.setState({ status: 'authenticating' })
      renderNavigation()
      expect(screen.queryByRole('button', { name: /cerrar sesión/i })).not.toBeInTheDocument()
    })

    it('clicking the button calls the backend logout, clears the auth store, clears the cache, and navigates to /login', async () => {
      useAuthStore.getState().login('access-token', 'refresh-token', makeUser(['CLIENT']))
      axiosMock.onPost(AUTH_LOGOUT).reply(204)

      const paths: string[] = []
      const queryClient = makeQueryClient()
      queryClient.setQueryData(['auth', 'me'], makeUser(['CLIENT']))

      renderNavigation({ queryClient, onLocationChange: (p) => paths.push(p) })

      fireEvent.click(screen.getByRole('button', { name: /cerrar sesión/i }))

      await waitFor(() => {
        expect(axiosMock.history.post.filter((r) => r.url === AUTH_LOGOUT)).toHaveLength(1)
      })
      expect(useAuthStore.getState().status).toBe('unauthenticated')
      expect(useAuthStore.getState().accessToken).toBeNull()
      expect(queryClient.getQueryData(['auth', 'me'])).toBeUndefined()
      await waitFor(() => {
        expect(paths.at(-1)).toBe('/login')
      })
    })

    it('still clears local state and redirects when the backend logout call fails', async () => {
      useAuthStore.getState().login('access-token', 'refresh-token', makeUser(['CLIENT']))
      axiosMock.onPost(AUTH_LOGOUT).reply(500)

      const paths: string[] = []
      renderNavigation({ onLocationChange: (p) => paths.push(p) })

      fireEvent.click(screen.getByRole('button', { name: /cerrar sesión/i }))

      await waitFor(() => {
        expect(useAuthStore.getState().status).toBe('unauthenticated')
      })
      await waitFor(() => {
        expect(paths.at(-1)).toBe('/login')
      })
    })
  })
})
