# backend-auth-dependencies Specification

## Purpose
FastAPI dependency functions for identity resolution and role-based access control. Introduced in Change 04 (`backend-base-patterns`). Provides `get_current_user` (401 paths) and `require_role` (403 paths), backed by JWT decode helpers in `core/security.py`. Token issuance is deferred to Change 09.
## Requirements
### Requirement: `oauth2_scheme` placeholder
`backend/app/api/deps.py` SHALL define `oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)`. The `auto_error=False` setting prevents the scheme from raising 401 automatically — only `get_current_user` raises 401 when needed, giving the application control over error formatting (RFC 7807).

#### Scenario: oauth2_scheme does not raise on missing token
- **WHEN** a request arrives at an endpoint that uses `oauth2_scheme` but without an `Authorization` header
- **THEN** `oauth2_scheme` returns `None` (not a 401 exception)
- **THEN** `get_current_user` is responsible for raising `UnauthorizedError` in that case

#### Scenario: oauth2_scheme is shown in OpenAPI security schemes
- **WHEN** FastAPI's `/openapi.json` is generated
- **THEN** the `securitySchemes` section contains an entry of type `oauth2` with `tokenUrl: /api/v1/auth/login`

---

### Requirement: `get_current_user` dependency
`backend/app/api/deps.py` SHALL define `get_current_user(token: str | None = Depends(oauth2_scheme), uow: UnitOfWork = Depends(get_uow)) -> Usuario`. It SHALL:
1. Raise `UnauthorizedError` (→ HTTP 401 RFC 7807) if `token` is `None` or empty
2. Call `security.decode_access_token(token)` — which may raise `UnauthorizedError` on invalid/expired token
3. Extract `sub` (user UUID) from the decoded payload
4. Look up `Usuario` via `uow.usuarios.get_by_id(UUID(sub))`
5. Raise `UnauthorizedError` if the user is not found or has `deleted_at IS NOT NULL` (soft-deleted)
6. Return the `Usuario` instance

#### Scenario: Valid token resolves to active user
- **WHEN** a request includes `Authorization: Bearer <valid_jwt>` where the JWT encodes a valid `sub` UUID
- **THEN** `get_current_user` calls `decode_access_token(token)` without error
- **THEN** `uow.usuarios.get_by_id(sub)` returns the `Usuario`
- **THEN** the dependency returns the `Usuario` instance to the route handler

#### Scenario: Missing Authorization header returns HTTP 401
- **WHEN** a request is made to a route with `Depends(get_current_user)` without an `Authorization` header
- **THEN** `get_current_user` raises `UnauthorizedError`
- **THEN** the error handler returns HTTP 401 with `Content-Type: application/problem+json`
- **THEN** the response body contains `"status": 401` and `"code": "missing_token"` (or equivalent)

#### Scenario: Expired token returns HTTP 401
- **WHEN** a request includes `Authorization: Bearer <expired_jwt>`
- **THEN** `decode_access_token` raises `UnauthorizedError` with `code="invalid_token"`
- **THEN** `get_current_user` propagates the error
- **THEN** the client receives HTTP 401 with RFC 7807 body

#### Scenario: Invalid signature returns HTTP 401
- **WHEN** a request includes a JWT with a tampered signature
- **THEN** `decode_access_token` raises `UnauthorizedError`
- **THEN** the client receives HTTP 401

#### Scenario: Soft-deleted user returns HTTP 401
- **WHEN** a valid JWT is provided for a user that has been soft-deleted (`deleted_at IS NOT NULL`)
- **THEN** `uow.usuarios.get_by_id(sub)` returns `None` (soft-delete filter active)
- **THEN** `get_current_user` raises `UnauthorizedError`
- **THEN** the client receives HTTP 401 with RFC 7807 body

#### Scenario: Non-existent user ID in token returns HTTP 401
- **WHEN** a valid JWT is provided but the `sub` UUID does not match any `Usuario` record
- **THEN** `uow.usuarios.get_by_id(sub)` returns `None`
- **THEN** `get_current_user` raises `UnauthorizedError`
- **THEN** the client receives HTTP 401

