## Why

Change 06 (`auth-register-login`) implemented registration and login, emitting a JWT pair and persisting the refresh token hash. The session lifecycle is incomplete: there is no mechanism to rotate refresh tokens, detect replay attacks, revoke sessions on logout, or expose the authenticated user's profile for store rehydration after page reload. Without these three endpoints (`/refresh`, `/logout`, `/me`) and the frontend interceptor wired to `/me`, the `authStore` cannot reconstruct the user on page reload and RBAC enforcement remains untested end-to-end.

## What Changes

- **NEW** `POST /api/v1/auth/refresh` — rotates the refresh token (revoke old, emit new with same `family_id`); detects replay by checking if the presented token is already revoked, revoking the entire family and forcing re-login; rate-limited 30/15 min.
- **NEW** `POST /api/v1/auth/logout` — revokes the specific refresh token provided in the body; access token remains valid until natural expiry (stateless JWT).
- **NEW** `GET /api/v1/auth/me` — returns `UserRead` for the bearer of a valid access token; consumed by the frontend `AuthSync` component on page load to reconstruct the user object.
- **BREAKING** `RefreshToken` model gains `family_id UUID NOT NULL` — requires a new Alembic migration. Every login creates a new family; every `/refresh` inherits the same `family_id`.
- **MODIFIED** `RefreshTokenRepository` — adds `find_by_hash`, `find_active_by_hash`, `revoke_family` (revoke all tokens with same `family_id`), `create_with_family`.
- **MODIFIED** `AuthService` — extended with `rotate_refresh`, `revoke_refresh`, `get_me` static methods.
- **MODIFIED** `auth_router` — three new endpoints registered; `/refresh` decorated with rate limit.
- **MODIFIED** `UnitOfWork` — no new repos needed; existing `refresh_tokens` repo receives extended methods.
- **MODIFIED** `authStore` (frontend) — adds `fetchMe()` action (calls `GET /auth/me`), `logout()` extended to call `POST /auth/logout` before clearing local state.
- **MODIFIED** `AuthSync` (frontend, `src/app/`) — detects `status === 'authenticating'` and calls `fetchMe()`; on 401 attempts refresh via interceptor; on refresh failure calls `authStore.logout()` and redirects to `/login`.
- **VALIDATED** `frontend-http-client` interceptor contract — confirms `POST /auth/refresh` response matches `TokenResponse` shape `{ access_token, refresh_token, token_type, expires_in }`.
- **NEW** backend tests: `test_auth_refresh.py`, `test_auth_logout.py`, `test_auth_me.py`, `test_rbac.py`.
- **NEW** frontend tests: `authStore` actions, `AuthSync` rehydration flow with mocks.

## Capabilities

### New Capabilities

- `backend-auth-refresh-rotation`: Refresh token rotation with family lineage and replay detection. Covers the `rotate_refresh` service logic, `revoke_family` repository operation, and the `/refresh` endpoint with rate limiting.
- `backend-auth-logout`: Logout endpoint that revokes a single refresh token. Covers the `revoke_refresh` service logic and the `/logout` endpoint (auth optional — works with Bearer or without if refresh token is provided).
- `backend-auth-me`: Authenticated endpoint that returns the current user profile. Covers `GET /api/v1/auth/me` and its `UserRead` response.
- `frontend-auth-rehydration`: Frontend rehydration flow — `AuthSync` component reads `status === 'authenticating'` from the store and calls `GET /auth/me` to reconstruct the user after page reload.

### Modified Capabilities

- `backend-auth-token-issuance`: `create_refresh_token` must now accept and embed `family_id` in the RefreshToken record. Login path seeds `family_id = uuid.uuid4()` on first issuance.
- `backend-auth-register-login`: Auth router gains three new endpoints (`/refresh`, `/logout`, `/me`) and the router file grows accordingly.
- `backend-api-v1-router`: No new router file required — new endpoints are added to the existing `auth_router` already mounted in `build_v1_router`.
- `frontend-auth-store`: Adds `fetchMe()` action and extends `logout()` to call the backend endpoint before clearing local state.
- `frontend-http-client`: Endpoint constant `AUTH_LOGOUT = '/auth/logout'` added to `endpoints.ts`; interceptor contract validated against `TokenResponse`.

