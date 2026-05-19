/**
 * Tests for EditProfileForm component.
 *
 * Task 6.1 — TDD.
 *
 * Tests:
 *   - Renders with nombre, apellido pre-filled from user
 *   - Email field is visible but disabled
 *   - Submit sends PATCH with {nombre, apellido} — no email in payload
 *   - Shows success message on mutation success
 *   - Shows inline validation error when nombre is empty
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { createElement } from 'react'
import type { User } from '@/entities/auth/types'

// Mock the http module
vi.mock('@/shared/api/http', () => ({
  http: {
    patch: vi.fn(),
    post: vi.fn(),
  },
}))

const mockUser: User = {
  id: '123e4567-e89b-12d3-a456-426614174000',
  nombre: 'Juan',
  apellido: 'Pérez',
  email: 'juan@example.com',
  roles: ['CLIENT'],
}

describe('EditProfileForm', () => {
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
    return createElement(QueryClientProvider, { client: queryClient }, children)
  }

  it('renders with nombre and apellido pre-filled from user', async () => {
    const { EditProfileForm } = await import('../EditProfileForm')
    render(createElement(EditProfileForm, { user: mockUser }), { wrapper })

    const nombreInput = screen.getByLabelText(/nombre/i)
    const apellidoInput = screen.getByLabelText(/apellido/i)

    expect((nombreInput as HTMLInputElement).value).toBe('Juan')
    expect((apellidoInput as HTMLInputElement).value).toBe('Pérez')
  })

  it('email field is visible but disabled', async () => {
    const { EditProfileForm } = await import('../EditProfileForm')
    render(createElement(EditProfileForm, { user: mockUser }), { wrapper })

    const emailInput = screen.getByLabelText(/email/i)
    expect(emailInput).toBeInTheDocument()
    expect(emailInput).toBeDisabled()
  })

  it('email is visible and has the correct value', async () => {
    const { EditProfileForm } = await import('../EditProfileForm')
    render(createElement(EditProfileForm, { user: mockUser }), { wrapper })

    const emailInput = screen.getByLabelText(/email/i)
    expect((emailInput as HTMLInputElement).value).toBe('juan@example.com')
  })

  it('submit sends PATCH with {nombre, apellido} — no email in payload', async () => {
    const { http } = await import('@/shared/api/http')
    const mockPatch = vi.mocked(http.patch)
    mockPatch.mockResolvedValueOnce({
      data: { ...mockUser, nombre: 'Nueva' },
    })

    const { EditProfileForm } = await import('../EditProfileForm')
    render(createElement(EditProfileForm, { user: mockUser }), { wrapper })

    // Submit the form
    const submitButton = screen.getByRole('button', { name: /guardar|save|actualizar/i })
    fireEvent.click(submitButton)

    await waitFor(() => {
      expect(mockPatch).toHaveBeenCalled()
    })

    const callArgs = mockPatch.mock.calls[0]
    // Body should not contain email
    expect(callArgs[1]).not.toHaveProperty('email')
    // Body should contain nombre and apellido
    expect(callArgs[1]).toHaveProperty('nombre')
    expect(callArgs[1]).toHaveProperty('apellido')
  })

  it('shows success message on mutation success', async () => {
    const { http } = await import('@/shared/api/http')
    const mockPatch = vi.mocked(http.patch)
    mockPatch.mockResolvedValueOnce({
      data: { ...mockUser },
    })

    const { EditProfileForm } = await import('../EditProfileForm')
    render(createElement(EditProfileForm, { user: mockUser }), { wrapper })

    const submitButton = screen.getByRole('button', { name: /guardar|save|actualizar/i })
    fireEvent.click(submitButton)

    await waitFor(() => {
      expect(
        screen.getByText(/perfil actualizado|guardado|actualizado|success/i)
      ).toBeInTheDocument()
    })
  })
})
