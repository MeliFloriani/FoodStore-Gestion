## Context

Change 06 (`auth-register-login`) established the login flow: password verification, JWT pair issuance (30 min access / 7 day refresh), and SHA-256 hash persistence. The current `RefreshToken` model has `token_hash`, `usuario_id`, `expires_at`, `revoked_at` — it does **not** have a `family_id` field, which is required to implement replay-attack detection.

The frontend `authStore` (Change 05) has `status: 'authenticating'` as a signal for rehydration, and the Axios interceptor already implements the 401-refresh-retry-queue pattern. The `AuthSync` component stub exists in `src/app/` but is not yet wired to call `GET /auth/me`.

This change closes the session lifecycle:
- Backend: rotation with family lineage, logout revocation, `/me` profile endpoint.
- Frontend: `fetchMe()` action in `authStore`, `AuthSync` wired to `GET /auth/me`, validated interceptor contract.

**Constraints inherited from prior changes:**
- `session.commit()` never in Service — UoW owns the transaction.
- `HTTPException` only in Service, never in Router or Repository.
- SHA-256 for refresh token hashing (not bcrypt — exact equality comparison).
- Rate limiting via `slowapi` with `get_limiter()` singleton.
- FSD import direction: `shared/api/http.ts` may read store via `getState()` only; `entities/auth/store` must not import `http.ts`.

---

## Goals / Non-Goals

**Goals:**

- Implement `POST /api/v1/auth/refresh` with token rotation, family lineage, and replay detection.
- Implement `POST /api/v1/auth/logout` with single-token revocation.
- Implement `GET /api/v1/auth/me` returning `UserRead` for the authenticated caller.
- Add Alembic migration for `RefreshToken.family_id`.
- Wire `authStore.fetchMe()` and `AuthSync` rehydration in the frontend.
- Validate (and minimally adjust if needed) the interceptor contract for `POST /auth/refresh`.
- Achieve ≥ 90% test coverage on new backend modules.
- Validate `require_role` end-to-end with a smoke test (RBAC infrastructure confirmed working).

**Non-Goals:**

- Full admin RBAC enforcement on all future endpoints (that is Changes 09+).
- Role assignment / management UI (Change 21).
- Any frontend pages or UI components beyond `AuthSync` plumbing.
- Redis-backed rate limiting (in-memory `slowapi` is sufficient for Sprint 1).
- Refresh token family pruning / cleanup job (deferred).

---

## Decisions

### D-07-A: `family_id` field on `RefreshToken` (Alembic migration required)

**Decision**: Add `family_id: uuid.UUID = Field(nullable=False, index=True)` to `RefreshToken`. Each login seeds `family_id = uuid.uuid4()`. Each `/refresh` inherits the parent's `family_id`.

**Rationale**: Replay detection requires grouping tokens by family to enable `revoke_family`. Without this field, the only option would be to revoke all tokens for the user on replay, which is too aggressive for multi-device scenarios (future). A per-family revocation is more surgical.

**Alternative considered**: Using `parent_id FK → refresh_token.id` (linked-list lineage). Rejected: requires a recursive CTE or iterative walk to find all siblings. A flat `family_id` column makes `DELETE WHERE family_id = X` atomic and O(1) in SQL.

**Migration note**: Existing test/dev `refresh_token` rows must be backfilled or the table dropped and recreated. In a dev-only environment (no production), the migration will use `server_default=text("gen_random_uuid()")` to backfill existing rows without a data migration script.

---

### D-07-B: Refresh token atomicity via UoW

**Decision**: The `/refresh` endpoint executes the following within a single `UnitOfWork` context manager (one `AsyncSession`, one `COMMIT`):
1. `find_active_by_hash(hash)` — load the token and verify it is not revoked and not expired.
2. `revoke_by_hash(hash)` — set `revoked_at = now()`.
3. `create_with_family(new_token)` — insert new `RefreshToken` with same `family_id`.
4. Issue new access token (in-memory, no DB write).

**Rationale**: If two concurrent requests arrive with the same refresh token, only one will succeed the `find_active_by_hash` check (the other sees `revoked_at IS NOT NULL` after the first transaction commits). The loser receives HTTP 401. The frontend interceptor queue ensures the second request is retried with the new token already in store — handled by Change 05's interceptor.