## Impact

- **Database**: Alembic migration adds `family_id UUID NOT NULL` to `refresh_token` table. Existing rows from Change 06 (dev/test only — no production data) will need backfill or table recreation in test environments.
- **Backend**: `backend/app/models/user.py` (RefreshToken model), `backend/app/repositories/user.py` (RefreshTokenRepository), `backend/app/services/auth.py` (AuthService), `backend/app/core/exceptions.py` (new `TokenReplayError` domain exception), `backend/app/api/v1/auth.py` (auth_router with replay detection second-UoW pattern), `backend/app/core/uow.py` (no structural change, comment update only), `alembic/versions/` (new migration).
- **Frontend**: `src/entities/auth/model/store.ts` (authStore — logout confirmed synchronous, no change needed), `src/app/` (AuthSync component), `src/shared/api/endpoints.ts` (AUTH_LOGOUT constant), `src/shared/api/http.ts` (contract validation; add AUTH_LOGOUT to skip list consideration), `src/shared/api/cross-tab-sync.ts` (NEW — storage event listener for multi-tab token synchronization).
- **Tests**: `backend/tests/test_auth_refresh.py`, `backend/tests/test_auth_logout.py`, `backend/tests/test_auth_me.py`, `backend/tests/test_rbac.py`; frontend test files for authStore and AuthSync.
- **No breaking changes to existing `/register` or `/login` endpoints.** The `family_id` addition to RefreshToken is an additive schema change (new non-null column with default generated at insert time).
- **PostgreSQL ≥ 13 required**: The migration uses `gen_random_uuid()` which is built-in since PostgreSQL 13 (no `pgcrypto` extension needed). Deployments on PostgreSQL < 13 must either upgrade or modify the migration to use `uuid_generate_v4()` (requires `pgcrypto`) or a Python-level default.

## Desviaciones documentadas

### DEV-01: Family-scoped revocation en lugar de revocación de todos los tokens del usuario

**Regla original (RN-AU05)**: "Si se detecta reuso de un refresh token ya utilizado (replay attack), se revocan TODOS los tokens del usuario".

**Implementación**: Este change implementa **family-scoped revocation** — solo se revocan los tokens de la familia comprometida (mismo `family_id`), no todos los refresh tokens del usuario.

**Justificación**:
1. **US-003 Notas Técnicas lo avala explícitamente**: las Notas Técnicas de US-003 mencionan `familyId` como mecanismo de detección de reuso — implicando que la unidad de revocación es la familia, no el usuario completo.
2. **Conflicto interno en US-003**: el AC de US-003 dice "TODOS los refresh tokens del usuario"; las Notas Técnicas dicen `familyId`. Este cambio resuelve la ambigüedad eligiendo la opción más granular, que preserva la experiencia multi-dispositivo.
3. **Multi-device UX**: si el usuario tiene sesiones activas en dos dispositivos y el token de uno es robado/reproducido, revocar TODOS los tokens forzaría el logout en el dispositivo no comprometido. La revocación por familia es más quirúrgica: solo la familia comprometida es anulada, las otras sesiones legítimas continúan activas.
4. **Seguridad suficiente**: la familia comprometida queda completamente revocada — el atacante no puede seguir usando ningún token de esa familia. El objetivo de replay detection se cumple.
5. **Alineación con la práctica de la industria**: OAuth2 con refresh token rotation estándar (IETF RFC 6749 y draft-ietf-oauth-security-topics) recomienda revocación de familia, no de usuario completo.

**Impacto en contrato externo**: ninguno — el endpoint `/auth/refresh` retorna HTTP 401 con `code="token_replay_detected"` en ambos casos. El cliente no puede distinguir family-revocation de user-revocation desde el exterior.

**Decisión tomada por**: equipo de arquitectura Change 07. Documentada aquí para trazabilidad en auditorías futuras.
