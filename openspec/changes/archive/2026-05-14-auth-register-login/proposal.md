## Why

The Food Store platform currently has JWT decode infrastructure and role-based dependency guards but no endpoints to register or log in users. Sprint 1 (US-001, US-002, US-073) requires a complete identity round-trip — registration, login, and token issuance — so that all subsequent protected features can be developed and tested end-to-end. Additionally, four contract fixes in the frontend auth layer (User.id type, missing apellido field, FastAPI 422 parsing, and AuthLayout spinner coverage) are bundled here to keep the propose→audit→apply cycle atomic and avoid a separate micro-change.

## What Changes

- **NEW** `POST /api/v1/auth/register` — creates a `Usuario` + auto-assigns role `CLIENT`, returns `UserRead` (201) or 409 on duplicate email
- **NEW** `POST /api/v1/auth/login` — validates credentials, issues access + refresh JWT pair, rate-limited at 5 req / 15 min per IP; never reveals email enumeration (401 generic)
- **EXTENDED** `backend/app/core/security.py` — lifts the D-07 decode-only restriction; adds `hash_password`, `verify_password`, `create_access_token`, `create_refresh_token`
- **NEW** `backend/app/schemas/auth.py` — Pydantic v2 schemas: `RegisterRequest`, `LoginRequest`, `UserRead`, `TokenResponse`
- **NEW** `backend/app/services/auth.py` — `AuthService` with `register_user` and `login_user` methods, all mutations through UoW
- **EXTENDED** `backend/app/repositories/user.py` — existing `RefreshTokenRepository` gains `insert` and `revoke_by_hash` methods (Option A: extend in-place, no new file)
- **MODIFIED** `backend/app/api/v1/router.py` — wires `auth_router` into `build_v1_router` factory; auth prefix `/auth`
- **MODIFIED** `frontend/src/entities/auth/types.ts` — `User.id` changed from `number` to `string` (UUID); `apellido: string` field added
- **MODIFIED** `frontend/src/shared/lib/errors.ts` — 422 fieldErrors parsing upgraded from flat-string to FastAPI `detail: [{loc, msg, type}]` array shape
- **MODIFIED** `frontend/src/app/layouts/AuthLayout.tsx` — spinner guard extended to cover `status === 'authenticating'` in addition to `'idle'`
- **NEW** `backend/app/api/v1/auth.py` — FastAPI auth router with the two endpoints and slowapi rate limit decorator
- **NEW** `backend/app/core/config.py` addition — `BCRYPT_COST: int = 12` setting

## Capabilities

### New Capabilities

- `backend-auth-register-login`: The two REST endpoints, body schemas, 409/401/422 error contracts, role auto-assignment, rate limiting, 401 enumeration policy
- `backend-auth-token-issuance`: Security primitives superseding D-07 — `hash_password`, `verify_password`, `create_access_token`, `create_refresh_token`; refresh token SHA-256 persistence contract

### Modified Capabilities

- `backend-api-v1-router`: `build_v1_router` factory now includes `auth_router` at prefix `/auth`
- `backend-auth-dependencies`: Supersedes the D-07 restriction in `core/security.py`; `core/security.py` requirement is now MODIFIED to include issuance functions
- `frontend-auth-store`: `User` type gains `apellido: string` and changes `id: number → string`
- `frontend-error-handling`: `normalizeError` 422 path upgraded to parse FastAPI `detail` array; `fieldErrors` keyed by field name (last non-`body` segment of `loc`)
- `frontend-routing`: `AuthLayout` spinner guard extended to cover `status === 'authenticating'`

## Impact

- **Backend**: `bcrypt` / `passlib[bcrypt]` must be in `requirements.txt` (already listed per project conventions); `slowapi` already wired in `app/core/rate_limit.py`. No new Alembic migration needed (models `RefreshToken` and `UsuarioRol` already exist from Change 03).
- **Frontend**: TypeScript strict mode — changing `id: number → string` is a **BREAKING** type change. Any consumer that compares `user.id` to a numeric literal will error at compile time. Audit all usages before merging.
- **Tests**: TDD strict mode; all tests for failing paths (register 409, login 401, rate limit 429) must be written before implementation.
- **Security**: Refresh token cleartext never persisted; only SHA-256 hex digest stored. bcrypt cost ≥ 12 enforced via `Settings.BCRYPT_COST`.
