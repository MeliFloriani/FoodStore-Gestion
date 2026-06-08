/**
 * PaymentRetryBanner — shows error details and retry option when payment fails.
 *
 * Change 19 — payments-mercadopago-integration (task 14.4).
 *
 * Displayed when paymentStore.status === "rejected" or "error".
 * Shows the mp_status_detail reason code in human-readable Spanish.
 * Offers a "Reintentar pago" button to go back to the card widget.
 *
 * Design decisions (task 16.5 / M-04):
 * - Do NOT show retry button when pedido.estado_codigo is "CANCELADO" or "ENTREGADO"
 *   (terminal states where payment retry is not valid).
 * - The banner maps common MP rejection codes to user-friendly messages.
 *   Unknown codes fall back to a generic message.
 */

import { usePaymentStore } from '@/shared/store/paymentStore'

interface PaymentRetryBannerProps {
  /** Raw mp_status_detail from PagoResponse — e.g. "cc_rejected_bad_filled_cvv" */
  statusDetail: string | null
  /** Called when user clicks "Reintentar pago" button */
  onRetry: () => void
  /**
   * Current pedido state code.
   * If "CANCELADO" or "ENTREGADO", the retry button is hidden (terminal states).
   */
  pedidoEstadoCodigo?: string | null
}

/** Map MP status_detail codes to user-friendly Spanish messages. */
function getDetailMessage(statusDetail: string | null): string {
  if (!statusDetail) {
    return 'El pago no pudo ser procesado. Por favor intentá de nuevo.'
  }

  switch (statusDetail) {
    case 'cc_rejected_bad_filled_cvv':
      return 'El código de seguridad (CVV) ingresado es incorrecto.'
    case 'cc_rejected_bad_filled_date':
      return 'La fecha de vencimiento ingresada es incorrecta.'
    case 'cc_rejected_bad_filled_other':
      return 'Los datos de la tarjeta son incorrectos. Verificá y volvé a intentarlo.'
    case 'cc_rejected_card_disabled':
      return 'La tarjeta está deshabilitada. Contactá a tu banco.'
    case 'cc_rejected_duplicated_payment':
      return 'Ya existe un pago duplicado para esta tarjeta.'
    case 'cc_rejected_insufficient_amount':
      return 'La tarjeta no tiene fondos suficientes.'
    case 'cc_rejected_invalid_installments':
      return 'La cantidad de cuotas seleccionada no es válida para esta tarjeta.'
    case 'cc_rejected_max_attempts':
      return 'Superaste el número máximo de intentos. Usá otra tarjeta.'
    case 'cc_rejected_other_reason':
      return 'La tarjeta fue rechazada. Contactá a tu banco o usá otra tarjeta.'
    default:
      return 'El pago no pudo ser procesado. Por favor intentá con otra tarjeta.'
  }
}

/** Terminal order states where payment retry makes no sense. */
const TERMINAL_ORDER_STATES = new Set(['CANCELADO', 'ENTREGADO'])

/**
 * Banner displayed when a payment attempt fails.
 *
 * Shows the human-readable rejection reason and a retry button.
 * The retry button is hidden for terminal order states (M-04).
 */
export function PaymentRetryBanner({ statusDetail, onRetry, pedidoEstadoCodigo }: PaymentRetryBannerProps) {
  const lastErrorCode = usePaymentStore((state) => state.lastErrorCode)
  const isTerminalState = pedidoEstadoCodigo != null && TERMINAL_ORDER_STATES.has(pedidoEstadoCodigo)

  const message = getDetailMessage(statusDetail ?? lastErrorCode)

  return (
    <div
      role="alert"
      className="rounded-md border border-red-200 bg-red-50 px-4 py-4"
    >
      <div className="flex items-start gap-3">
        {/* Error icon */}
        <svg
          className="mt-0.5 h-5 w-5 flex-shrink-0 text-red-500"
          xmlns="http://www.w3.org/2000/svg"
          viewBox="0 0 20 20"
          fill="currentColor"
          aria-hidden="true"
        >
          <path
            fillRule="evenodd"
            d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z"
            clipRule="evenodd"
          />
        </svg>

        <div className="flex-1">
          <p className="text-sm font-medium text-red-800">Pago rechazado</p>
          <p className="mt-1 text-sm text-red-700">{message}</p>

          {/* Retry button — hidden for terminal order states (M-04) */}
          {!isTerminalState && (
            <button
              type="button"
              onClick={onRetry}
              className="mt-3 rounded-md bg-red-100 px-3 py-1.5 text-sm font-medium text-red-800 hover:bg-red-200 transition-colors"
            >
              Reintentar pago
            </button>
          )}

          {isTerminalState && (
            <p className="mt-2 text-xs text-red-600">
              Este pedido ya no puede ser pagado.
            </p>
          )}
        </div>
      </div>
    </div>
  )
}
