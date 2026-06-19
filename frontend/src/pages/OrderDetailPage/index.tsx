/**
 * OrderDetailPage — full detail of a CLIENT's own order.
 *
 * Change 20: accessible at /orders/:id with RoleGuard roles={['CLIENT']}.
 *
 * Features:
 * - Consumes useOrderDetail(pedidoId) for the full PedidoDetail
 * - Shows items with snapshots, totals, address (best-effort)
 * - Conditionally mounts usePaymentStatus when estado_codigo === "PENDIENTE"
 * - Renders OrderHistoryTimeline
 * - Renders EstadoActionBar for CLIENT cancellation
 * - Redirects to /403 on 403, /404 on 404
 * - Skeleton loaders during load
 */

import { useEffect, useState } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { useOrderDetail } from '@/features/orders'
import { OrderHistoryTimeline } from '@/features/orders'
import {
  EstadoActionBar,
  useCancelarPedidoCliente,
  CancelReasonModal,
} from '@/features/pedido-state-actions'

import { useToast } from '@/shared/ui/toast'
import { useConfirm } from '@/shared/ui/confirm-dialog'
import { usePaymentStatus } from '@/features/checkout-payment'
import { usePaymentStore } from '@/shared/store/paymentStore'
import type { PedidoDetail } from '@/entities/pedido/model/types'
import { SkeletonRect, SkeletonLine } from '@/shared/ui/skeleton'

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

function estadoBadgeClass(estado: string): string {
  switch (estado) {
    case 'PENDIENTE': return 'bg-yellow-100 text-yellow-800'
    case 'CONFIRMADO': return 'bg-blue-100 text-blue-800'
    case 'EN_PREP': return 'bg-indigo-100 text-indigo-800'
    case 'EN_CAMINO': return 'bg-purple-100 text-purple-800'
    case 'ENTREGADO': return 'bg-green-100 text-green-800'
    case 'CANCELADO': return 'bg-red-100 text-red-800'
    default: return 'bg-muted text-muted-foreground'
  }
}

