/**
 * PedidosPanelPage — Kanban-style order management panel for PEDIDOS/ADMIN roles.
 *
 * Change 24: replaces table view with Kanban columns, one per FSM state.
 * Staff can advance or cancel orders directly from the card action buttons.
 *
 * Features:
 * - One column per state: PENDIENTE, CONFIRMADO, EN_PREP, EN_CAMINO, ENTREGADO, CANCELADO
 * - Column header: human-readable label + count badge
 * - Cards with: short ID, client name/email, total, date, state badge, action buttons
 * - CancelReasonModal for CANCELADO transitions (RN-05: motivo required)
 * - Toast feedback on success / error
 * - Horizontal scroll on small screens
 *
 * RoleGuard roles={['PEDIDOS','ADMIN']} is applied in the router.
 */

import { useState } from 'react'
import { useAdminOrders } from '@/features/orders-panel'
import {
  useTransitionEstado,
  CancelReasonModal,
} from '@/features/pedido-state-actions'
import { useToast, ToastList } from '@/shared/ui/Toast'
import type { PedidoListItem } from '@/entities/pedido/model/types'
import {
  ALL_STATES,
  ESTADO_LABELS,
  TRANSITION_LABELS,
  getAllowedTransitions,
  estadoBadgeClass,
  columnHeaderClass,
  transitionButtonClass,
  formatARS,
  formatDate,
  extractErrorMessage,
} from './utils'
import type { EstadoPedido } from './utils'
import { PedidoDetailModal } from './PedidoDetailModal'

// ---------------------------------------------------------------------------
// PedidoCard
// ---------------------------------------------------------------------------

interface PedidoCardProps {
  pedido: PedidoListItem
  onTransition: (pedidoId: string, nuevoEstado: EstadoPedido) => void
  onCardClick: (pedidoId: string) => void
  pendingPedidoId: string | null
}

function PedidoCard({ pedido, onTransition, onCardClick, pendingPedidoId }: PedidoCardProps) {
  const estado = pedido.estado_codigo as EstadoPedido
  const transitions = getAllowedTransitions(estado, pedido.forma_pago_codigo)
  const isThisCardPending = pendingPedidoId === pedido.id

  return (
    <article
      className="cursor-pointer rounded-lg border border-border bg-card p-3 shadow-sm transition-shadow hover:shadow-md"
      aria-label={`Pedido ${pedido.id.slice(-8).toUpperCase()}`}
      onClick={() => onCardClick(pedido.id)}
    >
      {/* Header: ID + estado badge */}
      <div className="mb-2 flex items-center justify-between gap-1">
        <span className="font-mono text-xs font-semibold text-muted-foreground">
          #{pedido.id.slice(-8).toUpperCase()}
        </span>
        <span
          className={`rounded-full px-2 py-0.5 text-xs font-semibold ${estadoBadgeClass(pedido.estado_codigo)}`}
        >
          {ESTADO_LABELS[estado] ?? estado}
        </span>
      </div>

      {/* Cliente */}
      {pedido.usuario_nombre ? (
        <div className="mb-1">
          <p className="truncate text-sm font-medium text-foreground">{pedido.usuario_nombre}</p>
          <p className="truncate text-xs text-muted-foreground">{pedido.usuario_email}</p>
        </div>
      ) : (
        <p className="mb-1 text-xs text-muted-foreground">—</p>
      )}

      {/* Total + date */}
      <div className="mb-3 flex items-center justify-between text-xs text-muted-foreground">
        <span className="font-semibold text-foreground">{formatARS(pedido.total)}</span>
        <span>{formatDate(pedido.created_at)}</span>
      </div>

      {/* Action buttons — stopPropagation prevents card click from firing */}
      {transitions.length > 0 && (
        <div className="flex flex-wrap gap-1" onClick={(e) => e.stopPropagation()}>
          {transitions.map((next) => (
            <button
              key={next}
              type="button"
              disabled={isThisCardPending}
              onClick={(e) => { e.stopPropagation(); onTransition(pedido.id, next) }}
              className={`rounded px-2 py-1 text-xs font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-50 ${transitionButtonClass(next)}`}
              aria-label={next === 'CANCELADO' ? 'Cancelar pedido' : `Avanzar a ${ESTADO_LABELS[next as EstadoPedido] ?? next}`}
            >
              {isThisCardPending
                ? 'Procesando…'
                : (TRANSITION_LABELS[next as EstadoPedido] ?? `→ ${ESTADO_LABELS[next as EstadoPedido] ?? next}`)}
            </button>
          ))}
        </div>
      )}
    </article>
  )
}

