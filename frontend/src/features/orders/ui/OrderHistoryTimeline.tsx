/**
 * OrderHistoryTimeline — visual chronological timeline of order state transitions.
 *
 * Change 20: renders the historial of a pedido fetched via useHistorialPedido.
 *
 * Design decisions:
 * - Reuses useHistorialPedido from features/pedido-state-actions (D-07).
 *   Does NOT reimplment the fetching logic.
 * - First entry has estado_desde: null — renders as "Pedido creado — PENDIENTE".
 * - actor_user_id: null → "Sistema" (webhook or system-generated transition).
 * - Chronological order is guaranteed by backend (ASC by created_at).
 * - FSD compliance: imports only from entities/ and shared/ or from
 *   features/pedido-state-actions (another feature — same level, allowed via
 *   feature barrel export).
 */

import { useHistorialPedido } from '@/features/pedido-state-actions'
import type { HistorialEstadoPedidoRead } from '@/entities/pedido/model/historialTypes'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Format ISO timestamp to locale AR: dd/MM/yyyy HH:mm */
function formatTimestamp(iso: string): string {
  try {
    return new Date(iso).toLocaleString('es-AR', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    })
  } catch {
    return iso
  }
}

/** Color variant per target state */
function estadoColor(estado: string): string {
  switch (estado) {
    case 'PENDIENTE':
      return 'bg-yellow-100 text-yellow-800 border-yellow-300'
    case 'CONFIRMADO':
      return 'bg-blue-100 text-blue-800 border-blue-300'
    case 'EN_PREP':
      return 'bg-indigo-100 text-indigo-800 border-indigo-300'
    case 'EN_CAMINO':
      return 'bg-purple-100 text-purple-800 border-purple-300'
    case 'ENTREGADO':
      return 'bg-green-100 text-green-800 border-green-300'
    case 'CANCELADO':
      return 'bg-red-100 text-red-800 border-red-300'
    default:
      return 'bg-muted text-muted-foreground border-border'
  }
}

/** Dot color for the timeline connector */
function dotColor(estado: string): string {
  switch (estado) {
    case 'PENDIENTE':
      return 'bg-yellow-400'
    case 'CONFIRMADO':
      return 'bg-blue-500'
    case 'EN_PREP':
      return 'bg-indigo-500'
    case 'EN_CAMINO':
      return 'bg-purple-500'
    case 'ENTREGADO':
      return 'bg-green-500'
    case 'CANCELADO':
      return 'bg-red-500'
    default:
      return 'bg-muted-foreground'
  }
}

// ---------------------------------------------------------------------------
// Skeleton
// ---------------------------------------------------------------------------

function TimelineSkeleton() {
  return (
    <div aria-busy="true" aria-label="Cargando historial">
      {[0, 1, 2].map((i) => (
        <div key={i} className="flex gap-3 pb-4">
          <div className="flex flex-col items-center">
            <div className="h-3 w-3 animate-pulse rounded-full bg-muted" />
            {i < 2 && <div className="mt-1 h-12 w-0.5 animate-pulse bg-muted" />}
          </div>
          <div className="flex-1 space-y-1.5 pb-2">
            <div className="h-4 w-32 animate-pulse rounded bg-muted" />
            <div className="h-3 w-24 animate-pulse rounded bg-muted" />
          </div>
        </div>
      ))}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Single timeline entry
// ---------------------------------------------------------------------------

interface TimelineEntryProps {
  entry: HistorialEstadoPedidoRead
  isLast: boolean
}

function TimelineEntry({ entry, isLast }: TimelineEntryProps) {
  const isFirst = entry.estado_desde === null
  const actor = entry.actor_user_id ? 'Gestor' : 'Sistema'
  const stateLabel = isFirst
    ? `Pedido creado — ${entry.estado_hacia}`
    : `${entry.estado_desde} → ${entry.estado_hacia}`

  return (
    <div className="flex gap-3">
      {/* Timeline connector */}
      <div className="flex flex-col items-center">
        <div
          className={`mt-1 h-3 w-3 flex-shrink-0 rounded-full ${dotColor(entry.estado_hacia)} ${isLast ? 'ring-2 ring-offset-1 ring-current' : ''}`}
        />
        {!isLast && <div className="mt-1 flex-1 w-0.5 min-h-8 bg-border" />}
      </div>

      {/* Content */}
      <div className={`pb-4 ${isLast ? '' : ''}`}>
        {/* State badge */}
        <span
          className={`inline-block rounded-full border px-2 py-0.5 text-xs font-semibold ${estadoColor(entry.estado_hacia)}`}
        >
          {stateLabel}
        </span>

        {/* Timestamp and actor */}
        <div className="mt-0.5 flex items-center gap-2 text-xs text-muted-foreground">
          <time dateTime={entry.created_at}>{formatTimestamp(entry.created_at)}</time>
          <span>·</span>
          <span>{actor}</span>
        </div>

        {/* Optional motivo */}
        {entry.motivo && (
          <p className="mt-0.5 text-xs italic text-muted-foreground">
            Motivo: {entry.motivo}
          </p>
        )}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export interface OrderHistoryTimelineProps {
  pedidoId: string
}

/**
 * Renders a chronological timeline of order state transitions.
 *
 * Consumes useHistorialPedido(pedidoId) — does NOT reimplment the hook.
 */
export function OrderHistoryTimeline({ pedidoId }: OrderHistoryTimelineProps) {
  const { data: historial, isLoading, isError } = useHistorialPedido(pedidoId)

  if (isLoading) {
    return <TimelineSkeleton />
  }

  if (isError) {
    return (
      <p className="text-sm text-destructive" role="alert">
        No se pudo cargar el historial del pedido.
      </p>
    )
  }

  if (!historial || historial.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">Sin historial disponible.</p>
    )
  }

  return (
    <div aria-label="Historial de estados del pedido">
      {historial.map((entry, index) => (
        <TimelineEntry
          key={entry.id}
          entry={entry}
          isLast={index === historial.length - 1}
        />
      ))}
    </div>
  )
}
