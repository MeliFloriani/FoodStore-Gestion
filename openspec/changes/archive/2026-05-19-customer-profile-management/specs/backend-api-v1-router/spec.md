## ADDED Requirements

### Requirement: Profile router mounted in build_v1_router
The `build_v1_router(settings: Settings) -> APIRouter` factory in `backend/app/api/v1/router.py` SHALL include the profile router from `backend/app/api/v1/profile.py` via `from app.api.v1.profile import profile_router` followed by `router.include_router(profile_router, prefix="/profile", tags=["profile"])`. The final mounted path for all profile endpoints SHALL be `{settings.API_V1_PREFIX}/profile/*` (e.g. `/api/v1/profile/me`, `/api/v1/profile/me/password`).

The profile router SHALL NOT be included in `app/main.py` directly — it is always registered through `build_v1_router`.

#### Scenario: Profile router is reachable under /api/v1/profile
- **WHEN** the app boots and routes are inspected
- **THEN** `PATCH /api/v1/profile/me` exists as a registered route
- **THEN** `POST /api/v1/profile/me/password` exists as a registered route

#### Scenario: Profile router prefix does not duplicate the v1 prefix
- **WHEN** the final route paths are resolved
- **THEN** the update endpoint path is exactly `/api/v1/profile/me` (not `/api/v1/api/v1/profile/me`)
- **THEN** no duplicate prefix appears in any registered profile route

#### Scenario: Profile tag appears in OpenAPI schema
- **WHEN** `GET /docs` or `GET /openapi.json` is accessed
- **THEN** a section tagged `"profile"` appears in the OpenAPI schema
- **THEN** both profile endpoints appear under that tag
