import { Link } from 'react-router-dom'

export default function NotFoundPage() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-4">
      <h1 className="text-2xl font-semibold">404 — Página no encontrada</h1>
      <p className="text-muted-foreground">La página que buscás no existe.</p>
      <Link to="/catalog" className="text-primary underline">
        Volver al catálogo
      </Link>
    </div>
  )
}
