/**
 * Utility helpers for PedidosPanelPage Kanban view.
 *
 * Kept separate from the page component to satisfy react-refresh/only-export-components.
 */

import { FRONTEND_ALLOWED_TRANSITIONS } from '@/features/pedido-state-actions'

export type EstadoPedido =
  | 'PENDIENTE'
  | 'CONFIRMADO'
  | 'EN_PREP'
  | 'EN_CAMINO'
  | 'ENTREGADO'
  | 'CANCELADO'

export const ALL_STATES: EstadoPedido[] = [
  'PENDIENTE',
  'CONFIRMADO',
  'EN_PREP',
  'EN_CAMINO',
  'ENTREGADO',
  'CANCELADO',
]

export const ESTADO_LABELS: Record<EstadoPedido, string> = {
  PENDIENTE: 'Pendiente',
  CONFIRMADO: 'Confirmado',
  EN_PREP: 'En Preparación',
  EN_CAMINO: 'En Camino',
  ENTREGADO: 'Entregado',
  CANCELADO: 'Cancelado',
}

/** Human-readable labels for action buttons (target state → button label). */
export const TRANSITION_LABELS: Partial<Record<EstadoPedido, string>> = {
  CONFIRMADO: 'Confirmar pedido',
  EN_PREP: 'Pasar a preparación',
  EN_CAMINO: 'Enviar pedido',
  ENTREGADO: 'Marcar como entregado',
  CANCELADO: 'Cancelar pedido',
}

/**
 * Returns the list of valid next states for a given current state.
 * Based on FRONTEND_ALLOWED_TRANSITIONS (spec-backed FSM map).
 * UI hint only — backend enforces actual authorization.
 *
 * For PENDIENTE orders, the available transitions depend on the payment method:
 * - EFECTIVO: staff can manually confirm → ['CONFIRMADO', 'CANCELADO']
 * - Other (MERCADOPAGO, etc.): auto-confirmed via webhook → ['CANCELADO'] only
 */
export function getAllowedTransitions(estado: EstadoPedido, forma_pago_codigo?: string): EstadoPedido[] {
  if (estado === 'PENDIENTE') {
    const base = ['CANCELADO'] as EstadoPedido[]
    return forma_pago_codigo === 'EFECTIVO'
      ? (['CONFIRMADO', 'CANCELADO'] as EstadoPedido[])
      : base
  }
  return (FRONTEND_ALLOWED_TRANSITIONS[estado] ?? []) as EstadoPedido[]
}

export function estadoBadgeClass(estado: string): string {
  switch (estado) {
    case 'PENDIENTE':  return 'bg-yellow-100 text-yellow-800'
    case 'CONFIRMADO': return 'bg-blue-100 text-blue-800'
    case 'EN_PREP':    return 'bg-indigo-100 text-indigo-800'
    case 'EN_CAMINO':  return 'bg-purple-100 text-purple-800'
    case 'ENTREGADO':  return 'bg-green-100 text-green-800'
    case 'CANCELADO':  return 'bg-red-100 text-red-800'
    default:           return 'bg-muted text-muted-foreground'
  }
}

export function columnHeaderClass(estado: EstadoPedido): string {
  switch (estado) {
    case 'PENDIENTE':  return 'border-yellow-400 bg-yellow-50'
    case 'CONFIRMADO': return 'border-blue-400 bg-blue-50'
    case 'EN_PREP':    return 'border-indigo-400 bg-indigo-50'
    case 'EN_CAMINO':  return 'border-purple-400 bg-purple-50'
    case 'ENTREGADO':  return 'border-green-400 bg-green-50'
    case 'CANCELADO':  return 'border-red-400 bg-red-50'
    default:           return 'border-border bg-muted'
  }
}

export function transitionButtonClass(nextEstado: string): string {
  switch (nextEstado) {
    case 'CONFIRMADO': return 'bg-blue-600 hover:bg-blue-700 text-white'
    case 'EN_PREP':    return 'bg-indigo-600 hover:bg-indigo-700 text-white'
    case 'EN_CAMINO':  return 'bg-purple-600 hover:bg-purple-700 text-white'
    case 'ENTREGADO':  return 'bg-green-600 hover:bg-green-700 text-white'
    case 'CANCELADO':  return 'bg-red-600 hover:bg-red-700 text-white'
    default:           return 'bg-gray-600 hover:bg-gray-700 text-white'
  }
}

export function formatARS(decimalStr: string): string {
  const num = parseFloat(decimalStr)
  if (isNaN(num)) return `$ ${decimalStr}`
  return `$ ${num.toLocaleString('es-AR', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`
}

export function formatDate(iso: string): string {
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

export const ERROR_MESSAGES: Record<string, string> = {
  INVALID_TRANSITION: 'Transición de estado no permitida desde el estado actual.',
  TERMINAL_STATE: 'El pedido ya está en un estado terminal y no puede modificarse.',
  MOTIVO_REQUIRED: 'Debes ingresar un motivo para cancelar el pedido.',
  CANCEL_NOT_ALLOWED_FOR_ROLE: 'Tu rol no permite cancelar pedidos en este estado.',
  ORDER_NOT_FOUND: 'Pedido no encontrado.',
  ORDER_NOT_OWNED: 'No puedes cancelar un pedido que no es tuyo.',
}

interface ApiErrorBody {
  code?: string
  detail?: string
}

export function extractErrorMessage(err: unknown): string {
  if (err && typeof err === 'object') {
    const axiosErr = err as { response?: { data?: ApiErrorBody } }
    const code = axiosErr.response?.data?.code
    if (code && ERROR_MESSAGES[code]) {
      return ERROR_MESSAGES[code]!
    }
    const detail = axiosErr.response?.data?.detail
    if (detail) return detail
  }
  return 'Ocurrió un error al actualizar el estado del pedido.'
}
