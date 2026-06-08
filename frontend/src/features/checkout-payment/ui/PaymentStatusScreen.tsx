/**
 * PaymentStatusScreen — renders the post-payment state based on paymentStore + polling.
 *
 * Change 19 — payments-mercadopago-integration (task 14.5).
 *
 * States rendered:
 * - "pending": spinner + "Procesando tu pago..." + polling via usePaymentStatus
 * - "approved": success message + order confirmation
 * - "rejected" / "error": PaymentRetryBanner with retry button
 * - "idle": nothing (not yet in checkout flow)
 *
 * Design decisions (task 15.2, 16.5):
 * - When polling returns mp_status="approved", paymentStore.setStatus("approved") is called
 *   by usePaymentStatus, which triggers re-render of this component to the success state.
 * - Terminal states "CANCELADO" / "ENTREGADO" propagate down to PaymentRetryBanner
 *   which hides the retry button (M-04).
 */

import { usePaymentStore } from '@/shared/store/paymentStore'
import { usePaymentStatus } from '../model/usePaymentStatus'
import { PaymentRetryBanner } from './PaymentRetryBanner'

interface PaymentStatusScreenProps {
  /** Called when user wants to retry with a new card */
  onRetry?: () => void
  /** Current pedido estado_codigo — used to gate terminal state retry (M-04) */
  pedidoEstadoCodigo?: string | null
}

/**
 * Displays the current payment status with appropriate UI for each state.
 *
 * Connects usePaymentStatus polling to the paymentStore status transitions.
 */
export function PaymentStatusScreen({ onRetry, pedidoEstadoCodigo }: PaymentStatusScreenProps) {
  const status = usePaymentStore((state) => state.status)
  const pedidoId = usePaymentStore((state) => state.pedidoId)

  // Poll for payment updates while in "pending" state (task 15.1)
  const { data: pagoData } = usePaymentStatus(pedidoId)

  const handleRetry = () => {
    onRetry?.()
  }

  if (status === 'idle') {
    return null
  }

  if (status === 'pending') {
    return (
      <div className="flex flex-col items-center gap-4 py-8" aria-live="polite" aria-busy="true">
        <svg
          className="h-12 w-12 animate-spin text-orange-500"
          xmlns="http://www.w3.org/2000/svg"
          fill="none"
          viewBox="0 0 24 24"
          aria-hidden="true"
        >
          <circle
            className="opacity-25"
            cx="12"
            cy="12"
            r="10"
            stroke="currentColor"
            strokeWidth="4"
          />
          <path
            className="opacity-75"
            fill="currentColor"
            d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
          />
        </svg>
        <div className="text-center">
          <p className="text-base font-semibold text-gray-800">Procesando tu pago...</p>
          <p className="mt-1 text-sm text-gray-500">
            Esto puede tardar unos segundos. No cierres esta pantalla.
          </p>
        </div>
      </div>
    )
  }

  if (status === 'approved') {
    return (
      <div
        role="status"
        className="flex flex-col items-center gap-4 rounded-lg border border-green-200 bg-green-50 px-6 py-8"
      >
        <svg
          className="h-12 w-12 text-green-500"
          xmlns="http://www.w3.org/2000/svg"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          aria-hidden="true"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"
          />
        </svg>
        <div className="text-center">
          <p className="text-lg font-semibold text-green-800">¡Pago aprobado!</p>
          <p className="mt-1 text-sm text-green-700">
            Tu pedido fue confirmado. Te avisaremos cuando esté listo.
          </p>
          {pedidoId && (
            <p className="mt-2 text-xs text-green-600">Pedido: {pedidoId}</p>
          )}
        </div>
      </div>
    )
  }

  if (status === 'rejected' || status === 'error') {
    return (
      <PaymentRetryBanner
        statusDetail={pagoData?.mp_status_detail ?? null}
        onRetry={handleRetry}
        {...(pedidoEstadoCodigo !== undefined && { pedidoEstadoCodigo })}
      />
    )
  }

  return null
}
