## ADDED Requirements

### Requirement: Login SHALL reject deactivated users (deleted_at IS NOT NULL)

The system SHALL guarantee that `AuthService.login_user` rejects deactivated users by relying on `UsuarioRepository.get_by_email` which applies a `WHERE deleted_at IS NULL` filter. A deactivated user (soft deleted by ADMIN) MUST NOT be found by `get_by_email`, causing the existing "not found" error path to execute.

This behavior is already implemented — no code change is required. This requirement documents the existing invariant explicitly to clarify the deactivation contract for Change 21.

> Security note: The login response for a deactivated user is IDENTICAL to the response for a wrong email or wrong password ("Invalid credentials", HTTP 401, RN-AU08). This is intentional — it prevents an attacker from enumerating deactivated accounts.

#### Scenario: Deactivated user cannot login
- **GIVEN** a user whose `deleted_at IS NOT NULL` (deactivated by ADMIN)
- **WHEN** `POST /api/v1/auth/login` is called with that user's correct email and password
- **THEN** `UsuarioRepository.get_by_email` returns `None` (soft delete filter: `WHERE deleted_at IS NULL`)
- **THEN** `AuthService.login_user` runs the dummy password check (timing attack prevention)
- **THEN** `UnauthorizedError("Invalid credentials", code="invalid_credentials")` is raised
- **THEN** the client receives HTTP 401 with a generic error message (no distinction from wrong password per RN-AU08)

#### Scenario: Active user with correct credentials can still login
- **GIVEN** a user with `deleted_at IS NULL` (active)
- **WHEN** `POST /api/v1/auth/login` is called with correct credentials
- **THEN** behavior is unchanged from the existing auth spec (HTTP 200, TokenResponse returned)

---

## ADDED Requirements (delta from backend-auth-dependencies)

### Requirement: get_current_user SHALL reject Bearer tokens for deactivated users

The system SHALL guarantee that `get_current_user` rejects Bearer tokens for deactivated users. `get_current_user` calls `uow.usuarios.get_by_id(user_uuid)` which applies `WHERE deleted_at IS NULL` via `BaseRepository.get_by_id`. A Bearer token for a deactivated user MUST produce a `None` result, causing the existing "user not found" error path.

This behavior is already implemented — no code change is required. Documented for clarity.

The deactivation flow in `AdminUsuariosService.deactivate_usuario` also calls `revoke_all_for_user` to revoke refresh tokens, so:
1. Existing Bearer tokens (access tokens, 30 min) become invalid immediately via `get_current_user`'s `deleted_at` check.
2. Existing refresh tokens are explicitly revoked — no new access tokens can be issued.
3. Login is blocked via `get_by_email`'s `deleted_at` filter.

All three layers enforce deactivation without any modification to existing auth code.

#### Scenario: Deactivated user's Bearer token is rejected
- **GIVEN** user U has a valid Bearer access token
- **WHEN** ADMIN deactivates user U (sets `deleted_at = now()`)
- **WHEN** user U calls any authenticated endpoint with the existing Bearer token
- **THEN** `get_current_user` calls `get_by_id(U.id)` which returns `None` (deleted_at filter)
- **THEN** `UnauthorizedError("Usuario no encontrado o inactivo", code="user_not_found")` is raised
- **THEN** HTTP 401 is returned

#### Scenario: Deactivated user's refresh token rotation fails
- **GIVEN** user U has a valid refresh token (not yet expired)
- **WHEN** ADMIN deactivates user U AND revokes all refresh tokens simultaneously (within same UoW)
- **WHEN** user U calls `POST /api/v1/auth/refresh` with their refresh token
- **THEN** `find_active_by_hash` returns `None` (token is revoked)
- **THEN** HTTP 401 is returned
