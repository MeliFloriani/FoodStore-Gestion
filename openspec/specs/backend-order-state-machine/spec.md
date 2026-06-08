# backend-order-state-machine Specification

## Purpose
FSM-based order state transition service introduced in Change 18 (`order-state-machine-transitions`). Provides `PATCH /api/v1/pedidos/{id}/estado` for manual advance and staff cancellation, and `DELETE /api/v1/pedidos/{id}` for CLIENT self-cancellation of PENDIENTE orders. All mutations run inside a single `UnitOfWork`, write one `HistorialEstadoPedido` row, and — for cancellation of CONFIRMADO or EN_PREP orders — atomically restore stock. Complements Change 17 (order creation, PENDIENTE state) and Change 19 (automatic PENDIENTE→CONFIRMADO via webhook).

## ADDED Requirements

---

### Requirement: PATCH /api/v1/pedidos/{id}/estado — manual state advance

The system SHALL provide `PATCH /api/v1/pedidos/{id}/estado` for staff (ADMIN or PEDIDOS) to advance or cancel orders. The request body SHALL be:

```
PedidoEstadoUpdate {
  nuevo_estado: str      -- target state code
  motivo: str | None     -- required when nuevo_estado == "CANCELADO" (RN-05)
}
```

The endpoint SHALL return `200 PedidoRead` on success.

#### Scenario: PEDIDOS advances CONFIRMADO → EN_PREP successfully
- **WHEN** a bearer token with role `PEDIDOS` sends `PATCH /api/v1/pedidos/{id}/estado` with `nuevo_estado = "EN_PREP"` and the order is in state `CONFIRMADO`
- **THEN** the server returns HTTP 200
- **THEN** `pedido.estado_codigo = "EN_PREP"` in the database
- **THEN** one new `HistorialEstadoPedido` row exists with `estado_desde = "CONFIRMADO"`, `estado_hacia = "EN_PREP"`, and `actor_user_id` equal to the requester's user id

#### Scenario: ADMIN advances EN_PREP → EN_CAMINO successfully
- **WHEN** a bearer token with role `ADMIN` sends the request with `nuevo_estado = "EN_CAMINO"` and the order is in state `EN_PREP`
- **THEN** the server returns HTTP 200
- **THEN** `pedido.estado_codigo = "EN_CAMINO"` in the database

#### Scenario: PEDIDOS advances EN_CAMINO → ENTREGADO successfully
- **WHEN** a bearer token with role `PEDIDOS` sends the request with `nuevo_estado = "ENTREGADO"` and the order is in state `EN_CAMINO`
- **THEN** the server returns HTTP 200
- **THEN** `pedido.estado_codigo = "ENTREGADO"` in the database

#### Scenario: CLIENT token rejected with 403
- **WHEN** a bearer token with role `CLIENT` sends `PATCH /api/v1/pedidos/{id}/estado`
- **THEN** the server returns HTTP 403
- **THEN** the order state is not modified

#### Scenario: STOCK token rejected with 403
- **WHEN** a bearer token with role `STOCK` sends `PATCH /api/v1/pedidos/{id}/estado`
- **THEN** the server returns HTTP 403

#### Scenario: Unauthenticated request rejected with 401
- **WHEN** no `Authorization` header is present
- **THEN** the server returns HTTP 401

#### Scenario: Non-existent pedido_id returns 404
- **WHEN** `{id}` does not match any row in the `pedido` table
- **THEN** the server returns HTTP 404
- **THEN** the body contains `{ "detail": "El pedido no fue encontrado.", "code": "ORDER_NOT_FOUND" }`

---

### Requirement: FSM validator — allowed transitions and terminal state rejection

The service SHALL enforce the FSM map before any mutation. All validation occurs after acquiring a `SELECT FOR UPDATE` lock on the `Pedido` row.

