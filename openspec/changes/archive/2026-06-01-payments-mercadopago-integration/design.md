## Context

Changes 17 and 18 established the order lifecycle: orders are created atomically in `PENDIENTE` state (Change 17) and can be advanced/cancelled manually by staff (Change 18). The `Pago` table exists in the schema (Change 03) with fields `mp_payment_id`, `mp_status`, `external_reference`, `idempotency_key` but no application code writes to it. The `FormaPago` seed includes `MERCADOPAGO`. The automatic `PENDIENTE → CONFIRMADO` transition was deliberately reserved for this change (declared as `NOT a valid manual transition` in Change 18 spec).

The integration goal is PCI SAQ-A compliant via MercadoPago Checkout Pro: card data (PAN, CVV, expiry) never pass through Food Store servers. The payment form is hosted entirely on MercadoPago's own pages. The browser is redirected to `init_point` (production) or `sandbox_init_point` (sandbox), the user pays on MP's hosted page, and then MP redirects back to `/checkout/return` via `back_urls`.

---

## Goals / Non-Goals

**Goals:**

- End-to-end payment flow: browser redirect to MP Checkout Pro → backend `Preference.create` → webhook → automatic order confirmation with atomic stock decrement.
- Idempotency: duplicate webhook deliveries, retried API calls, and duplicate frontend submissions are all handled gracefully.
- Payment retry: when a payment is rejected, the client can attempt a new payment for the same order (still in `PENDIENTE`).
- Frontend polling: the client observes the order state change from `PENDIENTE` to `CONFIRMADO` within ~30 seconds after returning to `/checkout/return`.
- Full HMAC webhook signature verification using `MP_WEBHOOK_SECRET`.

**Non-Goals:**

- Embedded card tokenization or `<CardPayment>` widget (removed — Checkout Pro is the flow).
- EFECTIVO or TRANSFERENCIA payment flows (out of scope this change).
- Push notifications or WebSockets (polling is sufficient per spec).
- Order creation logic (Change 17).
- Manual FSM transitions (Change 18).
- Order visualization UI (Change 20).
- Deploy / public URL (Change 26).

---

## Architecture

### End-to-End Sequence

```
Browser (React)                    Backend (FastAPI)              MercadoPago API
─────────────────                  ─────────────────              ──────────────────
1. User clicks "Pagar con
   MercadoPago" button
   (PayWithMercadoPagoButton)

2. POST /api/v1/pagos
   { pedido_id, idempotency_key }   3. Validate CLIENT owns pedido
                                       Assert estado == PENDIENTE
                                       Assert forma_pago_codigo == MERCADOPAGO
                                       Check idempotency_key uniqueness
                                       Call MP Preference.create(...)  →
                                                                        4. Returns preference_id
                                                                           + init_point
                                                                           + sandbox_init_point
                                       INSERT INTO pago(
                                         mp_preference_id=preference_id,
                                         mp_payment_id=NULL,
                                         mp_status='pending',
                                         ...)
                                       ← Return PagoResponse (201)
                                          with init_point, sandbox_init_point

5. window.location.href =
   sandbox_init_point (dev)
   or init_point (prod)

6. User pays on MP hosted page
   (MP's own UI — no card data
    ever reaches Food Store)

7. MP redirects browser to
   /checkout/return?status=approved
   &pedido_id=<uuid>
   (via back_urls)

8. CheckoutReturnPage mounts
   <PaymentStatusScreen> +
   polls GET /api/v1/pedidos/{id}
   every 30s

                                    [Asynchronous — seconds to minutes later]

                                   9. POST /api/v1/pagos/webhook
                                      (from MercadoPago IPN server)

                                      HTTP 200 immediately (RN-PA03)

                                      Inline processing:
                                      a. Verify x-signature HMAC
                                      b. Parse topic + data.id
                                      c. GET /v1/payments/{data.id} from MP API
                                      d. Idempotency: check pago by mp_payment_id
                                         → if already processed: SKIP
                                      e. First-webhook assignment:
                                         if pago.mp_payment_id IS NULL:
                                           lookup by external_reference (pedido_id)
                                           assign mp_payment_id to row
                                      f. UPDATE pago SET mp_status = <real_status>
                                      g. If approved:
                                         SINGLE UoW:
                                           - UPDATE pago mp_status='approved'
                                           - state_transition(pedido_id,
                                               actor_user_id=None,
                                               nuevo_estado='CONFIRMADO',
                                               motivo='Pago aprobado MP',
                                               actor_type='SYSTEM')
                                           - decrement_stock for each DetallePedido item

10. usePaymentStatus polling
    GET /api/v1/pedidos/{id}
    every 30s (TanStack Query)
    → detects estado_codigo = CONFIRMADO
    → show success UI / stop polling
```

