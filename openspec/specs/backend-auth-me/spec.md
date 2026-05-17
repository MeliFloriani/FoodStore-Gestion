# backend-auth-me Specification

## Purpose
Define the `GET /api/v1/auth/me` endpoint for the Food Store backend: returns the authenticated user's profile (UserRead schema) based on a valid Bearer access token. Also defines the `UserRead.created_at` field extension and the RBAC smoke test requirement for `require_role` end-to-end validation.

## Requirements

### Requirement: GET /api/v1/auth/me endpoint returns authenticated user profile
`backend/app/api/v1/auth.py` SHALL define `GET /auth/me` with:
- `response_model=UserRead`, `status_code=200`.
- `Depends(get_current_user)` — requires a valid Bearer access token (raises 401 on missing/invalid/expired token).
- No request body, no query parameters.
- Returns `UserRead.model_validate(current_user)` where `current_user` is the `Usuario` instance resolved by `get_current_user`.

No additional service method is required — `get_current_user` calls `uow.usuarios.get_by_id(user_uuid)` (verified in `backend/app/api/deps.py` line 100), which triggers the model-level `lazy='selectin'` eager load on `Usuario.usuario_roles` (defined in `backend/app/models/user.py`). The router calls `UserRead.model_validate(current_user)` directly.

**Correction to previous spec text**: The prior version stated "uses `get_with_roles`" — this is incorrect. The actual method used is `get_by_id`, which implicitly loads roles via `lazy='selectin'` on the `Usuario.usuario_roles` relationship. If that relationship's lazy strategy ever changes to `noload`, `UserRead.roles` will silently return `[]` — in that case, `get_current_user` must be updated to use an explicit `get_with_roles` eager query instead.

#### Scenario: Valid Bearer token returns 200 UserRead
- **WHEN** `GET /api/v1/auth/me` is called with `Authorization: Bearer <valid_access_token>`
- **THEN** HTTP 200 is returned
- **THEN** the response body matches `UserRead`: `{ id: <uuid-string>, nombre, apellido, email, roles: [<list of role codes>], created_at: <iso8601-datetime> }`
- **THEN** the `id` field is a UUID serialized as a string
- **THEN** the `created_at` field is present and is a valid ISO 8601 datetime string

#### Scenario: Missing Authorization header returns 401
- **WHEN** `GET /api/v1/auth/me` is called without an Authorization header
- **THEN** HTTP 401 is returned
- **THEN** the body is RFC 7807 format with `"status": 401`

#### Scenario: Expired access token returns 401
- **WHEN** `GET /api/v1/auth/me` is called with an expired JWT
- **THEN** HTTP 401 is returned
- **THEN** the body contains `"code": "invalid_token"`

#### Scenario: Soft-deleted user returns 401
- **WHEN** a valid JWT is provided for a user whose `deleted_at IS NOT NULL`
- **THEN** `get_current_user` raises `UnauthorizedError`
- **THEN** HTTP 401 is returned

#### Scenario: Response never includes password_hash
- **WHEN** `GET /api/v1/auth/me` returns a successful response
- **THEN** the response body does NOT contain a `password_hash` field
- **THEN** the response body matches the `UserRead` schema exactly

---

### Requirement: UserRead schema extended with created_at field
`backend/app/schemas/auth.py` `UserRead` SHALL be extended with `created_at: datetime` field. This field is required by the Integrador spec §6.1 (line 242: `UserResponse: id, nombre, apellido, email, roles: list[str], created_at`).

- `created_at: datetime` SHALL be read from the `Usuario` ORM object via `from_attributes=True`.
- The field SHALL be serialized as an ISO 8601 datetime string in the JSON response.
- `from datetime import datetime` SHALL be added to `backend/app/schemas/auth.py` imports if not already present.

#### Scenario: UserRead includes created_at field
- **WHEN** `UserRead.model_validate(usuario_instance)` is called
- **THEN** the resulting `UserRead` object has a `created_at` field of type `datetime`
- **THEN** the field serializes to an ISO 8601 string in JSON output

---

### Requirement: RBAC smoke test — require_role end-to-end validation
A test module `backend/tests/test_rbac.py` SHALL verify that `require_role` works correctly end-to-end. This requirement documents the test expectation, not a new endpoint.

At minimum:
- `GET /api/v1/auth/me` with a CLIENT-role token SHALL return 200 (authenticated, no role restriction on this endpoint).
- An endpoint decorated with `Depends(require_role("ADMIN"))` SHALL return 403 when called with a CLIENT-role token.
- An endpoint decorated with `Depends(require_role("ADMIN"))` SHALL return 401 when called without any token.

Implementation note: the test may use a test-only router registered only in the test app, or use an existing ADMIN-only endpoint if one exists. The goal is to confirm the `require_role` dependency chain (get_current_user → role check → ForbiddenError) works in an integration test context.

#### Scenario: CLIENT token on /auth/me returns 200
- **WHEN** `GET /api/v1/auth/me` is called with a CLIENT-role access token
- **THEN** HTTP 200 is returned

#### Scenario: CLIENT token on admin-protected endpoint returns 403
- **WHEN** a route decorated with `Depends(require_role("ADMIN"))` is called with a CLIENT-role access token
- **THEN** HTTP 403 is returned
- **THEN** the body follows RFC 7807 with `"status": 403`

#### Scenario: No token on admin-protected endpoint returns 401
- **WHEN** a route decorated with `Depends(require_role("ADMIN"))` is called without Authorization header
- **THEN** HTTP 401 is returned (not 403 — authentication precedes authorization)

#### Scenario: ADMIN token on admin-protected endpoint returns 200
- **WHEN** a route decorated with `Depends(require_role("ADMIN"))` is called with an ADMIN-role access token
- **THEN** HTTP 200 is returned
