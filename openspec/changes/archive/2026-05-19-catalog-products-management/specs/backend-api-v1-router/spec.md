# backend-api-v1-router — Delta Spec (Change 11)

## ADDED Requirements

### Requirement: Productos router mounted in build_v1_router
The `build_v1_router(settings: Settings) -> APIRouter` factory in `backend/app/api/v1/router.py` SHALL include the productos router from `backend/app/api/v1/productos.py` via `from app.api.v1.productos import productos_router` followed by `router.include_router(productos_router, prefix="/productos", tags=["productos"])`. The final mounted path for all product endpoints SHALL be `{settings.API_V1_PREFIX}/productos/*` (e.g. `/api/v1/productos`, `/api/v1/productos/{id}`, `/api/v1/productos/{id}/ingredientes`).

The productos router SHALL NOT be included in `app/main.py` directly — it is always registered through `build_v1_router`.

#### Scenario: Productos router is reachable under /api/v1/productos
- **WHEN** the app boots and routes are inspected
- **THEN** `GET /api/v1/productos` exists as a registered route
- **THEN** `GET /api/v1/productos/{id}` exists as a registered route
- **THEN** `POST /api/v1/productos` exists as a registered route
- **THEN** `PATCH /api/v1/productos/{id}` exists as a registered route
- **THEN** `DELETE /api/v1/productos/{id}` exists as a registered route
- **THEN** `PATCH /api/v1/productos/{id}/disponibilidad` exists as a registered route
- **THEN** `GET /api/v1/productos/{id}/ingredientes` exists as a registered route
- **THEN** `POST /api/v1/productos/{id}/ingredientes` exists as a registered route
- **THEN** `DELETE /api/v1/productos/{id}/ingredientes/{ing_id}` exists as a registered route

#### Scenario: Productos router prefix does not duplicate the v1 prefix
- **WHEN** the final route paths are resolved
- **THEN** the list endpoint path is exactly `/api/v1/productos` (not `/api/v1/api/v1/productos`)
- **THEN** no duplicate prefix appears in any registered product route

#### Scenario: productos tag appears in OpenAPI schema
- **WHEN** `GET /docs` or `GET /openapi.json` is accessed
- **THEN** a section tagged `"productos"` appears in the OpenAPI schema
- **THEN** all 9 product endpoints appear under that tag