---

## Decisions

### D-01: 1:N Pago per Pedido — relax external_reference UNIQUE constraint

**Decision**: Drop the `uq_pago_external_reference` database UNIQUE constraint via Alembic migration. Keep `idempotency_key` UNIQUE. Create a NON-UNIQUE index on `(pedido_id, created_at)` for query performance.

**Why**: The Integrador ERD v5 marks `external_reference` as `UQ, NN`. However, Historias de Usuario RN-PA08 explicitly states "Un pedido puede tener múltiples intentos de pago (relación 1:N Pedido→Pago)" and US-048 requires retrying a rejected payment on the same order. Retrying requires a new `Pago` row with the same `external_reference` (the pedido UUID) but a new `idempotency_key`. The `UQ` on `external_reference` directly prevents this. The functional requirement (retry) takes precedence over the ERD notation.

**Idempotency is preserved via `idempotency_key` UNIQUE**: each payment attempt gets a fresh `uuid4()` (client-supplied via `crypto.randomUUID()`) as `idempotency_key`. MP API calls pass `X-Idempotency-Key: <idempotency_key>` in the header. A duplicate webhook for the same `mp_payment_id` checks for an existing `Pago` row matching that `mp_payment_id`; if found, it is skipped. This is the correct idempotency guard.

**Migration**: Add `0010_pago_external_reference_non_unique.py` (DROP CONSTRAINT `uq_pago_external_reference`; CREATE INDEX `ix_pago_pedido_id_created_at` ON `pago(pedido_id, created_at DESC)`).

**Alternative considered**: Keep the UQ and use a separate `PagoIntento` table for retries. Rejected: over-engineering, the existing `Pago` table is sufficient with the constraint removed.

---

### D-02: Webhook responds HTTP 200 synchronously; verification and processing happen inline (no BackgroundTasks)

**Decision**: The webhook handler verifies the HMAC signature synchronously, then processes the full DB work inline (Pago update + FSM transition + stock decrement) within the same request coroutine, and returns HTTP 200 only after the UoW completes. **`BackgroundTasks` is NOT used in Change 19 and is not a valid alternative for this change.**

**Why**: RN-PA03 requires responding 200 to avoid MP retries. The DB work executes inside a single UoW (< 100ms typical). The `idempotency_key` UNIQUE constraint + `mp_payment_id` UNIQUE constraint + `SELECT FOR UPDATE` on the Pedido row provide full protection if a webhook delivery exceeds ~5s and MP retries: the second delivery will find the row already processed and skip. `BackgroundTasks` would complicate error handling and is explicitly descartado for v1.

**Flow**:
1. Parse `x-signature` header → verify HMAC + freshness (ts check, see D-08) → if invalid or stale: return HTTP 400 immediately.
2. Execute inline processing: parse topic + data.id, re-query MP API, run UoW (idempotency guard → Pago update → FSM transition → stock decrement).
3. Return HTTP 200 `{ "status": "ok" }` after processing completes.

> **BackgroundTasks — DESCARTADO para Change 19**: Using `FastAPI BackgroundTasks` to defer DB work after the 200 response was considered and explicitly rejected. Reasons: (a) errors in the background task cannot be communicated to the caller; (b) the idempotency guard already neutralises MP retries; (c) inline synchronous processing is simpler and sufficient for a university project. Do NOT introduce `BackgroundTasks` in the webhook handler implementation.

