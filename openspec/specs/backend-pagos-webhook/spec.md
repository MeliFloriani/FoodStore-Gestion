# backend-pagos-webhook Specification

## Purpose
IPN webhook handler — signature verification, idempotency guard, MP API re-query (external_reference lookup), automatic FSM transition + stock decrement. Introduced in Change 19 (payments-mercadopago-integration).

## ADDED Requirements

### Requirement: Webhook IPN endpoint — POST /api/v1/pagos/webhook
The system SHALL provide `POST /api/v1/pagos/webhook` as a public endpoint (no JWT authentication required) that receives MercadoPago IPN notifications. The endpoint SHALL be registered in `backend/app/pagos/router.py` at path `/webhook` (mounted as `/api/v1/pagos/webhook`).

The endpoint SHALL always return HTTP 200 `{ "status": "ok" }` after verifying the HMAC signature and completing inline processing. Processing (DB writes, FSM transition) happens **synchronously and inline** in the handler before returning 200 — **no `BackgroundTasks`** is used. If signature verification fails (invalid HMAC or stale timestamp), the endpoint returns HTTP 400 with the corresponding error code.

Query parameters sent by MP IPN: `type: str` (e.g. `"payment"`), `data.id: str` (mp_payment_id as string). Additional headers: `x-signature: str` (format: `ts=<timestamp>,v1=<hmac_sha256_hex>`), `x-request-id: str` (UUID).

#### Scenario: Valid webhook with approved payment triggers CONFIRMADO transition
- **GIVEN** a PENDIENTE pedido with a PENDING Pago row
- **WHEN** MP sends `POST /api/v1/pagos/webhook?type=payment&data.id=<mp_payment_id>` with valid x-signature
- **AND** the MP API re-query returns `mp_status = "approved"`
- **THEN** the server returns HTTP 200 `{ "status": "ok" }`
- **THEN** `pago.mp_status` is updated to `"approved"` in the database
- **THEN** `pedido.estado_codigo` is `"CONFIRMADO"` in the database
- **THEN** one new `HistorialEstadoPedido` row exists with `estado_desde = "PENDIENTE"`, `estado_hasta = "CONFIRMADO"` (columna real; alias en docs: `estado_hacia`), `motivo = "Pago aprobado MP"`, `cambiado_por_id = NULL`
- **THEN** stock is decremented for each DetallePedido item

#### Scenario: Valid webhook with rejected payment leaves order PENDIENTE
- **WHEN** MP sends a webhook with valid signature and MP API returns `mp_status = "rejected"`
- **THEN** the server returns HTTP 200
- **THEN** `pago.mp_status` is updated to `"rejected"`
- **THEN** `pedido.estado_codigo` remains `"PENDIENTE"`
- **THEN** no `HistorialEstadoPedido` row is written for this webhook
- **THEN** stock is NOT decremented

#### Scenario: Valid webhook with pending/in_process payment updates pago only
- **WHEN** MP sends a webhook and MP API returns `mp_status = "pending"` or `"in_process"`
- **THEN** the server returns HTTP 200
- **THEN** `pago.mp_status` is updated accordingly
- **THEN** `pedido.estado_codigo` remains `"PENDIENTE"`
- **THEN** no FSM transition is executed

#### Scenario: Invalid HMAC signature returns 400
- **WHEN** `POST /api/v1/pagos/webhook` is received with a tampered or missing `x-signature` header
- **THEN** the server returns HTTP 400 with `{ "detail": "Invalid webhook signature", "code": "INVALID_SIGNATURE" }`
- **THEN** no database operations are performed

#### Scenario: Non-payment webhook type is acknowledged and ignored
- **WHEN** `POST /api/v1/pagos/webhook?type=merchant_order&data.id=...` is received with valid signature
- **THEN** the server returns HTTP 200 `{ "status": "ok" }`
- **THEN** no database operations are performed (only payment type is processed)

---

### Requirement: HMAC signature verification with timestamp freshness
The system SHALL verify the `x-signature` header using `MP_WEBHOOK_SECRET` from settings. The verification algorithm SHALL:

