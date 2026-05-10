## Context

Change 01 dejó un backend FastAPI mínimo con tres dependencias (`fastapi`, `uvicorn`, `python-dotenv`) y una aplicación sin configuración tipada, sin motor de base de datos, sin estandarización de errores y sin middlewares. Change 02 establece toda la infraestructura técnica transversal que los cambios de dominio (Change 03 en adelante) necesitan consumir sin tener que tomar decisiones de infraestructura propias.

**Estado actual del código relevante:**
- `backend/app/main.py`: instancia FastAPI básica + `GET /health`.
- `backend/app/core/config.py`: solo docstring placeholder.
- `backend/app/db/__init__.py`, `backend/app/models/__init__.py`, etc.: vacíos.
- `backend/.env.example`: solo `ENVIRONMENT` y `BACKEND_CORS_ORIGINS`.
- `backend/pyproject.toml`: deps mínimas, sin SQLModel/asyncpg/pydantic-settings.

**Restricciones derivadas de CHANGES.md:**
- UnitOfWork y BaseRepository → Change 04 (depende de Change 03 para los modelos de dominio).
- Alembic `init` + `env.py` async + migraciones → Change 03.
- SECRET_KEY, JWT, passlib → Change 06.
- Modelos de dominio → Changes 09-17.

## Goals / Non-Goals

**Goals:**

- Configuración tipada y validada al arranque con pydantic-settings v2.
- Motor async PostgreSQL con pool de conexiones configurado y dependency `get_session()` lista para inyectar.
- Clase `Base(SQLModel)` con columnas comunes (`id` UUID, `created_at`, `updated_at`, `deleted_at`) reutilizable por todos los modelos de dominio.
- Jerarquía de excepciones de dominio base + handlers FastAPI que emiten RFC 7807 (`application/problem+json`).
- Middlewares de producción: CORS configurable, request_id UUID por request, logging estructurado.
- Rate limiting base con slowapi sin reglas específicas por endpoint.
- `Page[T]` y `ProblemDetail` como schemas reutilizables.
- Router `/api/v1` extensible; health liveness (`GET /health`) + readiness (`GET /api/v1/health` con ping a BD).
- Tests de infraestructura con fixtures async reutilizables.

**Non-Goals:**

- UnitOfWork y BaseRepository genérico → Change 04.
- Alembic `init`, `env.py`, migración inicial → Change 03.
- Modelos de dominio (Categoria, Producto, Usuario, etc.) → Changes 09-17.
- SECRET_KEY, JWT, passlib, bcrypt → Change 06.
- Credenciales MercadoPago → Change 19.
- Endpoints de negocio de ningún tipo.
- Reglas de rate limiting por endpoint → se aplican en cada change de dominio.

## Decisions

### D-01: Logging — structlog (no python-json-logger)

**Decisión**: usar `structlog` con renderer JSON.

**Alternativas consideradas**:
- `python-json-logger` + stdlib `logging`: más liviano pero menos ergonómico para structured logging contextual (añadir `request_id`, `user_id` por context vars es más manual).
- `loguru`: API simple pero no es el estándar en proyectos FastAPI de producción y su integración async es menos directa.

**Rationale**: structlog permite processors encadenables, integración nativa con `contextvars` (esencial para propagar `request_id` sin pasar el logger explícitamente), y su renderer JSON es production-ready. Configuración única en `app/core/logging.py`; el resto del código usa `get_logger(__name__)`.

### D-02: Soft delete — columna `deleted_at` (timestamp nullable)

**Decisión**: `deleted_at: datetime | None = Field(default=None)` en el modelo base.

**Alternativas consideradas**:
- `eliminado_en` (nombre en español): el Integrador v5.0 menciona ambas formas. Se elige `deleted_at` para consistencia con convenciones internacionales de ORM y evitar problemas con herramientas que asumen `_at` como sufijo temporal estándar.
- `is_deleted: bool`: no permite consultas por rango temporal ("eliminados en los últimos 7 días"); `deleted_at IS NOT NULL` es equivalente a `is_deleted = true` con información extra.

