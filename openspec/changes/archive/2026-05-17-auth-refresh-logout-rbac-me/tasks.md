## 1. Backend — Model and Migration

- [x] 1.1 Add `family_id: uuid.UUID` field to `RefreshToken` in `backend/app/models/user.py` (nullable=False, indexed)
- [x] 1.2 Create Alembic migration adding `family_id UUID NOT NULL DEFAULT gen_random_uuid()` to `refresh_token` table
- [x] 1.3 Verify migration runs cleanly with `alembic upgrade head` and `alembic downgrade -1`
- [x] 1.4 Confirm `RefreshToken` model round-trips correctly in a unit test (instantiate with `family_id`, verify field exists)

## 2. Backend — Schemas

- [x] 2.1 Add `RefreshRequest(BaseModel)` with `refresh_token: str` to `backend/app/schemas/auth.py`
- [x] 2.2 Add `LogoutRequest(BaseModel)` with `refresh_token: str` to `backend/app/schemas/auth.py`
- [x] 2.3 Add `created_at: datetime` field to `UserRead` in `backend/app/schemas/auth.py` (required by Integrador §6.1 — `UserResponse` includes `created_at`). Add `from datetime import datetime` import if missing. The field is populated from the `Usuario` ORM object via `from_attributes=True` (the `Base` model includes `created_at`).
- [x] 2.4 Update `backend/app/schemas/__init__.py` exports if needed to expose `RefreshRequest` and `LogoutRequest`

## 3. Backend — Repository

- [x] 3.1 Add `find_by_hash(token_hash: str) -> RefreshToken | None` to `RefreshTokenRepository` (no active filter)
- [x] 3.2 Add `find_active_by_hash(token_hash: str) -> RefreshToken | None` to `RefreshTokenRepository` (filters `revoked_at IS NULL AND expires_at > now`)
- [x] 3.3 Add `create_with_family(token: RefreshToken) -> RefreshToken` to `RefreshTokenRepository` (delegates to `create()`)
- [x] 3.4 Add `revoke_family(family_id: uuid.UUID) -> int` to `RefreshTokenRepository` (bulk UPDATE + return count)
- [x] 3.5 Update `insert()` docstring in `RefreshTokenRepository` to note callers must supply `family_id`

## 4. Backend — Services and Domain Exceptions

- [x] 4.0 Define `TokenReplayError(family_id: uuid.UUID, user_id: uuid.UUID)` in `backend/app/core/exceptions.py` as a plain Python exception. **Inheritance constraints (CRITICAL for B-1 fix correctness)**: MUST inherit directly from `Exception` — NOT a subclass of `HTTPException`, NOT a subclass of `AppError`, NOT a subclass of any custom error base class registered in a FastAPI `exception_handler`. **Do NOT register a global `@app.exception_handler(TokenReplayError)`** — the router's explicit `except TokenReplayError` block must be the sole catch point. If any handler intercepts this exception before the router's catch, the second-UoW `revoke_family` call never executes and the B-1 fix silently fails (family remains active, replay attack continues to succeed). This exception is raised by `AuthService.rotate_refresh` when replay is detected, and caught by the router to perform the second-UoW revocation before re-raising as `UnauthorizedError`.
- [x] 4.1 Update `AuthService.login_user` to generate `family_id = uuid.uuid4()` and include it when constructing the `RefreshToken` for persistence
- [x] 4.2 Add `AuthService.rotate_refresh(uow, refresh_token_cleartext, ip, user_agent) -> TokenResponse` static method implementing: hash lookup → active check → replay detection (raises `TokenReplayError`) → revoke old → emit new (same family_id) → persist → return TokenResponse
- [x] 4.3 Implement replay detection branch in `rotate_refresh`: if `find_active_by_hash` returns None, call `find_by_hash` — if found with `revoked_at` set, raise `TokenReplayError(family_id=token.family_id, user_id=token.usuario_id)`. DO NOT call `revoke_family` inside the service — the UoW would roll it back on exception. The router handles revocation.
- [x] 4.4 Implement expired-but-not-revoked branch in `rotate_refresh`: if `find_by_hash` finds a token with `revoked_at IS NULL` but `expires_at` in the past, raise `UnauthorizedError(code="token_expired")` without revoking family
- [x] 4.5 Add `AuthService.revoke_refresh(uow, refresh_token_cleartext) -> None` static method: hash → `revoke_by_hash` (ignore False return — idempotent)

## 5. Backend — Router

