/**
 * Tests for API endpoint constants (Change 13: customer-profile-management).
 *
 * Task 5.1 — TDD: verify PROFILE_ME and PROFILE_ME_PASSWORD constants exist
 * with correct values before implementing them in endpoints.ts.
 */

import { describe, it, expect } from 'vitest'
import { PROFILE_ME, PROFILE_ME_PASSWORD } from '../endpoints'

describe('Profile endpoint constants', () => {
  it('PROFILE_ME has correct value', () => {
    expect(PROFILE_ME).toBe('/api/v1/profile/me')
  })

  it('PROFILE_ME_PASSWORD has correct value', () => {
    expect(PROFILE_ME_PASSWORD).toBe('/api/v1/profile/me/password')
  })
})
