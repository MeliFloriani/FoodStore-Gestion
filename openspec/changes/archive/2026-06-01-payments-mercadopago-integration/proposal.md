## Why

Food Store has a complete order creation flow (Change 17) and a full manual FSM (Change 18), but no payment integration. Orders are created in `PENDIENTE` state with `forma_pago_codigo = MERCADOPAGO` but there is no mechanism to collect payment, charge the customer, or automatically advance the order to `CONFIRMADO`. Without this change, the purchase funnel is non-functional end-to-end and the primary evaluation criterion CE-09 (end-to-end MP payment) cannot be assessed.

Initial implementation used the embedded `<CardPayment>` widget (`@mercadopago/sdk-react`) with browser tokenization. This was migrated to **MercadoPago Checkout Pro** after sandbox testing blocked card payments with `Unauthorized use of live credentials`. Checkout Pro hosts the payment form on MP's own pages, eliminating browser-side tokenization entirely.

## What Changes

- **NEW** Backend module `pagos/` with Pydantic schemas, repository, service, and router following feature-first architecture.
- **NEW** `POST /api/v1/pagos` — initiates a MercadoPago Checkout Pro flow. Body: `{ pedido_id, idempotency_key }`. Calls `Preference.create`, inserts `Pago` row with `mp_preference_id`, returns `preference_id + init_point + sandbox_init_point`. Auth: CLIENT only.
- **NEW** `POST /api/v1/pagos/webhook` — public IPN endpoint. Verifies `x-signature` HMAC, re-queries `GET /v1/payments/{id}` MP API, obtains `external_reference` (=pedido_id) and `status`. Assigns `mp_payment_id` to the Pago row on first call. When `approved`: triggers automatic FSM transition `PENDIENTE → CONFIRMADO` plus atomic stock decrement inside a single `UnitOfWork`.
- **NEW** `GET /api/v1/pagos/{pedido_id}/latest` — returns latest `Pago` row for a pedido. AUTH: owner CLIENT or ADMIN.
- **MODIFIED** `frontend-checkout` — the last checkout step shows a "Pagar con MercadoPago" button. On click: `POST /api/v1/pagos` → redirect to `sandbox_init_point` (dev) or `init_point` (prod).
- **NEW** Frontend page `/checkout/return` — handles MP back_url redirect. Mounts `<PaymentStatusScreen>` with `usePaymentStatus` polling. User returns here after paying (or failing) on the MP hosted page.
- **NEW** Frontend payment feature: `PayWithMercadoPagoButton` component, `usePaymentStatus` polling hook (TanStack Query, `refetchInterval: 30_000`).
- **REMOVED** `@mercadopago/sdk-react` dependency, `<MercadoPagoProvider>`, `<CardPaymentWidget>` — replaced by Checkout Pro redirect flow.
- **MODIFIED** `backend-order-state-machine` — ADD automatic `PENDIENTE → CONFIRMADO` scenario triggered by the webhook SYSTEM actor (not a manual transition).
- **MODIFIED** `backend-api-v1-router` — register `pagos_router` in `build_v1_router`.
- **MODIFIED** `backend-data-model` — migration 0010: relax `external_reference` UNIQUE for retry support; migration 0011: add `mp_preference_id VARCHAR(100) UNIQUE NULL`.
- **NEW** env vars: `MP_ACCESS_TOKEN`, `MP_WEBHOOK_SECRET`, `MP_NOTIFICATION_URL`, `FRONTEND_BASE_URL` (backend). `VITE_MP_PUBLIC_KEY` not required (Checkout Pro doesn't need it).

## Capabilities

### New Capabilities

- `backend-pagos-management`: Backend pagos module — `POST /api/v1/pagos` start Checkout Pro, `GET /api/v1/pagos/{pedido_id}/latest` query, Pago schemas/repository/service/router.
- `backend-pagos-webhook`: IPN webhook handler — signature verification, idempotency guard, MP API re-query (external_reference lookup), automatic FSM transition + stock decrement.
- `frontend-checkout-payment`: `PayWithMercadoPagoButton` redirect in checkout final step, `usePaymentStatus` polling hook, payment success/error UI.
- `frontend-payment-polling`: `usePaymentStatus` TanStack Query hook polling `GET /api/v1/pagos/{pedido_id}/latest` every 30s while order is `PENDIENTE`.

### Modified Capabilities

- `backend-order-state-machine`: ADD scenario — automatic `PENDIENTE → CONFIRMADO` transition executed by SYSTEM actor via webhook (Change 19). No structural change to the FSM.
- `backend-api-v1-router`: ADD pagos router registration in `build_v1_router` factory.
- `frontend-checkout`: MODIFY — last checkout step shows `PayWithMercadoPagoButton`. On click: POST /api/v1/pagos → redirect to MP hosted checkout. `/checkout/return` page handles return.
- `backend-data-model`: MODIFY — migrations 0010 (external_reference non-unique) and 0011 (add mp_preference_id).

## Impact

- **Backend**: new `backend/app/pagos/` module (model already in `app/models/order.py`), new `backend/app/integrations/mercadopago_client.py`, migrations `0010` and `0011`, environment variables in `backend/.env.example`.
- **Frontend**: removed `@mercadopago/sdk-react`, new `PayWithMercadoPagoButton`, new `/checkout/return` page, updated `CheckoutPage`, updated `App.tsx` (no MercadoPagoProvider).
- **Security boundary**: Checkout Pro — card PAN/CVV never touch Food Store frontend or backend. MercadoPago hosts the payment form. PCI scope is SAQ-A (or better).
- **Dependencies consumed (do NOT redesign)**: Change 03 (`Pago` model, `FormaPago` seed), Change 17 (order creation, PENDIENTE state), Change 18 (`state_transition` service, `uow.historial_pedido`, `SELECT FOR UPDATE`).
- **Unlocks**: Change 20 (order visualization needs payment status), Change 22 (admin access to pagos), Change 25 (test_pagos domain), Change 26 (deploy + public webhook URL).

## User Stories Covered

- **US-045** — Iniciar proceso de pago (CLIENT)
- **US-046** — Procesar webhook IPN (SISTEMA)
- **US-047** — Consultar estado de pago (CLIENT/ADMIN)
- **US-048** — Reintentar pago rechazado (CLIENT)
- **US-039** — Transición automática PENDIENTE → CONFIRMADO (SISTEMA)
- **US-072** — Feedback de estado de pago al volver de MP / polling UI

## Non-Goals

- Embedded card tokenization or `<CardPayment>` widget (removed — Checkout Pro is the flow).
- Cash (EFECTIVO) or TRANSFERENCIA payment flows — only MERCADOPAGO in this change.
- Order creation logic — owned by Change 17 (do NOT redesign).
- Manual FSM transitions — owned by Change 18 (PATCH /estado, DELETE /{id}).
- Order visualization and timeline UI — owned by Change 20.
- Public URL provisioning / deploy — owned by Change 26.
- ADMIN users management — Change 21.
