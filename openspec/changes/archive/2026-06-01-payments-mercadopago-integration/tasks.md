## 1. Database Migration

- [x] 1.1 Create Alembic migration `0010_pago_external_reference_non_unique.py` (or next available version): DROP CONSTRAINT `uq_pago_external_reference`; ADD COLUMN `mp_status_detail VARCHAR(100) NULL`; CREATE INDEX `ix_pago_pedido_id_created_at ON pago(pedido_id, created_at DESC)`
- [x] 1.2 Implement `downgrade()` that reverts the migration: before re-adding the constraint, run a pre-check for duplicates:
  ```python
  result = op.get_bind().execute(
      text("SELECT external_reference, count(*) FROM pago GROUP BY external_reference HAVING count(*) > 1")
  )
  if result.fetchall():
      raise Exception("Cannot downgrade: duplicate external_references exist. Manual cleanup required.")
  ```
  Then: DROP INDEX `ix_pago_pedido_id_created_at`; DROP COLUMN `mp_status_detail`; ADD CONSTRAINT `uq_pago_external_reference UNIQUE (external_reference)`
- [x] 1.3 Run `alembic upgrade head` and verify migration applies without errors; confirm `uq_pago_external_reference` is absent from `\d pago` output

## 2. Backend — Settings

- [x] 2.1 Add `MP_ACCESS_TOKEN: str`, `MP_PUBLIC_KEY: str`, `MP_WEBHOOK_SECRET: str`, `MP_NOTIFICATION_URL: str` to `Settings` class in `backend/app/core/config.py` (required, no defaults)
- [x] 2.2 Document all four variables in `backend/.env.example` with placeholder values and inline comments explaining each
- [x] 2.3 (Checkout Pro) Add `FRONTEND_BASE_URL: str = "http://localhost:5173"` to Settings; document in `backend/.env.example`

## 3. Backend — MercadoPago HTTP Client

- [x] 3.1 Install `mercadopago` SDK (pin to v2.3.0+) in `backend/requirements.txt` / `pyproject.toml`
- [x] 3.2 Create `backend/app/integrations/mercadopago_client.py` with class `MercadoPagoClient`
- [x] 3.3 Define `MercadoPagoAPIError(Exception)` raised when MP returns status >= 400
- [x] 3.4 Instantiate `mp_client = MercadoPagoClient(access_token=settings.MP_ACCESS_TOKEN)` at module level (singleton); ensure `X-Idempotency-Key` header is passed
- [x] 3.5 Write unit tests in `backend/tests/test_pagos.py`: mock `MercadoPagoClient.create_preference` and `get_payment`; verify `MercadoPagoAPIError` is raised on 4xx responses

## 4. Backend — Pago Module Scaffolding

- [x] 4.1 Create directory `backend/app/pagos/` with `__init__.py`, `schemas.py`, `repository.py`, `service.py`, `router.py`
- [x] 4.2 Confirm `Pago` SQLModel already exists in `backend/app/models/order.py` (Change 03) — do NOT create a new model file; import from there

## 5. Backend — Pago Schemas

- [x] 5.1 Implement `PagoCreateRequest` in `backend/app/pagos/schemas.py` with Checkout Pro fields: `pedido_id: UUID`, `idempotency_key: str (min_length=8)`
- [x] 5.2 Implement `PagoResponse` in `backend/app/pagos/schemas.py` with all fields including `mp_preference_id`, `preference_id`, `init_point`, `sandbox_init_point`; add `@field_serializer` for `monto`; `model_config = ConfigDict(from_attributes=True)`

## 6. Backend — Pago Repository

- [x] 6.1 Implement `PagoRepository(BaseRepository[Pago])` in `backend/app/pagos/repository.py` with methods: `get_by_mp_payment_id`, `get_by_idempotency_key`, `get_latest_by_pedido_id`, `list_by_pedido_id`
- [x] 6.2 Write unit tests in `backend/tests/test_pagos.py` for repository methods: verify `get_by_mp_payment_id` returns None on miss; verify `get_latest_by_pedido_id` orders by `created_at DESC`

## 7. Backend — UnitOfWork: Add pagos accessor

- [x] 7.1 Add `self.pagos: PagoRepository` to `UnitOfWork.__init__` in `backend/app/core/uow.py`, initialized with the active session alongside existing repository accessors

## 8. Backend — Pago Service (start checkout pro)

- [x] 8.1 Implement `start_checkout_pro(uow, current_user, data: PagoCreateRequest) -> PagoResponse` in `backend/app/pagos/service.py` with all validation steps (ORDER_NOT_FOUND, ORDER_NOT_OWNED, ORDER_NOT_PAYABLE, PAYMENT_METHOD_MISMATCH)
- [x] 8.2 Idempotency check: if `uow.pagos.get_by_idempotency_key(data.idempotency_key)` returns existing Pago, return it without calling MP
- [x] 8.3 Build items from pedido.total (fallback) and back_urls from FRONTEND_BASE_URL setting
- [x] 8.4 Call `mp_client.create_preference(...)`. Catch `MercadoPagoAPIError` → raise `HTTPException(502, code="MP_PREFERENCE_ERROR")`
- [x] 8.5 Insert Pago row with `mp_preference_id=resp["id"]`, `mp_payment_id=None`, `mp_status="pending"`. Return PagoResponse with preference_id + init_point + sandbox_init_point