---

### D-03: Always re-query MP API — never trust webhook payload alone

**Decision**: Upon receiving a webhook, always call `GET /v1/payments/{data.id}` from the MP API to get the real payment status. Never use the `status` field from the webhook body.

**Why**: RN-PA04 mandates this. Webhook payloads can be spoofed or replayed. The canonical state is always in the MP API. Cost: 1 outbound HTTP call per webhook.

**Alternative considered**: Trust webhook payload for `status`. Rejected: violates RN-PA04 and is a security risk.

---

### D-04: SYSTEM actor for automatic FSM transition

**Decision**: The automatic `PENDIENTE → CONFIRMADO` transition triggered by the webhook uses `actor_user_id = None` (NULL in DB) with `motivo = "Pago aprobado MP"`. The `state_transition` service in Change 18 already accepts `actor_user_id: UUID | None` and stores it as `cambiado_por_id` (nullable FK). A `actor_type: str = "SYSTEM"` field is NOT added to `HistorialEstadoPedido` (no schema change, keeping the migration footprint minimal). The NULL `actor_user_id` combined with `motivo = "Pago aprobado MP"` is sufficient audit evidence.

**Why**: Change 18 already defined `cambiado_por_id` as nullable in `HistorialEstadoPedido` precisely for system-initiated transitions (documented in spec). Adding a separate `actor_type` column would require a new migration for marginal audit value.

**Note**: The `state_transition` service call from the webhook service passes `actor_user_id=None`. The service must not raise `MOTIVO_REQUIRED` for `CONFIRMADO` target (it only requires motivo for `CANCELADO`). This is already correct per Change 18 spec.

---

### D-05: Single UoW for webhook processing (upsert Pago + FSM transition + stock decrement)

**Decision**: The webhook handler uses a single `async with UnitOfWork() as uow:` that:
1. Fetches `Pedido` via `uow.pedidos.get_for_update(pedido_id)` (SELECT FOR UPDATE — pessimistic lock, per Change 18 pattern).
2. Upserts `Pago` row (`mp_status = approved`).
3. Calls `state_transition(uow, pedido_id, actor_user_id=None, nuevo_estado="CONFIRMADO", motivo="Pago aprobado MP")`.
4. Calls `decrement_stock` for each `DetallePedido` item via `uow.productos.decrement_stock(producto_id, delta)`.
5. All changes committed in one transaction by `UnitOfWork.__aexit__`.

If `decrement_stock` returns `None` for any item (insufficient stock), the entire UoW rolls back — the `Pedido` stays `PENDIENTE`, the `Pago` row is not updated, and no history row is written. This is the correct ACID behavior.

---

### D-06: Stock decrement uses atomic SQL — never in-memory read/write cycle

**Decision**: Use `ProductoRepository.decrement_stock()` which already exists from Change 11:

```sql
UPDATE producto
   SET stock_cantidad = stock_cantidad - :delta,
       updated_at = NOW()
 WHERE id = :producto_id
   AND stock_cantidad >= :delta
   AND deleted_at IS NULL
RETURNING *
```

If the UPDATE affects 0 rows (stock < delta or product deleted), it returns `None` and the service raises `HTTPException(507, "INSUFFICIENT_STOCK")`.

---

### D-07: Frontend polls pedido state — no new polling endpoint for state check

**Decision**: The frontend polls `GET /api/v1/pedidos/{id}` (the full pedido detail endpoint owned by Change 17/20) using TanStack Query `refetchInterval: 30_000, enabled: pedidoId !== null && pedidoEstado === "PENDIENTE"`. No new `GET /api/v1/pagos/{pedido_id}/latest` polling endpoint is needed for the polling use case, but `GET /api/v1/pagos/{pedido_id}/latest` IS created for displaying payment details (US-047).

**Why**: The `PedidoRead` response already includes `estado_codigo`. Adding a second polling target creates unnecessary network overhead. The frontend detects `CONFIRMADO` from the existing pedido endpoint. This also avoids Change 20 dependencies.

