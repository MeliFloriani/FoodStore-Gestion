/**
 * OrdersPage — displays the authenticated user's order history (Change 20).
 *
 * Fetches orders from GET /api/v1/pedidos via useMisPedidos() (TanStack Query).
 * Preserves the original "Último pago en curso" block (paymentStore) above the
 * list so the smoke-test flow for MercadoPago is not broken.
 *
 * States:
 *   - Loading: spinner + text while request is in-flight.
 *   - Error:   generic message + retry button.
 *   - Empty:   friendly message + link to catalog.
 *   - List:    card per order showing id, estado badge, forma de pago, totales,
 *              created_at, and a "Ver detalle" placeholder link.
 */

import { Link } from 'react-router-dom'
import { usePaymentStore } from '@/shared/store/paymentStore'
import { useMisPedidos } from '@/features/orders-list/hooks/useMisPedidos'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Map paymentStore status codes → human-readable labels */
function paymentStatusLabel(status: string): string {
  switch (status) {
    case 'pending':
      return 'Pago pendiente (esperando confirmación de MercadoPago)'
    case 'approved':
      return 'Pago aprobado'
    case 'rejected':
      return 'Pago rechazado'
    case 'error':
      return 'Error al procesar el pago'
    default:
      return 'Sin pago en curso'
  }
}

/** Shorten a UUID to last 8 chars for display — e.g. "…a1b2c3d4" */
function shortId(id: string): string {
  return `…${id.slice(-8)}`
}

/** Map estado_codigo → badge color classes */
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

/** Format ISO date string to locale string */
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

/** Format decimal string as ARS currency — "$ 1.234,50" */
function formatARS(decimalStr: string): string {
  const num = parseFloat(decimalStr)
  if (isNaN(num)) return `$ ${decimalStr}`
  return `$ ${num.toLocaleString('es-AR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function OrdersPage() {
  // paymentStore — kept for smoke-test compatibility (Change 19)
  const pedidoId = usePaymentStore((s) => s.pedidoId)
  const payStatus = usePaymentStore((s) => s.status)
  const lastErrorCode = usePaymentStore((s) => s.lastErrorCode)

  // TanStack Query — fetches from GET /api/v1/pedidos
  const { data: pedidos, isLoading, isError, error, refetch } = useMisPedidos()

  return (
    <section className="mx-auto max-w-2xl">
      <h1 className="mb-6 text-2xl font-bold text-foreground">Mis Pedidos</h1>

      {/* ── Último pago en curso (paymentStore — smoke-test block) ── */}
      {pedidoId && (
        <div className="mb-6 rounded-lg border border-border bg-card p-4">
          <p className="text-xs uppercase tracking-wider text-muted-foreground">
            Último pedido en curso
          </p>
          <p className="mt-1 text-sm font-mono text-foreground">{pedidoId}</p>
          <p className="mt-3 text-sm font-medium text-foreground">
            {paymentStatusLabel(payStatus)}
          </p>
          {lastErrorCode && (
            <p className="mt-2 text-xs text-red-600">
              Código de error: {lastErrorCode}
            </p>
          )}
          <div className="mt-4">
            <Link
              to="/checkout"
              className="inline-flex items-center justify-center rounded-md border border-border bg-background px-4 py-2 text-sm font-medium hover:bg-accent"
            >
              Volver al checkout
            </Link>
          </div>
        </div>
      )}

      {/* ── Loading state ── */}
      {isLoading && (
        <div className="rounded-lg border border-border bg-card p-8 text-center">
          <div className="mb-3 inline-block h-6 w-6 animate-spin rounded-full border-2 border-primary border-t-transparent" />
          <p className="text-sm text-muted-foreground">Cargando pedidos...</p>
        </div>
      )}

      {/* ── Error state ── */}
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

      {/* ── Empty state ── */}
      {!isLoading && !isError && pedidos !== undefined && pedidos.length === 0 && (
        <div className="rounded-lg border border-border bg-card p-8 text-center">
          <p className="mb-4 text-muted-foreground">
            Aún no tenés pedidos.
          </p>
          <Link
            to="/catalog"
            className="inline-flex items-center justify-center rounded-md bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground hover:bg-primary/90"
          >
            Ir al catálogo
          </Link>
        </div>
      )}

      {/* ── Order list ── */}
      {!isLoading && !isError && pedidos !== undefined && pedidos.length > 0 && (
        <ul className="flex flex-col gap-3">
          {pedidos.map((pedido) => (
            <li
              key={pedido.id}
              className="rounded-lg border border-border bg-card p-4"
            >
              {/* Header row */}
              <div className="flex items-center justify-between gap-2">
                <span className="font-mono text-xs text-muted-foreground">
                  {shortId(pedido.id)}
                </span>
                <span
                  className={`rounded-full px-2 py-0.5 text-xs font-semibold ${estadoBadgeClass(pedido.estado_codigo)}`}
                >
                  {pedido.estado_codigo}
                </span>
              </div>

              {/* Details */}
              <div className="mt-2 grid grid-cols-2 gap-x-4 gap-y-1 text-sm">
                <span className="text-muted-foreground">Forma de pago</span>
                <span className="text-foreground">{pedido.forma_pago_codigo}</span>

                <span className="text-muted-foreground">Subtotal</span>
                <span className="text-foreground">{formatARS(pedido.subtotal)}</span>

                <span className="text-muted-foreground">Envío</span>
                <span className="text-foreground">{formatARS(pedido.costo_envio)}</span>

                <span className="text-muted-foreground font-medium">Total</span>
                <span className="font-semibold text-foreground">{formatARS(pedido.total)}</span>

                <span className="text-muted-foreground">Fecha</span>
                <span className="text-foreground">{formatDate(pedido.created_at)}</span>
              </div>

              {/* Footer — Ver detalle placeholder */}
              <div className="mt-3 flex justify-end">
                <span className="cursor-not-allowed rounded-md border border-border bg-muted px-3 py-1.5 text-xs font-medium text-muted-foreground">
                  Ver detalle (próximamente)
                </span>
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