## 9. Backend — Pago Service (get latest)

- [x] 9.1 Implement `get_latest_payment(uow, current_user, pedido_id: UUID) -> PagoResponse` in `backend/app/pagos/service.py`: verify ownership (CLIENT must own pedido), call `uow.pagos.get_latest_by_pedido_id(pedido_id)`, raise `404 PAYMENT_NOT_FOUND` if None

## 10. Backend — Pago Router

- [x] 10.1 Implement `pagos_router` in `backend/app/pagos/router.py` with `POST /` (201, CLIENT), `POST /webhook` (200, public), `GET /{pedido_id}/latest` (200, CLIENT+PEDIDOS+ADMIN)
- [x] 10.2 Declare `POST /webhook` BEFORE `GET /{pedido_id}/latest` in the router to avoid path matching conflict
- [x] 10.3 Add `pagos_router` to `build_v1_router` in `backend/app/api/v1/router.py` with `prefix="/pagos"`, `tags=["pagos"]`
- [x] 10.4 Register alias route `POST /crear` in `pagos_router` pointing to the same handler as `POST /` (D-11 compatibility)

## 11. Backend — Webhook Handler

- [x] 11.1 Implement `process_webhook(query_params, headers, uow)` in `backend/app/pagos/service.py` (called from router)
- [x] 11.2 Implement HMAC signature verification with freshness check
- [x] 11.3 Implement MP API re-query: call `mp_client.get_payment(data_id)` to get real payment status (never trust webhook payload alone — RN-PA04)
- [x] 11.4 Implement idempotency guard + Checkout Pro first-webhook path: assign `mp_payment_id` when Pago.mp_payment_id is NULL and external_reference matches
- [x] 11.5 Implement atomic UoW block for approved payments
- [x] 11.6 Handle `decrement_stock` returning None: log `STOCK_DECREMENT_FAILED_AFTER_PAYMENT_APPROVED`; return HTTP 200 to MP
- [x] 11.7 Handle `rejected` / `pending` / `in_process` / `cancelled` statuses: update `pago.mp_status` only
- [x] 11.8 Handle non-payment webhook types (`type != "payment"`): return 200 immediately
- [x] 11.9 Write unit tests: signature verification, stale timestamp, idempotency, approved flow, rejected, stock rollback, orphan webhook

## 12. Frontend — Dependencies and Provider

- [x] 12.1 ~~Install `@mercadopago/sdk-react`~~ **REMOVED** — Checkout Pro does not require browser SDK
- [x] 12.2 Update `frontend/.env.example` — `VITE_MP_PUBLIC_KEY` commented out (not required)
- [x] 12.3 ~~Mount `<MercadoPagoProvider>`~~ **REMOVED** — `App.tsx` no longer wraps with MercadoPagoProvider

## 13. Frontend — Pago Entity

- [x] 13.1 Update `src/entities/pago/model/types.ts` with Checkout Pro `PagoCreateRequest` (`pedido_id`, `idempotency_key`) and `PagoResponse` (adds `preference_id`, `init_point`, `sandbox_init_point`)
- [x] 13.2 Update `src/entities/pago/api/pagosApi.ts` — `createPayment(data)` with Checkout Pro request body
- [x] 13.3 `src/entities/pago/index.ts` exports unchanged (types and API functions)

## 14. Frontend — Checkout Payment Feature

- [x] 14.1 Feature directory `src/features/checkout-payment/` exists with FSD structure
- [x] 14.2 Update `useCreatePayment()` in `src/features/checkout-payment/model/useCreatePayment.ts` for Checkout Pro API
- [x] 14.3 ~~`<CardPaymentWidget>`~~ **REMOVED** — replaced by `<PayWithMercadoPagoButton>` (task 19.8)
- [x] 14.4 `<PaymentRetryBanner>` unchanged — generic error/retry banner, not card-specific
- [x] 14.5 `<PaymentStatusScreen>` unchanged — polls and displays status
- [x] 14.6 Update `src/features/checkout-payment/index.ts` — export `PayWithMercadoPagoButton` instead of `CardPaymentWidget`

## 15. Frontend — Payment Polling Feature

- [x] 15.1 `usePaymentStatus` — unchanged (still polls `/pagos/{pedido_id}/latest`)
- [x] 15.2 Connect `usePaymentStatus` in `<PaymentStatusScreen>` — unchanged

## 16. Frontend — Checkout Integration