> **Fuente autoritativa**: Integrador §3.4 + RN-FS08 (ADMIN puede cancelar desde EN_PREP). Esta implementación sigue la especificación técnica oficial, que tiene precedencia sobre cualquier ambigüedad en las historias de usuario (US-043).

Valid manual transitions via `PATCH /estado` (ALLOWED_TRANSITIONS map — roles are for PATCH only):
- `PENDIENTE → CANCELADO` (PEDIDOS or ADMIN via PATCH only; CLIENT uses DELETE endpoint — see `cancel_own_client`)
- `CONFIRMADO → EN_PREP` (PEDIDOS, ADMIN)
- `CONFIRMADO → CANCELADO` (PEDIDOS, ADMIN)
- `EN_PREP → EN_CAMINO` (PEDIDOS, ADMIN)
- `EN_PREP → CANCELADO` (ADMIN only — RN-RB08)
- `EN_CAMINO → ENTREGADO` (PEDIDOS, ADMIN)

Note: `ALLOWED_TRANSITIONS["PENDIENTE"]["CANCELADO"] = {"PEDIDOS", "ADMIN"}`. CLIENT is NOT in this set because CLIENT cancellation is routed exclusively through `cancel_own_client()` via DELETE, never through `transition_state()` via PATCH.

`PENDIENTE → CONFIRMADO` is NOT a valid manual transition (reserved for Change 19 automatic webhook — RN-FS02). Any attempt to set `nuevo_estado = "CONFIRMADO"` via PATCH SHALL return `INVALID_TRANSITION`.

#### Scenario: INVALID_TRANSITION for skipped state
- **WHEN** the order is in state `CONFIRMADO` and `nuevo_estado = "EN_CAMINO"` (skipping EN_PREP)
- **THEN** the server returns HTTP 409
- **THEN** the body contains `{ "detail": "La transición solicitada no es válida desde el estado actual.", "code": "INVALID_TRANSITION" }`
- **THEN** no database mutation occurs

#### Scenario: INVALID_TRANSITION for manual PENDIENTE → CONFIRMADO attempt
- **WHEN** a staff user sends `nuevo_estado = "CONFIRMADO"`
- **THEN** the server returns HTTP 409
- **THEN** the body contains `{ "detail": "La transición solicitada no es válida desde el estado actual.", "code": "INVALID_TRANSITION" }`

#### Scenario: TERMINAL_STATE when order is ENTREGADO
- **WHEN** the order is in state `ENTREGADO` and any `nuevo_estado` is sent
- **THEN** the server returns HTTP 409
- **THEN** the body contains `{ "detail": "El pedido está en un estado terminal y no admite más transiciones.", "code": "TERMINAL_STATE" }` (RN-FS06 / RN-01)

#### Scenario: TERMINAL_STATE when order is already CANCELADO
- **WHEN** the order is in state `CANCELADO` and any `nuevo_estado` is sent
- **THEN** the server returns HTTP 409
- **THEN** the body contains `{ "detail": "El pedido está en un estado terminal y no admite más transiciones.", "code": "TERMINAL_STATE" }`
- **THEN** no database mutation occurs

---

### Requirement: motivo mandatory for cancellation (RN-05)

When `nuevo_estado = "CANCELADO"`, the `motivo` field SHALL be non-null and non-empty. This applies to both the PATCH endpoint (staff) and the DELETE endpoint (CLIENT).

#### Scenario: MOTIVO_REQUIRED when cancelling without motivo via PATCH
- **WHEN** staff sends `{ nuevo_estado: "CANCELADO", motivo: null }` or `motivo` is absent
- **THEN** the server returns HTTP 422
- **THEN** the body contains `{ "detail": "motivo es obligatorio al cancelar", "code": "MOTIVO_REQUIRED" }`
- **THEN** no transition is executed
- **NOTE**: This validation occurs in the **service** (`transition_state` function in `state_transition.py`), NOT in the Pydantic schema. The schema defines `motivo: str | None` without contextual validation. The service raises `HTTPException(status_code=422, detail="motivo es obligatorio al cancelar", code="MOTIVO_REQUIRED")` when `nuevo_estado == "CANCELADO"` and `motivo` is falsy.

