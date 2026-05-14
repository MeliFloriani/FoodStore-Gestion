# frontend-auth-store Specification

## Purpose
Define the Zustand authentication store for the Food Store frontend: the canonical `authStore` with typed state (accessToken, refreshToken, user, status), atomic `login`/`logout`/`updateTokens` actions, `localStorage` persistence of tokens only (never user object, never status), and a safe rehydration pattern that sets `status: 'authenticating'` as a signal for the `app/` layer to call `GET /auth/me` — keeping the FSD import direction intact. This store is the single source of truth for all authentication state consumed across the application.

## Requirements

### Requirement: authStore state shape and actions
`src/entities/auth/model/store.ts` SHALL export a Zustand store (`authStore`) with the following state and actions:

**State**:
- `accessToken: string | null`
- `refreshToken: string | null`
- `user: User | null` — where `User` is imported from `src/entities/auth/types.ts`
- `status: 'idle' | 'authenticating' | 'authenticated' | 'unauthenticated'`
- `isAuthenticated: boolean` — derived from `status === 'authenticated'`. This is a computed/derived field, NOT stored independently (to avoid sync bugs). It SHALL be exposed as a Zustand `computed` value or a selector function.

**Actions** (part of the store):
- `setTokens(accessToken: string, refreshToken: string): void`
- `setUser(user: User): void`
- `logout(): void` — sets `accessToken: null`, `refreshToken: null`, `user: null`, `status: 'unauthenticated'`
- `clear(): void` — same as logout (alias for explicit reset)
- `login(accessToken: string, refreshToken: string, user: User): void` — atomically calls `setTokens` + `setUser` + sets `status: 'authenticated'`. This is the canonical action for post-auth flows (US-000e).
- `updateTokens(accessToken: string, refreshToken: string): void` — alias for `setTokens`; exposed explicitly to match US-000e contract.

**Selectors**:
- `isAuthenticated(): boolean` — returns `status === 'authenticated'`
- `hasRole(role: string): boolean` — returns `user?.roles?.includes(role) ?? false`

#### Scenario: setTokens updates token fields
- **WHEN** `authStore.getState().setTokens('at123', 'rt456')` is called
- **THEN** `authStore.getState().accessToken` equals `'at123'`
- **THEN** `authStore.getState().refreshToken` equals `'rt456'`

#### Scenario: logout clears all auth state
- **WHEN** `authStore.getState().logout()` is called after a successful login
- **THEN** `accessToken`, `refreshToken`, and `user` are all `null`
- **THEN** `status` is `'unauthenticated'`

#### Scenario: login sets all auth state atomically
- **WHEN** `login(accessToken, refreshToken, user)` is called
- **THEN** `status` is `'authenticated'`, `accessToken` is set, `user` is set, `isAuthenticated` returns `true`

#### Scenario: logout clears isAuthenticated
- **WHEN** `logout()` is called
- **THEN** `status` is `'unauthenticated'`, `accessToken` is `null`, `user` is `null`, `isAuthenticated` returns `false`

#### Scenario: hasRole returns false when role not in user.roles
- **WHEN** `hasRole('admin')` is called with `user.roles = ['cliente']`
- **THEN** returns `false`

#### Scenario: hasRole returns true when role matches
- **WHEN** `hasRole('cliente')` is called with `user.roles = ['cliente']`
- **THEN** returns `true`

---

### Requirement: authStore persists tokens only (never user)
`authStore` SHALL use Zustand's `persist` middleware with `storage: localStorage`. The `partialize` function SHALL include ONLY `accessToken` and `refreshToken`. The `user` object and `status` field SHALL NOT be persisted.

Storage key: `food-store-auth`

#### Scenario: Only tokens are written to localStorage
- **WHEN** `authStore` has a user set and tokens set, and the store is serialized to localStorage
- **THEN** the stored value contains `accessToken` and `refreshToken`
- **THEN** the stored value does NOT contain `user` or `status`

#### Scenario: Store rehydrates with tokens after page reload
- **WHEN** localStorage contains a valid `food-store-auth` entry with tokens
- **THEN** after page reload `authStore.getState().accessToken` is non-null
- **THEN** `authStore.getState().user` is `null` (not rehydrated from storage)

> **Constraint — Persistence boundary**: The `login()` action atomically updates tokens, user, and status. The `partialize` function persists ONLY `accessToken` and `refreshToken`. The `user` field is NEVER persisted. The `isAuthenticated` derived value is NOT persisted. On rehydration, `user` is reconstructed via `GET /api/v1/auth/me` triggered by `triggerRehydrationFetch()` (see MED-05 resolution).

---

### Requirement: onRehydrateStorage signals authenticating state (no direct network call)
`authStore` SHALL use the `onRehydrateStorage` callback of the persist middleware. After rehydration, if `accessToken` is non-null, it SHALL set `status: 'authenticating'` as a signal. It SHALL NOT call `http.ts` or any network function directly. The `app/` layer is responsible for detecting `status === 'authenticating'` and calling `GET /api/v1/auth/me`, then dispatching `authStore.setUser(user)` and setting `status: 'authenticated'` on success (or `authStore.logout()` on failure).

`triggerRehydrationFetch(): void` — a public action exposed on the store. When called, it sets `status: 'authenticating'`. It does NOT import or call `http.ts` directly. It serves as a signal that an external caller (from the `app/` layer) should initiate `GET /api/v1/auth/me`.

> **Constraint — Import direction**: `shared/api/http.ts` MAY read from `entities/auth/store` via `getState()` (token injection). `entities/auth/store` SHALL NOT import from `shared/api/http.ts`. The rehydration fetch is initiated from `src/app/` (which is permitted to import from both `shared/api/` and `entities/`).

#### Scenario: Valid token on rehydration sets authenticating status
- **WHEN** `onRehydrateStorage` finds `accessToken` non-null
- **THEN** `status` is set to `'authenticating'` (not `'authenticated'`)

#### Scenario: AuthSync detects authenticating and calls auth/me
- **WHEN** a component in `app/` detects `status === 'authenticating'`
- **THEN** it calls `GET /api/v1/auth/me`

#### Scenario: Successful auth/me sets user and authenticated status
- **WHEN** `GET /auth/me` succeeds
- **THEN** `authStore.setUser(user)` is called and `status` becomes `'authenticated'`

#### Scenario: Failed auth/me triggers logout
- **WHEN** `GET /auth/me` fails
- **THEN** `authStore.logout()` is called

#### Scenario: Invalid token on rehydration clears store
- **WHEN** localStorage has a token that the server rejects with 401
- **THEN** `authStore.getState().accessToken` becomes `null`
- **THEN** `authStore.getState().status` is `'unauthenticated'`

---

### Requirement: User and AuthStatus types defined
`src/entities/auth/types.ts` SHALL export:
- `User` type with at minimum: `id: number`, `nombre: string`, `email: string`, `roles: string[]`
- `AuthStatus` type: `'idle' | 'authenticating' | 'authenticated' | 'unauthenticated'`

#### Scenario: User type matches LoginResponse schema
- **WHEN** the backend LoginResponse schema's `user` field is deserialized
- **THEN** it is assignable to the `User` type without type errors
