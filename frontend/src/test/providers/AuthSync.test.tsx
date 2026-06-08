import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render } from '@testing-library/react'
import { useAuthStore } from '@/entities/auth/model/store'
import { AuthSync } from '@/app/providers/AuthSync'

// Mock http so we control GET /auth/me responses
vi.mock('@/shared/api/http', () => ({
  http: {
    get: vi.fn(),
  },
  isRefreshing: vi.fn(() => false),
}))

// Mock cross-tab-sync to prevent real storage listeners in tests
vi.mock('@/shared/api/cross-tab-sync', () => ({
  initCrossTabSync: vi.fn(() => () => undefined),
}))

import { http } from '@/shared/api/http'

const mockUser = {
  id: '550e8400-e29b-41d4-a716-446655440000',
  nombre: 'Test',
  apellido: 'User',
  email: 'test@example.com',
  roles: ['CLIENT'],
}

describe('AuthSync', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    useAuthStore.getState().clear()
  })

  it('renders null (no visible UI)', () => {
    const { container } = render(<AuthSync />)
    expect(container.firstChild).toBeNull()
  })

  it('does not call GET /auth/me when status is idle', () => {
    render(<AuthSync />)
    // status is 'idle' by default — http.get must NOT be called
    expect(http.get).not.toHaveBeenCalled()
  })

  it('calls GET /auth/me when status is authenticating', async () => {
    // Arrange: return a resolved promise with mock user
    ;(http.get as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      data: mockUser,
    })

    // Set status to 'authenticating' (simulates rehydration)
    useAuthStore.getState().triggerRehydrationFetch()

    render(<AuthSync />)

    // Wait for microtasks to settle
    await vi.waitFor(() => {
      expect(http.get).toHaveBeenCalledWith('/api/v1/auth/me')
    })
  })

  it('calls setUser (NOT login) on successful /auth/me response', async () => {
    const setUser = vi.spyOn(useAuthStore.getState(), 'setUser')
    const login = vi.spyOn(useAuthStore.getState(), 'login')

    ;(http.get as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      data: mockUser,
    })

    useAuthStore.getState().triggerRehydrationFetch()
    render(<AuthSync />)

    await vi.waitFor(() => {
      expect(setUser).toHaveBeenCalledWith(mockUser)
    })
    expect(login).not.toHaveBeenCalled()
  })

  it('sets status to authenticated after successful /auth/me', async () => {
    ;(http.get as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      data: mockUser,
    })

    useAuthStore.getState().triggerRehydrationFetch()
    render(<AuthSync />)

    await vi.waitFor(() => {
      expect(useAuthStore.getState().status).toBe('authenticated')
    })
  })

  it('calls logout() when /auth/me fails', async () => {
    ;(http.get as ReturnType<typeof vi.fn>).mockRejectedValueOnce(
      new Error('Unauthorized'),
    )

    useAuthStore.getState().triggerRehydrationFetch()
    render(<AuthSync />)

    await vi.waitFor(() => {
      expect(useAuthStore.getState().status).toBe('unauthenticated')
    })
  })
})
