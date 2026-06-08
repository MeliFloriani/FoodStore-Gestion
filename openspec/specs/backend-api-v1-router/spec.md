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

### Requirement: Admin metricas router mounted in build_v1_router
The `build_v1_router` factory in `backend/app/api/v1/router.py` SHALL include the admin metricas router from `backend/app/modules/admin/metricas/router.py` via `router.include_router(metricas_router, prefix="/admin/metricas", tags=["admin-metricas"])`. The final mounted paths SHALL be:
- `GET /api/v1/admin/metricas/resumen`
- `GET /api/v1/admin/metricas/ventas`
- `GET /api/v1/admin/metricas/productos-top`
- `GET /api/v1/admin/metricas/pedidos-por-estado`

#### Scenario: Metricas endpoints reachable under /api/v1/admin/metricas
- **WHEN** the app boots and routes are inspected
- **THEN** `GET /api/v1/admin/metricas/resumen` exists as a registered route
- **THEN** `GET /api/v1/admin/metricas/ventas` exists as a registered route
- **THEN** `GET /api/v1/admin/metricas/productos-top` exists as a registered route
- **THEN** `GET /api/v1/admin/metricas/pedidos-por-estado` exists as a registered route

#### Scenario: Metricas router prefix does not duplicate
- **WHEN** the final route paths are resolved
- **THEN** the path is exactly `/api/v1/admin/metricas/resumen` (not `/api/v1/api/v1/admin/metricas/resumen`)

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

---

## ADDED Requirements

### Requirement: Router de direcciones montado en build_v1_router
La función `build_v1_router` en `backend/app/api/v1/router.py` SHALL incluir el router de direcciones importado desde `backend/app/api/v1/direcciones.py`. El router de direcciones SHALL tener prefijo `/direcciones` y tag `"Direcciones"` para que todos sus endpoints sean accesibles en `{settings.API_V1_PREFIX}/direcciones/*` (ej: `/api/v1/direcciones`, `/api/v1/direcciones/{id}`, `/api/v1/direcciones/{id}/principal`).

El router de direcciones SHALL incluirse de forma análoga a los routers existentes (auth, profile, categorias, productos, ingredientes), sin modificar el prefijo `/api/v1` del router base.

> IMPORTANTE: El endpoint `PATCH /{id}/principal` DEBE declararse ANTES de `PATCH /{id}` en el router de direcciones para evitar ambigüedad de path matching en FastAPI. FastAPI evalúa rutas en orden de declaración.

#### Scenario: Endpoint POST /api/v1/direcciones es accesible
- **WHEN** se inspecciona las rutas registradas en la app FastAPI
- **THEN** existe la ruta `POST /api/v1/direcciones` con tag "Direcciones"

#### Scenario: Endpoint PATCH /api/v1/direcciones/{id}/principal es accesible
- **WHEN** se inspecciona las rutas registradas en la app FastAPI
- **THEN** existe la ruta `PATCH /api/v1/direcciones/{id}/principal` con tag "Direcciones"

#### Scenario: Routers existentes no se ven afectados
- **WHEN** se agrega el router de direcciones en `build_v1_router`
- **THEN** los endpoints pre-existentes (`/api/v1/auth/*`, `/api/v1/perfil`, etc.) siguen operativos sin cambios

## ADDED Requirements

### Requirement: Pedidos-validacion router montado en build_v1_router

La función `build_v1_router(settings: Settings) -> APIRouter` en `backend/app/api/v1/router.py` SHALL incluir el router de validación pre-checkout importado desde `backend/app/api/v1/pedidos_validar.py` mediante `from app.api.v1.pedidos_validar import pedidos_validar_router` seguido de `router.include_router(pedidos_validar_router, prefix="/pedidos", tags=["pedidos-validacion"])`. El endpoint resultante SHALL quedar montado en `{settings.API_V1_PREFIX}/pedidos/validar` (ej: `/api/v1/pedidos/validar`).

El router de pedidos-validación SHALL NOT incluirse en `app/main.py` directamente — siempre se registra a través de `build_v1_router`.

El router SHALL declarar su propio path `/validar` (sin prefijo `/pedidos` — ese lo aporta `build_v1_router`).

#### Scenario: Endpoint POST /api/v1/pedidos/validar es accesible
- **WHEN** la app arranca y se inspeccionan las rutas registradas
- **THEN** existe la ruta `POST /api/v1/pedidos/validar` con tag `"pedidos-validacion"`

