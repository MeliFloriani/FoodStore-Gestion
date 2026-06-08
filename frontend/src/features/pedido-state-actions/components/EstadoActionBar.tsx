/**
 * EstadoActionBar — renders action buttons for FSM state transitions.
 *
 * IMPORTANT: This component drives UI only. It NEVER makes authorization decisions.
 * The buttons shown are derived from CLIENT_ALLOWED_TRANSITIONS (default, client view)
 * or FRONTEND_ALLOWED_TRANSITIONS (when showAdminActions=true, staff view).
 * Actual authorization (FSM + RBAC per transition) is enforced exclusively by the backend.
 *
 * Change 18: staff transition UI.
 * Pre-Change-24 fix: added showAdminActions prop to hide staff buttons from CLIENT context.
 */

import { FRONTEND_ALLOWED_TRANSITIONS, CLIENT_ALLOWED_TRANSITIONS } from '../api/pedidoEstadoApi'

export interface EstadoActionBarProps {
  /** Current order estado_codigo */
  estadoActual: string
  /** Called when a transition button is clicked */
  onTransition: (nuevoEstado: string) => void
  /** Whether a transition is in progress (disables all buttons) */
  isLoading?: boolean
  /** Optional className for the container */
  className?: string
  /**
   * When true, shows the full staff transition map (ADMIN/PEDIDOS panel context).
   * When false (default), shows only CLIENT-allowed transitions (cancel own order only).
   *
   * Always pass showAdminActions={true} explicitly in admin panel components.
   * Never pass it in client-facing pages — the default false is the safe baseline.
   */
  showAdminActions?: boolean
}

/** Human-readable labels for each estado_codigo */
const ESTADO_LABELS: Record<string, string> = {
  PENDIENTE: 'Pendiente',
  CONFIRMADO: 'Confirmado',
  EN_PREP: 'En Preparación',
  EN_CAMINO: 'En Camino',
  ENTREGADO: 'Entregado',
  CANCELADO: 'Cancelado',
}

/** Color variant for each transition target */
const TRANSITION_STYLES: Record<string, string> = {
  EN_PREP: 'bg-blue-600 hover:bg-blue-700 text-white',
  EN_CAMINO: 'bg-indigo-600 hover:bg-indigo-700 text-white',
  ENTREGADO: 'bg-green-600 hover:bg-green-700 text-white',
  CANCELADO: 'bg-red-600 hover:bg-red-700 text-white',
}

const DEFAULT_BUTTON_STYLE = 'bg-gray-600 hover:bg-gray-700 text-white'

/**
 * Renders action buttons for available FSM transitions.
 *
 * Defaults to CLIENT context (showAdminActions=false): only shows cancellation
 * buttons that a CLIENT user is permitted to trigger via DELETE /api/v1/pedidos/{id}.
 *
 * Admin panel components must pass showAdminActions={true} to see the full staff
 * transition set.
 */
export function EstadoActionBar({
  estadoActual,
  onTransition,
  isLoading = false,
  className = '',
  showAdminActions = false,
}: EstadoActionBarProps) {
  const transitionMap = showAdminActions
    ? FRONTEND_ALLOWED_TRANSITIONS
    : CLIENT_ALLOWED_TRANSITIONS

  const availableTransitions = transitionMap[estadoActual] ?? []

  if (availableTransitions.length === 0) {
    return null
  }

  return (
    <div className={`flex gap-2 flex-wrap ${className}`} role="group" aria-label="Acciones de estado del pedido">
      {availableTransitions.map((nuevoEstado) => (
        <button
          key={nuevoEstado}
          type="button"
          onClick={() => onTransition(nuevoEstado)}
          disabled={isLoading}
          className={`
            px-4 py-2 rounded-md text-sm font-medium transition-colors
            disabled:opacity-50 disabled:cursor-not-allowed
            ${TRANSITION_STYLES[nuevoEstado] ?? DEFAULT_BUTTON_STYLE}
          `}
          aria-label={`Avanzar a ${ESTADO_LABELS[nuevoEstado] ?? nuevoEstado}`}
        >
          {isLoading ? 'Procesando...' : `→ ${ESTADO_LABELS[nuevoEstado] ?? nuevoEstado}`}
        </button>
      ))}
    </div>
  )
}
