## ADDED Requirements

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
