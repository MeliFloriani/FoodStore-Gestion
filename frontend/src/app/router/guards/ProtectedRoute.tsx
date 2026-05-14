import { Navigate, Outlet } from 'react-router-dom'
import { useAuthStore } from '@/entities/auth/model/store'

export function ProtectedRoute() {
  const status = useAuthStore((s) => s.status)

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

  if (status === 'unauthenticated') {
    return <Navigate to="/login" replace />
  }

  return <Outlet />
}
