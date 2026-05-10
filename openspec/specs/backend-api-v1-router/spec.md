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