#### Scenario: Empty-string motivo also rejected
- **WHEN** staff sends `{ nuevo_estado: "CANCELADO", motivo: "" }`
- **THEN** the server returns HTTP 422
- **THEN** the body contains `{ "detail": "motivo es obligatorio al cancelar", "code": "MOTIVO_REQUIRED" }`

#### Scenario: motivo not required for advance transitions
- **WHEN** staff sends `{ nuevo_estado: "EN_CAMINO", motivo: null }`
- **THEN** the transition succeeds normally (motivo stored as NULL in history row)

---

### Requirement: RBAC per cancellation transition (fine-grained)

Beyond endpoint-level `require_role`, the service SHALL enforce role eligibility per transition (RN-FS08 / RN-RB08).

#### Scenario: PEDIDOS cannot cancel EN_PREP order
- **WHEN** a bearer token with role `PEDIDOS` sends `{ nuevo_estado: "CANCELADO" }` on an EN_PREP order
- **THEN** the server returns HTTP 403
- **THEN** the body contains `{ "detail": "Su rol no tiene permiso para cancelar pedidos en este estado.", "code": "CANCEL_NOT_ALLOWED_FOR_ROLE" }`

#### Scenario: ADMIN can cancel EN_PREP order
- **WHEN** a bearer token with role `ADMIN` sends `{ nuevo_estado: "CANCELADO", motivo: "..." }` on an EN_PREP order
- **THEN** the server returns HTTP 200 and stock is restored

#### Scenario: PEDIDOS can cancel CONFIRMADO order
- **WHEN** a bearer token with role `PEDIDOS` sends `{ nuevo_estado: "CANCELADO", motivo: "..." }` on a CONFIRMADO order
- **THEN** the server returns HTTP 200 and stock is restored

---

### Requirement: Stock restoration on cancel from CONFIRMADO or EN_PREP (RN-FS05)

When a CONFIRMADO or EN_PREP order is cancelled, the service SHALL restore stock atomically inside the same UoW via additive UPDATE.

#### Scenario: Stock restored when cancelling from CONFIRMADO
- **GIVEN** a CONFIRMADO order with items: Product A qty=2, Product B qty=1
- **GIVEN** Product A `stock_cantidad = 8`, Product B `stock_cantidad = 5` (after decrement in Change 19)
- **WHEN** staff cancels the order (`nuevo_estado = "CANCELADO"`, `motivo = "..."`)
- **THEN** `Product A.stock_cantidad = 10` after commit
- **THEN** `Product B.stock_cantidad = 6` after commit
- **THEN** `pedido.estado_codigo = "CANCELADO"` in the same atomic transaction

#### Scenario: Stock restored when cancelling from EN_PREP (ADMIN only)
- **GIVEN** an EN_PREP order with one item: Product C qty=3, `stock_cantidad = 7`
- **WHEN** ADMIN cancels (`nuevo_estado = "CANCELADO"`, `motivo = "..."`)
- **THEN** `Product C.stock_cantidad = 10` after commit
- **THEN** the state and stock change are in the same atomic transaction