---

### D-08: HMAC signature verification for webhook

**Decision**: Verify MP's `x-signature` header using `MP_WEBHOOK_SECRET`. The verification algorithm:
1. Compose the signed string: `"id:{data.id};request-id:{x-request-id};ts:{ts}"` where all three values come from query params and headers as documented by MP.
2. Compute `HMAC-SHA256(MP_WEBHOOK_SECRET, composed_string)`.
3. Compare with `v1=<hash>` from `x-signature` header (constant-time comparison via `hmac.compare_digest`).
4. If invalid: return HTTP 400 `INVALID_SIGNATURE`.

`MP_WEBHOOK_SECRET` is configured in backend `.env`. Value in production comes from Change 26 deploy.

---

### D-09: MercadoPago SDK wrapper — Checkout Pro

**Decision**: `backend/app/integrations/mercadopago_client.py` wraps the `mercadopago` Python SDK v2.3.0+ with Checkout Pro methods:
- `create_preference(items, external_reference, notification_url, back_urls, idempotency_key) -> dict`: calls `sdk.preference().create(preference_data, request_options)` with `X-Idempotency-Key` header. Returns `{"id": preference_id, "init_point": ..., "sandbox_init_point": ...}`.
- `get_payment(mp_payment_id: int) -> dict`: calls `sdk.payment().get(mp_payment_id)`. Used by webhook handler.

The SDK is initialized once at module level with `MP_ACCESS_TOKEN` from `settings`. This isolates the MP dependency from the service layer and makes it mockable in tests.

**Previous approach (removed)**: `create_payment()` with `card_token` was used for the embedded CardPayment widget. This caused `Unauthorized use of live credentials` in sandbox. Replaced entirely by `create_preference()`.

---

### D-10: Frontend redirect to Checkout Pro — no browser card tokenization

**Decision**:
- Remove `@mercadopago/sdk-react`, `<MercadoPagoProvider>`, and `<CardPaymentWidget>` entirely.
- Replace last checkout step with `<PayWithMercadoPagoButton>` component.
- On click: `crypto.randomUUID()` → `POST /api/v1/pagos` → `window.location.href = sandbox_init_point` (dev) or `init_point` (prod).
- New route `/checkout/return` renders `<CheckoutReturnPage>` with `<PaymentStatusScreen>` + polling.

**Sandbox detection**: `import.meta.env.DEV || import.meta.env.VITE_MP_USE_SANDBOX === 'true'` determines which URL to redirect to.

**PCI SAQ-A boundary**: Checkout Pro — card PAN/CVV never touch Food Store frontend or backend. MercadoPago hosts the payment form on their own pages. PCI scope is SAQ-A (or better).

---

### D-11: Alias POST /api/v1/pagos/crear for rubric compatibility

**Decision**: Add `POST /api/v1/pagos/crear` as an alias pointing to the same handler as `POST /api/v1/pagos`, preserving compatibility with Integrador §5.4 rubric while keeping the REST idiom. Both endpoints are functional and return identical responses.

---

## Data Model Changes

### Pago table — migrations required

**Migration 0010** (relaxes external_reference constraint):
```sql
-- Drop the unique constraint on external_reference
ALTER TABLE pago DROP CONSTRAINT IF EXISTS uq_pago_external_reference;

-- Add mp_status_detail column
ALTER TABLE pago ADD COLUMN IF NOT EXISTS mp_status_detail VARCHAR(100);

-- Add performance index for per-pedido queries
CREATE INDEX IF NOT EXISTS ix_pago_pedido_id_created_at ON pago(pedido_id, created_at DESC);
```

**Migration 0011** (adds mp_preference_id for Checkout Pro):
```sql
-- Add mp_preference_id column (nullable for backward compat)
ALTER TABLE pago ADD COLUMN mp_preference_id VARCHAR(100);

-- Add unique constraint
ALTER TABLE pago ADD CONSTRAINT uq_pago_mp_preference_id UNIQUE (mp_preference_id);

-- Add index for fast lookups
CREATE INDEX ix_pago_mp_preference_id ON pago(mp_preference_id);
```

