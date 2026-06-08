## ADDED Requirements

### Requirement: Automatic PENDIENTE → CONFIRMADO transition via SYSTEM actor (webhook)
The system SHALL support the automatic `PENDIENTE → CONFIRMADO` transition triggered exclusively by the MercadoPago webhook handler (Change 19). This transition is NOT reachable via `PATCH /api/v1/pedidos/{id}/estado` (it is explicitly excluded from the manual FSM transitions map per the existing `backend-order-state-machine` spec).

The webhook service SHALL reuse the existing `state_transition` function from `backend/app/pedidos/state_transition.py` (Change 18). The call signature is:

```python
await state_transition(
    uow=uow,
    pedido=pedido,              # Pydantic or SQLModel instance, already locked via get_for_update
    nuevo_estado="CONFIRMADO",
    actor_user_id=None,         # SYSTEM — no human actor
    motivo="Pago aprobado MP",
)
```

The `state_transition` function already accepts `actor_user_id: UUID | None` (stored as `cambiado_por_id` which is nullable). The `motivo` field carries the audit evidence of the automated trigger.

This transition creates one `HistorialEstadoPedido` row with:
- `estado_desde = "PENDIENTE"`
- `estado_hacia = "CONFIRMADO"` — **nota terminológica**: `estado_hacia` es el alias semántico utilizado en estos scenarios; la columna real en la base de datos es `HistorialEstadoPedido.estado_hasta` (definida en Change 03 `backend-data-model`). Ambos términos son intercambiables en la documentación; la implementación debe usar `estado_hasta`.
- `motivo = "Pago aprobado MP"`
- `cambiado_por_id = NULL` (SYSTEM actor)

The `state_transition` function SHALL NOT raise `MOTIVO_REQUIRED` for `nuevo_estado = "CONFIRMADO"` (that validation only applies to `CANCELADO`). This is already correct per the existing implementation.

The stock decrement for `PENDIENTE → CONFIRMADO` happens in the SAME `UnitOfWork` as the FSM transition (see `backend-pagos-webhook` spec). Stock is NOT decremented inside `state_transition` itself for this transition — the webhook handler calls `decrement_stock` separately, after `state_transition`, within the same UoW.

#### Scenario: Webhook triggers PENDIENTE → CONFIRMADO with NULL actor_user_id
- **GIVEN** a Pedido in state `PENDIENTE`
- **WHEN** the webhook service calls `state_transition(uow, pedido, nuevo_estado="CONFIRMADO", actor_user_id=None, motivo="Pago aprobado MP")`
- **THEN** `pedido.estado_codigo` becomes `"CONFIRMADO"` in the database
- **THEN** one `HistorialEstadoPedido` row is inserted with `estado_desde="PENDIENTE"`, `estado_hasta="CONFIRMADO"` (columna real; alias en docs: `estado_hacia`), `motivo="Pago aprobado MP"`, `cambiado_por_id=NULL`
- **THEN** the commit is performed by `UnitOfWork.__aexit__` (state_transition does not commit directly)

#### Scenario: PENDIENTE → CONFIRMADO is NOT reachable via PATCH /api/v1/pedidos/{id}/estado
- **WHEN** a staff user sends `PATCH /api/v1/pedidos/{id}/estado` with `nuevo_estado = "CONFIRMADO"`
- **THEN** the server returns HTTP 409 `INVALID_TRANSITION`
- **THEN** this behavior is unchanged from the existing FSM spec
- **NOTE**: The automatic CONFIRMADO transition is exclusively triggered by the webhook, never by a manual PATCH request.

#### Scenario: state_transition rejects CONFIRMADO → CONFIRMADO (idempotency guard above prevents this, but FSM still enforces)
- **GIVEN** a Pedido already in state `CONFIRMADO`
- **WHEN** `state_transition(nuevo_estado="CONFIRMADO")` is called
- **THEN** `state_transition` raises `INVALID_TRANSITION` (FSM does not allow same-state transitions)
- **THEN** the UoW rolls back
- **NOTE**: The idempotency guard in the webhook handler prevents reaching this state by checking mp_status before calling state_transition.

#### Scenario: Existing manual transitions are unaffected
- **WHEN** a PEDIDOS staff user advances `CONFIRMADO → EN_PREP` via `PATCH /api/v1/pedidos/{id}/estado`
- **THEN** the transition succeeds as per the existing FSM spec
- **THEN** no Change 19 code is involved in this flow
