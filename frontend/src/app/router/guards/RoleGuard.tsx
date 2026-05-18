import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { useRequireRoles } from './useRequireRoles'

type RoleGuardProps = { roles: string[] }

export function RoleGuard({ roles }: RoleGuardProps) {
  const location = useLocation()
  const result = useRequireRoles(roles)

  if (result.reason === 'loading') {
    return (
      <div
        role="status"
        aria-label="Loading"
        className="flex min-h-screen items-center justify-center"
      >
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
      </div>
    )
  }
  if (result.reason === 'unauthenticated') {
    return <Navigate to="/login" state={{ from: location.pathname }} replace />
  }
  if (result.reason === 'forbidden') {
    return <Navigate to="/403" state={{ from: location.pathname }} replace />
  }
  return <Outlet />
}
