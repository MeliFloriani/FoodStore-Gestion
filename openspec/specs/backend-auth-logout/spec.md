# backend-auth-logout Specification

## Purpose
Define the logout capability for the Food Store backend: a `POST /api/v1/auth/logout` endpoint that revokes a specific refresh token by hash. Logout is idempotent — unknown, already-revoked, or expired tokens all result in a silent no-op. The endpoint does not require an Authorization header; the refresh token in the body is the sole credential.

## Requirements

### Requirement: LogoutRequest schema
`backend/app/schemas/auth.py` SHALL define `LogoutRequest(BaseModel)` with `refresh_token: str`. This schema is used as the body for `POST /api/v1/auth/logout`.

#### Scenario: LogoutRequest accepts string refresh_token
- **WHEN** `LogoutRequest(refresh_token="some.jwt.string")` is instantiated
- **THEN** `request.refresh_token` equals `"some.jwt.string"`

#### Scenario: LogoutRequest rejects missing field
- **WHEN** `LogoutRequest()` is instantiated without `refresh_token`
- **THEN** a `ValidationError` is raised

---

### Requirement: AuthService.revoke_refresh for single-token logout
`backend/app/services/auth.py` SHALL define `AuthService.revoke_refresh(uow: UnitOfWork, refresh_token_cleartext: str) -> None` as a `@staticmethod`. It SHALL:

1. Compute `token_hash = hashlib.sha256(refresh_token_cleartext.encode()).hexdigest()`.
2. Call `uow.refresh_tokens.revoke_by_hash(token_hash)`.
   - If `revoke_by_hash` returns `False` (token not found), the method SHALL silently succeed (no error — idempotent logout).
3. Return `None`.

SHALL NOT raise an error if the token is unknown, already revoked, or expired. Logout is always idempotent.
SHALL NOT call `session.commit()`.

#### Scenario: Logout revokes the specified refresh token
- **WHEN** `revoke_refresh(uow, valid_cleartext_refresh)` is called
- **THEN** the corresponding `RefreshToken` row has `revoked_at` set to a non-null timestamp
- **THEN** no exception is raised

#### Scenario: Logout with unknown token is silent no-op
- **WHEN** `revoke_refresh(uow, unknown_cleartext)` is called
- **THEN** no exception is raised
- **THEN** no rows are modified

#### Scenario: Logout with already-revoked token is silent no-op
- **WHEN** `revoke_refresh(uow, already_revoked_cleartext)` is called
- **THEN** no exception is raised
- **THEN** the `revoked_at` timestamp is unchanged (already set)

#### Scenario: Logout does NOT revoke the entire family
- **WHEN** `revoke_refresh(uow, one_token_in_a_family)` is called
- **THEN** only the specific token's `revoked_at` is set
- **THEN** other tokens in the same family remain unaffected (their `revoked_at` stays NULL)

---

### Requirement: POST /api/v1/auth/logout endpoint
`backend/app/api/v1/auth.py` SHALL define `POST /auth/logout` with:
- `response_model=None`, `status_code=204`.
- Body: `LogoutRequest` schema with `refresh_token: str`.
- No rate limit decorator (logout is not a sensitive enumeration path).
- No `Depends(get_current_user)` — the endpoint is callable even if the access token is expired; revocation is keyed on the refresh token.
- Delegates to `AuthService.revoke_refresh(uow, data.refresh_token)`.
- Returns `Response(status_code=204)` with no body.

#### Scenario: Valid logout returns 204 No Content
- **WHEN** `POST /api/v1/auth/logout` is called with a valid refresh token in the body
- **THEN** HTTP 204 is returned with no response body
- **THEN** the corresponding `RefreshToken.revoked_at` is set

#### Scenario: Logout with unknown refresh token still returns 204
- **WHEN** `POST /api/v1/auth/logout` is called with an unrecognized refresh token
- **THEN** HTTP 204 is returned (idempotent — no error)
- **THEN** no database row is modified

#### Scenario: Logout without Bearer token still returns 204
- **WHEN** `POST /api/v1/auth/logout` is called without an Authorization header
- **THEN** HTTP 204 is returned (the access token is not required)

#### Scenario: Invalid body returns 422
- **WHEN** `POST /api/v1/auth/logout` is called without a `refresh_token` field
- **THEN** HTTP 422 is returned

#### Scenario: Logout does not invalidate the access token
- **WHEN** a user logs out via `POST /api/v1/auth/logout`
- **THEN** their current access token (if still within 30-min TTL) remains valid for subsequent requests
- **THEN** `GET /api/v1/auth/me` with the same access token still returns 200 until expiry
