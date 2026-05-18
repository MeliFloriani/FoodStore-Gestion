import { useAuthStore } from '@/entities/auth/model/store'

type RequireRolesResult =
  | { allowed: false; reason: 'loading' }
  | { allowed: false; reason: 'unauthenticated' }
  | { allowed: false; reason: 'forbidden' }
  | { allowed: true; reason: 'ok' }

export function useRequireRoles(requiredRoles: string[]): RequireRolesResult {
  const status = useAuthStore(s => s.status)
  // Read user directly to avoid creating a new array reference on each render
  // when user is null (which would cause infinite re-renders with `?? []`)
  const user = useAuthStore(s => s.user)
  const userRoles = user?.roles ?? []

  if (status === 'idle' || status === 'authenticating') {
    return { allowed: false, reason: 'loading' }
  }
  if (status === 'unauthenticated') {
    return { allowed: false, reason: 'unauthenticated' }
  }
  if (requiredRoles.length === 0) {
    return { allowed: true, reason: 'ok' }
  }
  if (requiredRoles.some(r => userRoles.includes(r))) {
    return { allowed: true, reason: 'ok' }
  }
  return { allowed: false, reason: 'forbidden' }
}
