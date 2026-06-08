# backend-pagos-management Specification

## Purpose
Backend pagos module — `POST /api/v1/pagos` start Checkout Pro, `GET /api/v1/pagos/{pedido_id}/latest` query, Pago schemas/repository/service/router. Introduced in Change 19 (payments-mercadopago-integration).

## ADDED Requirements

### Requirement: Pydantic schemas for Pago (Checkout Pro)
The system SHALL provide Pydantic v2 schemas in `backend/app/pagos/schemas.py` for all payment API operations.

`PagoCreateRequest` SHALL enforce:
- `pedido_id: UUID` — the order to pay for
- `idempotency_key: str (min_length=8)` — client-supplied key to prevent duplicate preferences

Note: No card data fields (`card_token`, `payment_method_id`, `installments`, `issuer_id`). Checkout Pro hosts the payment form — no browser tokenization needed.

`PagoResponse` SHALL include:
- `id: UUID`
- `pedido_id: UUID`
- `mp_payment_id: int | None` — NULL until webhook fires after user pays
- `mp_preference_id: str | None` — Checkout Pro preference ID
- `mp_status: str` — `"pending" | "approved" | "rejected" | "in_process" | "cancelled"`
- `mp_status_detail: str | None`
- `preference_id: str | None` — alias for mp_preference_id (for frontend convenience)
- `init_point: str | None` — live checkout URL
- `sandbox_init_point: str | None` — sandbox checkout URL
- `idempotency_key: str`
- `external_reference: str`
- `monto: str | None` — decimal string, nullable until confirmed
- `created_at: datetime`
- `model_config = ConfigDict(from_attributes=True)`

#### Scenario: PagoCreateRequest validates idempotency_key min_length
- **WHEN** a `PagoCreateRequest` payload has `idempotency_key` shorter than 8 chars
- **THEN** Pydantic raises `ValidationError` with a field error on `idempotency_key`

#### Scenario: PagoResponse serializes monto as string
- **WHEN** a `PagoResponse` instance with `monto = Decimal("150.00")` is serialized to JSON
- **THEN** the JSON value for `monto` is the string `"150.00"` (not a float)

---

### Requirement: PagoRepository with pedido-scoped queries
The system SHALL provide `PagoRepository(BaseRepository[Pago])` at `backend/app/pagos/repository.py` with these methods beyond `BaseRepository`:

- `get_by_mp_payment_id(mp_payment_id: int) -> Pago | None`: Returns `Pago` row matching `mp_payment_id`. Returns `None` if not found.
- `get_by_idempotency_key(idempotency_key: str) -> Pago | None`: Returns `Pago` matching `idempotency_key`.
- `get_latest_by_pedido_id(pedido_id: UUID) -> Pago | None`: Returns the most recently created `Pago` row for a pedido, ordered by `created_at DESC LIMIT 1`.
- `list_by_pedido_id(pedido_id: UUID) -> list[Pago]`: Returns all `Pago` rows for a pedido, ordered `created_at DESC`.

#### Scenario: get_by_mp_payment_id returns None when not found
- **WHEN** `get_by_mp_payment_id(9999999)` is called and no row matches
- **THEN** the method returns `None` without raising an exception

#### Scenario: get_latest_by_pedido_id returns most recent pago
- **GIVEN** two Pago rows for the same pedido_id with different created_at timestamps
- **WHEN** `get_latest_by_pedido_id(pedido_id)` is called
- **THEN** the method returns the row with the later `created_at`

---

### Requirement: UnitOfWork exposes pagos accessor
The system SHALL add `self.pagos: PagoRepository` to `UnitOfWork` in `backend/app/core/uow.py` alongside existing repository accessors.

#### Scenario: UnitOfWork.pagos is accessible from service
- **WHEN** `async with UnitOfWork() as uow:` is entered
- **THEN** `uow.pagos` is an instance of `PagoRepository` initialized with the active session
- **THEN** `uow.pagos.create(...)` inserts a row in the `pago` table

---

### Requirement: PagoService — start_checkout_pro (Checkout Pro)
The system SHALL provide `start_checkout_pro(uow, current_user, data: PagoCreateRequest) -> PagoResponse` in `backend/app/pagos/service.py`. The function SHALL:

