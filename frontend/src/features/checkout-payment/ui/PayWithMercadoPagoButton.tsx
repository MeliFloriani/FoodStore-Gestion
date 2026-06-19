/**
 * PayWithMercadoPagoButton — initiates MercadoPago Checkout Pro flow.
 *
 * Change 19 — payments-mercadopago-integration (task 19.8).
 *
 * Click handler:
 *   1. POST /api/v1/pagos with { pedido_id, idempotency_key: crypto.randomUUID() }
 *   2. On success: redirect to sandbox_init_point (dev) or init_point (prod)
 *   3. MP hosts the checkout page — no card data handled in our frontend.
 *
 * Design decisions:
 * - idempotency_key is generated with crypto.randomUUID() on each click.
 * - Uses import.meta.env.DEV to select sandbox vs prod init_point.
 *   Can be overridden with VITE_MP_USE_SANDBOX=true.
 * - Loading state prevents double-submit.
 * - Error state shows inline message without crashing the page.
 */

import { useState } from 'react'
import { createPayment } from '@/entities/pago'
import { useToast } from '@/shared/ui/toast'

interface PayWithMercadoPagoButtonProps {
  /** UUID of the order to pay */
  pedidoId: string
  /** Optional class names for the button container */
  className?: string
  /** Called after preference is created, before redirect */
  onBeforeRedirect?: () => void
  /** Called if preference creation fails */
  onError?: (errorCode: string) => void
}

/**
 * Button that starts the MercadoPago Checkout Pro redirect flow.
 *
 * After clicking, the user is redirected to the MP hosted checkout page
 * where they enter payment data. No card info is handled in our app.
 */
export function PayWithMercadoPagoButton({
  pedidoId,
  className,
  onBeforeRedirect,
  onError,
}: PayWithMercadoPagoButtonProps) {
  const [isLoading, setIsLoading] = useState(false)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const { toast } = useToast()

  const handleClick = async () => {
    if (isLoading) return
    setIsLoading(true)
    setErrorMessage(null)

    try {
      const idempotencyKey = crypto.randomUUID()

      const pago = await createPayment({
        pedido_id: pedidoId,
        idempotency_key: idempotencyKey,
      })

      // Choose sandbox or prod URL
      const useSandbox =
        import.meta.env.DEV ||
        import.meta.env.VITE_MP_USE_SANDBOX === 'true'

      const redirectUrl = useSandbox
        ? (pago.sandbox_init_point ?? pago.init_point)
        : pago.init_point

      if (!redirectUrl) {
        throw new Error('MP_NO_REDIRECT_URL')
      }

      onBeforeRedirect?.()
      toast({ variant: 'info', title: 'Redirigiendo a MercadoPago...' })
      window.location.href = redirectUrl
    } catch (error) {
      setIsLoading(false)
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const axiosError = error as any
      const code =
        (axiosError?.response?.data?.code as string) ??
        (axiosError?.message as string) ??
        'MP_PREFERENCE_ERROR'
      setErrorMessage('No se pudo iniciar el pago. Por favor intentá de nuevo.')
      toast({ variant: 'error', title: 'No se pudo iniciar el pago', description: 'Intentá de nuevo.' })
      onError?.(code)
    }
  }

  return (
    <div className={className}>
      <button
        type="button"
        onClick={handleClick}
        disabled={isLoading}
        className="flex w-full items-center justify-center gap-2 rounded-lg bg-[#009ee3] px-6 py-3 text-sm font-semibold text-white transition-colors hover:bg-[#007eb5] active:bg-[#006a9b] disabled:cursor-not-allowed disabled:opacity-60"
        aria-busy={isLoading}
        aria-label="Pagar con MercadoPago"
      >
        {isLoading ? (
          <>
            <svg
              className="h-4 w-4 animate-spin"
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
            <span>Redirigiendo...</span>
          </>
        ) : (
          <span>Pagar con MercadoPago</span>
        )}
      </button>

      {errorMessage && (
        <p role="alert" className="mt-2 text-center text-sm text-red-600">
          {errorMessage}
        </p>
      )}
    </div>
  )
}
