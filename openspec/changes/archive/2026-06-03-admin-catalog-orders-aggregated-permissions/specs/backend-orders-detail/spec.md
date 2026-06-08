## ADDED Requirements

### Requirement: ADMIN RBAC ratification for order detail — cross-reference
The `backend-orders-detail` spec SHALL ratify the ADMIN access matrix for the order detail endpoint as defined in `backend-admin-aggregated-permissions`.

The following MUST hold for `GET /api/v1/pedidos/{id}` — authenticated via `get_current_user`; RBAC SHALL be enforced in the service layer:
- CLIENT: MUST own the order (403 if not owner, 404 if not found)
- PEDIDOS: SHALL access any order
- ADMIN: SHALL access any order
- STOCK: SHALL receive 403 always

See `backend-admin-aggregated-permissions` for the canonical RBAC matrix.

#### Scenario: ADMIN can view any order detail regardless of ownership (ratification)
- **WHEN** `GET /api/v1/pedidos/{id}` is called with a valid ADMIN JWT for any existing order
- **THEN** response is HTTP 200 with `PedidoDetail` regardless of which user placed the order

#### Scenario: ADMIN RBAC smoke test — order detail returns non-403 for ADMIN
- **WHEN** `GET /api/v1/pedidos/{id}` is called with a valid ADMIN JWT for an existing order
- **THEN** response is HTTP 200 (not HTTP 403)
