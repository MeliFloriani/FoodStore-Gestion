/**
 * Tests for ChangePasswordForm component.
 *
 * Task 7.1 — TDD.
 *
 * Tests:
 *   - Submit sends ONLY {current_password, new_password} — no password_confirm in request
 *   - When response is 409 → inline error on current_password field
 *   - Client-side: password_confirm !== new_password → client error before submit
 *   - On 204 success → calls authStore.logout() + navigates to /login
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { createElement } from 'react'
import { MemoryRouter } from 'react-router-dom'

// Mock the http module
vi.mock('@/shared/api/http', () => ({
  http: {
    patch: vi.fn(),
    post: vi.fn(),
  },
}))

// Mock react-router-dom navigate
const mockNavigate = vi.fn()
vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal<typeof import('react-router-dom')>()
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  }
})

// Mock authStore
const mockLogout = vi.fn()
vi.mock('@/entities/auth/model/store', () => {
  const store = Object.assign(
    // When called with a selector (s) => s.logout, return mockLogout directly
    vi.fn((selector?: (s: { logout: typeof mockLogout }) => typeof mockLogout) => {
      const state = { logout: mockLogout }
      return selector ? selector(state) : state
    }),
    {
      getState: () => ({ logout: mockLogout }),
    }
  )
  return { useAuthStore: store }
})

describe('ChangePasswordForm', () => {
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

  it('submit sends ONLY {current_password, new_password} — no password_confirm', async () => {
    const { http } = await import('@/shared/api/http')
    const mockPost = vi.mocked(http.post)
    mockPost.mockResolvedValueOnce({ data: null, status: 204 })

    const { ChangePasswordForm } = await import('../ChangePasswordForm')
    render(createElement(ChangePasswordForm), { wrapper })

    const currentPassInput = screen.getByLabelText('Contraseña actual')
    const newPassInput = screen.getByLabelText('Nueva contraseña')
    const confirmPassInput = screen.getByLabelText('Confirmar nueva contraseña')

    fireEvent.change(currentPassInput, { target: { value: 'OldPass1!' } })
    fireEvent.change(newPassInput, { target: { value: 'NewPass1!' } })
    fireEvent.change(confirmPassInput, { target: { value: 'NewPass1!' } })

    const submitButton = screen.getByRole('button', { name: /cambiar|change|actualizar/i })
    fireEvent.click(submitButton)

    await waitFor(() => {
      expect(mockPost).toHaveBeenCalled()
    })

    const callArgs = mockPost.mock.calls[0]
    expect(callArgs[1]).toHaveProperty('current_password', 'OldPass1!')
    expect(callArgs[1]).toHaveProperty('new_password', 'NewPass1!')
    expect(callArgs[1]).not.toHaveProperty('password_confirm')
  })

  it('on 409 response → shows inline error on current_password field', async () => {
    const { http } = await import('@/shared/api/http')
    const mockPost = vi.mocked(http.post)

    const axiosError = new Error('409') as Error & {
      isAxiosError: boolean
      response: { status: number; data: { detail: string; code: string } }
    }
    axiosError.isAxiosError = true
    axiosError.response = {
      status: 409,
      data: { detail: 'La contraseña actual no coincide', code: 'CURRENT_PASSWORD_MISMATCH' },
    }
    mockPost.mockRejectedValueOnce(axiosError)

    const { ChangePasswordForm } = await import('../ChangePasswordForm')
    render(createElement(ChangePasswordForm), { wrapper })

    const currentPassInput = screen.getByLabelText('Contraseña actual')
    const newPassInput = screen.getByLabelText('Nueva contraseña')
    const confirmPassInput = screen.getByLabelText('Confirmar nueva contraseña')

    fireEvent.change(currentPassInput, { target: { value: 'WrongPass!' } })
    fireEvent.change(newPassInput, { target: { value: 'NewPass1!' } })
    fireEvent.change(confirmPassInput, { target: { value: 'NewPass1!' } })

    const submitButton = screen.getByRole('button', { name: /cambiar|change|actualizar/i })
    fireEvent.click(submitButton)

    await waitFor(() => {
      expect(
        screen.getByText(/contraseña actual incorrecta|contraseña actual no coincide|mismatch/i)
      ).toBeInTheDocument()
    })
  })

  it('client-side: password_confirm !== new_password → validation error before submit', async () => {
    const { ChangePasswordForm } = await import('../ChangePasswordForm')
    render(createElement(ChangePasswordForm), { wrapper })

    const newPassInput = screen.getByLabelText('Nueva contraseña')
    const confirmPassInput = screen.getByLabelText('Confirmar nueva contraseña')

    fireEvent.change(newPassInput, { target: { value: 'NewPass1!' } })
    fireEvent.change(confirmPassInput, { target: { value: 'DifferentPass!' } })
    fireEvent.blur(confirmPassInput)

    await waitFor(() => {
      expect(
        screen.getByText(/no coincid|do not match|contraseñas/i)
      ).toBeInTheDocument()
    })
  })

  it('on 204 success → calls authStore.logout() and navigates to /login', async () => {
    const { http } = await import('@/shared/api/http')
    const mockPost = vi.mocked(http.post)
    mockPost.mockResolvedValueOnce({ data: null, status: 204 })

    const { ChangePasswordForm } = await import('../ChangePasswordForm')
    render(createElement(ChangePasswordForm), { wrapper })

    const currentPassInput = screen.getByLabelText('Contraseña actual')
    const newPassInput = screen.getByLabelText('Nueva contraseña')
    const confirmPassInput = screen.getByLabelText('Confirmar nueva contraseña')

    fireEvent.change(currentPassInput, { target: { value: 'OldPass1!' } })
    fireEvent.change(newPassInput, { target: { value: 'NewPass1!' } })
    fireEvent.change(confirmPassInput, { target: { value: 'NewPass1!' } })

    const submitButton = screen.getByRole('button', { name: /cambiar|change|actualizar/i })
    fireEvent.click(submitButton)

    await waitFor(() => {
      expect(mockLogout).toHaveBeenCalled()
      expect(mockNavigate).toHaveBeenCalledWith('/login')
    })
  })
})
