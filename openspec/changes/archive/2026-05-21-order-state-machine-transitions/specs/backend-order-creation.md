# backend-order-creation Specification — delta

## Cross-Reference Note (Change 18: order-state-machine-transitions)

> This delta adds a clarifying cross-reference to the archived Change 17 spec. No existing requirement is modified. The purpose is to establish ownership boundaries between Change 17 (initial history row) and Change 18 (all subsequent history rows).

## ADDED Requirements

### Requirement: HistorialEstadoPedido ownership boundary — Change 17 vs Change 18

The `backend-order-creation` spec (Change 17) owns exactly **one** `HistorialEstadoPedido` row per order: the seed row written at creation time with `estado_desde = NULL` and `estado_hacia = "PENDIENTE"` (RN-02). All subsequent `HistorialEstadoPedido` rows — whether from manual transitions (Change 18) or the automatic PENDIENTE→CONFIRMADO webhook (Change 19) — are written by their respective changes, not by the order creation service.

This boundary is enforced architecturally:
- `pedidos_service.py` (Change 17) writes exactly one history row: the PENDIENTE seed.
- `state_transition.py` (Change 18) writes all manual-transition rows.
- `pagos_service.py` (Change 19) writes the PENDIENTE→CONFIRMADO row with `actor_user_id = NULL` (SISTEMA).

#### Scenario: Cross-reference — HistorialEstadoPedido row shape is consistent across changes
- **GIVEN** an order that has progressed through states: PENDIENTE (creation), CONFIRMADO (webhook), EN_PREP (manual), CANCELADO (manual)
- **WHEN** `GET /api/v1/pedidos/{id}/historial` is called
- **THEN** the response contains 4 rows ordered by `created_at ASC`
- **THEN** row 1: `{ estado_desde: null, estado_hacia: "PENDIENTE", actor_user_id: null }` (Change 17 — seed row, `cambiado_por_id=None` as confirmed in archived tasks; NULL = created automatically by the system at order creation, not a manual transition)
- **THEN** row 2: `{ estado_desde: "PENDIENTE", estado_hacia: "CONFIRMADO", actor_user_id: null }` (Change 19 — SISTEMA webhook, also NULL)
- **THEN** row 3: `{ estado_desde: "CONFIRMADO", estado_hacia: "EN_PREP", actor_user_id: <staff_user_id> }` (Change 18 — always non-NULL for manual transitions)
- **THEN** row 4: `{ estado_desde: "EN_PREP", estado_hacia: "CANCELADO", actor_user_id: <admin_user_id>, motivo: "..." }` (Change 18)
- **THEN** all rows share the same column schema (`HistorialRead` shape) regardless of which change wrote them

**Ownership boundaries (non-negotiable)**:
- Change 17 owns the PENDIENTE seed row. `actor_user_id = null` for that row is correct and intentional. Change 18 does NOT rewrite or correct it.
- Change 18 writes ALL subsequent manual-transition rows with `actor_user_id = <authenticated_user.id>` (always non-NULL).
- `HistorialRead.actor_user_id: UUID | None` allows the initial null row to be represented correctly in API responses.