---

### Requirement: `require_role` dependency factory
`backend/app/api/deps.py` SHALL define `require_role(*roles: str)` that returns a FastAPI-compatible callable dependency. The returned dependency SHALL call `get_current_user` via `Depends()` internally and check that the authenticated `Usuario` has at least one of the specified roles via `UsuarioRol`. If no role matches, it SHALL raise `ForbiddenError` (→ HTTP 403 RFC 7807).

#### Scenario: User with matching role proceeds
- **WHEN** a route is protected with `Depends(require_role("ADMIN"))` and the authenticated user has role `ADMIN` in `UsuarioRol`
- **THEN** the dependency resolves without raising an exception
- **THEN** the route handler executes normally

#### Scenario: User with at least one matching role out of multiple proceeds
- **WHEN** a route is protected with `Depends(require_role("ADMIN", "PEDIDOS"))` and the user has role `PEDIDOS` (but not `ADMIN`)
- **THEN** the dependency resolves without raising an exception (at least one match is sufficient)

#### Scenario: User without any matching role returns HTTP 403
- **WHEN** a route is protected with `Depends(require_role("ADMIN"))` and the user only has role `CLIENT`
- **THEN** `require_role` raises `ForbiddenError`
- **THEN** the client receives HTTP 403 with `Content-Type: application/problem+json`
- **THEN** the response body contains `"status": 403`

#### Scenario: Unauthenticated request to role-protected route returns HTTP 401 not 403
- **WHEN** a route is protected with `Depends(require_role("ADMIN"))` and no Authorization header is provided
- **THEN** `get_current_user` (called inside `require_role`) raises `UnauthorizedError` first
- **THEN** the client receives HTTP 401 (not 403) — authentication precedes authorization

#### Scenario: Role check uses active UsuarioRol records only
- **WHEN** a `UsuarioRol` record has been soft-deleted (or hard-deleted from the association table)
- **THEN** that role is NOT counted as an active role for the user
- **THEN** if it was the user's only role matching the requirement, HTTP 403 is returned

#### Scenario: Single UoW instance per request when both get_current_user and require_role are declared
- **WHEN** a route declares both `Depends(get_current_user)` and `Depends(require_role(...))`
- **THEN** exactly one `UnitOfWork` instance is created for the request (verifiable via `id(uow)` equality inside both dependencies)

---

### Requirement: Dependency identity invariant
The `get_uow` callable SHALL NOT be wrapped, aliased, or curried in any module that wires FastAPI dependencies. Wrappers break FastAPI's identity-based deduplication and result in multiple `AsyncSession` instances per request (see D-06 UoW deduplication).

#### Scenario: get_uow used directly, never wrapped
- **WHEN** any module under `app/api/` imports `get_uow`
- **THEN** it is used as `Depends(get_uow)` directly, never as `Depends(some_wrapper_of_get_uow)`

---

### Requirement: `core/security.py` — JWT decode helper
`backend/app/core/security.py` SHALL define `decode_access_token(token: str) -> dict` using `python-jose[cryptography]`. It SHALL:
1. Call `jwt.decode(token, settings.SECRET_KEY.get_secret_value(), algorithms=[settings.JWT_ALGORITHM])` with explicit `options` dict: `verify_signature=True`, `verify_exp=True`, `verify_nbf=True`, `verify_iat=True`, `verify_aud=False`, `verify_iss=False` (audience and issuer policies deferred).
2. On `JWTError` (including `ExpiredSignatureError`): raise `UnauthorizedError("Token inválido o expirado", code="invalid_token")`.
3. Return the decoded payload dict on success.

**Supersession of D-07**: This requirement now co-exists with token issuance functions in the same module. The restriction from Change 04 — "This module SHALL NOT contain token issuance functions" — is LIFTED by change `auth-register-login`. `backend/app/core/security.py` now also exports `hash_password`, `verify_password`, `create_access_token`, and `create_refresh_token` (see capability `backend-auth-token-issuance`). The import of `passlib[bcrypt]` and `hashlib` in `security.py` is valid and expected.

