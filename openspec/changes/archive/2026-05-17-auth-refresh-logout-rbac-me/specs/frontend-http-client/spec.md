## MODIFIED Requirements

### Requirement: URL constants defined in endpoints.ts
`src/shared/api/endpoints.ts` SHALL export URL path constants for all auth endpoints. This change extends the set defined in Change 05 with `AUTH_LOGOUT`. Constants SHALL be path-only (no base URL).

Required constants (complete list after this change):
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

### Requirement: Response interceptor refresh contract validated against TokenResponse
The Axios response interceptor (defined in Change 05) calls `POST /auth/refresh` and expects the response to contain `access_token` and `refresh_token` fields. This SHALL match the backend `TokenResponse` schema exactly:

```
{ access_token: string, refresh_token: string, token_type: 'bearer', expires_in: 1800 }
```

The interceptor SHALL extract `access_token` and `refresh_token` from the response data and call `authStore.updateTokens(newAccessToken, newRefreshToken)`. If the interceptor currently accesses a different field name (e.g., `data.token` instead of `data.access_token`), it SHALL be corrected to match the backend contract.

#### Scenario: Interceptor correctly maps access_token from refresh response
- **WHEN** `POST /auth/refresh` returns `{ access_token: "new.jwt.here", refresh_token: "new.refresh.here", token_type: "bearer", expires_in: 1800 }`
- **THEN** `authStore.updateTokens("new.jwt.here", "new.refresh.here")` is called
- **THEN** the original failing request is retried with `Authorization: Bearer new.jwt.here`

#### Scenario: Interceptor skips refresh for requests to /auth/logout
- **WHEN** a request to `POST /auth/logout` receives a 401 (possible edge case if the endpoint is later secured, or during an unexpected auth error)
- **THEN** the interceptor SHALL skip the refresh flow for `/auth/logout` by including `AUTH_LOGOUT` in the skip list check
- **THEN** the interceptor skip list SHALL include: `/auth/refresh`, `/auth/login`, and `/auth/logout`
- **THEN** the interceptor SHALL also skip the refresh flow for any request already marked `__isRetry: true` (UNCHANGED from Change 05)

**Rationale for adding AUTH_LOGOUT to skip list**: Even though `/auth/logout` does not currently require authentication (no `Depends(get_current_user)`), including it in the skip list is defensive programming. If the endpoint ever gains an optional auth header or a future change adds auth requirements, a 401 on logout should not trigger a refresh attempt — that would create an undesirable loop where a failed logout causes a refresh, which may fail, causing another logout attempt.

#### Scenario: Concurrent 401s result in a single refresh call (contract unchanged)
- **WHEN** three concurrent requests all receive a 401 response simultaneously
- **THEN** exactly one `POST /auth/refresh` call is made
- **THEN** all three original requests are retried after the refresh succeeds

#### Scenario: failedQueue is cleared on both success and error paths
- **WHEN** a refresh succeeds: `processQueue(null, access_token)` is called → `failedQueue.length = 0`
- **WHEN** a refresh fails: `processQueue(refreshError, null)` is called → `failedQueue.length = 0`
- **THEN** in both cases the queue is empty after processing (no memory leak, no stale entries)

#### Scenario: Interceptor calls logout on refresh failure without calling POST /auth/logout
- **WHEN** `POST /auth/refresh` returns a non-2xx response (e.g., 401 with revoked token)
- **THEN** the interceptor calls `useAuthStore.getState().logout()` to clear local state
- **THEN** the interceptor does NOT call `POST /auth/logout` (no nested HTTP call in the error handler)
- **THEN** `window.dispatchEvent(new CustomEvent('auth:expired'))` is fired
- **NOTE**: This is a deliberate design decision. The refresh token may remain valid in the DB until its 7-day TTL if the failure was a network error. If the failure was a 401 (token already invalid/expired), the DB entry is already invalid. Either way, the access token (which was the cause of the original 401) is expired and cannot be used.

#### Scenario: __isRetry flag prevents retry loops
- **WHEN** a retried request (with `__isRetry: true`) receives a 401
- **THEN** the interceptor skips the refresh flow (returns `Promise.reject(error)`)
- **THEN** no additional refresh call is made
- **NOTE**: Maximum 1 retry per original request. No exponential backoff. This is sufficient for auth token rotation.

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
