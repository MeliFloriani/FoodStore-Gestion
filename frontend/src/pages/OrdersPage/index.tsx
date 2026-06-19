/**
 * OrdersPage — paginated list of the authenticated CLIENT's orders.
 *
 * Change 20: replaces the placeholder at /orders.
 *
 * Features:
 * - Estado filter (select, no debounce)
 * - Pagination (prev/next with page number)
 * - Skeleton loaders during fetch
 * - Empty state with "Ir al catálogo" CTA
 * - Error state with retry
 * - Navigate to /orders/:id on item click
 *
 * RoleGuard roles={['CLIENT']} is applied in the router (see routes.tsx).
 */

import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { useClientOrders } from '@/features/orders'
import type { ClientOrdersParams } from '@/entities/pedido/model/types'
import { SkeletonList } from '@/shared/ui/skeleton'
import { EmptyState } from '@/shared/ui/empty-state'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const ESTADO_OPTIONS = [
  { value: '', label: 'Todos los estados' },
  { value: 'PENDIENTE', label: 'Pendiente' },
  { value: 'CONFIRMADO', label: 'Confirmado' },
  { value: 'EN_PREP', label: 'En preparación' },
  { value: 'EN_CAMINO', label: 'En camino' },
  { value: 'ENTREGADO', label: 'Entregado' },
  { value: 'CANCELADO', label: 'Cancelado' },
]

function estadoBadgeClass(estado: string): string {
  switch (estado) {
    case 'PENDIENTE':
      return 'bg-yellow-100 text-yellow-800'
    case 'CONFIRMADO':
      return 'bg-blue-100 text-blue-800'
    case 'EN_PREP':
      return 'bg-indigo-100 text-indigo-800'
    case 'EN_CAMINO':
      return 'bg-purple-100 text-purple-800'
    case 'ENTREGADO':
      return 'bg-green-100 text-green-800'
    case 'CANCELADO':
      return 'bg-red-100 text-red-800'
    default:
      return 'bg-muted text-muted-foreground'
  }
}

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleString('es-AR', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    })
  } catch {
    return iso
  }
}

function formatARS(decimalStr: string): string {
  const num = parseFloat(decimalStr)
  if (isNaN(num)) return `$ ${decimalStr}`
  return `$ ${num.toLocaleString('es-AR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
}

function shortId(id: string): string {
  return `#${id.slice(-8).toUpperCase()}`
}



// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

const PAGE_SIZE = 10

export default function OrdersPage() {
  const navigate = useNavigate()
  const [estado, setEstado] = useState<string>('')
  const [page, setPage] = useState(1)

  const params: ClientOrdersParams = {
    estado: estado || undefined,
    page,
    size: PAGE_SIZE,
  }

  const { data, isLoading, isError, error, refetch } = useClientOrders(params)

  const totalPages = data?.pages ?? 1
  const items = data?.items ?? []

  return (
    <section className="mx-auto max-w-2xl px-4 py-6">
      <h1 className="mb-6 text-2xl font-bold text-foreground">Mis Pedidos</h1>

      {/* Filters */}
      <div className="mb-4 flex gap-3">
        <div className="flex-1">
          <label htmlFor="estado-filter" className="sr-only">
            Filtrar por estado
          </label>
          <select
            id="estado-filter"
            value={estado}
            onChange={(e) => {
              setEstado(e.target.value)
              setPage(1)
            }}
            className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
          >
            {ESTADO_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Loading */}
      {isLoading && (
        <div aria-busy="true" aria-label="Cargando pedidos">
          <SkeletonList rows={5} />
        </div>
      )}

      {/* Error */}
      {isError && !isLoading && (
        <div className="rounded-lg border border-destructive/40 bg-destructive/5 p-8 text-center">
          <p className="mb-1 text-sm font-medium text-destructive">
            No se pudieron cargar tus pedidos.
          </p>
          <p className="mb-4 text-xs text-muted-foreground">
            {error instanceof Error ? error.message : 'Error desconocido.'}
          </p>
          <button
            onClick={() => void refetch()}
            className="inline-flex items-center justify-center rounded-md bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground hover:bg-primary/90"
          >
            Reintentar
          </button>
        </div>
      )}

      {/* Empty state */}
      {!isLoading && !isError && items.length === 0 && (
        <EmptyState
          title="Sin pedidos"
          description="Aún no realizaste ningún pedido."
          action={<Link to="/catalog" className="inline-flex items-center justify-center rounded-md bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground hover:bg-primary/90">Ver catálogo</Link>}
        />
      )}

      {/* Order list */}
      {!isLoading && !isError && items.length > 0 && (
        <>
          <ul className="flex flex-col gap-3">
            {items.map((pedido) => (
              <li
                key={pedido.id}
                onClick={() => navigate(`/orders/${pedido.id}`)}
                className="cursor-pointer rounded-lg border border-border bg-card p-4 transition-colors hover:border-primary/30 hover:bg-accent/50"
                role="button"
                tabIndex={0}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    navigate(`/orders/${pedido.id}`)
                  }
                }}
                aria-label={`Pedido ${shortId(pedido.id)} — ${pedido.estado_codigo}`}
              >
                {/* Header */}
                <div className="flex items-center justify-between gap-2">
                  <span className="font-mono text-xs font-semibold text-muted-foreground">
                    {shortId(pedido.id)}
                  </span>
                  <span
                    className={`rounded-full px-2 py-0.5 text-xs font-semibold ${estadoBadgeClass(pedido.estado_codigo)}`}
                  >
                    {pedido.estado_codigo}
                  </span>
                </div>

                {/* Details */}
                <div className="mt-2 flex items-center justify-between text-sm">
                  <span className="text-muted-foreground">
                    {formatDate(pedido.created_at)}
                  </span>
                  <span className="font-semibold text-foreground">
                    {formatARS(pedido.total)}
                  </span>
                </div>

                <div className="mt-1 text-xs text-muted-foreground">
                  {pedido.items_count}{' '}
                  {pedido.items_count === 1 ? 'ítem' : 'ítems'} ·{' '}
                  {pedido.forma_pago_codigo}
                </div>
              </li>
            ))}
          </ul>

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="mt-6 flex items-center justify-center gap-4">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page <= 1}
                className="rounded-md border border-border bg-background px-3 py-1.5 text-sm font-medium hover:bg-accent disabled:cursor-not-allowed disabled:opacity-50"
              >
                Anterior
              </button>
              <span className="text-sm text-muted-foreground">
                Página {page} de {totalPages}
              </span>
              <button
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                disabled={page >= totalPages}
                className="rounded-md border border-border bg-background px-3 py-1.5 text-sm font-medium hover:bg-accent disabled:cursor-not-allowed disabled:opacity-50"
              >
                Siguiente
              </button>
            </div>
          )}
        </>
      )}
    </section>
  )
}
