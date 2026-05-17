import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { useAuthStore } from '@/entities/auth/model/store'

// We mock isRefreshing so we can control its return value in tests
vi.mock('@/shared/api/http', () => ({
  http: { get: vi.fn(), post: vi.fn() },
  isRefreshing: vi.fn(() => false),
}))

import { isRefreshing } from '@/shared/api/http'
import { initCrossTabSync } from '@/shared/api/cross-tab-sync'

const AUTH_STORE_KEY = 'food-store-auth'

function makeStorageEvent(key: string, newValue: string | null): StorageEvent {
  return new StorageEvent('storage', { key, newValue })
}

function makeAuthStorageValue(accessToken: string | null, refreshToken: string | null): string {
  return JSON.stringify({
    state: { accessToken, refreshToken },
  })
}

describe('initCrossTabSync', () => {
  let cleanup: () => void

  beforeEach(() => {
    vi.clearAllMocks()
    useAuthStore.getState().clear()
    // Install the listener before each test
    cleanup = initCrossTabSync()
  })

  afterEach(() => {
    // Remove the listener to avoid cross-test pollution
    cleanup()
  })

  it('returns a cleanup function that can be called without error', () => {
    const c = initCrossTabSync()
    expect(() => c()).not.toThrow()
    c() // No listener registered now, but should not throw
  })

  it('ignores storage events for other keys', () => {
    const updateTokens = vi.spyOn(useAuthStore.getState(), 'updateTokens')
    window.dispatchEvent(makeStorageEvent('some-other-key', makeAuthStorageValue('a', 'b')))
    expect(updateTokens).not.toHaveBeenCalled()
  })

  it('calls logout() when newValue is null (cross-tab logout)', () => {
    const logout = vi.spyOn(useAuthStore.getState(), 'logout')
    window.dispatchEvent(makeStorageEvent(AUTH_STORE_KEY, null))
    expect(logout).toHaveBeenCalledOnce()
  })

  it('calls updateTokens() with parsed tokens on valid cross-tab login/rotation', () => {
    const updateTokens = vi.spyOn(useAuthStore.getState(), 'updateTokens')
    ;(isRefreshing as ReturnType<typeof vi.fn>).mockReturnValue(false)

    const value = makeAuthStorageValue('new-access', 'new-refresh')
    window.dispatchEvent(makeStorageEvent(AUTH_STORE_KEY, value))

    expect(updateTokens).toHaveBeenCalledWith('new-access', 'new-refresh')
  })

  it('does NOT call updateTokens() when isRefreshing() is true', () => {
    const updateTokens = vi.spyOn(useAuthStore.getState(), 'updateTokens')
    ;(isRefreshing as ReturnType<typeof vi.fn>).mockReturnValue(true)

    const value = makeAuthStorageValue('new-access', 'new-refresh')
    window.dispatchEvent(makeStorageEvent(AUTH_STORE_KEY, value))

    expect(updateTokens).not.toHaveBeenCalled()
  })

  it('does NOT call updateTokens() when token fields are missing from storage value', () => {
    const updateTokens = vi.spyOn(useAuthStore.getState(), 'updateTokens')
    ;(isRefreshing as ReturnType<typeof vi.fn>).mockReturnValue(false)

    // newValue present but no accessToken/refreshToken in state
    const value = JSON.stringify({ state: {} })
    window.dispatchEvent(makeStorageEvent(AUTH_STORE_KEY, value))

    expect(updateTokens).not.toHaveBeenCalled()
  })

  it('silently ignores malformed JSON in storage event', () => {
    const updateTokens = vi.spyOn(useAuthStore.getState(), 'updateTokens')
    ;(isRefreshing as ReturnType<typeof vi.fn>).mockReturnValue(false)

    window.dispatchEvent(makeStorageEvent(AUTH_STORE_KEY, '{invalid json'))

    expect(updateTokens).not.toHaveBeenCalled()
  })

  it('cleanup removes the listener (no updateTokens after cleanup)', () => {
    cleanup() // Remove the listener installed in beforeEach

    const updateTokens = vi.spyOn(useAuthStore.getState(), 'updateTokens')
    ;(isRefreshing as ReturnType<typeof vi.fn>).mockReturnValue(false)

    const value = makeAuthStorageValue('new-access', 'new-refresh')
    window.dispatchEvent(makeStorageEvent(AUTH_STORE_KEY, value))

    expect(updateTokens).not.toHaveBeenCalled()
  })
})