1. Extract `ts` and `v1` from the `x-signature` header (format: `ts=<timestamp>,v1=<sha256_hex>`).
2. **Freshness check**: validate `abs(time.time() - int(ts)) <= 300`. If the timestamp is older than 5 minutes: raise `HTTPException(400, "Webhook timestamp expired", code="WEBHOOK_EXPIRED")`. This step SHALL be executed BEFORE the HMAC computation to reject replayed webhooks early.
3. Extract `data_id` from query param `data.id`.
4. Extract `request_id` from `x-request-id` header.
5. Compose the signed string: `"id:{data_id};request-id:{request_id};ts:{ts}"`.
6. Compute `HMAC-SHA256(key=MP_WEBHOOK_SECRET.encode(), msg=composed_string.encode())`.
7. Compare result (hex digest) with `v1` using `hmac.compare_digest` (constant-time comparison to prevent timing attacks).
8. If comparison fails: raise `HTTPException(400, "Invalid webhook signature", code="INVALID_SIGNATURE")`.

Neither an invalid signature nor an expired timestamp MAY result in HTTP 200. Both conditions SHALL return HTTP 400 with the corresponding error code.

`MP_WEBHOOK_SECRET` SHALL be loaded from `settings.MP_WEBHOOK_SECRET` (added to `backend/app/core/config.py`).

#### Scenario: Correct signature passes verification
- **GIVEN** a known `MP_WEBHOOK_SECRET`, `data_id`, `request_id`, and `ts`
- **WHEN** the HMAC is computed correctly and passed as `v1` in `x-signature`
- **AND** `abs(time.time() - int(ts)) <= 300` (fresh timestamp)
- **THEN** verification passes without raising an exception

#### Scenario: Modified data_id fails verification
- **GIVEN** a valid signature for `data_id = "123"`
- **WHEN** the webhook arrives with `data.id = "456"` (tampered) but the same `v1`
- **THEN** verification fails with `INVALID_SIGNATURE`

#### Scenario: Stale timestamp returns 400 WEBHOOK_EXPIRED
- **WHEN** `POST /api/v1/pagos/webhook` is received with a valid HMAC signature but `ts` older than 5 minutes (`abs(time.time() - int(ts)) > 300`)
- **THEN** the server returns HTTP 400 with `{ "detail": "Webhook timestamp expired", "code": "WEBHOOK_EXPIRED" }`
- **THEN** no database operations are performed
- **NOTE**: This prevents replay attacks where a previously captured valid webhook is re-sent.

#### Scenario: Timing-safe comparison prevents timing attacks
- **WHEN** the verification code is inspected statically
- **THEN** it uses `hmac.compare_digest` (not `==`) for the final comparison

---

### Requirement: Idempotency guard — deduplicate webhook deliveries (Checkout Pro)
The system SHALL guard against duplicate webhook deliveries using the `mp_payment_id` field in the `Pago` table.

**Checkout Pro context**: When Checkout Pro is used, a `Pago` row is created with `mp_payment_id = NULL` (only `mp_preference_id` is set). The webhook fires after the user pays and carries the real `mp_payment_id` in `data.id`. The handler must assign `mp_payment_id` on the first webhook delivery.

Before performing any state transitions, the handler SHALL:
1. Query `uow.pagos.get_by_mp_payment_id(mp_payment_id)`.
2. If a `Pago` row with `mp_payment_id` already exists AND `mp_status == "approved"`: skip all processing and return 200 (the transition was already applied).
3. If the row exists but `mp_status != "approved"`: update `mp_status` only (no FSM transition again).
4. If no row exists matching `mp_payment_id` (Checkout Pro path — Pago was created with NULL mp_payment_id):
   a. Re-query MP API for `GET /v1/payments/{mp_payment_id}` to obtain `external_reference` (pedido_id UUID) and `status`.
   b. Search for the most recent `Pago` row for that `pedido_id` with `mp_payment_id IS NULL` (created by `POST /api/v1/pagos` Checkout Pro preference creation).
   c. If such a row exists: assign `pago.mp_payment_id = mp_payment_id` and proceed with full processing.
   d. If no such row exists: log a structured `ORPHAN_WEBHOOK` entry and respond HTTP 200 with no database side effects.

The `SELECT FOR UPDATE` lock on the `Pedido` row (via `uow.pedidos.get_for_update(pedido_id)`) ensures concurrent webhooks for the same order are serialized.

