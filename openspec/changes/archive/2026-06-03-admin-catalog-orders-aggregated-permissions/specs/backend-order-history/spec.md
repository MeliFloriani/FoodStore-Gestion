## ADDED Requirements

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