**Alternative considered**: Pessimistic locking (`SELECT FOR UPDATE`). Rejected: adds latency for the common case and SQLAlchemy async support for `FOR UPDATE` is available but adds implementation complexity. Given that two simultaneous refresh calls with the same token are rare and the consequence is a single 401 retry, optimistic check is sufficient.

---

### D-07-C: Replay detection — revoke entire family, not all user tokens

**Decision**: If a token whose `revoked_at IS NOT NULL` is presented to `/refresh`, the service raises a **specific internal exception** `TokenReplayError` (not `UnauthorizedError` directly) — the router catches `TokenReplayError`, opens a **second independent UoW**, calls `revoke_family(family_id)` within it, commits, and then re-raises as `UnauthorizedError(code="token_replay_detected")`. A WARNING log is emitted with `user_id`, `family_id`, `ip`, `user_agent`.

**Transactional Strategy: Opción A (second UoW in the router)**

The core problem is that `revoke_family()` must persist to the database even though a replay attack requires returning HTTP 401. UoW semantics guarantee that any exception causes a rollback — so if `revoke_family` is called inside the same UoW that later raises `UnauthorizedError`, the revocation is rolled back and never persisted.

**Flow**:
1. Router calls `AuthService.rotate_refresh(uow, ...)` inside `Depends(get_uow)`.
2. Service detects replay → raises `TokenReplayError(family_id=family_id, user_id=user_id)` (a domain exception, NOT an `HTTPException`).
3. The `Depends(get_uow)` UoW context manager catches this exception → calls `rollback()`. The revocation attempt within the original UoW is discarded.
4. **The router endpoint function** catches `TokenReplayError` explicitly:
   ```python
   except TokenReplayError as e:
       async with UnitOfWork() as uow2:
           await uow2.refresh_tokens.revoke_family(e.family_id)
       # uow2 commits here on clean exit
       logger.warning("auth.replay_detected", user_id=str(e.user_id), family_id=str(e.family_id), ip=_get_client_ip(request), user_agent=...)
       raise UnauthorizedError("Sesión comprometida", code="token_replay_detected")
   ```
5. The router re-raises `UnauthorizedError` → FastAPI returns HTTP 401.

**Why Opción A over alternatives**:
- **Opción B** (service opens its own internal UoW): requires injecting a UoW factory into the service, violating the service's stateless nature and complicating the dependency graph.
- **Opción C** (BackgroundTask): revocation is not synchronous — there is a window where the attacker's token family is still valid between the 401 response and the background task execution. Unacceptable for a security-critical operation.
- **Opción D** (Outbox/event pattern): over-engineering for Sprint 1.
- **Opción E** (UoW "commit before raise" flag): breaks the clean semantics of UoW and adds complexity to a core infrastructure component.

**Opción A tradeoffs**:
- Pro: simple, explicit, each UoW has a single responsibility, no infrastructure changes.
- Pro: revocation is synchronous — commits before the 401 is returned.
- Con: the router handles one domain-level concern (security side-effect) beyond pure HTTP translation. This is justified: replay detection is an HTTP-layer security response, not business logic.
- Con: `TokenReplayError` is a new domain exception that crosses the service→router boundary. It must be defined in `app/core/exceptions.py` and NOT be a subclass of `HTTPException`.

**Revoking family vs all user tokens**: Deviates from RN-AU05's literal wording; see proposal.md §Desviaciones documentadas for full rationale.

**Security note**: The `revoked_at` field serves double duty — it marks both "legitimately rotated" and "replay-detected". The service distinguishes between the two by checking whether the token was presented at all after revocation. Since `revoke_family` is idempotent (subsequent replays set `revoked_at` again on already-revoked rows, a no-op), the response is always 401 for any replay.

---

### D-07-D: Logout — revoke single token, Bearer optional

**Decision**: `POST /api/v1/auth/logout` requires `{ refresh_token: str }` in the body. The Bearer access token is optional (no `Depends(get_current_user)`). If the access token is provided and valid, it is ignored (not used for lookup). The logout is keyed exclusively on the refresh token hash.

**Rationale**: A user whose access token has just expired should still be able to log out cleanly. Requiring a valid Bearer would create a window where logout is impossible after access expiry. The refresh token is the session credential; revoking it is the logout.

**Security note**: An attacker who has stolen the refresh token could also call logout. This is acceptable — if an attacker has the refresh token, they could have used it anyway. Logout by hash is idempotent and harmless.

