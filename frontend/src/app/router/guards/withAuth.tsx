import { Navigate, useLocation } from 'react-router-dom'
import { useRequireRoles } from './useRequireRoles'

export function withAuth<P extends object>(
  Component: React.ComponentType<P>,
  requiredRoles: string[],
): React.FC<P> {
  function WrappedComponent(props: P) {
    const location = useLocation()
    const result = useRequireRoles(requiredRoles)

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
    return <Component {...props} />
  }

  WrappedComponent.displayName = `withAuth(${Component.displayName ?? Component.name})`
  return WrappedComponent
}
