import { Link } from 'react-router-dom'

export default function UnauthorizedPage() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-4">
      <h1 className="text-2xl font-semibold">401 — Sesión expirada</h1>
      <p className="text-muted-foreground">Tu sesión ha expirado. Por favor, iniciá sesión nuevamente.</p>
      <Link to="/login" className="text-primary underline">
        Ir al login
      </Link>
    </div>
  )
}