### Updated Pago constraint set

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| `mp_payment_id` | BIGINT | nullable, UNIQUE | NULL until webhook fires |
| `mp_preference_id` | VARCHAR(100) | nullable, UNIQUE | NEW — set at Preference.create |
| `mp_status` | VARCHAR(30) | NOT NULL | `pending\|approved\|rejected\|in_process\|cancelled` |
| `mp_status_detail` | VARCHAR(100) | nullable | NEW — MP's status_detail |
| `external_reference` | VARCHAR(100) | NOT NULL, **NOT UNIQUE** | pedido UUID, repeated on retry |
| `idempotency_key` | VARCHAR(100) | NOT NULL, UNIQUE | each attempt gets fresh UUID |
| `monto` | DECIMAL(10,2) | nullable | until confirmed |
| `pedido_id` | UUID FK | NOT NULL, indexed | → pedido.id |

---

## API Contracts

> **Nota de divergencia REST — alias `/pagos/crear`**: El Integrador §5.4 menciona `POST /api/v1/pagos/crear` como ruta de creación de pago. Esta ruta usa un verbo en la URL, lo cual diverge de la convención REST idiomática adoptada en este proyecto (`POST /api/v1/pagos` es el endpoint canónico, siguiendo el estándar de colecciones REST). **Decisión adoptada**: se añade `POST /api/v1/pagos/crear` como alias que apunta al mismo handler que `POST /api/v1/pagos`, preservando compatibilidad con la rúbrica sin abandonar el diseño REST. Ambos endpoints son funcionales y retornan idénticas respuestas. El endpoint canónico para uso interno y tests sigue siendo `POST /api/v1/pagos`.

### POST /api/v1/pagos — Start Checkout Pro

**Auth**: `require_role(["CLIENT"])`

**Request body** (`PagoCreateRequest`):
```json
{
  "pedido_id": "uuid",
  "idempotency_key": "string (min 8 chars, client-generated via crypto.randomUUID())"
}
```

**Success Response** `201 PagoResponse`:
```json
{
  "id": "uuid",
  "pedido_id": "uuid",
  "mp_payment_id": null,
  "mp_preference_id": "mp-preference-id-string",
  "preference_id": "mp-preference-id-string",
  "init_point": "https://www.mercadopago.com.ar/checkout/v1/redirect?...",
  "sandbox_init_point": "https://sandbox.mercadopago.com.ar/checkout/v1/redirect?...",
  "mp_status": "pending",
  "mp_status_detail": null,
  "idempotency_key": "client-uuid-string",
  "external_reference": "pedido-uuid-string",
  "monto": null,
  "created_at": "iso8601"
}
```

**Error responses** (RFC 7807):
- `404 ORDER_NOT_FOUND` — pedido_id does not exist
- `403 ORDER_NOT_OWNED` — pedido belongs to another user
- `409 ORDER_NOT_PAYABLE` — order is not in PENDIENTE state
- `409 PAYMENT_METHOD_MISMATCH` — order forma_pago_codigo != MERCADOPAGO
- `422` — Pydantic validation error
- `502 MP_PREFERENCE_ERROR` — MercadoPago API call failed

---

### POST /api/v1/pagos/webhook — IPN handler

**Auth**: Public (no JWT required). HMAC signature verification via `x-signature` + `MP_WEBHOOK_SECRET`.

**Query params** (sent by MP): `type=payment`, `data.id=<mp_payment_id>`, `id=<notification_id>` 

**Headers** (sent by MP): `x-signature: ts=<ts>,v1=<hmac_hash>`, `x-request-id: <uuid>`

**Success Response**: `200 { "status": "ok" }`

**Error responses**:
- `400 INVALID_SIGNATURE` — HMAC mismatch

---

### GET /api/v1/pagos/{pedido_id}/latest — Latest payment for a pedido

**Auth**: `require_role(["CLIENT", "PEDIDOS", "ADMIN"])` + ownership check for CLIENT

**Path param**: `pedido_id: UUID`

