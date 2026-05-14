import { Outlet } from 'react-router-dom'

type RoleGuardProps = {
  roles: string[]
}

/**
 * Stub RoleGuard — renders Outlet unconditionally.
 * Role enforcement is deferred to a future change.
 * The `roles` prop defines the interface contract for future use.
 */
// eslint-disable-next-line @typescript-eslint/no-unused-vars
export function RoleGuard({ roles: _roles }: RoleGuardProps) {
  return <Outlet />
}
