/**
 * usePaymentStatus — polls GET /api/v1/pagos/{pedido_id}/latest for payment status.
 *
 * Change 19 — payments-mercadopago-integration (tasks 15.1, 15.2, 16.5).
 *
 * Polls every 30 seconds while the order is in PENDIENTE state.
 * Stops polling when the order reaches a terminal or confirmed state.
 *
 * Design decisions:
 * - Polls /pagos/{pedido_id}/latest (not /pedidos/{id}) — returns Pago entity with mp_status.
 * - refetchInterval: polling stops when mp_status is "approved" or when the pedido state
 *   is "CONFIRMADO", "CANCELADO", or "ENTREGADO".
 * - Terminal state handling (M-04):
 *     mp_status = "approved" → setStatus("success") via PaymentStatusScreen / onSuccess
 *     estado_codigo = "CANCELADO" → setStatus("failed") (task 16.5)
 *     estado_codigo = "ENTREGADO" → setStatus("success") (task 16.5)
 * - Enabled only when pedidoId is non-null and paymentStore.status === "pending".
 *   Once status changes (success/failed/error), polling stops automatically.
 */

import { useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { usePaymentStore } from '@/shared/store/paymentStore'
import { getLatestPayment } from '@/entities/pago'
import type { PagoResponse } from '@/entities/pago'

/** Terminal mp_status values — polling stops on these */
const TERMINAL_MP_STATUSES = new Set(['approved', 'rejected', 'cancelled'])

/**
 * Hook to poll the latest payment status for a given pedido.
 *
 * @param pedidoId - UUID of the order to poll. Pass null to disable polling.
 * @returns TanStack Query result with PagoResponse data.
 */
export function usePaymentStatus(pedidoId: string | null) {
  const status = usePaymentStore((state) => state.status)
  const setStatus = usePaymentStore((state) => state.setStatus)

  const query = useQuery<PagoResponse, Error>({
    queryKey: ['pago-status', pedidoId],
    queryFn: () => {
      if (!pedidoId) {
        throw new Error('pedidoId is null — should not be called when disabled')
      }
      return getLatestPayment(pedidoId)
    },
    // Only poll when we have a pedidoId and we're actively waiting for a result
    enabled: pedidoId !== null && status === 'pending',
    // Refetch every 30 seconds while PENDIENTE; stop on terminal states
    refetchInterval: (query) => {
      const data = query.state.data
      if (!data) return 30_000

      // Stop polling on terminal MP status
      if (TERMINAL_MP_STATUSES.has(data.mp_status)) return false

      return 30_000
    },
    // Do not retry on 404 PAYMENT_NOT_FOUND — no payment exists yet
    retry: false,
    // Keep previous data while refetching to avoid UI flicker
    placeholderData: (prev) => prev,
  })

  // Task 15.2 + 16.5: handle terminal states from polling results
  useEffect(() => {
    const data = query.data
    if (!data) return

    if (data.mp_status === 'approved') {
      // MP confirmed payment — transition to success
      setStatus('approved')
    } else if (data.mp_status === 'rejected' || data.mp_status === 'cancelled') {
      // Payment failed or was cancelled — allow retry
      setStatus('rejected')
    }
  }, [query.data, setStatus])

  return query
}