**Success Response** `200 PagoResponse`:
Same schema as POST /api/v1/pagos response. Returns the most recently created `Pago` row for this pedido.

**Error responses**:
- `404 ORDER_NOT_FOUND`
- `403 ORDER_NOT_OWNED`
- `404 PAYMENT_NOT_FOUND` — no Pago exists yet for this pedido

---

## Environment Variables

### Backend (`backend/.env.example`)

```
MP_ACCESS_TOKEN=TEST-xxxx-your-access-token
MP_WEBHOOK_SECRET=your-webhook-secret-from-mp-dashboard
MP_NOTIFICATION_URL=https://your-domain.com/api/v1/pagos/webhook
FRONTEND_BASE_URL=http://localhost:5173
```

`MP_ACCESS_TOKEN` and `MP_WEBHOOK_SECRET` MUST never be sent to the frontend.

`VITE_MP_PUBLIC_KEY` is NOT required for Checkout Pro (the payment form is hosted by MP, no browser SDK initialization needed).

### Frontend (`frontend/.env.example`)

```
# VITE_MP_PUBLIC_KEY not required for Checkout Pro
VITE_MP_USE_SANDBOX=true   # optional — forces sandbox_init_point in non-dev mode
```

---

## Security — PCI SAQ-A Boundary (Checkout Pro)

```
┌─────────────────────────────────────────────────────┐
│                   Browser                            │
│  ┌──────────────────────────────────────────────┐   │
│  │  Food Store React App (our code)             │   │
│  │  [Pagar con MercadoPago] button              │   │
│  │  → POST /api/v1/pagos → gets init_point      │   │
│  │  → window.location.href = init_point         │   │
│  └──────────────────────────────────────────────┘   │
│                        │ browser redirect            │
│                        ▼                             │
│  ┌──────────────────────────────────────────────┐   │
│  │  MercadoPago hosted page (NOT our code)      │   │
│  │  [PAN] [CVV] [Expiry] — MP infrastructure   │   │
│  │  → back_url redirect after payment           │   │
│  └──────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────┘
         │ { pedido_id, idempotency_key } only
         ▼
┌─────────────────────────────────────────────────────┐
│       Food Store Backend (FastAPI)                   │
│       Receives: pedido_id + idempotency_key          │
│       Sends: Preference.create → gets init_point     │
│       Card data: NEVER SEEN                          │
└─────────────────────────────────────────────────────┘
```

Raw card PAN, CVV, and expiry date never exist in:
- React component state
- Network requests to Food Store backend
- Food Store database
- Backend logs

This qualifies as PCI DSS SAQ-A: card data only passes through the MP-hosted page (controlled by MP).

---

## Concurrency Invariants

1. **Double-click / double-submit on "Pay" button**: Frontend disables the submit button on `isPending`. Backend additionally guards via `idempotency_key` UNIQUE: two concurrent POST /api/v1/pagos for the same pedido_id in race with the same idempotency_key would result in one succeeding and one finding the existing row (returned as idempotent result).

2. **Concurrent webhook deliveries**: `SELECT FOR UPDATE` on `Pedido` row (inherited from Change 18 `get_for_update`) serializes concurrent webhook handlers for the same order. The idempotency check (`SELECT FROM pago WHERE mp_payment_id = :mp_payment_id`) runs inside the lock.

3. **Stock race condition on confirmation**: `decrement_stock` uses atomic `UPDATE ... WHERE stock_cantidad >= :delta`. If two orders are confirmed simultaneously for the same product, one will receive `None` (stock exhausted) and roll back. No double-decrement is possible.

4. **Retry after rollback**: If the webhook UoW rolls back (e.g., insufficient stock), the MP payment is already charged. This is an acceptable edge case for v1 — the pedido remains PENDIENTE with a `Pago` row in `approved` status but the state was not advanced. The business logic to handle this (refund, manual resolution) is out of scope for this change.