- [x] 16.1 Update `CheckoutPage` — render `<PayWithMercadoPagoButton pedidoId={pedido.id}>` instead of `<CardPaymentWidget>`
- [x] 16.2 Call `paymentStore.startCheckout(pedido.id)` in order creation success callback — unchanged
- [x] 16.3 `useEffect` cleanup calls `paymentStore.resetCheckout()` on unmount — unchanged
- [x] 16.4 `<CheckoutSubmit>` (Change 17) behavior is UNCHANGED

## 17. Unit Tests — Backend (test_pagos)

- [x] 17.1 `test_start_checkout_pro_creates_preference`: mock MP client, verify Pago row created with mp_preference_id, mp_payment_id=None
- [x] 17.2 ~~`test_create_payment_retry`~~ → `test_start_checkout_pro_idempotent_returns_existing`: same idempotency_key returns existing pago
- [x] 17.3 `test_webhook_signature_valid`: verify HMAC verification passes with correct secret/composed string
- [x] 17.4 `test_webhook_signature_invalid`: verify 400 INVALID_SIGNATURE with tampered data
- [x] 17.5 `test_webhook_approved_triggers_confirmado`: full flow — approved webhook → pedido CONFIRMADO → historial row → stock decremented
- [x] 17.6 `test_webhook_duplicate_idempotency`: send same approved webhook twice → second is skipped
- [x] 17.7 `test_webhook_rejected_stays_pendiente`: rejected webhook → pedido stays PENDIENTE → no historial row → stock unchanged
- [x] 17.8 `test_webhook_insufficient_stock_rollback`: approved webhook with insufficient stock → InsufficientStockError raised
- [x] 17.9 `test_get_latest_payment_returns_newest`: two Pago rows → getLatestPayment returns the one with later created_at
- [x] 17.10 `test_get_latest_payment_404_no_pago`: pedido with no Pago rows → 404 PAYMENT_NOT_FOUND

## 16.5 Frontend — Terminal State Polling Handlers (M-04)

- [x] 16.5 `usePaymentStatus` handles terminal states: CANCELADO → setStatus('failed'); ENTREGADO → setStatus('success'); no retry button for terminal states

## 17.11 Additional Unit Tests

- [x] 17.11 `test_webhook_stale_timestamp`: send webhook with `ts` older than 5 minutes → HTTP 400 WEBHOOK_EXPIRED
- [x] 17.12 `test_webhook_existing_pago_non_approved_becomes_approved`: pago exists with mp_status=pending, re-query returns approved → full processing

## 18. Sandbox Integration Test (opt-in, M-05)

- [x] 18.6 Update `test_mercadopago_sandbox_integration` in `backend/tests/test_pagos_e2e.py` for Checkout Pro: call `mp_client.create_preference(...)`, assert returned preference_id is a non-empty string; smoke test back_urls are reachable

## 18. Verification

- [x] 18.1 Run `openspec status --change "payments-mercadopago-integration" --json` and confirm all artifacts show `isComplete: true`
- [x] 18.2 Run `alembic upgrade head` and `alembic downgrade -1` successfully on a clean DB
- [x] 18.3 Run existing test suite (`pytest backend/tests/test_pagos*.py`) — verify no regressions
- [x] 18.4 Verify TypeScript compiles with `0` errors: `npx tsc --noEmit` in `frontend/`
- [x] 18.5 Smoke test with Checkout Pro + ngrok: create preference, redirect to sandbox, pay, verify webhook delivers, pedido CONFIRMADO

## 19. Checkout Pro Migration

- [x] 19.1 Backend: `MercadoPagoClient.create_preference()` + keep `get_payment()` (webhook requery)
- [x] 19.2 Backend: schemas `PagoCreateRequest` (pedido_id, idempotency_key) + `PagoResponse` (preference_id, init_point, sandbox_init_point)
- [x] 19.3 Backend: `start_checkout_pro()` replaces `create_payment()` in service layer
- [x] 19.4 Backend: webhook lookup by `external_reference` + assign `mp_payment_id` on first webhook
- [x] 19.5 Backend: Alembic migration 0011 add `mp_preference_id VARCHAR(100) UNIQUE NULL` to `pago` table
- [x] 19.6 Backend: tests `test_start_checkout_pro_creates_preference`, `test_start_checkout_pro_idempotent_returns_existing`, `test_webhook_assigns_payment_id_first_time`
- [x] 19.7 Frontend: remove `@mercadopago/sdk-react` from package.json; remove `<MercadoPagoProvider>` from App.tsx; remove `<CardPaymentWidget>` from barrel
- [x] 19.8 Frontend: `PayWithMercadoPagoButton` + click → POST /pagos → `window.location.href = sandbox_init_point` (dev) or `init_point` (prod)
- [x] 19.9 Frontend: page `/checkout/return` (`CheckoutReturnPage`) with `<PaymentStatusScreen>` + polling
- [x] 19.10 Frontend: `FRONTEND_BASE_URL` added to backend settings; `VITE_MP_PUBLIC_KEY` no longer required
- [x] 19.11 Manual smoke 18.5 with Checkout Pro + ngrok (see task 18.5)