#### Scenario: Router pedidos-validacion no duplica el prefijo v1
- **WHEN** se resuelven los paths finales de las rutas
- **THEN** el endpoint de validación queda exactamente en `/api/v1/pedidos/validar` (no `/api/v1/api/v1/pedidos/validar`)

#### Scenario: Routers existentes no se ven afectados
- **WHEN** se agrega el router de pedidos-validación en `build_v1_router`
- **THEN** los endpoints pre-existentes (`/api/v1/auth/*`, `/api/v1/productos/*`, `/api/v1/catalog/*`, `/api/v1/profile`, `/api/v1/direcciones/*`) siguen operativos sin cambios

#### Scenario: Tag pedidos-validacion aparece en schema OpenAPI
- **WHEN** se accede a `GET /docs` o `GET /openapi.json`
- **THEN** existe una sección con tag `"pedidos-validacion"` en el schema OpenAPI
- **THEN** el endpoint `POST /api/v1/pedidos/validar` aparece bajo ese tag

## MODIFIED Requirements

### Requirement: Pedidos router montado en build_v1_router

La función `build_v1_router(settings: Settings) -> APIRouter` en `backend/app/api/v1/router.py` SHALL incluir el router de pedidos importado desde `backend/app/api/v1/pedidos.py` mediante `from app.api.v1.pedidos import pedidos_router` seguido de `router.include_router(pedidos_router, prefix="/pedidos", tags=["pedidos"])`. El endpoint resultante SHALL quedar montado en `{settings.API_V1_PREFIX}/pedidos` (ej: `/api/v1/pedidos`).

El router de pedidos SHALL NOT incluirse en `app/main.py` directamente — siempre se registra a través de `build_v1_router`.

El router SHALL declarar sus propios paths sin prefijo `/pedidos` (ese lo aporta `build_v1_router`). El path de creación de pedido SHALL ser `POST /` (raíz del router), resultando en `POST /api/v1/pedidos`.

> IMPORTANTE: El router de pedidos (Change 17) y el router de pedidos-validacion (Change 16) comparten el mismo prefijo `/pedidos` en `build_v1_router`. El router de Change 16 define el path `/validar`; el de Change 17 define el path `/` (raíz). FastAPI resuelve correctamente ambos sin colisión.

#### Scenario: Endpoint POST /api/v1/pedidos es accesible
- **WHEN** la app arranca y se inspeccionan las rutas registradas
- **THEN** existe la ruta `POST /api/v1/pedidos` con tag `"pedidos"`

#### Scenario: Router pedidos no duplica el prefijo v1
- **WHEN** se resuelven los paths finales de las rutas
- **THEN** el endpoint de creación queda exactamente en `POST /api/v1/pedidos` (no `/api/v1/api/v1/pedidos`)

#### Scenario: Router pedidos coexiste con router pedidos-validacion sin colisión
- **WHEN** la app arranca con ambos routers montados bajo el prefijo `/pedidos`
- **THEN** `POST /api/v1/pedidos/validar` sigue operativo (Change 16)
- **THEN** `POST /api/v1/pedidos` es el nuevo endpoint de creación (Change 17)
- **THEN** no hay ambigüedad de path matching entre los dos routers

#### Scenario: Routers existentes no se ven afectados
- **WHEN** se agrega el router de pedidos en `build_v1_router`
- **THEN** los endpoints pre-existentes (`/api/v1/auth/*`, `/api/v1/productos/*`, `/api/v1/catalog/*`, `/api/v1/profile`, `/api/v1/direcciones/*`, `/api/v1/pedidos/validar`) siguen operativos sin cambios

#### Scenario: Tag pedidos aparece en schema OpenAPI
- **WHEN** se accede a `GET /docs` o `GET /openapi.json`
- **THEN** existe una sección con tag `"pedidos"` en el schema OpenAPI
- **THEN** el endpoint `POST /api/v1/pedidos` aparece bajo ese tag

## ADDED Requirements (Change 19: payments-mercadopago-integration)

### Requirement: Pagos router mounted in build_v1_router
The `build_v1_router(settings: Settings) -> APIRouter` factory in `backend/app/api/v1/router.py` SHALL include the pagos router from `backend/app/pagos/router.py` via `from app.pagos.router import pagos_router` followed by `router.include_router(pagos_router, prefix="/pagos", tags=["pagos"])`. The final mounted paths SHALL be:

