## Context

Change 04 (`backend-base-patterns`) established JWT decode infrastructure in `core/security.py` with a deliberate decode-only restriction (design decision D-07). Token issuance was deferred to "Change 09". This change (Sprint 1 auth) arrives earlier than originally numbered and lifts D-07. The UoW pattern, `BaseRepository[T]`, and RFC 7807 error handling are already in place from Changes 02–04. The `RefreshToken` and `UsuarioRol` models already exist from Change 03 migrations. slowapi rate limiting is already wired at `app/core/rate_limit.py`. The only missing piece is the auth surface: schemas, service, repository, router, and the security issuance functions.

Frontend: `authStore`, `AuthLayout`, `ProtectedRoute`, and `errors.ts` were introduced in prior changes. Four contract mismatches between the frontend type definitions and the actual backend `UserRead` response need to be patched atomically in this change.

## Goals / Non-Goals

**Goals:**
- Implement `POST /api/v1/auth/register` (201/409/422) and `POST /api/v1/auth/login` (200/401/429)
- Extend `core/security.py` with issuance functions, superseding D-07 from Change 04
- Persist refresh tokens as SHA-256 digests only; never store cleartext
- Rate-limit login at 5 attempts / 15 min per client IP
- Prevent email enumeration on login failures (always `401 { detail: "Invalid credentials", code: "invalid_credentials" }`)
- Auto-assign role `CLIENT` on registration via `UsuarioRol`
- Patch four frontend contract fixes for the auth round-trip to be type-safe

**Non-Goals:**
- Token refresh endpoint (`POST /auth/refresh`) — deferred to a future change
- `GET /auth/me` endpoint implementation — the route is referenced in `AuthSync` but its implementation is future work; the spec is not included here
- Logout endpoint — future change
- Email verification — out of scope for Sprint 1
- OAuth / social login — out of scope
- RBAC enforcement on any endpoint other than proving `CLIENT` role is assigned

## Decisions

### D-A: UserRead.id serialized as str (UUID → string)

**Decision**: `UserRead.id` is typed `str` at the HTTP boundary. The SQLModel model uses Python `UUID`; `UserRead` uses a `@field_serializer('id')` that calls `str(id)`. This matches the frontend fix (`id: string`) and avoids floating-point precision loss on very large numeric IDs that a plain `int` would introduce.

**Alternative considered**: `UUID` Pydantic type with automatic string serialization via `model_config = ConfigDict(json_encoders={UUID: str})`. Rejected — `field_serializer` is more explicit and compatible with Pydantic v2 strict mode.

### D-B: roles serialized as flat list[str] of codigo values

**Decision**: `UserRead.roles: list[str]` is computed via a Pydantic `@computed_field` that accesses `self.usuario_roles` (the lazy-loaded relationship) and extracts `ur.rol.codigo` for each `UsuarioRol`. SQLModel is configured with `lazy="selectin"` on both `Usuario.usuario_roles` and `UsuarioRol.rol` (established in Change 03), so no N+1 query results from a single `select` on `Usuario`.

**Alternative considered**: returning role objects `{ codigo, nombre }`. Rejected — the frontend `hasRole(role: string)` selector and the spec both expect flat string arrays.

### D-C: bcrypt cost in Settings

**Decision**: `Settings.BCRYPT_COST: int = 12` is added to `backend/app/core/config.py`. Tests can override via `BCRYPT_COST=4` in their `.env.test` or fixture monkeypatch, keeping test suites fast. Production must not override below 12.

**Alternative considered**: hardcoded constant in `security.py`. Rejected — not env-overridable, making test suites slow.

### D-D: Refresh token storage

**Decision**: `create_refresh_token(subject, expires_in)` returns `(cleartext_jwt: str, digest: str)` where `digest = sha256(cleartext_jwt.encode()).hexdigest()`. The router stores only `digest` in `RefreshToken.token_hash` (CHAR(64)). The cleartext JWT is returned to the client exactly once in the `TokenResponse`. The JWT payload contains `sub` (user UUID string), `iat`, `exp`, and `type: "refresh"` claims.

**Alternative considered**: opaque random token (UUID) instead of JWT for refresh. Rejected — JWT refresh tokens enable stateless partial validation (exp check) before hitting the DB, matching the established project pattern.

### D-E: 401 generic wording (enumeration prevention)

**Decision**: Both "wrong email" and "wrong password" return exactly: `{ "detail": "Invalid credentials", "code": "invalid_credentials" }` with HTTP 401. The frontend `errors.ts` normalizes 401 to `code: 'AUTH_EXPIRED'`. This is acceptable because on the register/login page the feature-level handler should display the `message` field, not rely on the `code` to distinguish user-not-found vs wrong password.

**Note**: The existing `errors.ts` maps 401 to `AUTH_EXPIRED`. Future work (if needed) can add `INVALID_CREDENTIALS` code for the login page context. For now the 401 message field carries the human-readable string.

### D-F: Rate limit key function

**Decision**: slowapi default key function uses `X-Forwarded-For` if present, else `request.client.host`. No custom key function needed — the existing `app/core/rate_limit.py` limiter instance already configures this. The `@limiter.limit("5/15minutes")` decorator is applied directly on the login endpoint function.

### D-G: Lifting D-07 (decode-only restriction)