**Rationale**: `deleted_at` es un superset de `is_deleted`; permite auditoría temporal. Los repositories (Change 04) implementarán `include_deleted=False` por defecto en `list()`.

### D-03: Naming conventions de constraints para Alembic

**Decisión**: aplicar `MetaData(naming_convention={...})` estándar SQLAlchemy en `app/db/base.py`:

```python
convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}
```

**Rationale**: sin naming convention, Alembic genera nombres de constraint implícitos que varían entre vendors. Con la convention, las migraciones de Change 03 generarán nombres deterministas y reversibles.

### D-04: Modelo base — UUID v4 + auto-update de `updated_at`

**Decisión**:
```python
class Base(SQLModel, table=False):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_column_kwargs={"server_default": func.now()},
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_column_kwargs={"onupdate": lambda: datetime.now(UTC)},
    )
    deleted_at: datetime | None = Field(default=None)
```

**Alternativas consideradas**:
- `int` autoincrement: más simple, predecible en URLs, pero expone volumen de registros y tiene problemas de colisión en imports/seeds.
- `ULID`: ordenable temporalmente, pero requiere dependencia extra no declarada en el stack.
- `updated_at` con solo `default_factory` (sin `onupdate`): **rechazado tras auditoría** — `default_factory` solo se ejecuta en INSERT, no en UPDATE; resultaría en un timestamp mentiroso.

**Rationale**: UUID v4 es el estándar del stack (Integrador v5.0 implica UUIDs en `RefreshToken.token_hash` y entidades de dominio). Evita enumeration attacks. asyncpg soporta UUID nativo. `sa_column_kwargs={"onupdate": ...}` delega al ORM la actualización automática del timestamp en cada UPDATE — esto es **crítico** para que TODOS los modelos de dominio futuros (Changes 09–17) hereden el comportamiento correcto sin pensar en ello.

**Vinculación de naming convention**: en `app/db/base.py` se setea `SQLModel.metadata.naming_convention = NAMING_CONVENTION` **antes** de cualquier import de modelos. Luego `class Base(SQLModel, table=False)` simple. El orden de imports es crítico y se documenta en una tarea explícita.

### D-05: Pool de conexiones async — instanciación lazy + lifespan

**Decisión**: el engine se construye **lazy** dentro de `get_engine()` con `@lru_cache(maxsize=1)`. La instanciación NUNCA ocurre al import de módulo. El cierre del pool se delega al `lifespan` de FastAPI.

```python
# app/db/session.py
@lru_cache(maxsize=1)
def get_engine() -> AsyncEngine:
    settings = get_settings()
    return create_async_engine(
        settings.DATABASE_URL,
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True,
        echo=settings.ENVIRONMENT == "development",
    )

@lru_cache(maxsize=1)
def get_session_factory() -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(get_engine(), class_=AsyncSession, expire_on_commit=False)

async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with get_session_factory()() as session:
        yield session
```

```python
# app/main.py
@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await get_engine().dispose()

app = FastAPI(..., lifespan=lifespan)
```

**Alternativas consideradas y rechazadas tras auditoría**:
- `engine = create_async_engine(...)` a nivel de módulo: bloquea el override de `DATABASE_URL` en tests, fuerza coupling al import time, deja conexiones colgadas al shutdown. **Rechazado.**

**Rationale**:
- **Lazy** → los tests pueden cambiar `DATABASE_URL` (vía `os.environ` + `get_settings.cache_clear()` + `get_engine.cache_clear()`) sin patches.
- **`lru_cache(maxsize=1)`** → se comporta como singleton sin acoplar al import.
- **`lifespan`** → cierra el pool en shutdown evitando warnings de pytest-asyncio y leaks de conexiones.
- **`pool_pre_ping=True`** → evita conexiones stale tras inactividad (crítico en cloud).
- `pool_size=5` / `max_overflow=10` → valores conservadores adecuados para dev/staging; se escalan vía env var en producción.

