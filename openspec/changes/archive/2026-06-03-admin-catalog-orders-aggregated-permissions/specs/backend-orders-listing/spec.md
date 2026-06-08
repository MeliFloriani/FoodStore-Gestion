## ADDED Requirements

### Requirement: ADMIN RBAC ratification for orders listing — cross-reference
The `backend-orders-listing` spec SHALL ratify the ADMIN access matrix for the listing endpoint as defined in `backend-admin-aggregated-permissions`.

The following MUST hold:
- `GET /api/v1/pedidos/` SHALL accept `require_role("CLIENT", "PEDIDOS", "ADMIN")`. CLIENT sees only their own orders; PEDIDOS and ADMIN SHALL see all orders with optional filters (estado, desde, hasta, cliente).
- STOCK role SHALL receive HTTP 403 always.

See `backend-admin-aggregated-permissions` for the canonical RBAC matrix.

#### Scenario: ADMIN can list all orders with full filter access (ratification)
- **WHEN** `GET /api/v1/pedidos/` is called with a valid ADMIN JWT
- **THEN** response is HTTP 200 with `Page[PedidoListItem]` containing all system orders
- **THEN** optional filters (estado, desde, hasta, cliente) are applied when provided

#### Scenario: ADMIN RBAC smoke test — listing returns non-403 for ADMIN
- **WHEN** `GET /api/v1/pedidos/` is called with a valid ADMIN JWT
- **THEN** response is HTTP 200 (not HTTP 403)