- [x] 5.1 Implement `_get_client_ip(request: Request) -> str` helper in `backend/app/api/v1/auth.py` (or `backend/app/api/utils.py` for reuse). Helper reads `X-Forwarded-For` header first, falls back to `request.client.host` with null guard (`request.client.host if request.client else "unknown"`). Used for audit logging and rate limiting context — NOT for authorization. See spec §Requirement: _get_client_ip helper.
- [x] 5.2 Add `POST /auth/refresh` endpoint to `backend/app/api/v1/auth.py`: body `RefreshRequest`, response `TokenResponse` 200, rate limit `30/15minutes`, delegates to `AuthService.rotate_refresh(uow, data.refresh_token, _get_client_ip(request), ...)`. Catch `TokenReplayError`: open second `async with UnitOfWork() as uow2: await uow2.refresh_tokens.revoke_family(e.family_id)` → log WARNING → raise `UnauthorizedError(code="token_replay_detected")`.
- [x] 5.3 Add `POST /auth/logout` endpoint to `backend/app/api/v1/auth.py`: body `LogoutRequest`, response `None` 204, no rate limit, no auth required, delegates to `AuthService.revoke_refresh`, returns `Response(status_code=204)`
- [x] 5.4 Add `GET /auth/me` endpoint to `backend/app/api/v1/auth.py`: `Depends(get_current_user)`, response `UserRead` 200, returns `UserRead.model_validate(current_user)`
- [x] 5.5 Confirm all five auth endpoints are reachable under `/api/v1/auth/*` (inspect OpenAPI output)
- [x] 5.6 Add Swagger OpenAPI examples (`openapi_extra` or `responses` descriptions) to all three new endpoints for `/docs` quality

## 6. Backend — Tests

- [x] 6.1 Create `backend/tests/test_auth_refresh.py`: happy path rotation (old revoked, new token returned), expired token returns 401, unknown token returns 401
- [x] 6.2 Add replay attack test to `test_auth_refresh.py`: present an already-rotated token → expect 401 `token_replay_detected` + verify entire family revoked in DB. The test MUST verify that the revocation is persisted (not rolled back) even though a 401 is returned — this validates the B-1 fix (second-UoW router pattern).
- [x] 6.3 Add rate limit test to `test_auth_refresh.py`: simulate > 30 requests in 15 min → expect 429
- [x] 6.4 Create `backend/tests/test_auth_logout.py`: valid token revoked on logout (204), unknown token → 204, already-revoked token → 204, no Bearer needed → 204
- [x] 6.5 Create `backend/tests/test_auth_me.py`: valid CLIENT token → 200 with UserRead (response includes `created_at` field), missing token → 401, expired token → 401, response never exposes `password_hash`, response includes `created_at` as ISO 8601 string
- [x] 6.6 Create `backend/tests/test_rbac.py`: CLIENT token on `/auth/me` → 200, CLIENT token on ADMIN-protected test endpoint → 403, no token → 401, ADMIN token → 200
- [x] 6.7 Add integration test verifying `login` now seeds `family_id` in the `RefreshToken` row
- [x] 6.8 Run coverage check — assert ≥ 90% coverage on new modules (`services/auth.py` new methods, `repositories/user.py` new methods, `api/v1/auth.py` new endpoints)

## 7. Frontend — authStore

- [x] 7.1 Confirm `authStore` already exports `setUser`, `login`, `updateTokens`, `logout`, `triggerRehydrationFetch` as per Change 05 spec (verified: all present in `frontend/src/entities/auth/model/store.ts`)
- [x] 7.2 Confirm `logout()` is synchronous (`(): void`) — NO changes needed to the signature. Add a JSDoc comment to the implementation clarifying: "Callers in `app/` or `features/` are responsible for calling `POST /auth/logout` BEFORE invoking this action. This store action is synchronous and does not make network calls."
- [x] 7.3 Verify `partialize` persists only `accessToken` and `refreshToken` (not `user`, not `status`) — verified in `store.ts`. No changes needed.
- [x] 7.4 Verify `onRehydrateStorage` sets `status: 'authenticating'` when `accessToken` is non-null after rehydration — verified in `store.ts`. No changes needed.

## 8. Frontend — AuthSync Component

- [x] 8.1 Locate `AuthSync` stub in `src/app/` (created by Change 05)
- [x] 8.2 Implement `useEffect` (or equivalent) that watches `authStore.status === 'authenticating'`
- [x] 8.3 On `'authenticating'`: call `http.get(endpoints.AUTH_ME)` and await response
- [x] 8.4 On success: call `authStore.getState().setUser(response.data)` — this atomically sets the user AND transitions `status` to `'authenticated'` (verified: `setUser` calls `set({ user, status: 'authenticated' })`). Do NOT also call `login()` — the tokens are already in the store from rehydration via `onRehydrateStorage`. Calling `login()` would be redundant and would read stale token values from `getState()` at the time of the call.
- [x] 8.5 On failure (any error): call `authStore.getState().logout()` to clear state
- [x] 8.6 Ensure `AuthSync` renders no visible UI (returns `null`) — side-effects only
- [x] 8.7 Confirm `AuthSync` is mounted in the app providers tree (check `src/app/providers/` or equivalent entry point)