---

### D-07-E: `/auth/me` — no rate limit, TanStack Query stale-while-revalidate

**Decision**: `GET /api/v1/auth/me` uses `Depends(get_current_user)` (401 on missing/invalid token). No rate limit applied. Returns `UserRead`.

**Frontend caching**: The `AuthSync` component in `src/app/` calls `GET /auth/me` once on page load via a direct `http.get` call (not TanStack Query — it's a store initialization concern, not a data-fetch concern). After store hydration, features that display user profile data may use TanStack Query with `staleTime: 5 * 60 * 1000` (5 min).

**`get_current_user` uses `get_by_id`, not `get_with_roles`**: Verified in `backend/app/api/deps.py` — `get_current_user` calls `uow.usuarios.get_by_id(user_uuid)`. The `usuario_roles` relationship is loaded automatically via the model-level `lazy='selectin'` on `Usuario.usuario_roles` (defined in `backend/app/models/user.py`). This means:
- If `lazy='selectin'` is present: `UserRead.roles` populates correctly.
- If someone changes `Usuario.usuario_roles` to `lazy='noload'` in the future: `UserRead.roles` silently returns `[]`. This is a fragile implicit dependency. Risk is documented in Risks/Trade-offs.
- The spec text previously stated "uses `get_with_roles`" — this is INCORRECT. The correct behavior is "uses `get_by_id` which relies on `lazy='selectin'` eager loading of `usuario_roles`". If the model lazy strategy changes, the service/dep must switch to an explicit `get_with_roles` eager query.

**`require_role` semantics — OR/ANY intersection**: `require_role(*roles)` in `backend/app/api/deps.py` uses `user_role_codes.intersection(required_set)` — the user is authorized if they have **ANY ONE** of the required roles (logical OR). This is intersection-based OR semantics: `require_role("ADMIN", "PEDIDOS")` allows any user with ADMIN OR PEDIDOS role. This is the correct behavior for most RBAC patterns but must be documented so future callers don't assume AND semantics.

---

### D-07-F: RBAC smoke test scope

**Decision**: This change confirms `require_role` works end-to-end by writing `test_rbac.py` covering:
- `GET /api/v1/auth/me` with a CLIENT token returns 200.
- A hypothetical admin-only endpoint (or the `/me` endpoint protected with `require_role(["ADMIN"])` in test) with a CLIENT token returns 403.
- No Bearer token returns 401.

The real application of `require_role` to product/order/admin endpoints occurs in Changes 09+. This change validates the infrastructure works.

---

### D-07-G: Frontend `authStore.logout()` — synchronous, caller handles backend call

**Decision**: `authStore.logout()` remains **synchronous** (`(): void`). It immediately clears local state (`accessToken: null`, `refreshToken: null`, `user: null`, `status: 'unauthenticated'`). Callers in `app/` layer (e.g., a logout button feature) are responsible for calling `POST /auth/logout` BEFORE invoking `authStore.getState().logout()`.

**Verified**: The actual `store.ts` implementation confirms `logout()` is synchronous. Making it async would violate the FSD import invariant (`entities/auth/store` cannot import `http.ts`).

**FSD import invariant**: The store MUST NOT import `http.ts`. Therefore, the network call for backend logout is always initiated from `app/` or `features/` layer, never from within the store action itself.

**Post-refresh-failure behavior**: When the Axios interceptor's refresh call fails, it calls `useAuthStore.getState().logout()` directly — WITHOUT first calling `POST /auth/logout`. This means:
- The refresh token remains valid in the DB until its 7-day TTL.
- The access token is already expired (that's why refresh was attempted).
- This is an acceptable trade-off: calling `POST /auth/logout` during an interceptor error handler would create a nested HTTP call that could itself fail or loop. The security impact is minimal — the expired access token cannot be used, and the refresh token will expire naturally.
- **This is a deliberate design decision, not a bug.** Document in interceptor code comments.

**Rationale**: Always clearing local state even if the backend call fails prevents a stuck state where the user can't log out because the network is down. The backend revocation is best-effort; the access token will expire naturally (30 min max).

---

### D-07-H: `AuthSync` placement and import rules

**Decision**: `AuthSync` lives in `src/app/` (already created by Change 05 as a stub). This change adds the `fetchMe` logic. `AuthSync` imports `http` from `src/shared/api/http.ts` (allowed — `app/` is the top FSD layer) and `authStore` from `src/entities/auth/model/store.ts`. No new FSD layer violations.

**Import invariant preserved**: `entities/auth/store` does NOT import `http.ts`. The fetch is initiated from `app/` layer, which is permitted to import from both `shared/api/` and `entities/`.

---

### D-07-I: Multi-tab token synchronization

**Decision**: Use the native `storage` event (Opción α) to synchronize auth state across browser tabs when a token rotation occurs in one tab.

**Flow**:
1. Tab A rotates tokens via the interceptor → `updateTokens(newAccess, newRefresh)` → Zustand `persist` writes `{ accessToken, refreshToken }` to `localStorage['food-store-auth']`.
2. Browser fires `storage` event on all OTHER tabs (not the writing tab).
3. A listener installed in `src/app/` (or `src/shared/api/cross-tab-sync.ts`) receives the event filtered by `e.key === 'food-store-auth'`.
4. If `e.newValue` is non-null: parse JSON, extract `accessToken`/`refreshToken`, call `useAuthStore.getState().updateTokens(accessToken, refreshToken)` to update in-memory state without triggering another write.
5. If `e.newValue === null` (another tab called `localStorage.removeItem` or cleared storage): call `useAuthStore.getState().logout()` to clear local state.

**Why Opción α over alternatives**:
- **Opción β** (BroadcastChannel): not supported in Safari < 15.4 (released Sep 2021). Given the target audience may include iOS users, a fallback would be needed, adding complexity.
- **Opción γ** (BroadcastChannel + storage event fallback): correct but more complex than needed for Sprint 1.
- **Opción δ** (Web Locks API): prevents concurrent refresh but doesn't solve the stale-token problem in tabs that are not actively refreshing.

**Opción α tradeoffs**:
- Pro: native browser API, no dependencies, works in all modern browsers.
- Pro: the `storage` event fires ONLY on other tabs — the writing tab doesn't need to listen, which is exactly the desired behavior.
- Con: Safari/iOS has known erratic `storage` event behavior in some edge cases (private browsing, aggressive iframe sandboxing). For Sprint 1 this is acceptable — the worst case is a stale 401 in an affected tab which the interceptor handles gracefully via the refresh flow.
- Con: if `e.newValue` does not change (value identical), some browsers may not fire the event. With token rotation this is not an issue — tokens always change.

**Edge cases**:
- **Race between rotation in Tab A and request in Tab B during the storage event window**: Tab B sends a request with the old token → 401 → interceptor tries to refresh → presents the old refresh token → service detects this as a valid rotation (the token is not yet revoked from Tab B's perspective). After B-1 fix (second UoW in router for replay), the race is: if Tab A has COMMITTED its rotation before Tab B presents the old token, Tab B gets a replay 401 → family revoked → user must re-login. This is the correct security outcome. If Tab A has NOT yet committed, Tab B successfully rotates too — but this is the pre-existing race documented in D-07-B (optimistic concurrency).
- **Tab with `refreshPromise` in progress**: if the storage event fires while Tab A is mid-refresh, the listener MUST check if a `refreshPromise` is already in progress. If yes, skip the storage event update (the in-progress refresh will write the correct final tokens). Implementation: export a `isRefreshing()` function from `http.ts` or expose `refreshPromise !== null` as a flag.

**Compatibility constraints**:
- Zustand `partialize` persists ONLY `accessToken` and `refreshToken` → the storage event payload contains only these two fields. The listener must NOT attempt to read `user` or `status` from the event.
- The listener lives in `src/app/` or `src/shared/api/` (cross-tab-sync module), NOT in `entities/`. FSD boundary respected.
- The listener is installed once (e.g., in a `useEffect` with empty deps in `AuthSync`, or as a module-level side effect in `cross-tab-sync.ts` called from `app/`).

**File recommendation**: `src/shared/api/cross-tab-sync.ts` — keeps the sync logic close to the HTTP client (`http.ts`) and `endpoints.ts`, maintains FSD boundaries (shared layer can be imported by app and features).

---

## Risks / Trade-offs

| Risk | Severity | Mitigation |
|------|----------|------------|
| `family_id` migration breaks existing test fixtures that insert `RefreshToken` without the new field | HIGH | Migration uses `server_default=gen_random_uuid()` to backfill; test fixtures must be updated to supply `family_id`. Add migration test to CI. |
| Two concurrent `/refresh` calls with the same token: one wins, one gets 401 | LOW | Expected by design. The frontend interceptor queue (Change 05) ensures the losing request is retried after the winner updates the store. Document in spec. |
| `authStore.logout()` becoming async may break existing callers that invoke it synchronously | REFUTED | Verified in `frontend/src/entities/auth/model/store.ts`: `logout()` is already synchronous (returns void). The spec's Action table entry `Promise<void>` is incorrect; the Resolution section of the spec correctly documents it as synchronous. No callers need to be updated. |
| `AuthSync` calling `GET /auth/me` fails on 401, interceptor retries refresh, refresh fails, infinite loop | LOW | The interceptor skips refresh for `/auth/refresh` and `/auth/login` but not `/auth/me`. Mitigate: `AuthSync` catches the error from the interceptor (which calls `logout()`) — no loop because after `logout()` the `status` is `unauthenticated` and `AuthSync` stops watching. |
| `family_id` backfill in migration: `gen_random_uuid()` requires PostgreSQL ≥ 13 | MED | `gen_random_uuid()` is built-in since PostgreSQL 13 (no extension needed). **Require PostgreSQL ≥ 13** — document as a deployment prerequisite in `proposal.md §Impact`. Fallback if needed: use `uuid_generate_v4()` from `pgcrypto` or supply the default via Python `op.execute()` in the migration. |
| Replay detection revocation lost if `revoke_family` is inside the same UoW that raises | BLOCKER → FIXED | Fixed by D-07-C (Opción A): router catches `TokenReplayError`, opens second UoW, commits revocation, then re-raises as 401. The primary UoW rollback does not affect the second UoW commit. |
| `lazy='selectin'` on `usuario_roles` is load-critical for `/auth/me` | MED | `get_current_user` uses `uow.usuarios.get_by_id()` which triggers the model-level `lazy='selectin'` eager load on `usuario_roles`. If the lazy strategy ever changes to `noload`, `UserRead.roles` will silently return an empty list. Mitigation: document the dependency (see §D-07-E). If model strategy changes, switch to explicit `get_with_roles` query in `get_current_user`. |
| Post-refresh-failure: interceptor calls `logout()` without calling `POST /auth/logout` | LOW | This is a deliberate design decision (see §D-07-G extended note): on refresh failure (network error or 401 from refresh endpoint), the interceptor calls `logout()` synchronously — there is no opportunity to call `POST /auth/logout` first. The refresh token remains valid in the DB until its 7-day TTL. This is acceptable: if refresh fails with 401, the token is likely already invalid (expired or revoked). If refresh fails with network error, the token remains valid and the user simply needs to re-login. Document as known behavior, not a bug. |
| Multi-tab stale tokens: Tab B presents old refresh token after Tab A rotates | MED | Mitigated by D-07-I (storage event listener). Without the listener: Tab B presents old refresh → if Tab A's rotation committed → family replay detection triggers → family revoked → Tab B and A forced to re-login. With listener: Tab B updates tokens immediately on storage event, avoiding the stale presentation. |
| `request.client.host` is `None` behind a reverse proxy | MED | Fixed by H-3: implement `_get_client_ip(request)` helper with `X-Forwarded-For` support and null-safe fallback. |

---

## Migration Plan

1. Write Alembic migration adding `family_id UUID NOT NULL DEFAULT gen_random_uuid()` to `refresh_token`.
2. Remove the `server_default` after confirming all test rows have been backfilled (optional cleanup in a subsequent migration).
3. Update `RefreshToken` model in `user.py` to declare `family_id: uuid.UUID = Field(nullable=False, index=True)`.
4. Update `RefreshTokenRepository` with new query methods.
5. Extend `AuthService` with new static methods.
6. Register new endpoints in `auth_router`.
7. Update frontend: `authStore`, `AuthSync`, `endpoints.ts`.
8. Run all backend tests — gate on ≥ 90% coverage for new modules.
9. Run frontend tests — gate on authStore and AuthSync suites passing.

**Rollback**: Revert migration with `alembic downgrade -1`. The `family_id` column is dropped. Frontend changes can be reverted independently.

---

## Open Questions

- **None blocking.** The `family_id` field name is confirmed as the correct abstraction (vs. `parent_id`). All design decisions above are resolved.