5. **mp_payment_id NULL on first webhook**: Checkout Pro creates `Pago` with `mp_payment_id=NULL`. Webhook handler detects `mp_payment_id IS NULL` and performs lookup by `external_reference` (pedido_id) via `get_latest_by_pedido_id()`, then assigns `mp_payment_id` to the row. Subsequent webhooks for the same payment find the row by `mp_payment_id` and skip (idempotency guard).

---

## Frontend Architecture

### Feature modules (FSD)

```
src/
  app/
    App.tsx                       ← REMOVED: <MercadoPagoProvider> (not needed)
    router/routes.tsx             ← ADD: /checkout/return route (lazy)
  features/
    checkout-payment/             ← MODIFIED feature
      ui/
        PayWithMercadoPagoButton.tsx  ← NEW: replaces CardPaymentWidget
      model/
        useCreatePayment.ts       ← MODIFIED: no card fields, idempotency_key only
        usePaymentStatus.ts       ← unchanged (polling hook)
      index.ts                    ← MODIFIED: exports PayWithMercadoPagoButton
  pages/
    checkout/
      ui/
        CheckoutPage.tsx          ← MODIFIED: uses PayWithMercadoPagoButton
        CheckoutReturnPage.tsx    ← NEW: handles MP back_url return
  entities/
    pago/
      model/
        types.ts                  ← MODIFIED: PagoCreateRequest no card fields,
                                     PagoResponse + mp_preference_id/init_point
      api/
        pagosApi.ts               ← unchanged (JSDoc updated)
```

### paymentStore integration

The existing `paymentStore` (Change 05) already has `status`, `pedidoId`, `setStatus()`, `reset()`. This change uses those existing actions:
- After order creation (Change 17), call `paymentStore.startCheckout(pedidoId)`.
- When `POST /api/v1/pagos` succeeds: redirect immediately (`window.location.href`), no status update needed before redirect.
- On `/checkout/return`: read `?status=` param from MP's back_url, map to `paymentStore.setStatus()`.
- When polling detects `CONFIRMADO`: call `paymentStore.setStatus('success')`.
- When payment is rejected: call `paymentStore.setStatus('failed')`.

No new `paymentStore` actions are required. No persistence is added (store is already ephemeral per Change 05 spec).

---

## Risks / Trade-offs

| Risk | Mitigation |
|------|-----------|
| Webhook not reachable in localhost dev | Use ngrok or similar tunnel; document in README. MP_NOTIFICATION_URL must be public. Change 26 provides production URL. |
| `external_reference` UQ drop breaks existing data | Only Change 03 seed and Change 17 integration tests create Pago rows. Migration is safe. Verify with `SELECT count(*) FROM pago GROUP BY external_reference HAVING count(*) > 1` before applying. |
| Stock rollback after approved payment leaves order stuck in PENDIENTE | v1 accepted risk. Mitigation: alert via structured log `logger.error("STOCK_DECREMENT_FAILED_AFTER_PAYMENT_APPROVED")`. Manual resolution out of scope. |
| MP API call from webhook creates latency spike | Acceptable for university project. In production: use async background worker. The `idempotency_key` guard prevents issues from MP's retry if the webhook handler exceeds the 5s response window. |
| Concurrent webhook for same pedido_id | Mitigated by `SELECT FOR UPDATE` lock on `Pedido` row (Change 18 pattern) + `mp_payment_id` UNIQUE guard. |
| back_url status param not trusted | `/checkout/return` uses the `?status=` param only for UX (showing pending/approved/failure screen). The webhook is the sole source of truth for order state changes. |
| sandbox_init_point selection | `import.meta.env.DEV || import.meta.env.VITE_MP_USE_SANDBOX === 'true'` — ensures sandbox in development without requiring env var change each time. |

---

## Migration Plan

1. Apply Alembic migration 0010: drop `uq_pago_external_reference`, add `mp_status_detail`, add `ix_pago_pedido_id_created_at`.
2. Apply Alembic migration 0011: add `mp_preference_id VARCHAR(100) UNIQUE NULL`, add index.
3. Deploy backend with new pagos module, `FRONTEND_BASE_URL`, and env vars.
4. Deploy frontend without `@mercadopago/sdk-react`, with `PayWithMercadoPagoButton` and `/checkout/return` route.
5. Register webhook URL in MP dashboard (requires Change 26 public URL).
6. Test with MP sandbox using Checkout Pro sandbox flow.

