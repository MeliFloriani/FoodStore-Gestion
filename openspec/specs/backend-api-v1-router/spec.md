# backend-api-v1-router Specification

## Purpose
API v1 router base with liveness and readiness health endpoints. Introduced in Change 02 (backend-core-foundation).
## Requirements
### Requirement: Router base API v1 registrado en main
El sistema SHALL proveer un `APIRouter` en `app/api/v1/router.py` con prefijo `/api/v1` (tomado de `settings.API_V1_PREFIX`). Este router SHALL estar incluido en `app/main.py` para que todos los endpoints de dominio futuros que lo importen hereden el prefijo automáticamente.

#### Scenario: Router v1 incluido en la app
- **WHEN** se inspecciona las rutas registradas en la app FastAPI
- **THEN** existe al menos una ruta con prefijo `/api/v1`

#### Scenario: Prefijo tomado de settings
- **WHEN** `settings.API_V1_PREFIX` es `/api/v1`
- **THEN** el router base usa exactamente ese prefijo sin duplicación

### Requirement: Health liveness endpoint conservado
El endpoint `GET /health` SHALL permanecer operativo sin autenticación ni dependencias de base de datos. Devuelve `{"status": "ok"}` con HTTP 200.

#### Scenario: Health liveness responde sin BD
- **WHEN** se realiza `GET /health` con la BD inaccesible
- **THEN** el servidor devuelve HTTP 200 con `{"status": "ok"}`

#### Scenario: Health liveness sin autenticación
- **WHEN** se realiza `GET /health` sin headers de autenticación
- **THEN** el servidor devuelve HTTP 200 (no 401 ni 403)

### Requirement: Health readiness endpoint con ping a BD
El sistema SHALL proveer `GET /api/v1/health` que realiza un ping a la base de datos (`SELECT 1`). Si la BD responde, devuelve HTTP 200 con `{"status": "ok", "database": "ok", "version": "<APP_VERSION>"}`. Si la BD no responde, devuelve HTTP 503 con `{"status": "error", "database": "error"}`.

#### Scenario: Readiness con BD disponible
- **WHEN** se realiza `GET /api/v1/health` con PostgreSQL accesible
- **THEN** el servidor devuelve HTTP 200
- **THEN** el body contiene `"database": "ok"` y `"version"` con el valor de `settings.APP_VERSION`

#### Scenario: Readiness con BD no disponible
- **WHEN** se realiza `GET /api/v1/health` con PostgreSQL inaccesible
- **THEN** el servidor devuelve HTTP 503
- **THEN** el body contiene `"database": "error"`

#### Scenario: Readiness sin autenticación
- **WHEN** se realiza `GET /api/v1/health` sin headers de autenticación
- **THEN** el servidor devuelve HTTP 200 o 503 (nunca 401 ni 403)

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

