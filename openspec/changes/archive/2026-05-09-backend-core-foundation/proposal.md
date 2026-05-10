## Why

El backend arrancado en Change 01 tiene una aplicación FastAPI mínima sin configuración tipada, sin conexión a base de datos, sin manejo de errores estandarizado ni middlewares de producción. Cualquier change de dominio que intente construirse sobre esta base tendría que tomar decisiones de infraestructura ad-hoc, generando inconsistencia y deuda técnica inmediata. Change 02 establece la capa de infraestructura técnica completa para que los cambios de dominio futuros (a partir de Change 03) puedan enfocarse exclusivamente en lógica de negocio.

## What Changes

- **Configuración tipada**: `app/core/config.py` con `Settings(BaseSettings)` via pydantic-settings v2, singleton `get_settings()` con `lru_cache`. Variables: `DATABASE_URL`, `ENVIRONMENT`, `BACKEND_CORS_ORIGINS`, `API_V1_PREFIX`, `LOG_LEVEL`, `RATE_LIMIT_DEFAULT`.
- **Database core async**: `app/db/session.py` con `create_async_engine` (asyncpg), `AsyncSessionLocal`, pool configurado (`pool_size`, `max_overflow`, `pool_pre_ping=True`) y dependency `get_session()`. `app/db/base.py` con metadata y naming conventions de constraints para Alembic.
- **Modelo base reutilizable**: `app/models/base.py` con clase `Base(SQLModel)` que define columnas comunes: `id` (UUID), `created_at`, `updated_at`, `deleted_at` (soft delete). Naming conventions de constraints embebidas en el metadata.
- **Schemas base**: `app/schemas/base.py` con `Page[T]` genérico para paginación `{items, total, page, size, pages}` y `ProblemDetail` (RFC 7807).
- **Manejo de errores RFC 7807**: `app/core/exceptions.py` con jerarquía de excepciones de dominio base (`NotFoundError`, `ConflictError`, `ValidationError`, `UnauthorizedError`, `ForbiddenError`). `app/api/errors.py` con handlers FastAPI que emiten `application/problem+json`.
- **CORS y middlewares**: CORS configurable via `BACKEND_CORS_ORIGINS`, middleware de `request_id` (UUID por request propagado al logger), middleware de logging estructurado.
- **Rate limiting base**: `app/core/rate_limit.py` con `Limiter` de slowapi usando `RATE_LIMIT_DEFAULT`. Handler para `RateLimitExceeded` → RFC 7807. Sin reglas por endpoint.
- **Logging estructurado**: `app/core/logging.py` con configuración global structlog (formato JSON), helper `get_logger(name)`, integración con request_id.
- **Router API v1**: `app/api/v1/router.py` con `APIRouter(prefix="/api/v1")`. Health endpoints: `GET /health` (liveness, sin BD) conservado; `GET /api/v1/health` (readiness, ping a BD). Ambos registrados en `main.py`.
- **Dependencias nuevas** en `pyproject.toml`: `sqlmodel`, `asyncpg`, `alembic`, `pydantic-settings`, `slowapi`, `structlog`. Dev: `pytest-cov`, `anyio`.
- **Tests de infraestructura**: `backend/tests/conftest.py` con fixtures `async_client`, `test_db_session`, `override_settings`. Tests de: settings carga, error handlers RFC 7807, CORS headers, health readiness.
- **`.env.example` ampliado** con todas las variables nuevas de Settings.

**Exclusión documentada — UnitOfWork y BaseRepository**: Según CHANGES.md, Change 04 (`backend-base-patterns`) implementa `BaseRepository[T]` genérico con CRUD + soft delete y `UnitOfWork` como context manager async. Estos componentes NO van en Change 02 para respetar la dependencia declarada: Change 04 depende de Change 03 (que define los modelos de dominio). Change 02 provee la sesión async pero la gestión de transacciones/repositorios es responsabilidad de Change 04.

**Exclusión documentada — Alembic init completo**: Change 03 define el ERD completo y genera las migraciones reproducibles. Change 02 agrega `alembic` como dependencia (runtime) para que esté disponible, pero NO ejecuta `alembic init` ni genera archivos de configuración — eso es alcance de Change 03.

## Capabilities

### New Capabilities

- `backend-config`: Configuración tipada con pydantic-settings v2, variables de entorno, singleton con lru_cache.
- `backend-database-core`: Engine async asyncpg, pool configurado, sesión async, metadata con naming conventions, modelo base con columnas comunes y soft delete.
- `backend-error-handling`: Jerarquía de excepciones de dominio base, handlers RFC 7807 (application/problem+json), handler de validación Pydantic y excepciones no capturadas.
- `backend-middleware-stack`: CORS configurable, request_id propagado, logging estructurado por request, rate limiting base con slowapi.
- `backend-api-v1-router`: Prefijo `/api/v1`, health liveness `/health` y readiness `/api/v1/health`, extensible para routers de dominio.
- `backend-structured-logging`: Configuración global structlog JSON, helper get_logger, integración con request_id middleware.
- `backend-pagination-schema`: Tipo genérico `Page[T]` y `ProblemDetail` reutilizables por todos los changes de dominio.

### Modified Capabilities

- `backend-scaffold`: Se modifican los requirements de dependencias declaradas en `pyproject.toml` (se agregan las deps runtime del Change 02) y el health check se extiende con el endpoint de readiness. Los requirements de estructura de carpetas y linting no cambian.

## Impact

- **Archivos modificados**: `backend/pyproject.toml`, `backend/.env.example`, `backend/app/main.py`, `backend/app/core/config.py`.
- **Archivos nuevos**: `backend/app/db/session.py`, `backend/app/db/base.py`, `backend/app/models/base.py`, `backend/app/schemas/base.py`, `backend/app/core/exceptions.py`, `backend/app/core/rate_limit.py`, `backend/app/core/logging.py`, `backend/app/api/errors.py`, `backend/app/api/v1/__init__.py`, `backend/app/api/v1/router.py`, `backend/tests/conftest.py`, `backend/tests/test_infrastructure.py`.
- **Dependencias nuevas**: `sqlmodel`, `asyncpg`, `alembic`, `pydantic-settings`, `slowapi`, `structlog` (runtime). `pytest-cov`, `anyio` (dev).
- **Sin cambios**: Frontend, estructura de carpetas ya existente, archivos `__init__.py` vacíos existentes.
- **Cambios de comportamiento**: `GET /health` sigue respondiendo sin BD. Se agrega `GET /api/v1/health` que requiere BD activa. Todos los errores no manejados pasan a emitir `application/problem+json`.
