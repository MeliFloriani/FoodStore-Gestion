# backend-error-handling Specification

## Purpose
Domain exception hierarchy and RFC 7807 (Problem Details) HTTP error handlers. Introduced in Change 02 (backend-core-foundation).

## Requirements

### Requirement: Jerarquía de excepciones de dominio base
El sistema SHALL proveer en `app/core/exceptions.py` una clase raíz `AppError(Exception)` y las subclases base: `NotFoundError`, `ConflictError`, `AppValidationError`, `UnauthorizedError`, `ForbiddenError`. Cada clase SHALL tener un atributo `status_code: int` y opcionalmente `detail: str` y `code: str`.

#### Scenario: NotFoundError instanciable con mensaje
- **WHEN** se lanza `NotFoundError("Producto no encontrado")`
- **THEN** la excepción tiene `status_code = 404` y `detail = "Producto no encontrado"`

#### Scenario: ConflictError con código semántico
- **WHEN** se lanza `ConflictError("Email ya registrado", code="email_conflict")`
- **THEN** la excepción tiene `status_code = 409`, `detail = "Email ya registrado"`, `code = "email_conflict"`

#### Scenario: ForbiddenError con status 403
- **WHEN** se lanza `ForbiddenError()`
- **THEN** la excepción tiene `status_code = 403`

### Requirement: Handlers FastAPI que emiten RFC 7807
El sistema SHALL registrar en `app/main.py` los exception handlers definidos en `app/api/errors.py` para:
- `AppError` (y subclases) → HTTP con el `status_code` de la excepción.
- `RequestValidationError` (Pydantic v2) → HTTP 422.
- `Exception` genérica no capturada → HTTP 500.
Todos los handlers SHALL emitir `Content-Type: application/problem+json` y body con al menos: `type`, `title`, `status`, `detail`, `instance` (path del request). Opcionalmente: `code` (string interno) y `field` (para errores de campo).

#### Scenario: NotFoundError produce respuesta RFC 7807
- **WHEN** un endpoint lanza `NotFoundError("Producto no encontrado")`
- **THEN** el cliente recibe HTTP 404
- **THEN** el header `Content-Type` es `application/problem+json`
- **THEN** el body JSON contiene `"status": 404`, `"detail": "Producto no encontrado"`

#### Scenario: RequestValidationError produce respuesta RFC 7807 con field
- **WHEN** el cliente envía un body con campo requerido faltante
- **THEN** el cliente recibe HTTP 422
- **THEN** el header `Content-Type` es `application/problem+json`
- **THEN** el body contiene `"status": 422` y lista de errores con `field` indicando el campo inválido

#### Scenario: Excepción no capturada produce HTTP 500
- **WHEN** un endpoint lanza una excepción Python genérica no capturada (ej: `RuntimeError`)
- **THEN** el cliente recibe HTTP 500
- **THEN** el header `Content-Type` es `application/problem+json`
- **THEN** el body contiene `"status": 500` y NO expone el traceback al cliente
- **THEN** el error completo (con traceback) es registrado en el logger del servidor

#### Scenario: ConflictError incluye code en el body
- **WHEN** un endpoint lanza `ConflictError("Email ya registrado", code="email_conflict")`
- **THEN** el cliente recibe HTTP 409
- **THEN** el body JSON contiene `"code": "email_conflict"`

### Requirement: RateLimitExceeded emite RFC 7807
El handler de `RateLimitExceeded` (de slowapi) SHALL emitir HTTP 429 con `Content-Type: application/problem+json` y body RFC 7807 con `"status": 429`.

#### Scenario: Rate limit excedido produce RFC 7807
- **WHEN** un cliente supera el límite de requests configurado
- **THEN** recibe HTTP 429
- **THEN** el header `Content-Type` es `application/problem+json`
- **THEN** el body contiene `"status": 429` y `"title"` descriptivo