- `POST /api/v1/pagos` — create payment (CLIENT) — canonical REST endpoint
- `POST /api/v1/pagos/crear` — **alias** pointing to the same handler as `POST /api/v1/pagos` (for Integrador §5.4 rubric compatibility — see design.md D-11). Returns identical response.
- `POST /api/v1/pagos/webhook` — IPN handler (public)
- `GET /api/v1/pagos/{pedido_id}/latest` — latest pago for a pedido (CLIENT, PEDIDOS, ADMIN)

The pagos router SHALL NOT be included in `app/main.py` directly — always registered through `build_v1_router`.

> **Alias declaration order**: `POST /pagos/crear` MUST be declared BEFORE `GET /pagos/{pedido_id}/latest` (and after `POST /pagos/webhook`) to avoid path matching ambiguity with the dynamic `{pedido_id}` segment.

> IMPORTANT: `POST /pagos/webhook` MUST be declared BEFORE `GET /pagos/{pedido_id}/latest` in the router to avoid path matching ambiguity. FastAPI evaluates routes in declaration order; the static segment `webhook` must precede the dynamic `{pedido_id}` segment.

#### Scenario: Alias POST /api/v1/pagos/crear is accessible and equivalent
- **WHEN** the app boots and routes are inspected
- **THEN** `POST /api/v1/pagos/crear` exists as a registered route with tag `"pagos"`
- **THEN** it delegates to the same handler as `POST /api/v1/pagos`
- **THEN** it returns the same HTTP 201 `PagoResponse` on success

#### Scenario: Endpoint POST /api/v1/pagos is accessible
- **WHEN** the app boots and routes are inspected
- **THEN** `POST /api/v1/pagos` exists as a registered route with tag `"pagos"`
- **THEN** the route requires role `CLIENT`

#### Scenario: Endpoint POST /api/v1/pagos/webhook is accessible
- **WHEN** the app boots and routes are inspected
- **THEN** `POST /api/v1/pagos/webhook` exists as a registered route with tag `"pagos"`
- **THEN** the route has NO JWT auth dependency (public endpoint)

#### Scenario: Endpoint GET /api/v1/pagos/{pedido_id}/latest is accessible
- **WHEN** the app boots and routes are inspected
- **THEN** `GET /api/v1/pagos/{pedido_id}/latest` exists as a registered route with tag `"pagos"`
- **THEN** the route requires roles `CLIENT`, `PEDIDOS`, or `ADMIN`

#### Scenario: Pagos router prefix does not duplicate the v1 prefix
- **WHEN** the final route paths are resolved
- **THEN** the create payment endpoint is exactly `POST /api/v1/pagos` (not `/api/v1/api/v1/pagos`)
- **THEN** the webhook endpoint is exactly `POST /api/v1/pagos/webhook`

#### Scenario: Pagos tag appears in OpenAPI schema
- **WHEN** `GET /docs` or `GET /openapi.json` is accessed
- **THEN** a section tagged `"pagos"` appears in the OpenAPI schema
- **THEN** all pagos endpoints appear under that tag

#### Scenario: Existing routers are unaffected
- **WHEN** the pagos router is added to `build_v1_router`
- **THEN** all pre-existing endpoints (`/api/v1/auth/*`, `/api/v1/productos/*`, `/api/v1/catalog/*`, `/api/v1/profile`, `/api/v1/direcciones/*`, `/api/v1/pedidos/*`) remain operational

---

## ADDED Requirements (Change 18: order-state-machine-transitions)

### Requirement: Tres nuevos endpoints pedidos registrados en build_v1_router

La función `build_v1_router(settings: Settings) -> APIRouter` en `backend/app/api/v1/router.py` SHALL exponer tres nuevos endpoints bajo el prefijo `/pedidos` (ya registrado por Change 17):

1. `PATCH /api/v1/pedidos/{id}/estado` — transición de estado (staff)
2. `DELETE /api/v1/pedidos/{id}` — cancelación propia (CLIENT)
3. `GET /api/v1/pedidos/{id}/historial` — historial de estados

Estos endpoints SHALL registrarse en el mismo `pedidos_router` de `backend/app/api/v1/pedidos.py` que ya contiene `POST /` (Change 17). No se crea un router adicional.

> IMPORTANTE: `PATCH /{id}/estado` y `GET /{id}/historial` deben declararse ANTES de cualquier ruta `/{id}` genérica (si existe) para evitar ambigüedad de path matching en FastAPI. FastAPI evalúa rutas en orden de declaración.

#### Scenario: Endpoint PATCH /api/v1/pedidos/{id}/estado es accesible
- **WHEN** la app arranca y se inspeccionan las rutas registradas
- **THEN** existe la ruta `PATCH /api/v1/pedidos/{id}/estado` con tag `"pedidos"`
- **THEN** la ruta requiere roles `PEDIDOS` o `ADMIN` (dependency `require_role`)

