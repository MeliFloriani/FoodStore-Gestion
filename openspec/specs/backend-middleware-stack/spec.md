# backend-middleware-stack Specification

## Purpose
CORS, request-ID injection, and rate limiting middleware stack. Introduced in Change 02 (backend-core-foundation).

## Requirements

### Requirement: CORS configurable via settings
El sistema SHALL registrar `CORSMiddleware` de Starlette en `app/main.py` usando `settings.BACKEND_CORS_ORIGINS` como lista de orígenes permitidos. SHALL permitir credentials, todos los métodos y todos los headers.

#### Scenario: Request con origen permitido incluye headers CORS
- **WHEN** el cliente envía `OPTIONS` o cualquier método HTTP con `Origin: http://localhost:5173` y ese origen está en `BACKEND_CORS_ORIGINS`
- **THEN** la respuesta incluye `Access-Control-Allow-Origin: http://localhost:5173`
- **THEN** la respuesta incluye `Access-Control-Allow-Credentials: true`

#### Scenario: Request con origen no permitido no incluye headers CORS
- **WHEN** el cliente envía un request con `Origin: http://evil.example.com` y ese origen no está en `BACKEND_CORS_ORIGINS`
- **THEN** la respuesta no incluye `Access-Control-Allow-Origin`

### Requirement: Middleware de request_id
El sistema SHALL incluir un middleware ASGI que, para cada request entrante: genere un UUID v4 único (`request_id`), lo almacene en una `ContextVar` accesible por el resto del stack, e inyecte el header `X-Request-ID` en la respuesta con ese mismo valor.

#### Scenario: Respuesta incluye X-Request-ID
- **WHEN** el cliente envía cualquier request al servidor
- **THEN** la respuesta incluye el header `X-Request-ID` con un UUID v4 válido

#### Scenario: Requests consecutivos tienen request_id únicos
- **WHEN** se realizan dos requests consecutivos
- **THEN** los valores de `X-Request-ID` en cada respuesta son diferentes

#### Scenario: request_id disponible en ContextVar durante el request
- **WHEN** cualquier logger o handler accede a la ContextVar de request_id durante el procesamiento de un request
- **THEN** obtiene el mismo UUID que aparece en el header `X-Request-ID` de la respuesta

### Requirement: Rate limiting base con slowapi
El sistema SHALL instanciar un `Limiter` de slowapi con `key_func=get_remote_address` y `default_limits=[settings.RATE_LIMIT_DEFAULT]` en `app/core/rate_limit.py`. El limiter SHALL estar adjunto a la aplicación FastAPI y el handler de `RateLimitExceeded` SHALL estar registrado.

#### Scenario: Limiter adjunto a la app FastAPI
- **WHEN** se inspecciona `app.state.limiter`
- **THEN** es una instancia del `Limiter` de slowapi configurado

#### Scenario: Handler RateLimitExceeded registrado
- **WHEN** se inspecciona los exception handlers de la app FastAPI
- **THEN** existe un handler para la excepción `RateLimitExceeded` de slowapi

### Requirement: Swagger y ReDoc disponibles
El sistema SHALL exponer la documentación interactiva de la API en `/docs` (Swagger UI) y en `/redoc` (ReDoc). Ambos endpoints deben estar habilitados en la instancia FastAPI.

#### Scenario: Swagger UI accesible
- **WHEN** se realiza `GET /docs`
- **THEN** el servidor devuelve HTTP 200 con contenido HTML de Swagger UI

#### Scenario: ReDoc accesible
- **WHEN** se realiza `GET /redoc`
- **THEN** el servidor devuelve HTTP 200 con contenido HTML de ReDoc