#### Scenario: Stock NOT restored when cancelling from PENDIENTE
- **GIVEN** a PENDIENTE order (stock was not decremented — Change 19 hasn't run)
- **WHEN** the order is cancelled
- **THEN** no stock UPDATE is executed
- **THEN** product stock values are unchanged

#### Scenario: Rollback if stock restore fails
- **GIVEN** a CONFIRMADO order being cancelled
- **WHEN** the stock UPDATE fails (e.g., DB error)
- **THEN** the UoW rolls back the entire transaction
- **THEN** `pedido.estado_codigo` remains `"CONFIRMADO"` (unchanged)
- **THEN** no `HistorialEstadoPedido` row is written

---

### Requirement: DELETE /api/v1/pedidos/{id} — CLIENT self-cancellation from PENDIENTE or CONFIRMADO

> **Source**: Integrador §5.3 — CLIENT can cancel their own order when in state PENDIENTE or CONFIRMADO.

The system SHALL provide `DELETE /api/v1/pedidos/{id}` exclusively for CLIENT role users to cancel their own order, provided it is in state `PENDIENTE` or `CONFIRMADO`.

Request body SHALL be optional: `{ motivo?: str }`. If omitted, the service SHALL substitute `"Cancelado por el cliente"` as the stored motivo.

When the order is in state `CONFIRMADO`, the service SHALL atomically restore stock (same UoW as the state transition and history append). When the order is in state `PENDIENTE`, no stock restoration is performed (Change 19 has not decremented stock yet).

For orders in any other state (EN_PREP, EN_CAMINO, ENTREGADO, CANCELADO), the endpoint SHALL return 409 `INVALID_TRANSITION`.

#### Scenario: CLIENT cancels own PENDIENTE order successfully
- **WHEN** a bearer token with role `CLIENT` sends `DELETE /api/v1/pedidos/{id}` and the order belongs to the authenticated user in state `PENDIENTE`
- **THEN** the server returns HTTP 200
- **THEN** `pedido.estado_codigo = "CANCELADO"` in the database
- **THEN** one `HistorialEstadoPedido` row with `estado_desde = "PENDIENTE"`, `estado_hacia = "CANCELADO"`, `actor_user_id = <client_user_id>`
- **THEN** no stock UPDATE is executed (stock was not decremented for PENDIENTE orders)

#### Scenario: CLIENT cancels own CONFIRMADO order successfully (with stock restore)
- **WHEN** a bearer token with role `CLIENT` sends `DELETE /api/v1/pedidos/{id}` and the order belongs to the authenticated user in state `CONFIRMADO`
- **THEN** the server returns HTTP 200
- **THEN** `pedido.estado_codigo = "CANCELADO"` in the database
- **THEN** one `HistorialEstadoPedido` row with `estado_desde = "CONFIRMADO"`, `estado_hacia = "CANCELADO"`, `actor_user_id = <client_user_id>`
- **THEN** `_restore_stock` is called within the same UoW — stock quantities are restored atomically
- **THEN** if stock restore fails, the entire transaction is rolled back (state remains CONFIRMADO)

#### Scenario: CLIENT DELETE from EN_PREP returns 409 INVALID_TRANSITION
- **WHEN** a CLIENT sends `DELETE /api/v1/pedidos/{id}` where the order is in state `EN_PREP`
- **THEN** the server returns HTTP 409
- **THEN** the body contains `{ "detail": "Solo se puede cancelar pedidos en estado PENDIENTE o CONFIRMADO desde este endpoint.", "code": "INVALID_TRANSITION" }`
- **THEN** no state mutation or stock change occurs

#### Scenario: CLIENT cannot cancel another user's order
- **WHEN** a CLIENT sends `DELETE /api/v1/pedidos/{id}` where `pedido.usuario_id != current_user.id`
- **THEN** the server returns HTTP 403
- **THEN** the body contains `{ "detail": "No tiene permiso para operar sobre este pedido.", "code": "ORDER_NOT_OWNED" }`

#### Scenario: ADMIN and PEDIDOS tokens rejected from DELETE endpoint
- **WHEN** a bearer token with role `PEDIDOS` or `ADMIN` sends `DELETE /api/v1/pedidos/{id}`
- **THEN** the server returns HTTP 403 (staff must use PATCH for all cancellations)

---

### Requirement: Transactional atomicity — single UoW for all mutations

Every state transition SHALL execute all mutations (state update + history append + optional stock restore) within a single `UnitOfWork`. No partial writes are permissible.

#### Scenario: Service does not call session.commit() directly
- **WHEN** the code of `state_transition.py` is inspected statically
- **THEN** no call to `session.commit()` exists in the file
- **THEN** commit is exclusively the responsibility of `UnitOfWork.__aexit__`

#### Scenario: Exception during history append rolls back state update
- **GIVEN** a valid transition where `update_estado` was flushed successfully
- **WHEN** `historial_pedido.append()` raises an unexpected exception
- **THEN** the UoW rolls back the entire transaction
- **THEN** `pedido.estado_codigo` retains its pre-transition value in the database

---

### Requirement: Pessimistic locking — `get_for_update(pedido_id)` before reading state

Before reading `pedido.estado_codigo` in any transition service function (`transition_state` and `cancel_own_client`), the service SHALL call `uow.pedidos.get_for_update(pedido_id)`. This method executes `SELECT * FROM pedido WHERE id = :pedido_id FOR UPDATE` (pessimistic row lock). This prevents two concurrent requests from both reading the same state and both attempting the same transition.

#### Scenario: Concurrent transition requests — only one succeeds
> **TEST MARKER**: `@pytest.mark.integration` — requires real PostgreSQL. Do not run with SQLite.

- **GIVEN** an order in state `CONFIRMADO`
- **WHEN** two concurrent `PATCH` requests both attempt `nuevo_estado = "EN_PREP"`
- **THEN** exactly one returns HTTP 200 with `estado_codigo = "EN_PREP"`
- **THEN** the second returns HTTP 409 `INVALID_TRANSITION` (state is now `EN_PREP`, cannot transition to `EN_PREP` again)
- **THEN** the database has exactly one `HistorialEstadoPedido` row for this transition

---

## ADDED Requirements (Change 19: payments-mercadopago-integration)

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
## Requirements
### Requirement: ADMIN RBAC ratification for order state machine — cross-reference
The `backend-order-state-machine` spec SHALL ratify the ADMIN access matrix for FSM endpoints as defined in `backend-admin-aggregated-permissions`.

The following MUST hold:
- `PATCH /api/v1/pedidos/{id}/estado` SHALL accept `require_role("PEDIDOS", "ADMIN")`. Both staff roles can advance or cancel orders via the FSM.
- `DELETE /api/v1/pedidos/{id}` SHALL accept `require_role("CLIENT")` ONLY — CLIENT-only self-cancellation path. ADMIN and PEDIDOS MUST NOT use this endpoint for cancellation. Administrative cancellation SHALL be performed exclusively via `PATCH /{id}/estado` with `nuevo_estado=CANCELADO`.

This distinction is a hard architectural boundary (D-12, Change 18). The semantic meaning of `DELETE /pedidos/{id}` is "client revokes their own order" — it is not equivalent to admin cancellation and MUST remain CLIENT-only.

See `backend-admin-aggregated-permissions` for the canonical RBAC matrix.

#### Scenario: ADMIN can advance order state via PATCH /estado (ratification)
- **WHEN** `PATCH /api/v1/pedidos/{id}/estado` is called with a valid ADMIN JWT and `{"nuevo_estado": "EN_PREP"}` with order in CONFIRMADO state
- **THEN** response is HTTP 200 with updated `PedidoRead`

#### Scenario: ADMIN can cancel an order via PATCH /estado (ratification)
- **WHEN** `PATCH /api/v1/pedidos/{id}/estado` is called with a valid ADMIN JWT and `{"nuevo_estado": "CANCELADO", "motivo": "Cancelado por administración"}`
- **WHEN** the order is in a cancellable state (PENDIENTE, CONFIRMADO, or EN_PREP per RN-RB08)
- **THEN** response is HTTP 200 with `PedidoRead` showing `estado_codigo = "CANCELADO"`

#### Scenario: ADMIN cannot cancel via DELETE endpoint (CLIENT-only path preserved)
- **WHEN** `DELETE /api/v1/pedidos/{id}` is called with a valid ADMIN JWT
- **THEN** response is HTTP 403
- **THEN** the order is not modified