1. Load `Pedido` via `uow.pedidos.get(pedido_id)`. Raise `HTTPException(404, "ORDER_NOT_FOUND")` if not found.
2. Verify `pedido.usuario_id == current_user.id`. Raise `HTTPException(403, "ORDER_NOT_OWNED")` if not.
3. Verify `pedido.estado_codigo == "PENDIENTE"`. Raise `HTTPException(409, "ORDER_NOT_PAYABLE")` if not.
4. Verify `pedido.forma_pago_codigo == "MERCADOPAGO"`. Raise `HTTPException(409, "PAYMENT_METHOD_MISMATCH")` if not.
5. Check idempotency: if `uow.pagos.get_by_idempotency_key(data.idempotency_key)` returns a row, return it without calling MP.
6. Build `items` list from pedido (fallback: single item with `pedido.total`).
7. Build `back_urls` using `settings.FRONTEND_BASE_URL` as base (success/pending/failure routes to `/checkout/return`).
8. Call `mp_client.create_preference(items, external_reference=str(pedido.id), notification_url, back_urls, idempotency_key)`.
9. On MP API error: raise `HTTPException(502, "MP_PREFERENCE_ERROR")`.
10. Insert `Pago` row with `mp_preference_id=resp["id"]`, `mp_payment_id=None`, `mp_status="pending"`, `external_reference=str(pedido.id)`, `idempotency_key`.
11. Return `PagoResponse` with `preference_id`, `init_point`, `sandbox_init_point` populated.

The function SHALL NOT call `session.commit()` directly.

#### Scenario: start_checkout_pro returns 404 for unknown pedido
- **WHEN** `POST /api/v1/pagos` is called with a `pedido_id` that does not exist
- **THEN** the service raises `HTTPException(404)` with `code = "ORDER_NOT_FOUND"`

#### Scenario: start_checkout_pro returns preference and redirect URLs
- **GIVEN** a valid PENDIENTE pedido with forma_pago_codigo = "MERCADOPAGO"
- **WHEN** `POST /api/v1/pagos` is called
- **THEN** a `Pago` row is inserted with `mp_preference_id` set and `mp_payment_id = NULL`
- **THEN** the response includes `preference_id`, `init_point`, `sandbox_init_point`

#### Scenario: start_checkout_pro is idempotent
- **GIVEN** an existing Pago row with the same `idempotency_key`
- **WHEN** `POST /api/v1/pagos` is called with the same `idempotency_key`
- **THEN** no new Pago row is created; the existing row is returned

---

### Requirement: PagoRouter — REST endpoints for pagos
The system SHALL provide `pagos_router: APIRouter` in `backend/app/pagos/router.py` with prefix `/pagos` and tag `"pagos"`.

`POST /` (mounted as `POST /api/v1/pagos`):
- Auth: `require_role(["CLIENT"])`
- Body: `PagoCreateRequest` — `{ pedido_id: UUID, idempotency_key: str }`
- Response model: `PagoResponse` HTTP 201
- Returns: `preference_id`, `init_point`, `sandbox_init_point`
- Calls `start_checkout_pro(uow, current_user, data)`

`POST /crear` (mounted as `POST /api/v1/pagos/crear`):
- **Alias** for `POST /api/v1/pagos` — same handler, same auth, same response (D-11)
- Required for Integrador §5.4 rubric compatibility

`GET /{pedido_id}/latest` (mounted as `GET /api/v1/pagos/{pedido_id}/latest`):
- Auth: `require_role(["CLIENT", "PEDIDOS", "ADMIN"])`
- Response model: `PagoResponse` HTTP 200
- Path param: `pedido_id: UUID`
- Raises `404 PAYMENT_NOT_FOUND` if no Pago exists

The router SHALL NOT call `session.commit()` directly.

---

### Requirement: MercadoPago HTTP client wrapper (Checkout Pro)
The system SHALL provide `backend/app/integrations/mercadopago_client.py` encapsulating the `mercadopago` Python SDK (v2.3.0+) with:

- Class `MercadoPagoClient` initialized with `access_token: str` from `settings.MP_ACCESS_TOKEN`.
- `create_preference(items, external_reference, notification_url, back_urls, idempotency_key) -> dict`: Calls `sdk.preference().create(body, request_options)` where `request_options.custom_headers = {"X-Idempotency-Key": idempotency_key}`. Returns `{"id", "init_point", "sandbox_init_point"}`.
- `get_payment(mp_payment_id: int) -> dict`: Calls `sdk.payment().get(mp_payment_id)`. Used by webhook handler.
- Both methods raise `MercadoPagoAPIError` if the SDK response status code >= 400.
- The client MUST be instantiated once at module level (singleton).

#### Scenario: create_preference passes X-Idempotency-Key header
- **WHEN** `create_preference(idempotency_key="abc-uuid", ...)` is called
- **THEN** the SDK request includes `{"X-Idempotency-Key": "abc-uuid"}` in custom headers

#### Scenario: create_preference raises MercadoPagoAPIError on 400 from MP
- **WHEN** the MP API returns status code 400
- **THEN** `MercadoPagoAPIError` is raised with the error detail from MP
- **THEN** the service catches this and raises `HTTPException(502, "MP_PREFERENCE_ERROR")`
