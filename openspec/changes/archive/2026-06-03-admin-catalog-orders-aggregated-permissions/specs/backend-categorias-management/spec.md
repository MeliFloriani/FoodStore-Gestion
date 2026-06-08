## ADDED Requirements

### Requirement: ADMIN RBAC ratification for categorias write endpoints — cross-reference
The `backend-categorias-management` spec SHALL ratify the ADMIN access matrix for all category endpoints as defined in `backend-admin-aggregated-permissions`. The following MUST hold for write endpoints:

- `POST /api/v1/categorias/` SHALL accept `require_role("ADMIN", "STOCK")`. Both roles can create categories.
- `PUT /api/v1/categorias/{id}` SHALL accept `require_role("ADMIN", "STOCK")`. Both roles can update categories.
- `DELETE /api/v1/categorias/{id}` SHALL accept `require_role("ADMIN", "STOCK")`. Both roles can soft-delete categories.

Read endpoints (`GET /api/v1/categorias/`, `GET /api/v1/categorias/{id}`) are public — no authentication required.

See `backend-admin-aggregated-permissions` for the canonical RBAC matrix.

#### Scenario: ADMIN RBAC smoke test — all category write endpoints return non-403 for ADMIN
- **WHEN** `POST /api/v1/categorias/`, `PUT /api/v1/categorias/{id}`, `DELETE /api/v1/categorias/{id}` are each called with a valid ADMIN JWT and valid payloads
- **THEN** none of these endpoints return HTTP 403 (authorization does not block ADMIN)

#### Scenario: ADMIN can create a category (ratification)
- **WHEN** `POST /api/v1/categorias/` is called with a valid ADMIN JWT and `{"nombre": "Bebidas"}`
- **THEN** response is HTTP 201 with `CategoriaRead`