#### Scenario: Endpoint DELETE /api/v1/pedidos/{id} es accesible
- **WHEN** la app arranca y se inspeccionan las rutas registradas
- **THEN** existe la ruta `DELETE /api/v1/pedidos/{id}` con tag `"pedidos"`
- **THEN** la ruta requiere rol `CLIENT` (dependency `require_role`)

#### Scenario: Endpoint GET /api/v1/pedidos/{id}/historial es accesible
- **WHEN** la app arranca y se inspeccionan las rutas registradas
- **THEN** existe la ruta `GET /api/v1/pedidos/{id}/historial` con tag `"pedidos"`
- **THEN** la ruta requiere roles `CLIENT`, `PEDIDOS` o `ADMIN` (STOCK excluido)

#### Scenario: Nuevos endpoints no duplican el prefijo v1
- **WHEN** se resuelven los paths finales de las rutas
- **THEN** el endpoint de transición queda exactamente en `/api/v1/pedidos/{id}/estado`
- **THEN** ningún path duplica el prefijo `/api/v1/api/v1/`

#### Scenario: Routers existentes no se ven afectados
- **WHEN** se agregan los tres nuevos endpoints al pedidos_router
- **THEN** `POST /api/v1/pedidos` (Change 17) sigue operativo
- **THEN** `POST /api/v1/pedidos/validar` (Change 16) sigue operativo
- **THEN** todos los demás routers (`/auth/*`, `/productos/*`, `/catalog/*`, `/profile`, `/direcciones/*`) siguen operativos

## ADDED Requirements (Change 20: orders-visualization)

### Requirement: Pedidos listing y detail endpoints registrados en build_v1_router

La función `build_v1_router(settings: Settings) -> APIRouter` en `backend/app/api/v1/router.py` SHALL exponer dos nuevos endpoints bajo el prefijo `/pedidos` (ya registrado por Changes 17 y 18):

1. `GET /api/v1/pedidos` — listado paginado con discriminación RBAC (CLIENT/PEDIDOS/ADMIN)
2. `GET /api/v1/pedidos/{id}` — detalle completo del pedido (CLIENT propietario/PEDIDOS/ADMIN)

Estos endpoints SHALL registrarse en el mismo `pedidos_router` de `backend/app/api/v1/pedidos.py` que ya contiene `POST /`, `PATCH /{id}/estado`, `DELETE /{id}`, y `GET /{id}/historial`. No se crea un router adicional.

> IMPORTANTE: `GET /{id}/historial` (Change 18) y `GET /` (listado, este change) deben declararse con paths estáticos o raíz ANTES de `GET /{id}` (detalle dinámico) para evitar ambigüedad de path matching en FastAPI. Orden recomendado: `POST /` → `GET /` → `PATCH /{id}/estado` → `GET /{id}/historial` → `GET /{id}` → `DELETE /{id}`.

#### Scenario: Endpoint GET /api/v1/pedidos es accesible con rol CLIENT
- **WHEN** la app arranca y se inspeccionan las rutas registradas
- **THEN** existe la ruta `GET /api/v1/pedidos` con tag `"pedidos"`
- **THEN** la ruta requiere roles `CLIENT`, `PEDIDOS` o `ADMIN` (STOCK excluido)

#### Scenario: Endpoint GET /api/v1/pedidos/{id} es accesible
- **WHEN** la app arranca y se inspeccionan las rutas registradas
- **THEN** existe la ruta `GET /api/v1/pedidos/{id}` con tag `"pedidos"`
- **THEN** la ruta requiere autenticación Bearer

#### Scenario: GET /api/v1/pedidos no colisiona con GET /api/v1/pedidos/{id}
- **WHEN** la app arranca con ambas rutas registradas
- **THEN** `GET /api/v1/pedidos` devuelve el listado paginado
- **THEN** `GET /api/v1/pedidos/some-uuid` devuelve el detalle de ese pedido
- **THEN** no hay ambigüedad de path matching

#### Scenario: Rutas existentes no se ven afectadas
- **WHEN** se agregan los dos nuevos endpoints GET al pedidos_router
- **THEN** `POST /api/v1/pedidos` (Change 17) sigue operativo
- **THEN** `PATCH /api/v1/pedidos/{id}/estado` (Change 18) sigue operativo
- **THEN** `DELETE /api/v1/pedidos/{id}` (Change 18) sigue operativo
- **THEN** `GET /api/v1/pedidos/{id}/historial` (Change 18) sigue operativo
- **THEN** todos los demás routers (`/auth/*`, `/productos/*`, `/catalog/*`, `/profile`, `/direcciones/*`, `/pedidos/validar`, `/pagos/*`) siguen operativos

