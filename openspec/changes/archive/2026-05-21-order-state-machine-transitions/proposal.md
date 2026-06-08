# Proposal: order-state-machine-transitions (Change 18)

## Context

Change 18 is **Sprint 6, part 1 of 2** for the order lifecycle. Change 17 (`order-creation-with-snapshots`, archived) established the creation of orders in `PENDIENTE` state and the initial `HistorialEstadoPedido` seed row. Change 19 (`order-payment-webhook`) will handle the fully automatic `PENDIENTE → CONFIRMADO` transition triggered by MercadoPago IPN — it is intentionally excluded here so the manual FSM can be tested independently of the payment provider.

This change delivers the complete manual state-machine: five user stories (US-040 through US-044) covering advance transitions, cancellation with conditional stock restoration, the audit trail repository contract, and the order history endpoint.

## Why Now

- **Depends on**: Change 17 (archived) — `Pedido`, `DetallePedido`, `HistorialEstadoPedido` tables, UoW patterns, PedidoRepository, and `estado_codigo: "PENDIENTE"` as the starting state.
- **Unlocks**: Change 19 (webhook auto-transition needs the FSM validator already in place), Change 20 (order panel UI needs the history endpoint and action hooks), Change 22 (aggregated ADMIN access policy adjusts `require_role` on these endpoints).

## Scope — What's IN

- **US-040**: Manual advance `CONFIRMADO → EN_PREP` — ADMIN or PEDIDOS via `PATCH /api/v1/pedidos/{id}/estado`.
- **US-041**: Manual advance `EN_PREP → EN_CAMINO` — ADMIN or PEDIDOS via `PATCH /api/v1/pedidos/{id}/estado`.
- **US-042**: Manual advance `EN_CAMINO → ENTREGADO` — ADMIN or PEDIDOS via `PATCH /api/v1/pedidos/{id}/estado`.
- **US-043**: Cancellation transitions:
  - `PENDIENTE → CANCELADO` — CLIENT (own order) via `DELETE /api/v1/pedidos/{id}` (no stock restore); PEDIDOS or ADMIN via PATCH.
  - `CONFIRMADO → CANCELADO` — CLIENT (own order) via `DELETE /api/v1/pedidos/{id}` (with atomic stock restore); PEDIDOS or ADMIN via PATCH (with atomic stock restore).
  - `EN_PREP → CANCELADO` — ADMIN only via PATCH; triggers atomic stock restoration. CLIENT cannot cancel from EN_PREP via DELETE (returns 409).
  - `motivo` is mandatory when `nuevo_estado = CANCELADO` (RN-05). Validated in service, not schema.
- **US-044**: Append-only audit trail (`HistorialEstadoPedido`) — every transition writes one row within the same UoW; no UPDATE/DELETE ever allowed from any layer (RN-FS07 / RN-03).
- **US-044**: History endpoint `GET /api/v1/pedidos/{id}/historial` — returns `List[HistorialRead]` ordered by `created_at ASC`; accessible to the order owner (CLIENT), ADMIN, or PEDIDOS; STOCK receives 403.
- **Frontend minimal layer**: TanStack Query hooks (`useTransitionEstado`, `useCancelarPedidoCliente`, `useHistorialPedido`), `EstadoActionBar` component, `CancelReasonModal` with mandatory reason input. No full panel UI.

## Non-goals — What's OUT

- `POST /api/v1/pedidos` — owned by Change 17 (archived).
- Automatic `PENDIENTE → CONFIRMADO` + stock decrement — Change 19 (MercadoPago webhook).
- Full order listing/detail panel pages (`/pedidos-panel/...`) — Change 20.
- Pagination — Change 20.
- Aggregated ADMIN access policy adjustments — Change 22.
- Global test coverage pass — Change 25 (unit tests for this feature are included here; integration/coverage closing is Change 25).
- `EN_CAMINO → CANCELADO` is **NOT** a valid transition (Integrador §3.4 FSM table — EN_CAMINO can only advance to ENTREGADO).

## User Stories Covered

