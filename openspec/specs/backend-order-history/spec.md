# backend-order-history Specification

## Purpose
Append-only order state history capability introduced in Change 18 (`order-state-machine-transitions`). Every order state transition — whether manual (Change 18) or automatic (Change 19 webhook) — writes one immutable `HistorialEstadoPedido` row. This spec covers the repository contract (no UPDATE/DELETE), the `GET /api/v1/pedidos/{id}/historial` endpoint, and the `HistorialRead` response schema.

## ADDED Requirements

---

### Requirement: GET /api/v1/pedidos/{id}/historial — ordered audit trail

The system SHALL provide `GET /api/v1/pedidos/{id}/historial` that returns the complete chronological list of state transitions for a given order.

Response: `200 List[HistorialRead]` ordered by `created_at ASC`.

Schema:
```
HistorialRead {
  id: UUID
  pedido_id: UUID
  estado_desde: str | None   -- NULL for the initial PENDIENTE entry (RN-02)
  estado_hacia: str
  motivo: str | None
  actor_user_id: UUID | None -- NULL if transition performed by SISTEMA (Change 19)
  created_at: datetime (ISO 8601, UTC)
}
```

#### Scenario: Order owner (CLIENT) retrieves own order historial
- **WHEN** a bearer token with role `CLIENT` sends `GET /api/v1/pedidos/{id}/historial` and `pedido.usuario_id == current_user.id`
- **THEN** the server returns HTTP 200
- **THEN** the body is a JSON array of `HistorialRead` objects ordered by `created_at ASC`
- **THEN** the first entry has `estado_desde = null` and `estado_hacia = "PENDIENTE"` (RN-02)

#### Scenario: ADMIN retrieves any order's historial
- **WHEN** a bearer token with role `ADMIN` sends the request for any order
- **THEN** the server returns HTTP 200 regardless of order ownership

#### Scenario: PEDIDOS retrieves any order's historial
- **WHEN** a bearer token with role `PEDIDOS` sends the request for any order
- **THEN** the server returns HTTP 200

#### Scenario: STOCK is forbidden from historial endpoint
- **WHEN** a bearer token with role `STOCK` sends `GET /api/v1/pedidos/{id}/historial`
- **THEN** the server returns HTTP 403 (RN-RB06)

#### Scenario: CLIENT is forbidden from another user's order historial
- **WHEN** a CLIENT sends the request for an order that does not belong to them (`pedido.usuario_id != current_user.id`)
- **THEN** the server returns HTTP 403
- **THEN** the body contains `{ "detail": "No tiene permiso para operar sobre este pedido.", "code": "ORDER_NOT_OWNED" }`

#### Scenario: Non-existent order returns 404
- **WHEN** `{id}` does not match any row in the `pedido` table
- **THEN** the server returns HTTP 404
- **THEN** the body contains `{ "detail": "El pedido no fue encontrado.", "code": "ORDER_NOT_FOUND" }`

#### Scenario: Unauthenticated request rejected
- **WHEN** no `Authorization` header is present
- **THEN** the server returns HTTP 401

#### Scenario: Results are ordered by created_at ascending
- **GIVEN** an order with 4 history rows (PENDIENTE creation, CONFIRMADO, EN_PREP, CANCELADO)
- **WHEN** the historial is retrieved
- **THEN** entries appear in chronological order: `PENDIENTE` first, `CANCELADO` last
- **THEN** no descending or random ordering is applied

---

### Requirement: HistorialEstadoPedidoRepository — append-only contract (RN-FS07 / RN-03)

`HistorialEstadoPedidoRepository` SHALL expose only two public methods:
- `append(row: HistorialEstadoPedido) -> HistorialEstadoPedido` — inserts and flushes one row
- `list_by_pedido(pedido_id: UUID) -> list[HistorialEstadoPedido]` — SELECT ORDER BY created_at ASC

The repository SHALL NOT inherit or expose `update` or `delete` methods from `BaseRepository`. This invariant ensures that no layer of the application can mutate or delete historical records. The class SHALL document this constraint explicitly (class-level docstring or type comment referencing RN-FS07 / RN-03).

#### Scenario: append() writes one row per transition
- **WHEN** a state transition completes within a UoW
- **THEN** exactly one new row exists in `historial_estado_pedido` for that transition
- **THEN** `created_at` is set server-side (database default `NOW()`, not from client)

#### Scenario: No update or delete method callable on HistorialEstadoPedidoRepository
- **WHEN** the repository class is inspected
- **THEN** no `update()` method is defined or inherited and callable
- **THEN** no `delete()` method is defined or inherited and callable
- **THEN** attempting to call `uow.historial_pedido.update(...)` raises `AttributeError` or is not possible at the type level

#### Scenario: actor_user_id is NULL for SISTEMA transitions (future Change 19)
- **WHEN** a history row is created with `actor_user_id = None`
- **THEN** the row is accepted (column allows NULL)
- **THEN** `HistorialRead.actor_user_id = null` in the API response

#### Scenario: actor_user_id is the authenticated user's id for all Change 18 transitions
- **WHEN** any manual transition (PATCH or DELETE) completes
- **THEN** `historial_estado_pedido.actor_user_id = current_user.id` (non-null) in the database

---

### Requirement: UoW accessor — uow.historial_pedido

`UnitOfWork` SHALL expose a typed `historial_pedido` lazy property accessor that returns a `HistorialEstadoPedidoRepository` instance sharing the same `AsyncSession`.

#### Scenario: uow.historial_pedido returns HistorialEstadoPedidoRepository
- **WHEN** `uow.historial_pedido` is accessed inside an `async with UnitOfWork() as uow:` block
- **THEN** the returned object is an instance of `HistorialEstadoPedidoRepository`
- **THEN** the repository uses the same `AsyncSession` instance as all other UoW accessors. This is verified **indirectly**: a cancellation that modifies the pedido and writes the historial in the same UoW is persisted or rolled back atomically (verified by the rollback scenario in Task 7.1). Direct inspection of private `_session` attributes from outside the class is NOT required by this spec.

#### Scenario: Existing UoW accessors unaffected
- **WHEN** `uow.historial_pedido` is added to `UnitOfWork`
- **THEN** all pre-existing accessors (`uow.pedidos`, `uow.productos`, `uow.usuarios`, etc.) continue to function correctly
## Requirements
### Requirement: ADMIN RBAC ratification for order history — cross-reference
The `backend-order-history` spec SHALL ratify the ADMIN access matrix for the history endpoint as defined in `backend-admin-aggregated-permissions`.

The following MUST hold:
- `GET /api/v1/pedidos/{id}/historial` SHALL accept `require_role("CLIENT", "PEDIDOS", "ADMIN")`. CLIENT MUST own the order (403 if not owner). PEDIDOS and ADMIN SHALL access history for any order.

See `backend-admin-aggregated-permissions` for the canonical RBAC matrix.

#### Scenario: ADMIN can view order history for any order (ratification)
- **WHEN** `GET /api/v1/pedidos/{id}/historial` is called with a valid ADMIN JWT for any existing order
- **THEN** response is HTTP 200 with `list[HistorialEstadoPedidoRead]` ordered by `created_at ASC`
- **THEN** the ownership check is not applied (ADMIN can view any order's history)

#### Scenario: ADMIN RBAC smoke test — order history returns non-403 for ADMIN
- **WHEN** `GET /api/v1/pedidos/{id}/historial` is called with a valid ADMIN JWT for an existing order
- **THEN** response is HTTP 200 (not HTTP 403)