The `decode_access_token` implementation itself is UNCHANGED from Change 04.

#### Scenario: Valid token decodes to payload dict
- **WHEN** `decode_access_token(valid_jwt)` is called with a JWT signed with the correct `SECRET_KEY` and not expired
- **THEN** the method returns a `dict` containing at minimum the `sub` field (user UUID as string)
- **THEN** no exception is raised

#### Scenario: Expired token raises UnauthorizedError
- **WHEN** `decode_access_token(expired_jwt)` is called where the token's `exp` claim is in the past
- **THEN** `UnauthorizedError` is raised (not `JWTError` — the jose exception is wrapped)
- **THEN** the `UnauthorizedError` has `code="invalid_token"` and `status_code=401`

#### Scenario: Wrong signature raises UnauthorizedError
- **WHEN** `decode_access_token(tampered_jwt)` is called where the signature does not match `SECRET_KEY`
- **THEN** `UnauthorizedError` is raised (not a raw `JWTError`)

#### Scenario: nbf claim in the future raises UnauthorizedError
- **WHEN** `decode_access_token` is called with a token whose `nbf` is in the future
- **THEN** it raises `UnauthorizedError` (not a raw `JWTError`) and the deps layer maps it to HTTP 401

#### Scenario: options dict is passed explicitly with all verification flags
- **WHEN** `decode_access_token` is called
- **THEN** `options={"verify_signature": True, "verify_exp": True, "verify_nbf": True, "verify_iat": True, "verify_aud": False, "verify_iss": False}` is passed explicitly to `jwt.decode`

#### Scenario: security.py now contains both decode and issuance functions
- **WHEN** `backend/app/core/security.py` is statically inspected
- **THEN** it defines `decode_access_token` (unchanged), `hash_password`, `verify_password`, `create_access_token`, and `create_refresh_token`
- **THEN** the D-07 "decode-only" restriction is no longer in effect

### Requirement: JWT-related Settings additions
`backend/app/core/config.py` SHALL declare the following new fields in `Settings`, and `backend/.env.example` SHALL document them:

| Field | Type | Default | Required |
|---|---|---|---|
| `SECRET_KEY` | `SecretStr` | — | Yes |
| `JWT_ALGORITHM` | `str` | `"HS256"` | No |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `int` | `30` | No |
| `REFRESH_TOKEN_EXPIRE_DAYS` | `int` | `7` | No |

These additions are purely additive — no existing `Settings` fields are modified.

#### Scenario: SECRET_KEY is required
- **WHEN** `Settings()` is instantiated without `SECRET_KEY` in environment or `.env`
- **THEN** pydantic-settings raises `ValidationError` identifying `SECRET_KEY` as missing

#### Scenario: SECRET_KEY is SecretStr (not exposed in logs)
- **WHEN** `str(get_settings().SECRET_KEY)` is called
- **THEN** the output is `"**********"` (Pydantic SecretStr masking) — not the actual key value

#### Scenario: JWT defaults are applied when not set
- **WHEN** only `DATABASE_URL` and `SECRET_KEY` are set in the environment
- **THEN** `settings.JWT_ALGORITHM` is `"HS256"`
- **THEN** `settings.ACCESS_TOKEN_EXPIRE_MINUTES` is `30`
- **THEN** `settings.REFRESH_TOKEN_EXPIRE_DAYS` is `7`

#### Scenario: .env.example contains JWT entries
- **WHEN** `backend/.env.example` is read
- **THEN** it contains placeholder entries for `SECRET_KEY`, `JWT_ALGORITHM`, `ACCESS_TOKEN_EXPIRE_MINUTES`, `REFRESH_TOKEN_EXPIRE_DAYS`
- **THEN** the `SECRET_KEY` placeholder is a clearly fake example value (e.g., `your-super-secret-key-change-in-production`)

