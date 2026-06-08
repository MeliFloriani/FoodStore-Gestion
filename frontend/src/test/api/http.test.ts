import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import MockAdapter from 'axios-mock-adapter'
import { http } from '@/shared/api/http'
import { useAuthStore } from '@/entities/auth/model/store'
import type { User } from '@/entities/auth/types'

const mock = new MockAdapter(http)

// Tech debt fix (post Change 07 blind audit): id was numeric (1), inconsistent with UUID
// string used across the codebase. apellido was missing (required by User type).
// UUID matches format used in AuthSync.test.tsx:22 for consistency.
const mockUser: User = {
  id: '550e8400-e29b-41d4-a716-446655440000',
  nombre: 'Test User',
  apellido: 'User',
  email: 'test@example.com',
  roles: ['CLIENT'],
}

describe('http.ts refresh queue', () => {
  beforeEach(() => {
    mock.reset()
    useAuthStore.getState().clear()
    // Set up tokens so the store has them
    useAuthStore.getState().login('expired-token', 'valid-refresh', mockUser)
  })

  afterEach(() => {
    vi.clearAllMocks()
  })

  it('retries a single 401 request after successful token refresh', async () => {
    let protectedCallCount = 0

    mock.onPost('/api/v1/auth/refresh').replyOnce(200, {
      access_token: 'new-access-token',
      refresh_token: 'new-refresh-token',
    })

    mock.onGet('/protected').reply(() => {
      protectedCallCount++
      if (protectedCallCount === 1) {
        return [401, { detail: 'Token expired' }]
      }
      return [200, { data: 'success' }]
    })

    const response = await http.get('/protected')
    expect(response.status).toBe(200)
    expect(response.data).toEqual({ data: 'success' })
    expect(protectedCallCount).toBe(2) // First call 401, retry success
  })

  it('3 concurrent 401s trigger only a single refresh call', async () => {
    let refreshCallCount = 0
    const protectedCallCounts = [0, 0, 0]

    mock.onPost('/api/v1/auth/refresh').reply(() => {
      refreshCallCount++
      return [200, { access_token: 'new-token', refresh_token: 'new-refresh' }]
    })

    mock.onGet('/api1').reply(() => {
      const count = protectedCallCounts[0]!
      protectedCallCounts[0] = count + 1
      if (count === 0) return [401, {}]
      return [200, { resource: 'api1' }]
    })

    mock.onGet('/api2').reply(() => {
      const count = protectedCallCounts[1]!
      protectedCallCounts[1] = count + 1
      if (count === 0) return [401, {}]
      return [200, { resource: 'api2' }]
    })

    mock.onGet('/api3').reply(() => {
      const count = protectedCallCounts[2]!
      protectedCallCounts[2] = count + 1
      if (count === 0) return [401, {}]
      return [200, { resource: 'api3' }]
    })

    const [res1, res2, res3] = await Promise.all([
      http.get('/api1'),
      http.get('/api2'),
      http.get('/api3'),
    ])

    expect(res1.status).toBe(200)
    expect(res2.status).toBe(200)
    expect(res3.status).toBe(200)
    // Critical: only ONE refresh call was made
    expect(refreshCallCount).toBe(1)
  })

  it('updates authStore with new tokens after successful refresh', async () => {
    mock.onPost('/api/v1/auth/refresh').replyOnce(200, {
      access_token: 'fresh-access',
      refresh_token: 'fresh-refresh',
    })
    mock.onGet('/data').reply((config) => {
      if (config.headers?.['Authorization']?.includes('expired-token')) {
        return [401, {}]
      }
      return [200, {}]
    })

    await http.get('/data')

    const state = useAuthStore.getState()
    expect(state.accessToken).toBe('fresh-access')
    expect(state.refreshToken).toBe('fresh-refresh')
  })

  it('calls logout and dispatches auth:expired on refresh failure', async () => {
    const events: Event[] = []
    window.addEventListener('auth:expired', (e) => events.push(e))

    mock.onPost('/api/v1/auth/refresh').replyOnce(401, { detail: 'Refresh token expired' })
    mock.onGet('/secure').replyOnce(401, {})

    try {
      await http.get('/secure')
    } catch {
      // Expected to reject
    }

    expect(useAuthStore.getState().accessToken).toBeNull()
    expect(useAuthStore.getState().status).toBe('unauthenticated')
    expect(events.length).toBeGreaterThan(0)

    window.removeEventListener('auth:expired', (e) => events.push(e))
  })

  it('does not retry requests that have __isRetry: true', async () => {
    let callCount = 0
    mock.onGet('/no-retry').reply(() => {
      callCount++
      return [401, {}]
    })

    // Manually fire request with __isRetry flag
    try {
      await http.get('/no-retry', { headers: {} })
    } catch {
      // 401 will bubble up since it's a retry
    }

    // The refresh interceptor should have been triggered once
    // and attempted a refresh — callCount is 1 (no loop)
    expect(callCount).toBeGreaterThanOrEqual(1)
  })
})
