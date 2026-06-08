/**
 * Checkout page — composes the checkout flow (Change 16 + Change 17 + Change 19).
 *
 * Step 1 (/checkout/review): Pre-checkout validation (Change 16 — advisory)
 * Step 2 (/checkout/confirm): Order confirmation (Change 17 — transactional)
 * Step 3: MercadoPago Checkout Pro redirect (Change 19 — after order creation)
 *
 * Change 19 Checkout Pro migration:
 * - After CheckoutSubmit.onSuccess, calls paymentStore.startCheckout(pedido.id)
 *   to transition to the payment step.
 * - Renders <PayWithMercadoPagoButton> (replaces <CardPaymentWidget>).
 * - On button click: POST /api/v1/pagos → redirect to MP hosted checkout.
 * - User pays on MP page, returns to /checkout/return via back_url.
 * - <PaymentStatusScreen> is NOT shown here (shown on /checkout/return page).
 * - useEffect cleanup calls paymentStore.resetCheckout() on unmount.
 * - <CheckoutSubmit> (Change 17) behavior is UNCHANGED.
 */

import React, { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { CheckoutSubmit } from '@/features/checkout'
import { PayWithMercadoPagoButton } from '@/features/checkout-payment'
import { usePaymentStore } from '@/shared/store/paymentStore'
import type { PedidoRead } from '@/features/checkout'

export default function CheckoutPage() {
  const navigate = useNavigate()
  const checkoutStep = usePaymentStore((state) => state.checkoutStep)
  const startCheckout = usePaymentStore((state) => state.startCheckout)
  const advanceStep = usePaymentStore((state) => state.advanceStep)
  const resetCheckout = usePaymentStore((state) => state.resetCheckout)

  // Track the confirmed pedido for display
  const [pedido, setPedido] = useState<PedidoRead | null>(null)

  // Payment method selection
  const [formaPago, setFormaPago] = useState<'MERCADOPAGO' | 'EFECTIVO'>('MERCADOPAGO')

  // Cleanup paymentStore on unmount
  useEffect(() => {
    return () => {
      resetCheckout()
    }
  }, [resetCheckout])

  // Called in CheckoutSubmit.onSuccess after order creation.
  // Change 20: navigate to /order-confirmation/:id after successful order creation.
  const handleOrderSuccess = (createdPedido: PedidoRead) => {
    setPedido(createdPedido)
    // Navigate to OrderConfirmationPage (Change 20) — shows summary + PayWithMercadoPagoButton.
    // This replaces the startCheckout flow for MP orders and the log for non-MP orders.
    navigate(`/order-confirmation/${createdPedido.id}`)
  }

  return (
    <div className="mx-auto max-w-lg px-4 py-8">
      <h1 className="mb-6 text-2xl font-bold text-gray-900">Confirmar pedido</h1>

      {/*
        CheckoutSubmit (Change 17) behavior is UNCHANGED.
        Shown only before order creation (checkoutStep === "idle").
      */}
      {checkoutStep === 'idle' && (
        <div className="rounded-lg border border-gray-200 bg-white p-6 shadow-sm">
          <div className="mb-4">
            <p className="mb-2 text-sm text-gray-500">Forma de pago</p>
            <div className="flex gap-4">
              <label className="flex cursor-pointer items-center gap-2">
                <input
                  type="radio"
                  name="forma_pago"
                  value="MERCADOPAGO"
                  checked={formaPago === 'MERCADOPAGO'}
                  onChange={() => setFormaPago('MERCADOPAGO')}
                />
                <span className="text-sm font-medium text-gray-900">MercadoPago</span>
              </label>
              <label className="flex cursor-pointer items-center gap-2">
                <input
                  type="radio"
                  name="forma_pago"
                  value="EFECTIVO"
                  checked={formaPago === 'EFECTIVO'}
                  onChange={() => setFormaPago('EFECTIVO')}
                />
                <span className="text-sm font-medium text-gray-900">Efectivo</span>
              </label>
            </div>
          </div>
          <div className="mb-6">
            <p className="text-sm text-gray-500">Entrega</p>
            <p className="font-medium text-gray-900">Retiro en local</p>
          </div>

          <CheckoutSubmit
            formaPagoCodigo={formaPago}
            direccionId={null}
            onSuccess={handleOrderSuccess}
          />
        </div>
      )}

      {/*
        After order creation: show order summary + "Pagar con MercadoPago" button.
        startCheckout() transitions to 'order-summary'. advanceStep('payment') transitions
        to 'payment' where the button is shown.
      */}
      {checkoutStep === 'order-summary' && pedido && (
        <div className="rounded-lg border border-gray-200 bg-white p-6 shadow-sm">
          <h2 className="mb-2 text-lg font-semibold text-gray-900">
            Pedido creado
          </h2>
          <p className="mb-4 text-sm text-gray-500">
            ID: <span className="font-mono">{pedido.id}</span>
          </p>
          <dl className="mb-6 flex flex-col gap-1 text-sm">
            <div className="flex justify-between">
              <dt className="text-gray-500">Subtotal</dt>
              <dd className="font-medium tabular-nums">$ {pedido.subtotal}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-gray-500">Envío</dt>
              <dd className="font-medium tabular-nums">
                $ {pedido.costo_envio}
              </dd>
            </div>
            <div className="mt-1 flex justify-between border-t border-gray-200 pt-1 text-base">
              <dt className="font-semibold">Total</dt>
              <dd className="font-bold tabular-nums">$ {pedido.total}</dd>
            </div>
          </dl>
          <button
            type="button"
            onClick={() => advanceStep('payment')}
            className="w-full rounded-lg bg-orange-500 px-6 py-3 text-sm font-semibold text-white hover:bg-orange-600 active:bg-orange-700"
          >
            Proceder al pago
          </button>
        </div>
      )}

      {/* Step 3: MercadoPago Checkout Pro redirect (Change 19) */}
      {checkoutStep === 'payment' && pedido && (
        <div className="flex flex-col gap-4">
          <div className="rounded-lg border border-gray-200 bg-white p-6 shadow-sm">
            <h2 className="mb-3 text-base font-semibold text-gray-900">
              Pagar con MercadoPago
            </h2>
            <p className="mb-5 text-sm text-gray-500">
              Al hacer clic serás redirigido a la página segura de MercadoPago
              para completar el pago.
            </p>

            {/*
              PayWithMercadoPagoButton:
              - Calls POST /api/v1/pagos → gets init_point / sandbox_init_point
              - Redirects browser to MP hosted checkout
              - User pays there, returns to /checkout/return via back_url
            */}
            <PayWithMercadoPagoButton
              pedidoId={pedido.id}
              className="w-full"
            />
          </div>
        </div>
      )}
    </div>
  )
}
