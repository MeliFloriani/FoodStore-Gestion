/**
 * CheckoutReturnPage — handles the return from MercadoPago Checkout Pro.
 *
 * Change 19 — payments-mercadopago-integration (task 19.9).
 *
 * Route: /checkout/return
 * Query params (from MP back_url):
 *   - status: 'success' | 'pending' | 'failure'
 *   - pedido_id: UUID of the order (echo of external_reference)
 *   - payment_id: MP payment ID (only present on success/pending)
 *   - external_reference: echo of external_reference
 *   - preference_id / merchant_order_id: ignored (logged only)
 *
 * Design decisions:
 * - Back_url params are used ONLY for initial UI state and reconcile trigger.
 *   The REAL confirmation comes from backend reconcile + polling.
 * - On mount with payment_id present, the page POSTs /api/v1/pagos/reconcile
 *   ONCE so localhost backends (where MP webhooks can't reach) still see
 *   the approved payment. Failures are logged silently — polling will keep
 *   working anyway.
 * - Mounts <PaymentStatusScreen> with polling via usePaymentStatus.
 * - status=failure: shows rejection banner with link back to the order page.
 * - If pedido_id is missing from query params: shows generic error.
 */

import { useEffect, useRef } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { usePaymentStore } from '@/shared/store/paymentStore'
import { PaymentStatusScreen } from '@/features/checkout-payment'
import { reconcilePayment } from '@/entities/pago'

export default function CheckoutReturnPage() {
  const [searchParams] = useSearchParams()
  const status = searchParams.get('status') as 'success' | 'pending' | 'failure' | null
  const pedidoId = searchParams.get('pedido_id')
  const paymentIdParam = searchParams.get('payment_id')
  const externalReference = searchParams.get('external_reference')

  const startCheckout = usePaymentStore((state) => state.startCheckout)
  const setStatus = usePaymentStore((state) => state.setStatus)
  const resetCheckout = usePaymentStore((state) => state.resetCheckout)

  // Guard so reconcile fires at most once per mount (StrictMode double-invoke safe)
  const reconcileFiredRef = useRef(false)

  useEffect(() => {
    if (!pedidoId) return

    // Initialize the payment store with pedido_id so polling can start
    startCheckout(pedidoId)

    // Map back_url status param to paymentStore status
    if (status === 'success' || status === 'pending') {
      // Set to pending so polling activates — webhook/reconcile is the source of truth
      setStatus('pending')
    } else if (status === 'failure') {
      setStatus('rejected')
    }

    // Fire reconcile ONCE if we have a payment_id and status is not failure.
    // This is the fallback that lets localhost dev pick up the approved state
    // when MP webhook servers can't reach the backend.
    const shouldReconcile =
      !reconcileFiredRef.current &&
      status !== 'failure' &&
      paymentIdParam != null &&
      paymentIdParam.length > 0

    if (shouldReconcile) {
      reconcileFiredRef.current = true
      const paymentIdNum = Number(paymentIdParam)
      if (Number.isFinite(paymentIdNum)) {
        const body: Parameters<typeof reconcilePayment>[0] = {
          pedido_id: pedidoId,
          payment_id: paymentIdNum,
        }
        if (externalReference != null) {
          body.external_reference = externalReference
        }
        reconcilePayment(body).catch((err) => {
          // Silent: the existing polling will keep trying. Log for debugging.
          // eslint-disable-next-line no-console
          console.warn('[CheckoutReturnPage] reconcile failed', err)
        })
      }
    }

    return () => {
      // Cleanup on unmount (navigate away)
      resetCheckout()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pedidoId, status, paymentIdParam, externalReference])

  if (!pedidoId) {
    return (
      <div className="mx-auto max-w-lg px-4 py-16 text-center">
        <p className="text-base text-gray-600">
          No se encontró el pedido. Por favor revisá tu historial de pedidos.
        </p>
        <Link
          to="/orders"
          className="mt-4 inline-block rounded-lg bg-orange-500 px-5 py-2.5 text-sm font-semibold text-white hover:bg-orange-600"
        >
          Ver mis pedidos
        </Link>
      </div>
    )
  }

  const handleRetry = () => {
    // Navigate back to checkout to try again
    window.history.back()
  }

  // Status-specific banner messages
  let banner: { tone: 'success' | 'pending' | 'failure'; title: string; body: string } | null = null
  if (status === 'success') {
    banner = {
      tone: 'success',
      title: '¡Pago aprobado!',
      body: 'Confirmando tu pedido…',
    }
  } else if (status === 'pending') {
    banner = {
      tone: 'pending',
      title: 'Estamos confirmando tu pago.',
      body: 'Esto puede demorar unos minutos.',
    }
  } else if (status === 'failure') {
    banner = {
      tone: 'failure',
      title: 'Tu pago fue rechazado.',
      body: 'Podés reintentar desde la página del pedido.',
    }
  }

  const bannerClasses = (() => {
    switch (banner?.tone) {
      case 'success':
        return 'border-green-200 bg-green-50 text-green-900'
      case 'pending':
        return 'border-yellow-200 bg-yellow-50 text-yellow-900'
      case 'failure':
        return 'border-red-200 bg-red-50 text-red-900'
      default:
        return 'border-gray-200 bg-gray-50 text-gray-900'
    }
  })()

  return (
    <div className="mx-auto max-w-lg px-4 py-8">
      <h1 className="mb-6 text-xl font-bold text-gray-900">Estado del pago</h1>

      <p className="mb-4 text-sm text-gray-500">
        Pedido:{' '}
        <span className="font-mono text-xs">{pedidoId}</span>
      </p>

      {banner && (
        <div className={`mb-6 rounded-lg border px-4 py-3 ${bannerClasses}`} role="status">
          <p className="text-sm font-semibold">{banner.title}</p>
          <p className="mt-0.5 text-xs">{banner.body}</p>
          {banner.tone === 'failure' && (
            <Link
              to={`/order-confirmation/${pedidoId}`}
              className="mt-2 inline-block text-xs font-semibold underline"
            >
              Volver al pedido
            </Link>
          )}
        </div>
      )}

      {/*
        PaymentStatusScreen uses paymentStore status + usePaymentStatus polling.
        The store was initialized in the useEffect above.
        When polling detects mp_status=approved → shows success state.
      */}
      <PaymentStatusScreen
        onRetry={handleRetry}
        pedidoEstadoCodigo={null}
      />

      {/* Link to orders list for convenience */}
      <div className="mt-6 text-center">
        <Link
          to="/orders"
          className="text-sm text-orange-500 hover:text-orange-600 underline"
        >
          Ver todos mis pedidos
        </Link>
      </div>
    </div>
  )
}
