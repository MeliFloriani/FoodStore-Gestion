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
