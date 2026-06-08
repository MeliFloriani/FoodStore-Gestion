/**
 * TypeScript types for the Pago (payment) entity.
 *
 * Change 19 — payments-mercadopago-integration (Checkout Pro migration).
 *
 * These types mirror the backend Pydantic schemas in app/pagos/schemas.py.
 * monto is a decimal string (serialized from Python Decimal) or null.
 *
 * Checkout Pro flow:
 *   - PagoCreateRequest: only pedido_id + idempotency_key (no card data).
 *   - PagoResponse: includes preference_id, init_point, sandbox_init_point.
 *   - Frontend redirects user to sandbox_init_point (dev) or init_point (prod).
 *   - mp_payment_id stays null until webhook fires after user pays.
 */

/**
 * Request body for POST /api/v1/pagos and POST /api/v1/pagos/crear.
 *
 * Corresponds to backend PagoCreateRequest schema.
 * Checkout Pro: no card data needed — tokenization handled by MP hosted page.
 */
export interface PagoCreateRequest {
  /** UUID of the order to pay */
  pedido_id: string
  /** Client-supplied idempotency key (min 8 chars) — prevents duplicate preferences */
  idempotency_key: string
}

/**
 * Response from POST /api/v1/pagos and GET /api/v1/pagos/{pedido_id}/latest.
 *
 * Corresponds to backend PagoResponse schema.
 */
export interface PagoResponse {
  /** UUID of this payment record */
  id: string
  /** UUID of the associated order */
  pedido_id: string
  /** MercadoPago payment ID — null until webhook fires after user pays */
  mp_payment_id: number | null
  /** MercadoPago preference ID — set when preference is created */
  mp_preference_id: string | null
  /** MP payment status: "pending" | "approved" | "rejected" | "cancelled" | "in_process" */
  mp_status: string
  /** Detailed MP status reason — e.g. "cc_rejected_bad_filled_cvv" | "accredited" */
  mp_status_detail: string | null
  /** MercadoPago Checkout Pro preference ID (same as mp_preference_id) */
  preference_id: string | null
  /** Live checkout URL — redirect for production */
  init_point: string | null
  /** Sandbox checkout URL — redirect for development/testing */
  sandbox_init_point: string | null
  /** Client-supplied idempotency key */
  idempotency_key: string
  /** Equals pedido_id (used as external_reference in MP) */
  external_reference: string
  /** Payment amount as decimal string — e.g. "150.00" | null */
  monto: string | null
  /** ISO 8601 timestamp of payment creation */
  created_at: string
}

/**
 * Request body for POST /api/v1/pagos/reconcile.
 *
 * Frontend-driven fallback when the MP webhook can't reach the backend
 * (typical in local development). CheckoutReturnPage uses the query params
 * MP appended to the back_url to ask the backend to re-query MP.
 */
export interface PagoReconcileRequest {
  /** UUID of the order whose payment must be reconciled */
  pedido_id: string
  /** MercadoPago payment ID from the back_url query param */
  payment_id?: number | null
  /** Echo of external_reference from MP back_url (optional) */
  external_reference?: string | null
}

/**
 * Response for POST /api/v1/pagos/reconcile.
 *
 * Reports post-reconcile state so the frontend can decide whether to stop
 * polling (approved/rejected) or keep showing the spinner (pending).
 */
export interface PagoReconcileResponse {
  /** Always "ok" when the call succeeds */
  status: string
  /** Updated MP payment status: "pending" | "approved" | "rejected" | ... */
  mp_status: string
  /** Pedido FSM state code after reconcile (e.g. "PENDIENTE" | "CONFIRMADO") */
  pedido_estado: string
  /** True when the Pago was already approved and no work was done */
  already_processed: boolean
}
