/**
 * Tests for ProfilePage component.
 *
 * Task 8.1 — TDD.
 *
 * Tests:
 *   - Renders EditProfileForm and ChangePasswordForm when user data is loaded
 *   - Shows skeleton/loading while user query is loading
 *   - Auth guard behavior already covered by Change 08 test suite
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { createElement } from 'react'
import { MemoryRouter } from 'react-router-dom'
import type { User } from '@/entities/auth/types'

// Mock auth store
const mockUser: User = {
  id: '123e4567-e89b-12d3-a456-426614174000',
  nombre: 'Juan',
  apellido: 'Pérez',
  email: 'juan@example.com',
  roles: ['CLIENT'],
}

// Mock the http module
vi.mock('@/shared/api/http', () => ({
  http: {
    get: vi.fn(),
    patch: vi.fn(),
    post: vi.fn(),
  },
}))

// Mock react-router-dom navigate
vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal<typeof import('react-router-dom')>()
  return {
    ...actual,
    useNavigate: () => vi.fn(),
  }
})

// Mock authStore
vi.mock('@/entities/auth/model/store', () => {
  const store = Object.assign(
    vi.fn((selector?: (s: { logout: ReturnType<typeof vi.fn> }) => ReturnType<typeof vi.fn>) => {
      const state = { logout: vi.fn() }
      return selector ? selector(state) : state
    }),
    {
      getState: () => ({ logout: vi.fn() }),
    }
  )
  return { useAuthStore: store }
})

describe('ProfilePage', () => {
  let queryClient: QueryClient

  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
        mutations: { retry: false },
      },
    })
    vi.clearAllMocks()
  })

  function wrapper({ children }: { children: React.ReactNode }) {
    return createElement(
      MemoryRouter,
      {},
      createElement(QueryClientProvider, { client: queryClient }, children)
    )
  }

  it('shows loading skeleton while user query is loading', async () => {
    const { http } = await import('@/shared/api/http')
    const mockGet = vi.mocked(http.get)
    // Never resolve — stays in loading state
    mockGet.mockImplementationOnce(() => new Promise(() => {}))

    const { default: ProfilePage } = await import('../index')
    render(createElement(ProfilePage), { wrapper })

    expect(screen.getByRole('status')).toBeInTheDocument()
  })

  it('renders EditProfileForm and ChangePasswordForm with mock user data', async () => {
    const { http } = await import('@/shared/api/http')
    const mockGet = vi.mocked(http.get)
    mockGet.mockResolvedValueOnce({ data: mockUser })

    const { default: ProfilePage } = await import('../index')
    render(createElement(ProfilePage), { wrapper })

    // Wait for the data to load and forms to appear
    await screen.findByLabelText('Nombre')
    expect(screen.getByLabelText('Nombre')).toBeInTheDocument()
    expect(screen.getByLabelText('Contraseña actual')).toBeInTheDocument()
  })
})
