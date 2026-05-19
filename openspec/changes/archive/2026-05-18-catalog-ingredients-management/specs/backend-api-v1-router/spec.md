## ADDED Requirements

### Requirement: Ingredientes router mounted in build_v1_router
The `build_v1_router(settings: Settings) -> APIRouter` factory in `backend/app/api/v1/router.py` SHALL include the ingredientes router from `backend/app/api/v1/ingredientes.py` via `from app.api.v1.ingredientes import ingredientes_router` followed by `router.include_router(ingredientes_router, prefix="/ingredientes", tags=["ingredientes"])`. The final mounted path for all ingredient endpoints SHALL be `{settings.API_V1_PREFIX}/ingredientes/*` (e.g. `/api/v1/ingredientes`, `/api/v1/ingredientes/{id}`).

The ingredientes router SHALL NOT be included in `app/main.py` directly — it is always registered through `build_v1_router`.

#### Scenario: Ingredientes router is reachable under /api/v1/ingredientes
- **WHEN** the app boots and routes are inspected
- **THEN** `GET /api/v1/ingredientes` exists as a registered route
- **THEN** `GET /api/v1/ingredientes/{id}` exists as a registered route
- **THEN** `POST /api/v1/ingredientes` exists as a registered route
- **THEN** `PUT /api/v1/ingredientes/{id}` exists as a registered route
- **THEN** `DELETE /api/v1/ingredientes/{id}` exists as a registered route

#### Scenario: Ingredientes router prefix does not duplicate the v1 prefix
- **WHEN** the final route paths are resolved
- **THEN** the list endpoint path is exactly `/api/v1/ingredientes` (not `/api/v1/api/v1/ingredientes`)
- **THEN** no duplicate prefix appears in any registered ingredient route
