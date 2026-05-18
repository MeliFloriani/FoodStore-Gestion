## ADDED Requirements

### Requirement: Categorias router mounted in build_v1_router
The `build_v1_router(settings: Settings) -> APIRouter` factory in `backend/app/api/v1/router.py` SHALL include the categorias router from `backend/app/api/v1/categorias.py` via `from app.api.v1.categorias import categorias_router` followed by `router.include_router(categorias_router, prefix="/categorias", tags=["categorias"])`. The final mounted path for all category endpoints SHALL be `{settings.API_V1_PREFIX}/categorias/*` (e.g. `/api/v1/categorias`, `/api/v1/categorias/{id}`).

The categorias router SHALL NOT be included in `app/main.py` directly — it is always registered through `build_v1_router`.

#### Scenario: Categorias router is reachable under /api/v1/categorias
- **WHEN** the app boots and routes are inspected
- **THEN** `GET /api/v1/categorias` exists as a registered route
- **THEN** `GET /api/v1/categorias/{id}` exists as a registered route
- **THEN** `POST /api/v1/categorias` exists as a registered route
- **THEN** `PUT /api/v1/categorias/{id}` exists as a registered route
- **THEN** `DELETE /api/v1/categorias/{id}` exists as a registered route

#### Scenario: Categorias router prefix does not duplicate the v1 prefix
- **WHEN** the final route paths are resolved
- **THEN** the list endpoint path is exactly `/api/v1/categorias` (not `/api/v1/api/v1/categorias`)
- **THEN** no duplicate prefix appears in any registered category route
