# frontend-http-client Specification

## Purpose
Define the Axios HTTP client singleton for the Food Store frontend: a single `axios.create` instance with a request interceptor that attaches Bearer tokens from `authStore`, and a response interceptor that implements a 401-refresh-queue pattern — one refresh call at a time, all concurrent 401s awaiting the same promise, with strict token-store update ordering on success and logout + `auth:expired` event dispatch on failure. Also defines the `endpoints.ts` URL constants and a strict unidirectional dependency rule (http reads from store, store never imports http).

## Requirements

### Requirement: Single Axios instance with configurable base URL
`src/shared/api/http.ts` SHALL export a single Axios instance created with `axios.create({ baseURL: env.VITE_API_BASE_URL })` where `env` is imported from `@/shared/lib/env`. No other file in `src/` SHALL create an additional Axios instance.

#### Scenario: Axios instance uses VITE_API_BASE_URL
- **WHEN** the http module is imported
- **THEN** the instance's baseURL matches the value of `VITE_API_BASE_URL` from the environment

#### Scenario: Only one Axios instance exists in the codebase
- **WHEN** the source tree is searched for `axios.create`
- **THEN** exactly one call exists, in `src/shared/api/http.ts`

---

### Requirement: Request interceptor attaches Bearer token
The Axios instance SHALL have a request interceptor that reads `accessToken` from `authStore.getState().accessToken` (NOT via a React hook). If the token is non-null, it SHALL set `Authorization: Bearer <token>` on the request config. If the token is null, the header SHALL NOT be set (public requests proceed without auth).

#### Scenario: Request includes Authorization header when token present
- **WHEN** an HTTP request is made via the Axios instance and `authStore` has a non-null `accessToken`
- **THEN** the outgoing request contains `Authorization: Bearer <token>`

#### Scenario: Request proceeds without Authorization header when no token
- **WHEN** an HTTP request is made via the Axios instance and `authStore.accessToken` is null
- **THEN** the outgoing request does not contain an `Authorization` header

---

### Requirement: Response interceptor handles 401 with token refresh and concurrent request queue
The Axios instance SHALL have a response interceptor that:
1. Detects 401 responses.
2. Skips the refresh flow for requests to `/auth/refresh`, `/auth/login`, and `/auth/logout` (preventing infinite loops). The skip list SHALL include `AUTH_LOGOUT` as defensive programming — even though `/auth/logout` does not currently require authentication, including it prevents undesirable loops if the endpoint ever gains auth requirements.
3. Skips the refresh flow for requests already marked with `__isRetry: true` in config.
4. On first 401: sets `refreshPromise` (module-scope singleton) to a call to `POST /auth/refresh` with `refreshToken` from `authStore.getState()`. Updates `authStore` tokens on success.
5. While `refreshPromise` is in flight: any additional 401 requests SHALL await the same `refreshPromise` (no second refresh call is made).
6. On refresh success: retries all queued requests with the new access token. Sets `refreshPromise` to null. **See ordering rule below.**
7. On refresh failure: rejects all queued requests, calls `authStore.getState().logout()`, dispatches `new CustomEvent('auth:expired')` on `window`. Sets `refreshPromise` to null last. **See ordering rule below.**

> **Ordering rule (success path)**:
> 1. Call `authStore.updateTokens(newAccessToken, newRefreshToken)` (or `authStore.setTokens()`).
> 2. Resolve the `refreshPromise` with the new `accessToken`.
> 3. Each queued request receives the new token and is dispatched.
> 4. Only AFTER all queued dispatches are initiated, set `refreshPromise = null`.
>
> `refreshPromise` SHALL remain non-null until all queued request dispatches are initiated, ensuring no new 401 can start a second refresh cycle before the queue drains.

> **Ordering rule (failure path)**:
> 1. Call `authStore.logout()`.
> 2. Reject all queued requests with the refresh error.
> 3. Dispatch `CustomEvent('auth:expired')` for router to handle.
> 4. Set `refreshPromise = null` last.
> (This ordering is intentional.)

