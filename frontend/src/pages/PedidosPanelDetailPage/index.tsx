/**
 * PedidosPanelDetailPage — full order detail for PEDIDOS/ADMIN staff.
 *
 * Change 20: accessible at /pedidos-panel/:id with RoleGuard roles={['PEDIDOS','ADMIN']}.
 *
 * Features:
 * - Consumes useOrderDetail(pedidoId) for full PedidoDetail
 * - Shows cliente data (nombre, apellido, email from usuario field)
 * - Shows items with snapshots, totals, address (best-effort)
 * - OrderHistoryTimeline
 * - EstadoActionBar for staff state transitions
 * - Pago state display (mp_status)
 * - "Volver al panel" → /pedidos-panel
 */

import { useEffect, useState } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { useOrderDetail } from '@/features/orders'
import { OrderHistoryTimeline } from '@/features/orders'
import {
  EstadoActionBar,
  useTransitionEstado,
  CancelReasonModal,
} from '@/features/pedido-state-actions'

import { useToast } from '@/shared/ui/toast'
import { useConfirm } from '@/shared/ui/confirm-dialog'
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
// Skeleton
// ---------------------------------------------------------------------------

function SkeletonDetail() {
  return (
    <div className="animate-pulse space-y-4" aria-busy="true" aria-label="Cargando detalle del pedido">
      <SkeletonRect height="h-6" className="w-56" />
      <div className="rounded-lg border border-border bg-card p-4 space-y-2">
        {Array.from({ length: 3 }).map((_, i) => (
          <SkeletonLine key={i} width="w-full" />
        ))}
      </div>
      <SkeletonRect height="h-40" className="w-full" />
    </div>
  )
}

// ---------------------------------------------------------------------------
// Content
// ---------------------------------------------------------------------------

interface PanelDetailContentProps {
  pedido: PedidoDetail
  pedidoId: string
}

function PanelDetailContent({ pedido, pedidoId }: PanelDetailContentProps) {
  const { mutateAsync: transition, isPending } = useTransitionEstado()
  const { toast } = useToast()
  const { confirm } = useConfirm()
  const [cancelModal, setCancelModal] = useState<{ pedidoId: string; open: boolean } | null>(null)

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
    try {
      await transition({ pedidoId, request: { nuevo_estado: nuevoEstado, motivo: undefined } })
      toast({ variant: 'success', title: `Pedido actualizado a ${nuevoEstado}` })
    } catch {
      toast({ variant: 'error', title: 'Error al actualizar el pedido.' })
    }
  }

  const handleCancelConfirm = (motivo: string) => {
    if (!cancelModal) return
    const pid = cancelModal.pedidoId
    setCancelModal(null)
    transition({ pedidoId: pid, request: { nuevo_estado: 'CANCELADO', motivo } })
      .then(() => {
        toast({ variant: 'success', title: 'Pedido cancelado exitosamente.' })
      })
      .catch(() => {
        toast({ variant: 'error', title: 'Error al cancelar el pedido.' })
      })
  }

  return (
    <div className="space-y-6">
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

      {/* Estado action bar (staff) */}
      <EstadoActionBar
        estadoActual={pedido.estado_codigo}
        onTransition={(nuevoEstado) => void handleTransition(nuevoEstado)}
        isLoading={isPending}
      />

      {/* Cliente info */}
      {pedido.usuario && (
        <div className="rounded-lg border border-border bg-card p-4">
          <h2 className="mb-2 text-sm font-semibold text-foreground">Datos del cliente</h2>
          <dl className="space-y-1 text-sm">
            <div className="flex gap-2">
              <dt className="min-w-16 text-muted-foreground">Nombre:</dt>
              <dd className="text-foreground">
                {pedido.usuario.nombre} {pedido.usuario.apellido}
              </dd>
            </div>
            <div className="flex gap-2">
              <dt className="min-w-16 text-muted-foreground">Email:</dt>
              <dd className="text-foreground">{pedido.usuario.email}</dd>
            </div>
          </dl>
        </div>
      )}

      {/* Payment info */}
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
            {pedido.pago.monto && (
              <span className="ml-auto text-sm font-medium text-foreground">
                {formatARS(pedido.pago.monto)}
              </span>
            )}
          </div>
        </div>
      )}

      {/* Items */}
      <div className="rounded-lg border border-border bg-card p-4">
        <h2 className="mb-3 text-sm font-semibold text-foreground">Ítems del pedido</h2>
        <ul className="space-y-2">
          {pedido.items.map((item) => (
            <li key={item.id} className="flex justify-between gap-2 text-sm">
              <div>
                <span className="font-medium text-foreground">{item.nombre_snapshot}</span>
                <span className="ml-2 text-xs text-muted-foreground">x{item.cantidad}</span>
              </div>
              <span className="font-medium text-foreground whitespace-nowrap">
                {formatARS(item.precio_snapshot)}
              </span>
            </li>
          ))}
        </ul>
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
      <div>
        <Link
          to="/pedidos-panel"
          className="rounded-md border border-border bg-background px-4 py-2 text-sm font-medium hover:bg-accent"
        >
          ← Volver al panel
        </Link>
      </div>

      {/* Cancel reason modal */}
      <CancelReasonModal
        isOpen={cancelModal?.open ?? false}
        onClose={() => setCancelModal(null)}
        onConfirm={handleCancelConfirm}
        isLoading={isPending}
        title="Cancelar pedido"
      />
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main page component
// ---------------------------------------------------------------------------

export default function PedidosPanelDetailPage() {
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
      <div className="mx-auto max-w-2xl px-4 py-8 text-center">
        <p className="text-destructive">Error al cargar el pedido.</p>
        <Link to="/pedidos-panel" className="mt-4 inline-block text-sm underline">
          Volver al panel
        </Link>
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-2xl px-4 py-6">
      {isLoading && <SkeletonDetail />}
      {data && pedidoId && (
        <PanelDetailContent pedido={data} pedidoId={pedidoId} />
      )}
    </div>
  )
}
