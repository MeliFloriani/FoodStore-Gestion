import { Navigate, Outlet } from 'react-router-dom'
import { useAuthStore } from '@/entities/auth/model/store'

export function AuthLayout() {
  const status = useAuthStore((s) => s.status)

  if (status === 'idle') {
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
    return <Navigate to="/" replace />
  }

  return <Outlet />
}