function formatARS(decimalStr: string): string {
  const num = parseFloat(decimalStr)
  if (isNaN(num)) return `$ ${decimalStr}`
  return `$ ${num.toLocaleString('es-AR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
}

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleString('es-AR', {
      year: 'numeric', month: '2-digit', day: '2-digit',
      hour: '2-digit', minute: '2-digit',
    })
  } catch { return iso }
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function SkeletonDetail() {
  return (
    <div className="space-y-4" aria-busy="true" aria-label="Cargando detalle del pedido">
      <SkeletonRect height="h-6" className="w-48" />
      <div className="rounded-lg border border-border bg-card p-4 space-y-3">
        {Array.from({ length: 3 }).map((_, i) => (
          <div key={i} className="flex justify-between">
            <SkeletonLine width="w-40" />
            <SkeletonLine width="w-16" />
          </div>
        ))}
      </div>
      <SkeletonRect height="h-32" className="w-full" />
    </div>
  )
}

interface OrderDetailContentProps {
  pedido: PedidoDetail
  pedidoId: string
}

function PaymentStatusPolling({ pedidoId }: { pedidoId: string }) {
  // This component is only rendered when estado_codigo === 'PENDIENTE'
  // Mounting usePaymentStatus here activates polling while order is pending.
  // It uses queryKey ['pago-status', pedidoId] so it's independent from
  // useOrderDetail's ['pedido', pedidoId]. No duplication — different concerns.
  usePaymentStatus(pedidoId)
  return null
}

function OrderDetailContent({ pedido, pedidoId }: OrderDetailContentProps) {
  const paymentStatus = usePaymentStore((s) => s.status)
  const { mutateAsync: cancel, isPending: isCancelPending } = useCancelarPedidoCliente()
  const { toast } = useToast()
  const { confirm } = useConfirm()
  const [cancelModal, setCancelModal] = useState<{ pedidoId: string; open: boolean } | null>(null)

  // CLIENT context: only CANCELADO is ever offered (showAdminActions defaults to false).
  // Staff transitions (EN_PREP, EN_CAMINO, ENTREGADO, CONFIRMADO) are not shown here.
  const handleTransition = async (nuevoEstado: string) => {
    if (nuevoEstado === 'CANCELADO') {
      const ok = await confirm({
        variant: 'destructive',
        title: '¿Cancelar pedido?',
        description: 'Esta acción no se puede deshacer.',
        confirmLabel: 'Sí, cancelar',
      })
      if (!ok) return
      setCancelModal({ pedidoId, open: true })
      return
    }
  }

  const handleCancelConfirm = (motivo: string) => {
    if (!cancelModal) return
    const pid = cancelModal.pedidoId
    setCancelModal(null)
    cancel({ pedidoId: pid, motivo })
      .then(() => {
        toast({ variant: 'success', title: 'Pedido cancelado exitosamente.' })
      })
      .catch(() => {
        toast({ variant: 'error', title: 'Error al cancelar el pedido.' })
      })
  }

  const isLoading = isCancelPending

  return (
    <div className="space-y-6">
      {/* Polling — only when PENDIENTE */}
      {pedido.estado_codigo === 'PENDIENTE' && (
        <PaymentStatusPolling pedidoId={pedidoId} />
      )}

      {/* Header */}
      <div className="flex items-start justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold text-foreground">
            Pedido #{pedido.id.slice(-8).toUpperCase()}
          </h1>
          <p className="text-sm text-muted-foreground">{formatDate(pedido.created_at)}</p>
        </div>
        <span
          className={`rounded-full px-3 py-1 text-xs font-semibold ${estadoBadgeClass(pedido.estado_codigo)}`}
        >
          {pedido.estado_codigo}
        </span>
      </div>

      {/* Estado action bar */}
      <EstadoActionBar
        estadoActual={pedido.estado_codigo}
        onTransition={(nuevoEstado) => void handleTransition(nuevoEstado)}
        isLoading={isLoading}
      />

      {/* Payment status display */}
      {pedido.pago && (
        <div className="rounded-lg border border-border bg-card p-4">
          <h2 className="mb-2 text-sm font-semibold text-foreground">Estado del pago</h2>
          <div className="flex items-center gap-2">
            <span className={`rounded px-2 py-0.5 text-xs font-medium ${
              pedido.pago.mp_status === 'approved' ? 'bg-green-100 text-green-800' :
              pedido.pago.mp_status === 'rejected' ? 'bg-red-100 text-red-800' :
              'bg-yellow-100 text-yellow-800'
            }`}>
              {pedido.pago.mp_status}
            </span>
            {pedido.pago.mp_status_detail && (
              <span className="text-xs text-muted-foreground">{pedido.pago.mp_status_detail}</span>
            )}
          </div>
          {pedido.estado_codigo === 'PENDIENTE' && paymentStatus === 'pending' && (
            <p className="mt-1 text-xs text-muted-foreground">Verificando estado de pago...</p>
          )}
        </div>
      )}

      {/* Items */}
      <div className="rounded-lg border border-border bg-card p-4">
        <h2 className="mb-3 text-sm font-semibold text-foreground">Ítems del pedido</h2>
        <ul className="space-y-3">
          {pedido.items.map((item) => (
            <li key={item.id} className="flex justify-between gap-2 text-sm">
              <div>
                <span className="font-medium text-foreground">{item.nombre_snapshot}</span>
                {item.personalizacion.length > 0 && (
                  <p className="text-xs text-muted-foreground">
                    Sin: {item.personalizacion.join(', ')}
                  </p>
                )}
                <span className="text-xs text-muted-foreground">x{item.cantidad}</span>
              </div>
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
            <span className="text-foreground">{formatARS(pedido.subtotal)}</span>
          </div>
          <div className="flex justify-between text-sm">
            <span className="text-muted-foreground">Envío</span>
            <span className="text-foreground">{formatARS(pedido.costo_envio)}</span>
          </div>
          <div className="flex justify-between font-semibold text-base">
            <span>Total</span>
            <span>{formatARS(pedido.total)}</span>
          </div>
        </div>
      </div>

      {/* Address */}
      {pedido.direccion && (
        <div className="rounded-lg border border-border bg-card p-4">
          <h2 className="mb-1 text-sm font-semibold text-foreground">Dirección de entrega</h2>
          <p className="text-sm text-foreground">{pedido.direccion.linea1}</p>
          {pedido.direccion.alias && (
            <p className="text-xs text-muted-foreground">{pedido.direccion.alias}</p>
          )}
        </div>
      )}

      {/* Notes */}
      {pedido.notas && (
        <div className="rounded-lg border border-border bg-card p-4">
          <h2 className="mb-1 text-sm font-semibold text-foreground">Notas</h2>
          <p className="text-sm text-muted-foreground">{pedido.notas}</p>
        </div>
      )}

      {/* Timeline */}
      <div className="rounded-lg border border-border bg-card p-4">
        <h2 className="mb-3 text-sm font-semibold text-foreground">Historial de estados</h2>
        <OrderHistoryTimeline pedidoId={pedidoId} />
      </div>

      {/* Footer */}
      <div className="flex gap-3">
        <Link
          to="/orders"
          className="rounded-md border border-border bg-background px-4 py-2 text-sm font-medium hover:bg-accent"
        >
          ← Volver a mis pedidos
        </Link>
      </div>

      {/* Cancel reason modal */}
      <CancelReasonModal
        isOpen={cancelModal?.open ?? false}
        onClose={() => setCancelModal(null)}
        onConfirm={handleCancelConfirm}
        isLoading={isLoading}
        title="Cancelar pedido"
      />
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main page component
// ---------------------------------------------------------------------------

export default function OrderDetailPage() {
  const { id: pedidoId } = useParams<{ id: string }>()
  const navigate = useNavigate()

  const { data, isLoading, isError, error } = useOrderDetail(pedidoId)

  const httpStatus = isError ? getHttpStatus(error) : null

  useEffect(() => {
    if (httpStatus === 403) navigate('/403', { replace: true })
    else if (httpStatus === 404) navigate('/404', { replace: true })
  }, [httpStatus, navigate])

  // Render error state only when status is not a handled redirect
  if (isError && httpStatus !== 403 && httpStatus !== 404) {
    return (
      <div className="mx-auto max-w-2xl px-4 py-8 text-center">
        <p className="text-destructive">Error al cargar el pedido.</p>
        <Link to="/orders" className="mt-4 inline-block text-sm underline">
          Volver a mis pedidos
        </Link>
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-2xl px-4 py-6">
      {isLoading && <SkeletonDetail />}
      {data && pedidoId && (
        <OrderDetailContent pedido={data} pedidoId={pedidoId} />
      )}
    </div>
  )
}