**Aplicación del mismo patrón lazy** a otros singletons que dependen de `Settings`: `get_limiter()` (slowapi) y la construcción de `api_v1_router` se ejecutan dentro de funciones factory (ver D-12). Ningún módulo del backend evalúa `settings.X` al import.

### D-06: get_session() — dependency async generator

**Decisión**: `async def get_session() -> AsyncGenerator[AsyncSession, None]` como FastAPI dependency.

**Alternativas consideradas**:
- `Depends(get_uow)` directamente en routers: Change 04 introduce UoW; Change 02 solo provee la sesión raw para que Change 04 pueda construir UoW sobre ella.

**Rationale**: los routers de Change 02 (solo health readiness) necesitan una sesión simple para el ping. Change 04 envuelve esta sesión en UoW. La separación es limpia y no anticipa lógica de Change 04.

### D-07: Request ID — middleware vs dependency

**Decisión**: middleware ASGI que genera UUID v4, lo escribe en `contextvars` y lo inyecta en el header de respuesta `X-Request-ID`.

**Rationale**: un middleware garantiza que TODOS los requests (incluyendo errores 422 de validación Pydantic antes de que llegue al router) tienen `request_id` en el log. Un Dependency solo cubriría los requests que llegan al handler.

### D-08: CORS — CORSMiddleware de Starlette

**Decisión**: usar `app.add_middleware(CORSMiddleware, allow_origins=settings.BACKEND_CORS_ORIGINS, ...)` parseando la variable como lista de orígenes.

**Rationale**: es la solución oficial de FastAPI/Starlette, sin dependencias extra. `BACKEND_CORS_ORIGINS` se declara como `list[str]` en Settings con validator que acepta string separado por comas (para compatibilidad con variables de entorno planas).

### D-09: Rate limiting — slowapi sin reglas por endpoint

**Decisión**: instanciar `Limiter(key_func=get_remote_address, default_limits=[settings.RATE_LIMIT_DEFAULT])` y registrar el handler de `RateLimitExceeded` que devuelve RFC 7807. No decorar ningún endpoint en este change.

**Rationale**: la infra debe estar lista para que Change 06 (auth, con 5 req/15min) y otros la consuman. Declarar el Limiter global aquí evita que cada change tenga que configurar slowapi desde cero.

### D-10: Tests con base de datos — transaction rollback fixture

**Decisión**: fixture `test_db_session` que abre una transacción, cede la sesión al test, y hace rollback al finalizar (sin commits reales). El engine de test apunta a una BD PostgreSQL de test configurada via `TEST_DATABASE_URL`.

**Alternativas consideradas**:
- SQLite en memoria: incompatible con asyncpg y con features PostgreSQL-específicas (UUID, JSONB, CTE, `FOR UPDATE`).
- BD dedicada que se recrea entre tests: más lento; el rollback-fixture es equivalente y más rápido.

**Rationale**: PostgreSQL 15+ es requisito del stack. El fixture de rollback aísla los tests sin estado residual y sin necesidad de recrear tablas.

### D-11: RFC 7807 — estructura de respuesta de error

**Decisión**: body de error con campos `type`, `title`, `status`, `detail`, `instance` (mínimo). Opcionalmente `code` (string semántico interno) y `field` (para errores de validación de campo específico). Content-Type: `application/problem+json`.

**Rationale**: CHANGES.md Change 02 especifica explícitamente `{ detail, code, field? }`. Se alinea con RFC 7807 agregando `type`, `title`, `status` e `instance` como campos estándar, y `code`/`field` como extensiones propias del sistema.

### D-12: Estructura de archivos definitiva (Change 02)