#### Scenario: Concurrent 401s result in a single refresh call
- **WHEN** three concurrent requests all receive a 401 response simultaneously
- **THEN** exactly one `POST /auth/refresh` call is made
- **THEN** all three original requests are retried after the refresh succeeds

#### Scenario: refreshPromise nulled only after all queued retries dispatched
- **WHEN** refresh succeeds and 3 requests were queued with 401
- **THEN** all 3 are retried with the new token before `refreshPromise` is set to null

#### Scenario: Refresh failure triggers logout and event
- **WHEN** the 401 interceptor fires and `POST /auth/refresh` returns a 401 or network error
- **THEN** `authStore.logout()` is called
- **THEN** a `CustomEvent('auth:expired')` is dispatched on `window`
- **THEN** the original request's promise rejects

#### Scenario: Interceptor skips refresh for requests to /auth/logout
- **WHEN** a request to `POST /auth/logout` receives a 401 (possible edge case if the endpoint is later secured, or during an unexpected auth error)
- **THEN** the interceptor SHALL skip the refresh flow for `/auth/logout` by including `AUTH_LOGOUT` in the skip list check
- **THEN** the interceptor skip list SHALL include: `/auth/refresh`, `/auth/login`, and `/auth/logout`
- **THEN** the interceptor SHALL also skip the refresh flow for any request already marked `__isRetry: true` (UNCHANGED from Change 05)

#### Scenario: Interceptor correctly maps access_token from refresh response
- **WHEN** `POST /auth/refresh` returns `{ access_token: "new.jwt.here", refresh_token: "new.refresh.here", token_type: "bearer", expires_in: 1800 }`
- **THEN** `authStore.updateTokens("new.jwt.here", "new.refresh.here")` is called
- **THEN** the original failing request is retried with `Authorization: Bearer new.jwt.here`

#### Scenario: Interceptor calls logout on refresh failure without calling POST /auth/logout
- **WHEN** `POST /auth/refresh` returns a non-2xx response (e.g., 401 with revoked token)
- **THEN** the interceptor calls `useAuthStore.getState().logout()` to clear local state
- **THEN** the interceptor does NOT call `POST /auth/logout` (no nested HTTP call in the error handler)
- **THEN** `window.dispatchEvent(new CustomEvent('auth:expired'))` is fired
- **NOTE**: This is a deliberate design decision. The refresh token may remain valid in the DB until its 7-day TTL if the failure was a network error. If the failure was a 401 (token already invalid/expired), the DB entry is already invalid. Either way, the access token (which was the cause of the original 401) is expired and cannot be used.

#### Scenario: failedQueue is cleared on both success and error paths
- **WHEN** a refresh succeeds: `processQueue(null, access_token)` is called → `failedQueue.length = 0`
- **WHEN** a refresh fails: `processQueue(refreshError, null)` is called → `failedQueue.length = 0`
- **THEN** in both cases the queue is empty after processing (no memory leak, no stale entries)

#### Scenario: __isRetry flag prevents retry loops
- **WHEN** a retried request (with `__isRetry: true`) receives a 401
- **THEN** the interceptor skips the refresh flow (returns `Promise.reject(error)`)
- **THEN** no additional refresh call is made
- **NOTE**: Maximum 1 retry per original request. No exponential backoff. This is sufficient for auth token rotation.

#### Scenario: Retry request is not intercepted again
- **WHEN** a request with `__isRetry: true` receives a 401
- **THEN** the interceptor does NOT call refresh again and the request's promise rejects normally

---

### Requirement: Store-HTTP unidirectional dependency
`src/shared/api/http.ts` SHALL read from stores via `getState()` only. Stores SHALL NOT import `http.ts` as a direct dependency. This keeps the dependency arrow: `http.ts → store (read-only via getState)`.

#### Scenario: http.ts does not import any store module for writes
- **WHEN** `http.ts` is inspected
- **THEN** it does not import `authStore` for the purpose of calling store actions from within the module definition (only `getState()` calls are permitted, inside interceptor callbacks)

#### Scenario: authStore does not import http.ts
- **WHEN** `src/entities/auth/model/store.ts` is inspected
- **THEN** it does not contain an import of `http.ts` or any module from `src/shared/api/`

