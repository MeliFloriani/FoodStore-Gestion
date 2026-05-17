# frontend-auth-rehydration Specification

## Purpose
Define the auth rehydration capability for the Food Store frontend: the `AuthSync` component that bridges Zustand's `persist` rehydration signal (`status: 'authenticating'`) to the backend `GET /api/v1/auth/me` call. Also defines the `AUTH_ME` and `AUTH_LOGOUT` endpoint constants required for this flow. Keeps FSD import direction intact — the component lives in `src/app/` and is side-effect-only (no rendered UI).

## Requirements

### Requirement: AuthSync component calls GET /auth/me on authenticating status
`src/app/` SHALL contain an `AuthSync` component (already stubbed by Change 05) that is updated to:

1. Subscribe to `authStore` and watch for `status === 'authenticating'`.
2. When `status` transitions to `'authenticating'`, call `GET /api/v1/auth/me` via `http.get(endpoints.AUTH_ME)`.
3. On success (`UserRead` response): call `authStore.getState().setUser(user)`. This action atomically sets `user` AND transitions `status` to `'authenticated'`. **Do NOT call `login()`** — tokens are already in the store from rehydration via `onRehydrateStorage`; calling `login()` here would redundantly re-write the same tokens and risks reading stale token values from the store at an inopportune moment.
4. On failure (any error including 401): call `authStore.getState().logout()` which clears tokens and sets `status: 'unauthenticated'`. If the failure is 401, the Axios interceptor will have already attempted a token refresh before `AuthSync` sees the error — if refresh also fails, `authStore.logout()` is called by the interceptor. `AuthSync` catches the final error and ensures `logout()` is called at least once (idempotent).
5. `AuthSync` does NOT render any UI — it is a side-effect-only component placed high in the component tree (inside the router or app providers).

**Import rules** (FSD): `AuthSync` lives in `src/app/` and MAY import from `src/shared/api/http.ts`, `src/shared/api/endpoints.ts`, and `src/entities/auth/model/store.ts`. It SHALL NOT be imported by `entities/` or `shared/` layers.

#### Scenario: AuthSync detects authenticating status and calls GET /auth/me
- **WHEN** the page loads and `authStore.status` is `'authenticating'` (tokens present in localStorage)
- **THEN** `AuthSync` calls `GET /api/v1/auth/me`

#### Scenario: Successful auth/me response hydrates user in store
- **WHEN** `GET /api/v1/auth/me` returns 200 with `UserRead`
- **THEN** `authStore.getState().user` is set to the returned user object
- **THEN** `authStore.getState().status` becomes `'authenticated'`

#### Scenario: auth/me 401 with failed refresh triggers logout
- **WHEN** `GET /api/v1/auth/me` returns 401 and the Axios interceptor's refresh attempt also fails
- **THEN** `authStore.getState().logout()` is called
- **THEN** `authStore.getState().status` becomes `'unauthenticated'`
- **THEN** `authStore.getState().accessToken` becomes `null`

#### Scenario: auth/me 401 with successful refresh retries and succeeds
- **WHEN** `GET /api/v1/auth/me` returns 401 but the Axios interceptor successfully refreshes the token
- **THEN** the interceptor retries `GET /auth/me` with the new access token
- **THEN** if the retry succeeds, `authStore.getState().user` is populated and `status` becomes `'authenticated'`

#### Scenario: AuthSync does not call auth/me when status is not authenticating
- **WHEN** `authStore.status` is `'authenticated'` or `'unauthenticated'` or `'idle'`
- **THEN** `AuthSync` does NOT call `GET /api/v1/auth/me`

---

### Requirement: AUTH_ME and AUTH_LOGOUT constants in endpoints.ts
`src/shared/api/endpoints.ts` SHALL export `AUTH_LOGOUT = '/auth/logout'` in addition to the constants already defined by Change 05 (`AUTH_LOGIN`, `AUTH_REFRESH`, `AUTH_ME`, `AUTH_REGISTER`). If `AUTH_ME` is not already defined, it SHALL be added here.

#### Scenario: endpoints.ts exports AUTH_LOGOUT
- **WHEN** `endpoints.ts` is imported
- **THEN** it exports `AUTH_LOGOUT = '/auth/logout'`

#### Scenario: endpoints.ts exports AUTH_ME
- **WHEN** `endpoints.ts` is imported
- **THEN** it exports `AUTH_ME = '/auth/me'`
