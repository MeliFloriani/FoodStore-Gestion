/**
 * TypeScript types for admin-users feature (Change 21).
 *
 * All types mirror the backend Pydantic schemas exactly.
 * Strict mode: no `any`, no implicit `undefined`.
 *
 * D-01: UsuarioAdminUpdate does NOT contain email (immutable).
 * D-05: UsuarioEstadoUpdate supports activo=true (backend), but frontend
 *        only exposes activo=false (deactivation) in this change.
 */

/** Compact role representation (mirrors backend RolRead). */
export interface RolRead {
  id: string
  codigo: string
  nombre: string
}

/**
 * Full user detail returned by admin endpoints.
 * Mirrors backend UsuarioAdminRead.
 *
 * Note: is_active is a computed boolean derived from deleted_at.
 */
export interface UsuarioAdminRead {
  id: string
  email: string
  nombre: string
  apellido: string
  created_at: string
  deleted_at: string | null
  roles: RolRead[]
}

/** Helper to derive active status from deleted_at field. */
export function isUserActive(user: UsuarioAdminRead): boolean {
  return user.deleted_at === null
}

/** Query params for GET /admin/usuarios. */
export interface UsersQueryParams {
  page?: number
  size?: number
  q?: string
  rol?: string
  activo?: boolean
}

/**
 * Editable fields for PUT /admin/usuarios/{id}.
 * D-01: email is NOT included (immutable).
 */
export interface UsuarioAdminUpdate {
  nombre?: string
  apellido?: string
}

/** Full role set replacement for PUT /admin/usuarios/{id}/roles. */
export interface UsuarioRolesUpdate {
  roles: string[]
}

/** Activation/deactivation payload for PATCH /admin/usuarios/{id}/estado. */
export interface UsuarioEstadoUpdate {
  activo: boolean
}

/** Valid role codes in the system. */
export const VALID_ROLES = ['ADMIN', 'STOCK', 'PEDIDOS', 'CLIENT'] as const
export type RolCodigo = (typeof VALID_ROLES)[number]