#### Scenario: Nuevos endpoints no duplican el prefijo v1
- **WHEN** se resuelven los paths finales
- **THEN** el listado queda exactamente en `GET /api/v1/pedidos`
- **THEN** el detalle queda exactamente en `GET /api/v1/pedidos/{id}`
- **THEN** ningún path duplica el prefijo `/api/v1/api/v1/`

#### Scenario: Tag pedidos contiene los nuevos endpoints en OpenAPI
- **WHEN** se accede a `GET /docs` o `GET /openapi.json`
- **THEN** `GET /api/v1/pedidos` aparece bajo el tag `"pedidos"`
- **THEN** `GET /api/v1/pedidos/{id}` aparece bajo el tag `"pedidos"`

## ADDED Requirements (Change 21: admin-users-management)

### Requirement: Admin-usuarios router mounted in build_v1_router

The `build_v1_router(settings: Settings) -> APIRouter` factory in `backend/app/api/v1/router.py` SHALL include the admin-usuarios router from `backend/app/api/v1/admin_usuarios.py` via `from app.api.v1.admin_usuarios import admin_usuarios_router` followed by `router.include_router(admin_usuarios_router, prefix="/admin/usuarios", tags=["admin-usuarios"])`. The final mounted paths SHALL be:

- `GET /api/v1/admin/usuarios` — paginated user list (ADMIN only)
- `GET /api/v1/admin/usuarios/{id}` — user detail (ADMIN only)
- `PUT /api/v1/admin/usuarios/{id}` — update user data (ADMIN only)
- `PUT /api/v1/admin/usuarios/{id}/roles` — update user roles with last-admin guard (ADMIN only)
- `PATCH /api/v1/admin/usuarios/{id}/estado` — deactivate/reactivate user (ADMIN only)

The admin-usuarios router SHALL NOT be included in `app/main.py` directly — always registered through `build_v1_router`.

All 5 endpoints require `Depends(require_role("ADMIN"))`.

> IMPORTANT: Route declaration order within the router: `GET /`, `GET /{id}`, `PUT /{id}/roles`, `PATCH /{id}/estado`, `PUT /{id}`. This order ensures sub-resource paths (`/{id}/roles`, `/{id}/estado`) are matched before the generic `/{id}` PUT.

#### Scenario: Admin-usuarios endpoints are accessible under /api/v1/admin/usuarios
- **WHEN** the app boots and routes are inspected
- **THEN** `GET /api/v1/admin/usuarios` exists as a registered route with tag `"admin-usuarios"`
- **THEN** `GET /api/v1/admin/usuarios/{id}` exists as a registered route
- **THEN** `PUT /api/v1/admin/usuarios/{id}` exists as a registered route
- **THEN** `PUT /api/v1/admin/usuarios/{id}/roles` exists as a registered route
- **THEN** `PATCH /api/v1/admin/usuarios/{id}/estado` exists as a registered route

#### Scenario: Admin-usuarios endpoints require ADMIN role
- **WHEN** any of the 5 admin-usuarios endpoints is called without an ADMIN-role JWT
- **THEN** the response is HTTP 403 (for authenticated non-ADMIN) or HTTP 401 (for unauthenticated)

#### Scenario: Admin-usuarios router prefix does not duplicate the v1 prefix
- **WHEN** the final route paths are resolved
- **THEN** the list endpoint path is exactly `/api/v1/admin/usuarios` (not `/api/v1/api/v1/admin/usuarios`)

#### Scenario: Admin-usuarios tag appears in OpenAPI schema
- **WHEN** `GET /docs` or `GET /openapi.json` is accessed
- **THEN** a section tagged `"admin-usuarios"` appears in the OpenAPI schema
- **THEN** all 5 admin-usuarios endpoints appear under that tag

#### Scenario: Existing routers are unaffected
- **WHEN** the admin-usuarios router is added to `build_v1_router`
- **THEN** all pre-existing endpoints (`/api/v1/auth/*`, `/api/v1/productos/*`, `/api/v1/catalog/*`, `/api/v1/profile`, `/api/v1/direcciones/*`, `/api/v1/pedidos/*`, `/api/v1/pagos/*`) remain operational