---

### Requirement: URL constants defined in endpoints.ts
`src/shared/api/endpoints.ts` SHALL export URL path constants for all auth endpoints referenced by the interceptors and by future feature changes. Constants SHALL be path-only (no base URL). Required constants (complete list):
- `AUTH_LOGIN = '/auth/login'` — UNCHANGED
- `AUTH_REFRESH = '/auth/refresh'` — UNCHANGED
- `AUTH_ME = '/auth/me'` — ADDED (if not already present from Change 05)
- `AUTH_REGISTER = '/auth/register'` — UNCHANGED
- `AUTH_LOGOUT = '/auth/logout'` — ADDED

#### Scenario: Endpoint constants cover all auth paths including logout
- **WHEN** `endpoints.ts` is imported
- **THEN** it exports `AUTH_LOGIN = '/auth/login'`
- **THEN** it exports `AUTH_REFRESH = '/auth/refresh'`
- **THEN** it exports `AUTH_ME = '/auth/me'`
- **THEN** it exports `AUTH_REGISTER = '/auth/register'`
- **THEN** it exports `AUTH_LOGOUT = '/auth/logout'`

---

### Requirement: Cross-tab token synchronization via storage event
`src/shared/api/cross-tab-sync.ts` (NEW file) SHALL implement a `storage` event listener that keeps the in-memory Zustand store synchronized across browser tabs when tokens are rotated in another tab.

**Contract**:
- Listen to `window.addEventListener('storage', handler)`.
- Filter by `e.key === 'food-store-auth'` (the Zustand `persist` storage key).
- If `e.newValue` is non-null: parse JSON → extract `accessToken: string | null` and `refreshToken: string | null` → call `useAuthStore.getState().updateTokens(accessToken, refreshToken)` IF AND ONLY IF `refreshPromise` is NOT currently in progress (to avoid interfering with an active refresh in this tab).
- If `e.newValue === null` (storage cleared): call `useAuthStore.getState().logout()`.
- The listener MUST NOT trigger a new write to localStorage (would cause infinite loop on browsers that fire storage event to all tabs including the writer, though most do not).

**Installation**: The listener is installed once when the module is first imported. The module SHALL export an `initCrossTabSync(): () => void` function that:
1. Installs the event listener.
2. Returns a cleanup function (`() => window.removeEventListener('storage', handler)`) for React strict mode / testing.

**Usage**: Called from `src/app/` (e.g., inside `AuthSync` `useEffect` with `[]` deps, or in the app providers setup).

**FSD compliance**: `cross-tab-sync.ts` lives in `src/shared/api/` — it may import `useAuthStore` via `getState()` (not as a React hook) and does NOT import anything from `app/` or `features/` layers.

#### Scenario: Token rotation in Tab A updates Tab B's in-memory store
- **WHEN** Tab A successfully rotates tokens (interceptor calls `updateTokens`)
- **WHEN** Zustand `persist` writes new tokens to `localStorage['food-store-auth']`
- **THEN** browser fires a `storage` event on Tab B (and all other tabs except Tab A)
- **THEN** Tab B's cross-tab listener extracts the new tokens from `e.newValue`
- **THEN** Tab B calls `useAuthStore.getState().updateTokens(newAccessToken, newRefreshToken)`
- **THEN** Tab B's subsequent requests use the new access token

#### Scenario: Logout in Tab A clears Tab B's state
- **WHEN** Tab A's `logout()` is called → `localStorage['food-store-auth']` is removed or cleared
- **THEN** browser fires `storage` event on Tab B with `e.newValue === null`
- **THEN** Tab B calls `useAuthStore.getState().logout()`
- **THEN** Tab B's status becomes `'unauthenticated'`

#### Scenario: Listener does not interfere with active refresh in same tab
- **WHEN** a storage event fires while `refreshPromise !== null` in the current tab
- **THEN** the listener skips the `updateTokens` call (the in-progress refresh will update tokens when it resolves)
- **THEN** no double-update or race condition occurs
