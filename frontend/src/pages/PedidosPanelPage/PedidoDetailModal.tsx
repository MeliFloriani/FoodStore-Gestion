/**
 * PedidoDetailModal — full order detail modal for the admin Kanban panel.
 *
 * Fetches PedidoDetail via useOrderDetail (GET /api/v1/pedidos/{id}).
 * Displays: ID, estado, client, dates, totals, payment, address, notes,
 * line items with snapshots/personalizations, and state history.
 *
 * Action buttons call onTransition — the parent (PedidosPanelPage) handles
 * the CancelReasonModal flow and the actual mutation.
 *
 * Modal stays open after a successful transition so the user can see the
 * updated state (useOrderDetail auto-refetches when invalidated by the
 * useTransitionEstado onSuccess invalidation).
 */

import { useOrderDetail } from '@/features/orders'
import type { PedidoListItem } from '@/entities/pedido/model/types'
import {
  ESTADO_LABELS,
  TRANSITION_LABELS,
  getAllowedTransitions,
  estadoBadgeClass,
  transitionButtonClass,
  formatARS,
  formatDate,
} from './utils'
import type { EstadoPedido } from './utils'

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface PedidoDetailModalProps {
  /** ID of the order to show; null = modal is closed */
  pedidoId: string | null
  /**
   * Compact list item — used as fallback for client name/email when the full
   * detail's usuario field is null (e.g. user account deleted).
   */
  listItem?: PedidoListItem
  onClose: () => void
  /** Callback for state-change buttons — parent handles cancel-reason flow */
  onTransition: (pedidoId: string, nuevoEstado: EstadoPedido) => void
  /** ID of the pedido currently being mutated (disables buttons) */
  pendingPedidoId: string | null
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function PedidoDetailModal({
  pedidoId,
  listItem,
  onClose,
  onTransition,
  pendingPedidoId,
}: PedidoDetailModalProps) {
  const { data: pedido, isLoading, isError, error } = useOrderDetail(pedidoId)

  if (!pedidoId) return null

  const estado = (pedido?.estado_codigo ?? '') as EstadoPedido
  const transitions = pedido ? getAllowedTransitions(estado, pedido.forma_pago_codigo) : []
  const isThisPending = pendingPedidoId === pedidoId

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="pedido-detail-title"
      className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/50 p-4"
    >
      <div className="my-8 w-full max-w-2xl rounded-lg bg-background shadow-xl">
        {/* ── Header ── */}
        <div className="flex items-center justify-between border-b border-border p-4">
          <h2
            id="pedido-detail-title"
            className="text-lg font-semibold text-foreground"
          >
            {isLoading
              ? 'Cargando pedido…'
              : pedido
                ? `Pedido #${pedido.id.slice(-8).toUpperCase()}`
                : 'Detalle del pedido'}
          </h2>
          <button
            type="button"
            onClick={onClose}
            aria-label="Cerrar modal"
            className="rounded p-1 text-muted-foreground hover:bg-muted transition-colors"
          >
            ✕
          </button>
        </div>

        {/* ── Body ── */}
        <div className="space-y-5 p-5">
          {/* Loading */}
          {isLoading && (
            <div className="flex h-40 items-center justify-center">
              <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
            </div>
          )}

          {/* Error */}
          {isError && (
            <div className="rounded-md border border-destructive/40 bg-destructive/5 p-4 text-sm text-destructive">
              {error instanceof Error ? error.message : 'Error al cargar el pedido.'}
            </div>
          )}

          {/* Detail */}
          {pedido && (
            <>
              {/* Estado + fecha */}
              <div className="flex flex-wrap items-center gap-3">
                <span
                  className={`rounded-full px-3 py-1 text-xs font-semibold ${estadoBadgeClass(pedido.estado_codigo)}`}
                >
                  {ESTADO_LABELS[estado] ?? pedido.estado_codigo}
                </span>
                <span className="text-xs text-muted-foreground">
                  {formatDate(pedido.created_at)}
                </span>
              </div>

              {/* Cliente */}
              {(() => {
                const nombre = pedido.usuario
                  ? `${pedido.usuario.nombre} ${pedido.usuario.apellido}`
                  : listItem?.usuario_nombre ?? null
                const email = pedido.usuario?.email ?? listItem?.usuario_email ?? null
                if (!nombre && !email) return null
                return (
                  <div>
                    <p className="mb-1 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                      Cliente
                    </p>
                    {nombre && (
                      <p className="text-sm font-medium text-foreground">{nombre}</p>
                    )}
                    {email && (
                      <p className="text-xs text-muted-foreground">{email}</p>
                    )}
                  </div>
                )
              })()}

              {/* Totales */}
              <div className="grid grid-cols-2 gap-4 rounded-md bg-muted/40 p-3 text-sm sm:grid-cols-4">
                <div>
                  <p className="text-xs text-muted-foreground">Subtotal</p>
                  <p className="font-medium">{formatARS(pedido.subtotal)}</p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground">Envío</p>
                  <p className="font-medium">{formatARS(pedido.costo_envio)}</p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground">Total</p>
                  <p className="font-semibold text-foreground">{formatARS(pedido.total)}</p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground">Pago</p>
                  <p className="font-medium">{pedido.forma_pago_codigo}</p>
                </div>
              </div>

              {/* Dirección / retiro */}
              {pedido.direccion ? (
                <div>
                  <p className="mb-1 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                    Dirección de entrega
                  </p>
                  {pedido.direccion.alias && (
                    <p className="mb-0.5 text-xs font-medium text-foreground">
                      {pedido.direccion.alias}
                    </p>
                  )}
                  <p className="text-sm">{pedido.direccion.linea1}</p>
                  {pedido.direccion.linea2 && (
                    <p className="text-sm">{pedido.direccion.linea2}</p>
                  )}
                  {(pedido.direccion.ciudad || pedido.direccion.provincia) && (
                    <p className="text-sm">
                      {[pedido.direccion.ciudad, pedido.direccion.provincia]
                        .filter(Boolean)
                        .join(', ')}
                      {pedido.direccion.codigo_postal && ` (${pedido.direccion.codigo_postal})`}
                    </p>
                  )}
                  {pedido.direccion.referencia && (
                    <p className="mt-1 text-xs text-muted-foreground">
                      Referencia: {pedido.direccion.referencia}
                    </p>
                  )}
                </div>
              ) : (
                <div>
                  <p className="mb-1 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                    Entrega
                  </p>
                  <p className="text-sm">Retiro en local</p>
                </div>
              )}

              {/* Notas */}
              {pedido.notas && (
                <div>
                  <p className="mb-1 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                    Notas
                  </p>
                  <p className="rounded-md border border-border bg-muted/20 p-2 text-sm">
                    {pedido.notas}
                  </p>
                </div>
              )}

              {/* Productos */}
              <div>
                <p className="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                  Productos ({pedido.items.length})
                </p>
                <div className="divide-y divide-border rounded-md border border-border">
                  {pedido.items.map((item) => {
                    const subtotalItem = (
                      parseFloat(item.precio_snapshot) * item.cantidad
                    ).toFixed(2)
                    return (
                      <div
                        key={item.id}
                        className="flex items-start justify-between gap-2 px-3 py-2"
                      >
                        <div className="flex-1 text-sm">
                          <p className="font-medium">{item.nombre_snapshot}</p>
                          {item.personalizacion.length > 0 && (
                            <p className="text-xs text-muted-foreground">
                              Sin: {item.personalizacion.join(', ')}
                            </p>
                          )}
                        </div>
                        <div className="text-right text-sm">
                          <p className="text-muted-foreground">
                            {item.cantidad} × {formatARS(item.precio_snapshot)}
                          </p>
                          <p className="font-medium">{formatARS(subtotalItem)}</p>
                        </div>
                      </div>
                    )
                  })}
                </div>
              </div>

              {/* Historial */}
              {pedido.historial.length > 0 && (
                <div>
                  <p className="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                    Historial de estados
                  </p>
                  <ol className="space-y-1">
                    {pedido.historial.map((h) => (
                      <li key={h.id} className="flex items-start gap-2 text-xs">
                        <span className="mt-0.5 h-2 w-2 shrink-0 rounded-full bg-muted-foreground" />
                        <div>
                          <span className="font-medium">
                            {h.estado_desde
                              ? `${ESTADO_LABELS[h.estado_desde as EstadoPedido] ?? h.estado_desde} → ${ESTADO_LABELS[h.estado_hacia as EstadoPedido] ?? h.estado_hacia}`
                              : ESTADO_LABELS[h.estado_hacia as EstadoPedido] ?? h.estado_hacia}
                          </span>
                          {h.motivo && (
                            <span className="ml-1 text-muted-foreground">
                              — {h.motivo}
                            </span>
                          )}
                          <span className="ml-1 text-muted-foreground">
                            {formatDate(h.created_at)}
                          </span>
                        </div>
                      </li>
                    ))}
                  </ol>
                </div>
              )}

              {/* Info badge for PENDIENTE + MERCADOPAGO (auto-confirmed via webhook) */}
              {estado === 'PENDIENTE' && pedido.forma_pago_codigo !== 'EFECTIVO' && (
                <div className="rounded-md border border-blue-200 bg-blue-50 px-3 py-2 text-xs text-blue-700">
                  Esperando confirmación de pago (MercadoPago). La confirmación es automática.
                </div>
              )}

              {/* Action buttons */}
              {transitions.length > 0 && (
                <div className="flex flex-wrap gap-2 border-t border-border pt-4">
                  {transitions.map((next) => (
                    <button
                      key={next}
                      type="button"
                      disabled={isThisPending}
                      onClick={() => onTransition(pedidoId, next)}
                      aria-label={
                        next === 'CANCELADO'
                          ? 'Cancelar pedido'
                          : `Avanzar a ${ESTADO_LABELS[next as EstadoPedido] ?? next}`
                      }
                      className={`rounded-md px-4 py-2 text-sm font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-50 ${transitionButtonClass(next)}`}
                    >
                      {isThisPending
                        ? 'Procesando…'
                        : (TRANSITION_LABELS[next as EstadoPedido] ?? `→ ${ESTADO_LABELS[next as EstadoPedido] ?? next}`)}
                    </button>
                  ))}
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  )
}