```
backend/
├── app/
│   ├── main.py                    # modificado: lifespan, middlewares, router v1, error handlers
│   ├── core/
│   │   ├── config.py              # Settings(BaseSettings), get_settings() lazy
│   │   ├── context.py             # ContextVar[str | None] para request_id (única fuente)
│   │   ├── exceptions.py          # jerarquía de excepciones base
│   │   ├── logging.py             # structlog config + processor que lee context.request_id_var
│   │   ├── middleware.py          # RequestIDMiddleware (lee/escribe context.request_id_var)
│   │   └── rate_limit.py          # get_limiter() lazy, handler RateLimitExceeded
│   ├── db/
│   │   ├── base.py                # SQLModel.metadata.naming_convention (seteado ANTES de modelos)
│   │   └── session.py             # get_engine() lazy, get_session_factory() lazy, get_session()
│   ├── models/
│   │   └── base.py                # Base(SQLModel, table=False) con id, created_at, updated_at + onupdate, deleted_at
│   ├── schemas/
│   │   └── base.py                # Page[T], ProblemDetail, create_pagination_meta()
│   └── api/
│       ├── errors.py              # exception handlers FastAPI → RFC 7807
│       └── v1/
│           ├── __init__.py
│           └── router.py          # build_v1_router(settings) factory; GET /api/v1/health (excepción documentada al patrón de capas)
├── tests/
│   ├── conftest.py                # fixtures: async_client (ASGITransport), test_db_session, override_settings (con cache_clear)
│   └── test_infrastructure.py    # tests partidos por archivo: test_settings, test_health, test_rfc7807, test_cors, test_request_id
└── .env.example                   # ampliado con DATABASE_URL, API_V1_PREFIX, LOG_LEVEL, RATE_LIMIT_DEFAULT
```

**Notas estructurales tras auditoría**:
- `app/core/context.py` aloja la `ContextVar` de `request_id` como **única fuente** (resuelve la duplicación 3.2↔11.1 detectada). `logging.py` y `middleware.py` la importan; nunca la redefinen.
- `app/core/middleware.py` aloja `RequestIDMiddleware` (path canónico, antes ambiguo entre `core/` y `api/`).
- `app/db/base.py` ejecuta `SQLModel.metadata.naming_convention = NAMING_CONVENTION` **antes** de cualquier import de modelo. Esta es una restricción de orden, documentada también en D-04.
- `app/api/v1/router.py` expone `build_v1_router(settings) -> APIRouter` como **factory**, no instancia al import (alinea con D-05 lazy).
- `main.py` define `lifespan` que llama `await get_engine().dispose()` en shutdown.

### D-13: Health endpoints — única excepción documentada al patrón de capas

**Decisión**: `GET /api/v1/health` (readiness) ejecuta `SELECT 1` directamente desde el router usando `Depends(get_session)`, **sin pasar por Service / UoW / Repository**. Es la **única excepción** permitida al patrón de capas Router → Service → UoW → Repo → Model en este change.

**Rationale**: un health check no es lógica de negocio. No tiene reglas, no requiere transacción, no opera sobre entidades. Forzarlo a través de las 4 capas crearía un `HealthService` vacío y un `HealthRepository` que solo ejecuta `SELECT 1`, pura ceremonia sin valor. La excepción se documenta explícitamente para evitar imitación incorrecta en endpoints futuros.

**Restricción**: cualquier endpoint que toque entidades de dominio (CRUD, queries, mutaciones) **debe** pasar por las 4 capas. La excepción se limita a:
- `GET /health` (liveness, sin BD)
- `GET /api/v1/health` (readiness, con `SELECT 1`)

Esta nota se incluye como comentario en el código del router y se referencia desde `proposal.md` de Change 04 (que introducirá UoW/Repo).

### D-14: Versión de la app — fuente única en pyproject.toml

**Decisión**: la versión se lee con `importlib.metadata.version("foodstore-backend")` en `app/main.py`. **No se duplica** en `Settings.APP_VERSION`.

**Rationale**: `pyproject.toml [project].version` es la fuente de verdad canónica. Tener `APP_VERSION` en Settings invita drift cuando alguien actualiza una y no la otra. `importlib.metadata` es stdlib desde Python 3.8.

