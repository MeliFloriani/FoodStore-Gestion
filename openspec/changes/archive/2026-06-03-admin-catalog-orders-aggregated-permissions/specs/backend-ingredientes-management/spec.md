## ADDED Requirements

### Requirement: ADMIN RBAC ratification for ingredientes endpoints — cross-reference
The `backend-ingredientes-management` spec SHALL ratify the ADMIN access matrix for all ingredient endpoints as defined in `backend-admin-aggregated-permissions`. All ingredient endpoints (including reads) MUST require ADMIN or STOCK role per the D-01 decision in Change 09 (ingredients are an internal catalog resource).

The following MUST hold:
- `GET /api/v1/ingredientes/` SHALL accept `require_role("ADMIN", "STOCK")`. Both roles can list ingredients.
- `GET /api/v1/ingredientes/{id}` SHALL accept `require_role("ADMIN", "STOCK")`. Both roles can retrieve a single ingredient.
- `POST /api/v1/ingredientes/` SHALL accept `require_role("ADMIN", "STOCK")`. Both roles can create ingredients.
- `PUT /api/v1/ingredientes/{id}` SHALL accept `require_role("ADMIN", "STOCK")`. Both roles can update ingredients.
- `DELETE /api/v1/ingredientes/{id}` SHALL accept `require_role("ADMIN", "STOCK")`. Both roles can soft-delete ingredients.

See `backend-admin-aggregated-permissions` for the canonical RBAC matrix.

#### Scenario: ADMIN RBAC smoke test — all ingredient endpoints return non-403 for ADMIN
- **WHEN** `GET /api/v1/ingredientes/`, `GET /api/v1/ingredientes/{id}`, `POST /api/v1/ingredientes/`, `PUT /api/v1/ingredientes/{id}`, `DELETE /api/v1/ingredientes/{id}` are each called with a valid ADMIN JWT
- **THEN** none of these endpoints return HTTP 403 (authorization does not block ADMIN)

#### Scenario: ADMIN can create an ingredient (ratification)
- **WHEN** `POST /api/v1/ingredientes/` is called with a valid ADMIN JWT and valid body
- **THEN** response is HTTP 201 with `IngredienteRead`
