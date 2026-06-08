## ADDED Requirements

### Requirement: ADMIN RBAC ratification for productos write endpoints — cross-reference
The `backend-products-management` spec SHALL ratify the ADMIN access matrix for all product endpoints as defined in `backend-admin-aggregated-permissions`. The following MUST hold:

- `POST /api/v1/productos/` SHALL accept `require_role("ADMIN")`. STOCK MUST NOT have full product CRUD; ADMIN-exclusive.
- `PATCH /api/v1/productos/{id}` SHALL accept `require_role("ADMIN")`. ADMIN-exclusive.
- `DELETE /api/v1/productos/{id}` SHALL accept `require_role("ADMIN")`. ADMIN-exclusive.
- `PATCH /api/v1/productos/{id}/disponibilidad` SHALL accept `require_role("ADMIN", "STOCK")`. Both roles can toggle availability.
- `POST /api/v1/productos/{id}/ingredientes` SHALL accept `require_role("ADMIN")`. ADMIN-exclusive.
- `DELETE /api/v1/productos/{id}/ingredientes/{ing_id}` SHALL accept `require_role("ADMIN")`. ADMIN-exclusive.

See `backend-admin-aggregated-permissions` for the canonical RBAC matrix. This requirement serves as the cross-reference anchor for the product domain.

#### Scenario: ADMIN has full product CRUD access
- **WHEN** `POST /api/v1/productos/` is called with a valid ADMIN JWT and a valid `ProductoCreate` body
- **THEN** response is HTTP 201 with `ProductoRead`

#### Scenario: STOCK role cannot perform full product CRUD
- **WHEN** `POST /api/v1/productos/` is called with a valid STOCK JWT
- **THEN** response is HTTP 403

#### Scenario: ADMIN RBAC smoke test — all product write endpoints return non-403 for ADMIN
- **WHEN** `POST /api/v1/productos/`, `PATCH /api/v1/productos/{id}`, `DELETE /api/v1/productos/{id}`, `PATCH /api/v1/productos/{id}/disponibilidad`, `POST /api/v1/productos/{id}/ingredientes`, `DELETE /api/v1/productos/{id}/ingredientes/{ing_id}` are each called with a valid ADMIN JWT and valid payloads
- **THEN** none of these endpoints return HTTP 403 (authorization does not block ADMIN)