## 9. Frontend — HTTP Client, Endpoints, and Cross-Tab Sync

- [x] 9.1 Add `AUTH_LOGOUT = '/auth/logout'` to `src/shared/api/endpoints.ts` (currently missing — verified)
- [x] 9.2 Confirm `AUTH_ME = '/auth/me'` exists in `endpoints.ts` (already present — verified)
- [x] 9.3 Inspect Axios interceptor in `src/shared/api/http.ts` — verify it reads `response.data.access_token` and `response.data.refresh_token` from the `/auth/refresh` response (matching `TokenResponse` contract). Verified: interceptor already uses correct field names.
- [x] 9.4 Import `AUTH_LOGOUT` from `endpoints.ts` in `src/shared/api/http.ts` and add it to the interceptor skip list: `url.includes(AUTH_REFRESH) || url.includes(AUTH_LOGIN) || url.includes(AUTH_LOGOUT)`.
- [x] 9.5 Add JSDoc comment to the interceptor's catch block documenting the deliberate decision: "On refresh failure, `logout()` is called without posting to `/auth/logout`. The refresh token may remain valid in DB until TTL expiry. This is acceptable: expired access token cannot be used; network-error scenario does not invalidate the refresh token on the backend."
- [x] 9.6 Create `src/shared/api/cross-tab-sync.ts` implementing `initCrossTabSync(): () => void`. The function installs a `window.addEventListener('storage', ...)` listener filtered by `e.key === 'food-store-auth'`. On `e.newValue` non-null: parse JSON, extract `accessToken`/`refreshToken`, call `useAuthStore.getState().updateTokens(...)` only if no refresh is in progress. On `e.newValue === null`: call `useAuthStore.getState().logout()`. Returns a cleanup function `() => window.removeEventListener(...)`.
- [x] 9.7 Call `initCrossTabSync()` from `src/app/` (e.g., inside `AuthSync` `useEffect` with `[]` deps or in the app providers entry point). Store the cleanup function and call it on component unmount.
- [x] 9.8 Export `isRefreshing(): boolean` (or expose `refreshPromise !== null` check) from `src/shared/api/http.ts` so `cross-tab-sync.ts` can check whether a refresh is in progress before calling `updateTokens`.

## 10. Frontend — Tests

- [x] 10.1 Add test for `authStore.triggerRehydrationFetch()` — verify `status` becomes `'authenticating'`
- [x] 10.2 Add test for `authStore.logout()` — verify state cleared synchronously (void return, not Promise)
- [x] 10.3 Write `AuthSync` unit test (with mocked `http` and `authStore`): when `status === 'authenticating'`, verify `GET /auth/me` is called
- [x] 10.4 Write `AuthSync` unit test: on successful `/auth/me` response, `authStore.setUser` is called (NOT `login`) and status becomes `'authenticated'`
- [x] 10.5 Write `AuthSync` unit test: on `/auth/me` failure, `authStore.logout()` is called
- [x] 10.6 Write interceptor contract test: mock `POST /auth/refresh` to return `TokenResponse` shape, verify interceptor correctly calls `authStore.updateTokens(access_token, refresh_token)`
- [x] 10.7 Write `cross-tab-sync.ts` unit test: mock `window.addEventListener('storage', ...)` and `useAuthStore.getState().updateTokens` — fire a storage event with new tokens → verify `updateTokens` is called with the parsed values
- [x] 10.8 Write `cross-tab-sync.ts` unit test: fire storage event with `e.newValue === null` → verify `useAuthStore.getState().logout()` is called
- [x] 10.9 Write `cross-tab-sync.ts` unit test: when `isRefreshing()` returns true, fire storage event → verify `updateTokens` is NOT called (listener skips update during active refresh)

## 11. Documentation and Cleanup

- [x] 11.1 Update Swagger tags in all three new endpoints to `["auth"]` — confirm consistent grouping in `/docs`
- [x] 11.2 Add OpenAPI `summary` and `description` strings to `/refresh`, `/logout`, `/me` endpoints
- [x] 11.3 Verify `backend/.env.example` does not require new variables for this change (no new secrets)
- [x] 11.4 Verify migration file is named with the correct Alembic revision format and references `auth-refresh-logout-rbac-me` in its docstring
