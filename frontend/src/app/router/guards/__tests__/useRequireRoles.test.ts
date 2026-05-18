import { describe, it, expect, beforeEach } from 'vitest'
import { renderHook } from '@testing-library/react'
import { useRequireRoles } from '../useRequireRoles'
import { useAuthStore } from '@/entities/auth/model/store'
import type { User } from '@/entities/auth/types'

const mockClientUser: User = {
  id: '550e8400-e29b-41d4-a716-446655440000',
  nombre: 'Test',
  apellido: 'User',
  email: 'test@example.com',
  roles: ['CLIENT'],
}

const mockAdminUser: User = {
  id: '550e8400-e29b-41d4-a716-446655440001',
  nombre: 'Admin',
  apellido: 'User',
  email: 'admin@example.com',
  roles: ['ADMIN', 'CLIENT'],
}

const mockEmptyRolesUser: User = {
  id: '550e8400-e29b-41d4-a716-446655440002',
  nombre: 'No',
  apellido: 'Roles',
  email: 'noroles@example.com',
  roles: [],
}

describe('useRequireRoles', () => {
  beforeEach(() => {
    useAuthStore.getState().clear()
  })

  it('returns loading when status is idle', () => {
    useAuthStore.setState({ status: 'idle' })
    const { result } = renderHook(() => useRequireRoles(['ADMIN']))
    expect(result.current).toEqual({ allowed: false, reason: 'loading' })
  })

  it('returns loading when status is authenticating', () => {
    useAuthStore.setState({ status: 'authenticating' })
    const { result } = renderHook(() => useRequireRoles(['ADMIN']))
    expect(result.current).toEqual({ allowed: false, reason: 'loading' })
  })

  it('returns unauthenticated when status is unauthenticated', () => {
    useAuthStore.setState({ status: 'unauthenticated' })
    const { result } = renderHook(() => useRequireRoles(['ADMIN']))
    expect(result.current).toEqual({ allowed: false, reason: 'unauthenticated' })
  })

  it('returns forbidden when CLIENT user tries to access ADMIN route', () => {
    useAuthStore.setState({ status: 'authenticated', user: mockClientUser })
    const { result } = renderHook(() => useRequireRoles(['ADMIN']))
    expect(result.current).toEqual({ allowed: false, reason: 'forbidden' })
  })

  it('returns ok when ADMIN+CLIENT user accesses ADMIN route', () => {
    useAuthStore.setState({ status: 'authenticated', user: mockAdminUser })
    const { result } = renderHook(() => useRequireRoles(['ADMIN']))
    expect(result.current).toEqual({ allowed: true, reason: 'ok' })
  })

  it('returns forbidden when user with no roles tries to access ADMIN route', () => {
    useAuthStore.setState({ status: 'authenticated', user: mockEmptyRolesUser })
    const { result } = renderHook(() => useRequireRoles(['ADMIN']))
    expect(result.current).toEqual({ allowed: false, reason: 'forbidden' })
  })

  it('returns ok when requiredRoles is empty (public authenticated route)', () => {
    useAuthStore.setState({ status: 'authenticated', user: mockClientUser })
    const { result } = renderHook(() => useRequireRoles([]))
    expect(result.current).toEqual({ allowed: true, reason: 'ok' })
  })
})
