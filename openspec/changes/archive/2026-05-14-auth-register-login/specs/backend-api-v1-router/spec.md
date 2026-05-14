## ADDED Requirements

### Requirement: Auth router mounted in build_v1_router
The `build_v1_router(settings: Settings) -> APIRouter` factory in `backend/app/api/v1/router.py` SHALL include the auth router from `backend/app/api/v1/auth.py` via `router.include_router(auth_router)`. The auth router MUST declare its own prefix `/auth` so that the final mounted path for all auth endpoints is `{settings.API_V1_PREFIX}/auth/*` (e.g. `/api/v1/auth/register`, `/api/v1/auth/login`).

The auth router SHALL NOT be included in `app/main.py` directly — it is always registered through `build_v1_router`.

#### Scenario: Auth router is reachable under /api/v1/auth
- **WHEN** the app boots and routes are inspected
- **THEN** `POST /api/v1/auth/register` exists as a registered route
- **THEN** `POST /api/v1/auth/login` exists as a registered route

#### Scenario: Auth router prefix does not duplicate the v1 prefix
- **WHEN** the final route paths are resolved
- **THEN** the register endpoint path is exactly `/api/v1/auth/register` (not `/api/v1/api/v1/auth/register`)
