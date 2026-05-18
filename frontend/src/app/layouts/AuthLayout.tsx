import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { useAuthStore } from '@/entities/auth/model/store'
import { resolveDefaultRoute } from '@/shared/lib/navigation'

export function AuthLayout() {
  const status = useAuthStore(s => s.status)
  const user = useAuthStore(s => s.user)
  const location = useLocation()

  if (status === 'idle' || status === 'authenticating') {
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

  if (status === 'authenticated') {
    const from = (location.state as { from?: string } | null)?.from
    const target = from ?? resolveDefaultRoute(user?.roles ?? [])
    return <Navigate to={target} replace />
  }

  return <Outlet />
}
