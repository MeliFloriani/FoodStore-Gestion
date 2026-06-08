/**
 * OrderConfirmationPage — post-creation order summary with payment CTA.
 *
 * Change 20: accessible at /order-confirmation/:id with RoleGuard roles={['CLIENT']}.
 *
 * Shown immediately after useCreateOrder succeeds (navigate from CheckoutPage).
 *
 * Features:
 * - Reads :id from URL params
 * - Fetches order detail via useOrderDetail(pedidoId)
 * - Shows items with snapshots, totals, status "PENDIENTE - Esperando pago"
 * - PayWithMercadoPagoButton (reused from Change 19 — no logic duplication)
 * - "Ver detalle del pedido" → /orders/:id
 * - Skeleton loaders during load
 * - Redirect to /403 on 403; /404 on 404
 *
 * Does NOT mount usePaymentStatus — that is the responsibility of CheckoutReturnPage.
 */

import { useEffect } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { useOrderDetail } from '@/features/orders'
import { PayWithMercadoPagoButton } from '@/features/checkout-payment'
import type { PedidoDetail } from '@/entities/pedido/model/types'

/** Extract HTTP status from any error object (works without axios.isAxiosError) */
function getHttpStatus(error: unknown): number | null {
  if (error && typeof error === 'object') {
    const e = error as Record<string, unknown>
    const response = e['response'] as Record<string, unknown> | undefined
    if (response && typeof response['status'] === 'number') {
      return response['status']
    }
  }
  return null
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatARS(decimalStr: string): string {
  const num = parseFloat(decimalStr)
  if (isNaN(num)) return `$ ${decimalStr}`
  return `$ ${num.toLocaleString('es-AR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
}

// ---------------------------------------------------------------------------
// Skeleton
// ---------------------------------------------------------------------------

function SkeletonConfirmation() {
  return (
    <div className="animate-pulse space-y-4" aria-busy="true" aria-label="Cargando confirmación del pedido">
      <div className="h-8 w-48 rounded bg-muted" />
      <div className="h-5 w-32 rounded bg-muted" />
      <div className="rounded-lg border border-border bg-card p-4 space-y-3">
        {Array.from({ length: 2 }).map((_, i) => (
          <div key={i} className="flex justify-between">
            <div className="h-4 w-40 rounded bg-muted" />
            <div className="h-4 w-20 rounded bg-muted" />
          </div>
        ))}
        <div className="border-t border-border pt-3">
          <div className="h-5 w-32 rounded bg-muted ml-auto" />
        </div>
      </div>
      <div className="h-12 w-full rounded-lg bg-muted" />
    </div>
  )
}

// ---------------------------------------------------------------------------
// Content (mounted when data is ready)
// ---------------------------------------------------------------------------

interface ConfirmationContentProps {
  pedido: PedidoDetail
  pedidoId: string
}

function ConfirmationContent({ pedido, pedidoId }: ConfirmationContentProps) {
  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <div className="flex items-center gap-2">
          <span className="text-2xl">✓</span>
          <h1 className="text-2xl font-bold text-foreground">Pedido creado</h1>
        </div>
        <p className="mt-1 font-mono text-sm text-muted-foreground">
          #{pedido.id.slice(-8).toUpperCase()}
        </p>
      </div>

      {/* Status badge — varies by payment method */}
      {pedido.forma_pago_codigo === 'EFECTIVO' ? (
        <div className="rounded-lg border border-green-200 bg-green-50 px-4 py-3">
          <p className="text-sm font-semibold text-green-800">
            PENDIENTE — Pendiente de confirmación
          </p>
          <p className="mt-0.5 text-xs text-green-700">
            Tu pedido fue recibido. El equipo lo confirmará a la brevedad.
          </p>
        </div>
      ) : (
        <div className="rounded-lg border border-yellow-200 bg-yellow-50 px-4 py-3">
          <p className="text-sm font-semibold text-yellow-800">
            PENDIENTE — Esperando pago
          </p>
          <p className="mt-0.5 text-xs text-yellow-700">
            Completá el pago para confirmar tu pedido.
          </p>
        </div>
      )}

      {/* Items */}
      <div className="rounded-lg border border-border bg-card p-4">
        <h2 className="mb-3 text-sm font-semibold text-foreground">Resumen del pedido</h2>
        <ul className="space-y-2">
          {pedido.items.map((item) => (
            <li key={item.id} className="flex justify-between gap-2 text-sm">
              <span className="text-foreground">
                {item.nombre_snapshot}{' '}
                <span className="text-muted-foreground">x{item.cantidad}</span>
              </span>
              <span className="font-medium text-foreground whitespace-nowrap">
                {formatARS(item.precio_snapshot)}
              </span>
            </li>
          ))}
        </ul>

        {/* Totals */}
        <div className="mt-4 border-t border-border pt-3 space-y-1.5">
          <div className="flex justify-between text-sm">
            <span className="text-muted-foreground">Subtotal</span>
            <span>{formatARS(pedido.subtotal)}</span>
          </div>
          <div className="flex justify-between text-sm">
            <span className="text-muted-foreground">Envío</span>
            <span>{formatARS(pedido.costo_envio)}</span>
          </div>
          <div className="flex justify-between font-bold text-base">
            <span>Total</span>
            <span>{formatARS(pedido.total)}</span>
          </div>
        </div>
      </div>

      {/* Payment CTA — conditional on payment method */}
      {pedido.forma_pago_codigo !== 'EFECTIVO' && (
        <PayWithMercadoPagoButton pedidoId={pedidoId} className="w-full" />
      )}
      {pedido.forma_pago_codigo === 'EFECTIVO' && (
        <div className="rounded-lg border border-border bg-muted/30 px-4 py-3 text-center text-sm text-muted-foreground">
          No se requiere pago online. El equipo gestionará tu pedido.
        </div>
      )}

      {/* View detail link */}
      <div className="text-center">
        <Link
          to={`/orders/${pedidoId}`}
          className="text-sm text-primary underline-offset-2 hover:underline"
        >
          Ver detalle del pedido →
        </Link>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main page component
// ---------------------------------------------------------------------------

export default function OrderConfirmationPage() {
  const { id: pedidoId } = useParams<{ id: string }>()
  const navigate = useNavigate()

  const { data, isLoading, isError, error } = useOrderDetail(pedidoId)

  const httpStatus = isError ? getHttpStatus(error) : null

  useEffect(() => {
    if (httpStatus === 403) navigate('/403', { replace: true })
    else if (httpStatus === 404) navigate('/404', { replace: true })
  }, [httpStatus, navigate])

  if (isError && httpStatus !== 403 && httpStatus !== 404) {
    return (
      <div className="mx-auto max-w-lg px-4 py-8 text-center">
        <p className="text-destructive">Error al cargar el pedido.</p>
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-lg px-4 py-8">
      {isLoading && <SkeletonConfirmation />}
      {data && pedidoId && (
        <ConfirmationContent pedido={data} pedidoId={pedidoId} />
      )}
    </div>
  )
}
