## ADDED Requirements

### Requirement: Catalog router mounted in build_v1_router
The `build_v1_router(settings: Settings) -> APIRouter` factory in `backend/app/api/v1/router.py` SHALL include the public catalog router from `backend/app/api/v1/catalog.py` via `from app.api.v1.catalog import catalog_router` followed by `router.include_router(catalog_router, prefix="/catalog", tags=["catalog"])`. The final mounted path for all public catalog endpoints SHALL be `{settings.API_V1_PREFIX}/catalog/*` (e.g. `/api/v1/catalog/productos`, `/api/v1/catalog/productos/{id}`).

The catalog router SHALL NOT be included in `app/main.py` directly — it is always registered through `build_v1_router`.

The catalog router SHALL declare NO auth dependencies at the router level — individual endpoints are fully public and require no `Authorization` header.

#### Scenario: Catalog router is reachable under /api/v1/catalog
- **WHEN** the app boots and routes are inspected
- **THEN** `GET /api/v1/catalog/productos` exists as a registered route
- **THEN** `GET /api/v1/catalog/productos/{id}` exists as a registered route
- **THEN** `GET /api/v1/catalog/ingredientes-alergenos` exists as a registered route

#### Scenario: Catalog router prefix does not duplicate the v1 prefix
- **WHEN** the final route paths are resolved
- **THEN** the list endpoint path is exactly `/api/v1/catalog/productos` (not `/api/v1/api/v1/catalog/productos`)
- **THEN** no duplicate prefix appears in any registered catalog route

#### Scenario: Catalog endpoints have no auth dependency
- **WHEN** `GET /api/v1/catalog/productos` is called without any `Authorization` header
- **THEN** the response is HTTP 200 (never 401 or 403)
- **WHEN** `GET /api/v1/catalog/productos/{id}` is called without any `Authorization` header
- **THEN** the response is HTTP 200 or HTTP 404 (never 401 or 403)

#### Scenario: Public allergen endpoint requires no auth
- **WHEN** `GET /api/v1/catalog/ingredientes-alergenos` is called without any `Authorization` header
- **THEN** the response is HTTP 200 (never 401 or 403)

#### Scenario: Catalog tag appears in OpenAPI schema
- **WHEN** `GET /docs` or `GET /openapi.json` is accessed
- **THEN** a section tagged `"catalog"` appears in the OpenAPI schema
- **THEN** both catalog endpoints appear under that tag
