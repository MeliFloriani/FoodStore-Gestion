## MODIFIED Requirements

### Requirement: authStore state shape and actions
`src/entities/auth/model/store.ts` SHALL export a Zustand store (`authStore`) with the following state and actions (extending the definition from Change 05):

**State** (UNCHANGED):
- `accessToken: string | null`
- `refreshToken: string | null`
- `user: User | null`
- `status: 'idle' | 'authenticating' | 'authenticated' | 'unauthenticated'`
- `isAuthenticated: boolean` — derived from `status === 'authenticated'`

**Actions** (MODIFIED and ADDED):
- `setTokens(accessToken: string, refreshToken: string): void` — UNCHANGED
- `setUser(user: User): void` — UNCHANGED
- `login(accessToken: string, refreshToken: string, user: User): void` — UNCHANGED
- `updateTokens(accessToken: string, refreshToken: string): void` — UNCHANGED
- `clear(): void` — UNCHANGED
- `logout(): void` — SYNCHRONOUS (verified in `frontend/src/entities/auth/model/store.ts`). Immediately sets state: `accessToken: null`, `refreshToken: null`, `user: null`, `status: 'unauthenticated'`. Does NOT make any network calls.
  NOTE: The store MUST NOT import `http.ts` — the HTTP call to `POST /auth/logout` is the responsibility of the caller in the `app/` or `features/` layer, invoked BEFORE calling `logout()`. This preserves the FSD import invariant: `entities/auth/store` SHALL NOT import `shared/api/http.ts`.

**Clarification**: The Action table entry previously listed `logout(): Promise<void>` — this was incorrect. The store action is and remains synchronous. The "async" behavior described in prior drafts referred to the caller's responsibility to first await the backend logout call, then call `authStore.getState().logout()` synchronously. The store action itself is not async.

- `triggerRehydrationFetch(): void` — UNCHANGED

**Selectors** (UNCHANGED):
- `isAuthenticated(): boolean`
- `hasRole(role: string): boolean`

#### Scenario: logout clears all auth state synchronously
- **WHEN** `authStore.getState().logout()` is called
- **THEN** `accessToken`, `refreshToken`, and `user` are all `null`
- **THEN** `status` is `'unauthenticated'`
- **THEN** `isAuthenticated()` returns `false`

#### Scenario: Caller is responsible for backend logout before calling store logout
- **WHEN** a logout action is triggered from the UI
- **THEN** the caller (feature or app layer) first calls `POST /auth/logout` with the current `refreshToken`
- **THEN** after the network call completes (success or failure), the caller calls `authStore.getState().logout()` to clear local state
- **THEN** local state is cleared regardless of network outcome

---

### Requirement: authStore persists tokens only (never user)
UNCHANGED from Change 05. `authStore` SHALL use Zustand's `persist` middleware with `storage: localStorage`. The `partialize` function SHALL include ONLY `accessToken` and `refreshToken`. The `user` object and `status` field SHALL NOT be persisted. Storage key: `food-store-auth`.

#### Scenario: Only tokens are written to localStorage
- **WHEN** `authStore` has a user set and tokens set, and the store is serialized to localStorage
- **THEN** the stored value contains `accessToken` and `refreshToken`
- **THEN** the stored value does NOT contain `user` or `status`

#### Scenario: Store rehydrates with tokens after page reload
- **WHEN** localStorage contains a valid `food-store-auth` entry with tokens
- **THEN** after page reload `authStore.getState().accessToken` is non-null
- **THEN** `authStore.getState().user` is `null` (not rehydrated from storage)

---

### Requirement: onRehydrateStorage signals authenticating state (no direct network call)
UNCHANGED from Change 05. `authStore` SHALL set `status: 'authenticating'` after rehydration if `accessToken` is non-null. The `app/` layer (`AuthSync`) is responsible for detecting this signal and calling `GET /auth/me`.

#### Scenario: Valid token on rehydration sets authenticating status
- **WHEN** `onRehydrateStorage` finds `accessToken` non-null
- **THEN** `status` is set to `'authenticating'`

#### Scenario: AuthSync detects authenticating and calls auth/me
- **WHEN** a component in `app/` detects `status === 'authenticating'`
- **THEN** it calls `GET /api/v1/auth/me`

#### Scenario: Successful auth/me sets user and authenticated status
- **WHEN** `GET /auth/me` succeeds
- **THEN** `authStore.setUser(user)` is called and `status` becomes `'authenticated'`

#### Scenario: Failed auth/me triggers logout
- **WHEN** `GET /auth/me` fails
- **THEN** `authStore.logout()` is called
