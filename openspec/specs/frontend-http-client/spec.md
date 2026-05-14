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
2. Skips the refresh flow for requests to `/auth/refresh` and `/auth/login` (preventing infinite loops).
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
`src/shared/api/endpoints.ts` SHALL export URL path constants for all auth endpoints referenced by the interceptors and by future feature changes. Constants SHALL be path-only (no base URL). Minimum required:
- `AUTH_LOGIN`, `AUTH_REFRESH`, `AUTH_ME`, `AUTH_REGISTER`

#### Scenario: Endpoint constants cover auth paths
- **WHEN** `endpoints.ts` is imported
- **THEN** it exports `AUTH_LOGIN = '/auth/login'`, `AUTH_REFRESH = '/auth/refresh'`, `AUTH_ME = '/auth/me'`, `AUTH_REGISTER = '/auth/register'`
