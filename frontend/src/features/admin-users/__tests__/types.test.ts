/**
 * Unit tests for admin-users types and helper functions (Change 21).
 *
 * Phase 8 (frontend) — covers types.ts and type helpers.
 */

import { describe, it, expect } from 'vitest'
import { isUserActive, VALID_ROLES } from '../types'
import type { UsuarioAdminRead } from '../types'

const activeUser: UsuarioAdminRead = {
  id: '123e4567-e89b-12d3-a456-426614174000',
  email: 'active@example.com',
  nombre: 'Ana',
  apellido: 'García',
  created_at: '2024-01-01T00:00:00Z',
  deleted_at: null,
  roles: [{ id: 'rol-1', codigo: 'ADMIN', nombre: 'Admin' }],
}

const inactiveUser: UsuarioAdminRead = {
  ...activeUser,
  id: '123e4567-e89b-12d3-a456-426614174001',
  deleted_at: '2024-06-01T12:00:00Z',
}

describe('isUserActive', () => {
  it('returns true when deleted_at is null', () => {
    expect(isUserActive(activeUser)).toBe(true)
  })

  it('returns false when deleted_at is set', () => {
    expect(isUserActive(inactiveUser)).toBe(false)
  })
})

describe('VALID_ROLES', () => {
  it('includes all 4 expected role codes', () => {
    expect(VALID_ROLES).toContain('ADMIN')
    expect(VALID_ROLES).toContain('STOCK')
    expect(VALID_ROLES).toContain('PEDIDOS')
    expect(VALID_ROLES).toContain('CLIENT')
  })

  it('has exactly 4 entries', () => {
    expect(VALID_ROLES).toHaveLength(4)
  })
})