#### Scenario: Duplicate webhook for already-approved payment is ignored
- **GIVEN** a Pago row with `mp_payment_id = 123` and `mp_status = "approved"`, and a Pedido in `CONFIRMADO` state
- **WHEN** MP re-delivers the same webhook `data.id=123`
- **THEN** the server returns HTTP 200
- **THEN** no duplicate `HistorialEstadoPedido` row is written
- **THEN** `pedido.estado_codigo` remains `"CONFIRMADO"` (no double-transition)
- **THEN** `producto.stock_cantidad` is NOT decremented again

#### Scenario: SELECT FOR UPDATE prevents concurrent double-processing
- **GIVEN** an order in state `PENDIENTE`
- **WHEN** two concurrent webhook deliveries for the same `mp_payment_id` arrive
- **THEN** exactly one UoW acquires the row lock and processes the transition
- **THEN** the second UoW either skips (idempotency check after lock) or receives INVALID_TRANSITION from FSM
- **THEN** the database has exactly one `HistorialEstadoPedido` row for `PENDIENTE → CONFIRMADO`
- **THEN** stock is decremented exactly once per item

---

### Requirement: Atomic UoW — Pago update + FSM transition + stock decrement
When the MP re-query returns `approved`, the handler SHALL execute all mutations inside a single `UnitOfWork`:

1. Lock: `pedido = await uow.pedidos.get_for_update(pedido_id)`
2. Idempotency check: if pago already approved → skip
3. Update: `pago.mp_status = "approved"`, `pago.mp_payment_id = mp_payment_id`
4. FSM: call `state_transition(uow=uow, pedido=pedido, nuevo_estado="CONFIRMADO", actor_user_id=None, motivo="Pago aprobado MP")` (reuse Change 18 service)
5. Stock: for each `DetallePedido` item, call `uow.productos.decrement_stock(producto_id, cantidad)`. If any call returns `None` (insufficient stock): raise an exception to trigger UoW rollback.
6. `UnitOfWork.__aexit__` commits all changes atomically.

If any step fails after step 3, the entire UoW rolls back: Pago row reverts, no FSM history row, no stock change.

#### Scenario: Stock exhaustion causes rollback — order stays PENDIENTE
- **GIVEN** a PENDIENTE order with item: Product A qty=5
- **GIVEN** Product A `stock_cantidad = 2` (insufficient)
- **WHEN** an approved payment webhook arrives
- **THEN** `decrement_stock` returns `None` for Product A
- **THEN** the entire UoW rolls back
- **THEN** `pedido.estado_codigo` remains `"PENDIENTE"`
- **THEN** no `HistorialEstadoPedido` row is written
- **THEN** `pago.mp_status` is NOT updated to `"approved"` in DB
- **THEN** HTTP 200 is still returned (webhook acknowledged)
- **THEN** a structured error log `STOCK_DECREMENT_FAILED_AFTER_PAYMENT_APPROVED` is emitted

#### Scenario: Full approval flow commits atomically
- **GIVEN** a PENDIENTE order with two items, both with sufficient stock
- **WHEN** an approved payment webhook arrives
- **THEN** the UoW commits in one transaction
- **THEN** `pedido.estado_codigo = "CONFIRMADO"` persists
- **THEN** `pago.mp_status = "approved"` persists
- **THEN** stock is decremented for both items in the same transaction
- **THEN** `HistorialEstadoPedido` row persists

---

### Requirement: Settings — MP environment variables
The system SHALL add the following fields to `backend/app/core/config.py` (`Settings` class):

- `MP_ACCESS_TOKEN: str` — MercadoPago access token for server-side API calls.
- `MP_PUBLIC_KEY: str` — MercadoPago public key (also served as info but not used server-side).
- `MP_WEBHOOK_SECRET: str` — Secret used to verify webhook HMAC signatures.
- `MP_NOTIFICATION_URL: str` — Full public URL of the webhook endpoint (passed to MP when creating payments).

All four fields SHALL be required (no defaults) and loaded from the environment via `pydantic-settings`. They SHALL be documented in `backend/.env.example`.

#### Scenario: App fails to start if MP_ACCESS_TOKEN is missing
- **WHEN** `MP_ACCESS_TOKEN` is not set in the environment
- **THEN** `Settings()` raises a `ValidationError` (pydantic-settings)
- **THEN** the application does not start

#### Scenario: .env.example documents all MP variables
- **WHEN** `backend/.env.example` is inspected
- **THEN** the file contains `MP_ACCESS_TOKEN`, `MP_PUBLIC_KEY`, `MP_WEBHOOK_SECRET`, `MP_NOTIFICATION_URL` with placeholder values and comments