**Rollback**: Both migrations are reversible via `alembic downgrade`. Migration 0010 downgrade includes mandatory duplicate check before re-adding `uq_pago_external_reference` — aborts if duplicates exist.

---

## Scenarios adicionales

### Scenario: Checkout Pro redirect and return

- **GIVEN** a valid PENDIENTE pedido with forma_pago_codigo = "MERCADOPAGO"
- **WHEN** user clicks "Pagar con MercadoPago"
- **THEN** frontend POSTs to `/api/v1/pagos` and receives `sandbox_init_point` (dev)
- **THEN** browser is redirected to MP's hosted checkout page
- **THEN** user completes payment on MP's page
- **THEN** MP redirects to `/checkout/return?status=approved&pedido_id=<uuid>`
- **THEN** `CheckoutReturnPage` shows polling UI while waiting for CONFIRMADO

### Scenario: Webhook assigns mp_payment_id on first call

- **GIVEN** a `Pago` row with `mp_payment_id=NULL` and `mp_preference_id` set
- **WHEN** webhook fires with `data.id=<mp_payment_id>` for that payment
- **THEN** handler finds Pago by `external_reference` (pedido_id)
- **THEN** assigns `mp_payment_id` to the row
- **THEN** if status=approved, transitions order to CONFIRMADO

---

## Open Questions — Resolved

- Q1: Should `GET /api/v1/pedidos/{id}` include the latest `Pago` in the response (`PedidoRead`) so the frontend can use one endpoint for polling? **Resolution for this change**: `PedidoRead` does NOT include Pago (Change 20 is responsible for the full detail view). The polling hook polls `GET /api/v1/pedidos/{id}` only for `estado_codigo`. Payment detail is fetched separately via `GET /api/v1/pagos/{pedido_id}/latest`.
- Q2: Should `mp_status_detail` be stored in the `Pago` table? **Resolution**: Add `mp_status_detail VARCHAR(100) NULL` as an in-migration column to `Pago` (necessary for frontend error messages on rejection). This is additive and non-breaking.
- Q3: CardPayment vs Checkout Pro? **Resolution**: Checkout Pro. CardPayment caused `Unauthorized use of live credentials` in sandbox. Checkout Pro hosts the payment form on MP's pages — no browser tokenization needed.

---

## Decision Log Summary

| ID | Decision | Alternative Rejected | Reason |
|----|----------|---------------------|--------|
| D-01 | 1:N Pago/Pedido via dropping external_reference UQ | Separate PagoIntento table | Simpler, same idempotency guarantee via idempotency_key |
| D-02 | Inline processing in webhook handler | Background task queue (Celery/ARQ) | Out of scope for university project |
| D-03 | Always re-query MP API | Trust webhook payload | RN-PA04 + security |
| D-04 | NULL actor_user_id for SYSTEM transitions | New actor_type column | No schema change needed, nullable already exists |
| D-05 | Single UoW for Pago + FSM + stock | Separate UoWs | ACID atomicity requirement |
| D-06 | Atomic SQL for stock decrement | In-memory read-modify-write | Race condition prevention |
| D-07 | Poll pedido endpoint (not new endpoint) | New /pagos/status endpoint | Fewer endpoints, less work, same information |
| D-08 | HMAC-SHA256 with MP_WEBHOOK_SECRET | Skip signature verification | Security requirement |
| D-09 | SDK wrapper — create_preference() for Checkout Pro | create_payment() with card_token | CardPayment caused sandbox auth error |
| D-10 | PayWithMercadoPagoButton + browser redirect | MercadoPagoProvider + CardPayment iframe | Checkout Pro eliminates browser tokenization |
| D-11 | Add alias POST /api/v1/pagos/crear pointing to same handler as POST /api/v1/pagos | Drop alias entirely | Compatibility with Integrador §5.4 rubric while keeping REST idiom |
