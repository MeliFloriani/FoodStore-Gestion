/**
 * Pago entity — public API barrel export.
 *
 * Change 19 — payments-mercadopago-integration.
 *
 * FSD rule: features and pages import from entities/pago via this barrel.
 * Direct imports from internal entity paths are forbidden by eslint-plugin-boundaries.
 */

// Types
export type {
  PagoCreateRequest,
  PagoReconcileRequest,
  PagoReconcileResponse,
  PagoResponse,
} from './model/types'

// API functions
export { createPayment, getLatestPayment, reconcilePayment } from './api/pagosApi'