// ---------------------------------------------------------------------------
// KanbanColumn
// ---------------------------------------------------------------------------

interface KanbanColumnProps {
  estado: EstadoPedido
  pedidos: PedidoListItem[]
  onTransition: (pedidoId: string, nuevoEstado: EstadoPedido) => void
  onCardClick: (pedidoId: string) => void
  pendingPedidoId: string | null
}

function KanbanColumn({ estado, pedidos, onTransition, onCardClick, pendingPedidoId }: KanbanColumnProps) {
  const headerClass = columnHeaderClass(estado)

  return (
    <div
      className="flex min-w-[220px] flex-col gap-3"
      aria-label={`Columna ${ESTADO_LABELS[estado]}`}
      data-estado={estado}
    >
      {/* Column header */}
      <div
        className={`flex items-center justify-between rounded-md border-b-2 px-3 py-2 ${headerClass}`}
      >
        <span className="text-sm font-semibold text-foreground">
          {ESTADO_LABELS[estado]}
        </span>
        <span
          className="rounded-full bg-muted px-2 py-0.5 text-xs font-bold text-muted-foreground"
          aria-label={`${pedidos.length} pedidos`}
        >
          {pedidos.length}
        </span>
      </div>

      {/* Cards */}
      <div className="flex max-h-[calc(100vh-220px)] flex-col gap-3 overflow-y-auto pb-2">
        {pedidos.map((pedido) => (
          <PedidoCard
            key={pedido.id}
            pedido={pedido}
            onTransition={onTransition}
            onCardClick={onCardClick}
            pendingPedidoId={pendingPedidoId}
          />
        ))}
        {pedidos.length === 0 && (
          <div className="rounded-lg border border-dashed border-border px-3 py-6 text-center text-xs text-muted-foreground">
            Sin pedidos
          </div>
        )}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export default function PedidosPanelPage() {
  const { toasts, showToast } = useToast()

  // Fetch ALL pedidos (large page for Kanban — no per-column pagination)
  const { data, isLoading, isError, error, refetch } = useAdminOrders({ size: 100 })
  const items: PedidoListItem[] = data?.items ?? []

  // Mutation
  const { mutateAsync: transitionMutate, isPending } = useTransitionEstado()

  // Track which pedido is currently being mutated (to disable its buttons)
  const [pendingPedidoId, setPendingPedidoId] = useState<string | null>(null)

  // Detail modal state — null = closed; track full list item for client-name fallback
  const [selectedPedido, setSelectedPedido] = useState<PedidoListItem | null>(null)

  // Cancel modal state
  const [cancelModal, setCancelModal] = useState<{
    pedidoId: string
    open: boolean
  } | null>(null)

  // ---------------------------------------------------------------------------
  // Group pedidos by estado
  // ---------------------------------------------------------------------------

  const grouped: Record<EstadoPedido, PedidoListItem[]> = {
    PENDIENTE:  [],
    CONFIRMADO: [],
    EN_PREP:    [],
    EN_CAMINO:  [],
    ENTREGADO:  [],
    CANCELADO:  [],
  }

  for (const pedido of items) {
    const estado = pedido.estado_codigo as EstadoPedido
    if (grouped[estado]) {
      grouped[estado].push(pedido)
    }
  }

  // ---------------------------------------------------------------------------
  // Transition handler
  // ---------------------------------------------------------------------------

  function handleTransition(pedidoId: string, nuevoEstado: EstadoPedido) {
    if (nuevoEstado === 'CANCELADO') {
      // Open cancel modal to collect motivo (RN-05: motivo required)
      setCancelModal({ pedidoId, open: true })
      return
    }
    void executeTransition(pedidoId, nuevoEstado, undefined)
  }

  async function executeTransition(
    pedidoId: string,
    nuevoEstado: EstadoPedido,
    motivo: string | undefined,
  ) {
    setPendingPedidoId(pedidoId)
    try {
      await transitionMutate({
        pedidoId,
        request: { nuevo_estado: nuevoEstado, motivo: motivo ?? null },
      })
      showToast(`Pedido actualizado a ${ESTADO_LABELS[nuevoEstado]}`, 'success')
    } catch (err: unknown) {
      const message = extractErrorMessage(err)
      showToast(message, 'error')
    } finally {
      setPendingPedidoId(null)
    }
  }

  function handleCancelConfirm(motivo: string) {
    if (!cancelModal) return
    const { pedidoId } = cancelModal
    setCancelModal(null)
    void executeTransition(pedidoId, 'CANCELADO', motivo)
  }

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  return (
    <div className="space-y-6 p-6">
      {/* Header */}
      <header>
        <h1 className="text-2xl font-bold text-foreground">Panel de Pedidos</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Vista Kanban — usá los botones de cada tarjeta para avanzar o cancelar pedidos.
        </p>
      </header>

      {/* Error state */}
      {isError && !isLoading && (
        <div className="rounded-lg border border-destructive/40 bg-destructive/5 p-6 text-center">
          <p className="mb-2 text-sm font-medium text-destructive">
            Error al cargar los pedidos.
          </p>
          <p className="mb-4 text-xs text-muted-foreground">
            {error instanceof Error ? error.message : 'Error desconocido.'}
          </p>
          <button
            onClick={() => void refetch()}
            className="rounded-md bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground hover:bg-primary/90"
          >
            Reintentar
          </button>
        </div>
      )}

      {/* Loading skeleton */}
      {isLoading && (
        <div className="overflow-x-auto">
          <div className="flex gap-4 pb-4">
            {ALL_STATES.map((estado) => (
              <div key={estado} className="flex min-w-[220px] flex-col gap-3">
                <div className="h-10 animate-pulse rounded-md bg-muted" />
                {[1, 2].map((i) => (
                  <div key={i} className="h-28 animate-pulse rounded-lg bg-muted" />
                ))}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Kanban board */}
      {!isLoading && !isError && (
        <div className="overflow-x-auto">
          <div className="flex gap-4 pb-4" role="list" aria-label="Tablero Kanban de pedidos">
            {ALL_STATES.map((estado) => (
              <KanbanColumn
                key={estado}
                estado={estado}
                pedidos={grouped[estado]}
                onTransition={handleTransition}
                onCardClick={(id) => setSelectedPedido(grouped[estado].find(p => p.id === id) ?? null)}
                pendingPedidoId={pendingPedidoId}
              />
            ))}
          </div>
        </div>
      )}

      {/* Order detail modal */}
      <PedidoDetailModal
        pedidoId={selectedPedido?.id ?? null}
        listItem={selectedPedido ?? undefined}
        onClose={() => setSelectedPedido(null)}
        onTransition={handleTransition}
        pendingPedidoId={pendingPedidoId}
      />

      {/* Cancel reason modal */}
      <CancelReasonModal
        isOpen={cancelModal?.open ?? false}
        onClose={() => setCancelModal(null)}
        onConfirm={handleCancelConfirm}
        isLoading={isPending}
        title="Cancelar pedido"
      />

      {/* Toast notifications */}
      <ToastList toasts={toasts} />
    </div>
  )
}
