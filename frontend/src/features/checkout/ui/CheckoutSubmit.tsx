/**
 * CheckoutSubmit component — confirms order and handles transactional errors.
 *
 * Change 17: order-creation-with-snapshots.
 *
 * Orchestrates the final checkout step:
 * - Shows a "Confirmar pedido" button (disabled + spinner while pending).
 * - On success: cart is cleared (via useCreateOrder onSuccess), shows confirmation.
 * - On error: shows human-readable message mapped from the backend error code.
 *   The cart is NOT cleared on error (the user can adjust and retry).
 *
 * Design decisions:
 * - Does NOT re-validate with Change 16 — backend re-validates transactionally.
 * - Does NOT show raw backend error messages — maps codes to Spanish UX copy.
 * - D-13: clearCart is called inside useCreateOrder.onSuccess — not here.
 * - Navigates to /orders/{id} on success if the route exists (Change 20).
 *   If not, shows inline confirmation message.
 */

import React, { useEffect } from 'react'
import { useCreateOrder } from '../hooks/useCreateOrder'
import { useToast } from '@/shared/ui/toast'
import { SkeletonRect, SkeletonLine } from '@/shared/ui/skeleton'
import type { PedidoRead } from '../model/types'

interface CheckoutSubmitProps {
  formaPagoCodigo: string
  direccionId: string | null
  notas?: string
  onSuccess?: (pedido: PedidoRead) => void
}

/** Map backend error codes to user-friendly Spanish messages. */
function getErrorMessage(error: Error | null): string | null {
  if (!error) return null

  // Try to extract the RFC 7807 code from AxiosError response
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const axiosError = error as any
  const code = axiosError?.response?.data?.code as string | undefined

  switch (code) {
    case 'CART_EMPTY':
      return 'Tu carrito está vacío. Agregá al menos un producto.'
    case 'PRODUCT_NOT_FOUND':
      return 'Uno o más productos de tu carrito ya no están disponibles en el catálogo.'
    case 'PRODUCT_NOT_AVAILABLE':
      return 'Uno o más productos de tu carrito no están disponibles actualmente.'
    case 'INSUFFICIENT_STOCK':
      return 'Uno o más productos no tienen stock suficiente. Por favor revisá tu carrito.'
    case 'INVALID_CUSTOMIZATION':
      return 'Una personalización de tu pedido no es válida. Revisá las exclusiones seleccionadas.'
    case 'PAYMENT_METHOD_INVALID':
      return 'La forma de pago seleccionada no está disponible.'
    case 'ADDRESS_NOT_FOUND':
      return 'La dirección de entrega seleccionada no existe.'
    case 'ADDRESS_NOT_OWNED':
      return 'No tenés permiso para usar esa dirección de entrega.'
    default:
      return 'Ocurrió un error al procesar tu pedido. Por favor intentá de nuevo.'
  }
}

export function CheckoutSubmit({
  formaPagoCodigo,
  direccionId,
  notas,
  onSuccess,
}: CheckoutSubmitProps) {
  const { mutateAsync, isPending, isError, isSuccess, data, error } = useCreateOrder()
  const { toast } = useToast()

  const handleConfirm = async () => {
    try {
      const pedido = await mutateAsync({
        forma_pago_codigo: formaPagoCodigo,
        direccion_id: direccionId,
        notas,
      })
      // Cart is cleared in useCreateOrder.onSuccess
      if (onSuccess) {
        onSuccess(pedido)
      }
    } catch {
      // Error is captured in mutation.error — no additional handling needed here
    }
  }

  const errorMessage = getErrorMessage(error)

  // Toast on error
  useEffect(() => {
    if (isError && error) {
      toast({ variant: 'error', title: getErrorMessage(error) || 'Error al procesar el pedido' })
    }
  }, [isError, error, toast])

  // Skeleton loading overlay
  if (isPending) {
    return (
      <div className="flex flex-col gap-4 rounded-lg bg-card p-6" aria-busy="true">
        <SkeletonLine width="w-1/3" />
        <SkeletonLine width="w-1/2" />
        <SkeletonRect height="h-20" />
        <SkeletonRect height="h-12" />
        <p className="text-center text-sm text-muted-foreground">Procesando pedido...</p>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-4">
      {/* Error message — shows on transactional errors from backend */}
      {isError && errorMessage && (
        <div
          role="alert"
          className="rounded-md bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-800"
        >
          {errorMessage}
        </div>
      )}

      {/* Success message — fallback when /orders/{id} route doesn't exist yet */}
      {isSuccess && data && !onSuccess && (
        <div
          role="status"
          className="rounded-md bg-green-50 border border-green-200 px-4 py-3 text-sm text-green-800"
        >
          ¡Pedido confirmado! #{data.estado_codigo} — ID: {data.id}
        </div>
      )}

      {/* Confirm button */}
      <button
        type="button"
        onClick={handleConfirm}
        disabled={isPending}
        className={[
          'w-full rounded-lg px-6 py-3 text-sm font-semibold text-white transition-colors',
          isPending
            ? 'bg-gray-400 cursor-not-allowed'
            : 'bg-orange-500 hover:bg-orange-600 active:bg-orange-700',
        ].join(' ')}
        aria-busy={isPending}
      >
        Confirmar pedido
      </button>
    </div>
  )
}
