## MODIFIED Requirements

### Requirement: Auth router registered under /api/v1/auth
`backend/app/api/v1/auth.py` SHALL define an `APIRouter` with prefix `/auth` and tags `["auth"]`. This router SHALL be included inside the `build_v1_router` factory in `app/api/v1/router.py` so that all auth endpoints are reachable at `/api/v1/auth/*`.

In addition to `POST /auth/register` and `POST /auth/login` (defined in Change 06), this change adds:
- `POST /auth/refresh`
- `POST /auth/logout`
- `GET /auth/me`

All five endpoints are reachable under `/api/v1/auth/*`.

#### Scenario: All five auth endpoints are reachable at correct paths
- **WHEN** the app routes are inspected
- **THEN** `POST /api/v1/auth/register` exists and is wired to the register handler
- **THEN** `POST /api/v1/auth/login` exists and is wired to the login handler
- **THEN** `POST /api/v1/auth/refresh` exists and is wired to the refresh handler
- **THEN** `POST /api/v1/auth/logout` exists and is wired to the logout handler
- **THEN** `GET /api/v1/auth/me` exists and is wired to the me handler

#### Scenario: Auth router prefix does not duplicate the v1 prefix
- **WHEN** the final route paths are resolved
- **THEN** the refresh endpoint path is exactly `/api/v1/auth/refresh` (not `/api/v1/api/v1/auth/refresh`)

---

### Requirement: POST /api/v1/auth/login seeds family_id in RefreshToken
The existing `POST /api/v1/auth/login` requirement from Change 06 is extended: when the `RefreshToken` row is persisted, it SHALL include `family_id = uuid.uuid4()` (a new UUID generated per login call). The `token_hash`, `usuario_id`, `expires_at` fields remain unchanged.

#### Scenario: Successful login creates RefreshToken with family_id
- **WHEN** `POST /api/v1/auth/login` is called with correct credentials
- **THEN** HTTP 200 is returned with `TokenResponse`
- **THEN** the inserted `RefreshToken` row has a non-null `family_id`
- **THEN** the `family_id` is a valid UUID (not empty, not nil UUID)

#### Scenario: Two consecutive logins produce different family_ids
- **WHEN** `POST /api/v1/auth/login` is called twice with the same credentials
- **THEN** two `RefreshToken` rows exist, each with a unique `family_id`