| ID | Description | Endpoint | Roles |
|----|-------------|----------|-------|
| US-040 | Advance `CONFIRMADO → EN_PREP` | `PATCH /api/v1/pedidos/{id}/estado` | ADMIN, PEDIDOS |
| US-041 | Advance `EN_PREP → EN_CAMINO` | `PATCH /api/v1/pedidos/{id}/estado` | ADMIN, PEDIDOS |
| US-042 | Advance `EN_CAMINO → ENTREGADO` | `PATCH /api/v1/pedidos/{id}/estado` | ADMIN, PEDIDOS |
| US-043 | Cancel from PENDIENTE/CONFIRMADO/EN_PREP | `PATCH` or `DELETE /api/v1/pedidos/{id}` | Role depends on state |
| US-044 | Append-only audit trail + history query | `GET /api/v1/pedidos/{id}/historial` | Owner, ADMIN, PEDIDOS |

## Decision Log

**D-01 — FSM map location: service layer, not router**
The transition-allowed map (`ALLOWED_TRANSITIONS`) lives in `app/modules/pedidos/services/state_transition.py`. No router can call a state mutation without going through the FSM validator. This enforces the architectural rule that no router bypasses service validation (Integrador §3.4, rúbrica §15).

**D-02 — RBAC enforcement: two layers**
Role authorization is enforced at two levels: (a) the router dependency (`require_role`) blocks requests from roles that cannot call the endpoint at all; (b) the service additionally checks per-transition role eligibility for PATCH (e.g., only ADMIN can cancel from EN_PREP). Double enforcement ensures no role can reach the FSM validator with an unauthorized transition.

**D-03 — CLIENT cancel uses DELETE, staff uses PATCH**
Integrador §5.3 specifies `DELETE /api/v1/pedidos/{id}` for CLIENT-initiated cancellation and `PATCH /api/v1/pedidos/{id}/estado` for staff. Rationale: `DELETE` aligns with REST semantics for a CLIENT "withdrawing" their own order; the body is optional (`{ motivo?: string }`) and `motivo` defaults to `"Cancelado por el cliente"` if omitted. Staff use PATCH because they need a uniform body (`PedidoEstadoUpdate`) for all transitions including cancellations with mandatory `motivo`.

**D-04 — Append-only enforcement strategy: no inherited update/delete**
`HistorialEstadoPedidoRepository` SHALL NOT inherit the `update` and `delete` methods from `BaseRepository[T]`. It defines only `append(row)` and `list_by_pedido(pedido_id)`. This is enforced at the class level so no caller can accidentally mutate history rows. The spec documents this as RN-FS07 / RN-03 invariant.

**D-05 — Stock restoration strategy: additive UPDATE with RETURNING**
Cancel from CONFIRMADO or EN_PREP restores stock via `UPDATE producto SET stock_cantidad = stock_cantidad + :qty WHERE id = :id RETURNING stock_cantidad`. The additive form is safe under concurrent transactions. The `RETURNING` clause allows the service to verify the updated value is non-negative (a sanity check, not a business rule). This runs inside the same UoW as the state transition — atomicity is guaranteed by the single transaction.

**D-06 — `actor_user_id` semantics: NULL = SISTEMA, always non-NULL in Change 18**
`HistorialEstadoPedido.actor_user_id` is `NULL` when the transition is performed by the system (e.g., automatic webhook from Change 19). All transitions in Change 18 are human-initiated so `actor_user_id` is always the authenticated user's `id`. The field is named `actor_user_id` to distinguish it from `usuario_id` on the Pedido itself.

**D-07 — No migration required**
The `historial_estado_pedido` table with columns `id`, `pedido_id`, `estado_desde`, `estado_hacia`, `motivo`, `actor_user_id`, `created_at` was fully created by Change 03/04/17. No schema changes are needed; this change only adds service logic and endpoints.

**D-08 — `motivo` field on DELETE endpoint**
CLIENT's `DELETE /api/v1/pedidos/{id}` accepts an optional JSON body `{ motivo?: string }`. FastAPI supports optional request bodies via `Body(default=None)`. If omitted, the service substitutes a default string. This keeps the CLIENT experience frictionless while still recording a `motivo` in the history row.