**Decision**: D-07 from Change 04 is formally superseded by this change. `backend/app/core/security.py` now contains both decode and issuance functions. The `backend-auth-dependencies` spec's requirement `core/security.py — JWT decode helper` is MODIFIED to remove the prohibition clause. The requirement text in the delta spec replaces the sentence "This module SHALL NOT contain token issuance functions" with documentation of the new issuance functions.

**Reference**: Change 04 archive at `openspec/changes/archive/` (exact date TBD) contains the original D-07 record.

### D-H: FastAPI 422 fieldErrors mapping rule

**Decision**: When `loc` is `["body", "<field>"]`, use `loc[1]` as the key. When `loc` has deeper nesting (`["body", "address", "calle"]`), join from index 1 onward with `.` → `"address.calle"`. When `loc` starts with a non-body prefix (`"query"`, `"path"`), prefix with that segment → `"query.<field>"`. The `msg` string of each entry is used as the error message. Multiple entries for the same field are accumulated into `fieldErrors[field]: string[]`.

This maps FastAPI's array-of-detail-objects to the existing `AppError.fieldErrors: Record<string, string[]>` shape without breaking any existing 401/403/429/500 paths.

## Risks / Trade-offs

- **`User.id: number → string` is a BREAKING frontend type change** → All existing consumers of `User.id` must be audited. Since this is Sprint 1 and there are no downstream features using `User.id` in comparisons yet, the blast radius is minimal. Risk: LOW.
- **bcrypt cost=12 makes test suite slow** → Mitigated by `BCRYPT_COST` in `Settings` — test fixtures set cost=4. Risk: LOW.
- **Rate limit state lost on process restart (in-memory by default)** → slowapi with in-memory backend is acceptable for Sprint 1. Future change should move to Redis backend for multi-process deployments. Risk: MEDIUM (note in open questions).
- **`selectin` loading on `usuario_roles` + `rol` means two extra SELECTs per login** → Acceptable for Sprint 1 user volumes. No N+1 (it's 1+2 total). Risk: LOW.
- **Refresh token not revoked on `POST /auth/register`** → No refresh token is issued on register; only on login. No cross-change risk.
- **D-E decision: 401 mapped to `AUTH_EXPIRED` in errors.ts** → Login/register feature handlers should display `error.message` directly rather than switching on `error.code`. Document this constraint in the auth feature design when it arrives.
- **TokenResponse without `user` field vs `authStore.login(accessToken, refreshToken, user)` signature** — `POST /api/v1/auth/login` returns only `{ access_token, refresh_token, token_type, expires_in }`, but the Zustand `authStore.login()` action defined in Change 05 takes a `user: User` argument. The frontend must obtain the `User` via `GET /api/v1/auth/me` (called by `AuthSync` when `status === 'authenticating'`). Since `/auth/me` is a Non-Goal of this change, the login feature implementation in Sprint 1 will require either (a) a temporary mock of `/auth/me` for AuthLayout tests, or (b) a follow-up change adding `/auth/me`, or (c) a future decision to enrich `TokenResponse` with the `user` payload. **Severity: MEDIUM — does not block apply but blocks end-to-end login UX.**
- **`login_user(request: Request)` framework coupling** — `tasks.md §6.1` passes a FastAPI `Request` object into `AuthService.login_user()` for slowapi rate-limit identity. This couples the service layer to FastAPI, breaking the framework-agnostic principle of the service layer. The slowapi `@limiter.limit("5/15minutes")` decorator on the endpoint already rejects requests before the service is called, so passing `Request` is technically redundant for rate-limit enforcement. **Decision deferred**: keep the parameter for now to expose a hook for future per-user rate limiting (where the service may need to inspect headers); revisit in a follow-up change. **Severity: LOW — known debt, no functional impact.**

## Migration Plan

No database migration required — `RefreshToken`, `UsuarioRol`, `Rol` tables exist. No data migrations required — `CLIENT` role is already seeded (Change 03, task 8.4). Deployment is additive: new endpoints, new file modules. No rollback complexity.

## Open Questions

1. **Redis rate-limit backend**: Should we configure slowapi with a Redis backend now (multi-process safe) or defer to a future change? Recommended: defer — Sprint 1 is single-process.
2. **`GET /auth/me` implementation timing**: `AuthSync` in the frontend calls this endpoint. Is it implemented in this change or the next? Current decision: deferred. If tests for `AuthLayout` `authenticating` state require a working `/auth/me`, use a mock.
3. **Refresh token rotation policy**: On `POST /auth/refresh` (future change), should old refresh tokens be revoked (rotation) or allowed multi-use until expiry? TBD in that change's design.
4. **JWT `jti` (token ID) claim is intentionally omitted** — Both access and refresh tokens carry only `{sub, iat, exp, type}` claims. Without `jti`, individual tokens cannot be revoked before their natural expiration (access: 30 min; refresh: 7 days), and replay within the TTL window cannot be detected without a full blacklist. This is acceptable for Sprint 1 MVP scope, but a future change introducing logout / token revocation / "log out from all devices" MUST add `jti` to the token payload and a revocation registry. **Open question for follow-up change**: should `jti` be added eagerly (Change N+1) or deferred until a logout feature is requested? **Severity: LOW for Sprint 1.**