### D-15: Anyio — solo `anyio` (sin `[trio]`)

**Decisión**: si se necesita `anyio` como dev dependency (para httpx async testing), se declara como `anyio` simple. **No** `anyio[trio]`.

**Rationale**: `trio` no se usa en ninguna parte del proyecto. `httpx` y `pytest-asyncio` operan con asyncio puro. Agregar trio es cruft transitivo.

### D-16: Override de Settings en tests — protocolo explícito

**Decisión**: el fixture `override_settings` aplica este protocolo:
1. `os.environ` actualizado con valores de test (`TEST_DATABASE_URL`, etc.).
2. `get_settings.cache_clear()` para invalidar el singleton.
3. `get_engine.cache_clear()` y `get_session_factory.cache_clear()` para invalidar el pool/factory.
4. El test corre.
5. En teardown: revertir `os.environ` + `cache_clear()` de los tres callables.

**Rationale**: `lru_cache` es la fuente de cualquier sospecha de "el override no surte efecto". Documentar el protocolo evita debugging recurrente.

## Risks / Trade-offs

| ID | Riesgo | Mitigación |
|----|--------|------------|
| R-01 | asyncpg requiere PostgreSQL corriendo al arrancar tests | Fixture `override_settings` permite `TEST_DATABASE_URL`; documentar en README. Si PostgreSQL no está disponible, los tests de BD se saltean con `pytest.mark.skip`. |
| R-02 | structlog añade complejidad de configuración inicial | Encapsular toda la configuración en `app/core/logging.py`; una sola llamada en `main.py`. |
| R-03 | `BACKEND_CORS_ORIGINS` como lista en .env puede causar errores de parsing | Validator pydantic-settings que acepta tanto JSON list `["http://..."]` como string separado por comas `http://...,http://...`. |
| R-04 | `pool_pre_ping=True` agrega latencia mínima | Latencia de ping es < 1ms en LAN/localhost. Tradeoff aceptable vs conexiones stale. |
| R-05 | UoW ausente en Change 02 puede confundir al lector de tasks | Documentar explícitamente en tasks.md que UoW/BaseRepository son Change 04. |
| R-06 | UUID como PK puede ser más lento que int para queries con índices btree | Aceptable para el volumen del TPI; en producción se mitiga con índices parciales o ULIDs (decisión post-entrega). |

## Migration Plan

1. Instalar dependencias nuevas: `pip install -e ".[dev]"` tras actualizar `pyproject.toml`.
2. Crear `backend/.env` local copiando `.env.example` y completando `DATABASE_URL`.
3. Verificar que PostgreSQL 15+ esté corriendo y la BD de desarrollo existe.
4. Arrancar: `uvicorn app.main:app --reload` desde `backend/`.
5. Verificar `GET /health` → 200, `GET /api/v1/health` → 200 con BD up (o 503 si BD caída).
6. Ejecutar `pytest -v` para validar tests de infraestructura.

**Rollback**: los cambios son aditivos. Si se necesita revertir, eliminar los módulos nuevos y restaurar `main.py`, `pyproject.toml` y `.env.example` al estado de Change 01.

## Open Questions

- OQ-01: ¿`pool_size` y `max_overflow` se exponen como variables de entorno en Settings o se hardcodean como constantes? → Decisión: hardcodeados con valores conservadores en Change 02; se pueden externalizar en un change posterior si se necesita tuning en producción.
- OQ-02: ¿El endpoint `GET /api/v1/health` devuelve solo `{"status": "ok"}` o también info de versión/timestamp? → Decisión: devuelve `{"status": "ok", "database": "ok"|"error", "version": settings.APP_VERSION}` para readiness real; si la BD falla, devuelve HTTP 503.
- OQ-03: ¿`RATE_LIMIT_DEFAULT` como `"100/minute"` o `"100 per minute"`? → Usar formato slowapi estándar `"100/minute"`.
