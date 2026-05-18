import { Link, useLocation } from 'react-router-dom'

export default function ForbiddenPage() {
  const location = useLocation()
  const from = (location.state as { from?: string } | null)?.from

  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-4">
      <h1 className="text-2xl font-semibold">403 — Acceso denegado</h1>
      <p className="text-muted-foreground">No tenés permisos para acceder a esta página.</p>
      <Link to={from ?? '/catalog'} className="text-primary underline">
        Volver
      </Link>
    </div>
  )
}
