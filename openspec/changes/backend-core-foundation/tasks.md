## 0. Prerrequisitos

- [x] 0.1 Verificar que Change 01 (`bootstrap-monorepo-structure`) está archivado y la estructura `backend/app/{core,db,models,schemas,api,services,repositories}/__init__.py` existe
- [x] 0.2 Verificar que Python 3.11+ está activo en el entorno virtual (`python --version`)
- [x] 0.3 Verificar que PostgreSQL 15+ está corriendo y accesible localmente (`psql -h localhost -U postgres -c "SELECT version();"`)
- [x] 0.4 Crear la base de datos de desarrollo si no existe (cross-platform): `psql -h localhost -U postgres -c "CREATE DATABASE foodstore_dev;"` (ignorar error si ya existe)
- [x] 0.5 Crear la base de datos de test si no existe (cross-platform): `psql -h localhost -U postgres -c "CREATE DATABASE foodstore_test;"` (ignorar error si ya existe)

## 1. Dependencias Python

- [x] 1.1 Agregar al bloque `[project.dependencies]` de `backend/pyproject.toml`: `sqlmodel`, `asyncpg`, `alembic`, `pydantic-settings`, `slowapi`, `structlog`
- [x] 1.2 Agregar al bloque `[project.optional-dependencies.dev]` de `backend/pyproject.toml`: `pytest-cov`, `anyio` (sin extra `[trio]` — pytest-anyio usa asyncio backend por default; trio no se requiere en este change)
- [x] 1.3 Ejecutar `pip install -e ".[dev]"` desde `backend/` y verificar exit code 0
- [x] 1.4 Verificar importación: `python -c "import sqlmodel, asyncpg, structlog, slowapi, pydantic_settings; print('ok')"` sin errores
- [x] 1.5 Regenerar `backend/requirements.txt` ejecutando `pip freeze --exclude-editable > requirements.txt` desde `backend/` para fijar versiones reproducibles del lockfile (NO incluir el propio paquete editable)

## 2. Configuración tipada (app/core/config.py)

- [x] 2.1 Implementar `Settings(BaseSettings)` en `app/core/config.py` con campos: `DATABASE_URL` (obligatorio, sin default), `ENVIRONMENT` (default `"development"`), `BACKEND_CORS_ORIGINS` (list[str], default `["http://localhost:5173"]`), `API_V1_PREFIX` (default `"/api/v1"`), `LOG_LEVEL` (default `"INFO"`), `RATE_LIMIT_DEFAULT` (default `"100/minute"`). NO incluir `APP_VERSION` (decisión D-14: la versión se obtiene de la metadata del paquete, no de Settings)
- [x] 2.2 Agregar validator (`field_validator` de Pydantic v2) para `BACKEND_CORS_ORIGINS` que acepte tanto string separado por comas como JSON array
- [x] 2.3 Implementar `get_settings()` con `@lru_cache(maxsize=1)` que retorna la instancia singleton de `Settings`. Esta función es el ÚNICO punto de acceso a Settings en todo el codebase
- [x] 2.4 Agregar `model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")` a `Settings`
- [x] 2.5 Crear helper `get_app_version() -> str` en `app/core/config.py` (o en módulo aparte `app/core/version.py`) que retorna `importlib.metadata.version("foodstore-backend")` con try/except para devolver `"0.0.0"` si el paquete no está instalado (escenario de tests sin install)
- [x] 2.6 Actualizar `backend/.env.example` con todas las variables: `DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/foodstore_dev`, `ENVIRONMENT=development`, `BACKEND_CORS_ORIGINS=http://localhost:5173`, `API_V1_PREFIX=/api/v1`, `LOG_LEVEL=INFO`, `RATE_LIMIT_DEFAULT=100/minute`. NO incluir `APP_VERSION`
- [x] 2.7 Crear `backend/.env` local (no versionado) copiando `.env.example` y completando con valores reales de desarrollo

## 3. ContextVar y logging estructurado

- [x] 3.1 Crear `app/core/context.py` como ÚNICO módulo dueño de la `ContextVar[str | None]` para `request_id`. Exportar: `request_id_ctx: ContextVar[str | None]` (con `default=None`), helpers `get_request_id() -> str | None` y `set_request_id(value: str) -> Token`. Razón: evita duplicación entre logging y middleware (corrección P-04 de la auditoría)
- [x] 3.2 Crear `app/core/logging.py` con función `configure_logging(log_level: str, environment: str)` que configura structlog con processors: `add_log_level`, `add_timestamp` (ISO 8601 UTC), `StackInfoRenderer`, renderer `JSONRenderer` para `environment != "development"` y `ConsoleRenderer` para `environment == "development"`
- [x] 3.3 En `app/core/logging.py`, definir un processor `inject_request_id(logger, method_name, event_dict)` que importa `get_request_id` desde `app/core/context.py` y agrega la clave `request_id` al `event_dict` cuando exista. Registrarlo en la cadena de processors de structlog
- [x] 3.4 Implementar `get_logger(name: str)` que retorna `structlog.get_logger(name)`
- [x] 3.5 Verificar que `get_logger("test").info("prueba")` no lanza excepción

## 4. Database core (app/db/)

- [x] 4.1 Crear `app/db/base.py` que: (a) importa `SQLModel` desde `sqlmodel`, (b) define `NAMING_CONVENTION = {"ix": "ix_%(column_0_label)s", "uq": "uq_%(table_name)s_%(column_0_name)s", "ck": "ck_%(table_name)s_%(constraint_name)s", "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s", "pk": "pk_%(table_name)s"}`, (c) ejecuta `SQLModel.metadata.naming_convention = NAMING_CONVENTION` ANTES de cualquier import de modelos. Este módulo NO debe importar modelos
- [x] 4.2 Crear `app/db/session.py` con `get_engine() -> AsyncEngine` decorada con `@lru_cache(maxsize=1)` que llama a `get_settings()` y construye `create_async_engine(settings.DATABASE_URL, pool_size=5, max_overflow=10, pool_pre_ping=True, echo=settings.ENVIRONMENT == "development")`. PROHIBIDO instanciar el engine a nivel de módulo — debe ser lazy (corrección P-01 de la auditoría)
- [x] 4.3 En `app/db/session.py`, definir `get_session_factory() -> async_sessionmaker[AsyncSession]` decorada con `@lru_cache(maxsize=1)` que retorna `async_sessionmaker(get_engine(), class_=AsyncSession, expire_on_commit=False)`. PROHIBIDO instanciar `AsyncSessionLocal` a nivel de módulo
- [x] 4.4 Implementar `async def get_session() -> AsyncGenerator[AsyncSession, None]` en `app/db/session.py` que invoca `get_session_factory()()` dentro de `async with` y hace `yield session`. Esta es la dependency FastAPI a usar via `Depends(get_session)`
- [x] 4.5 Actualizar `app/db/__init__.py` para exponer únicamente las funciones públicas: `get_engine`, `get_session_factory`, `get_session` (NO exponer instancias)

## 5. Modelo base (app/models/base.py)

- [x] 5.1 Crear `app/models/base.py` que importa primero `app.db.base` (para garantizar que `SQLModel.metadata.naming_convention` ya está aplicado — corrección P-07 de la auditoría) y luego declara `class Base(SQLModel, table=False)` con campos:
  - `id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)`
  - `created_at: datetime = Field(default_factory=lambda: datetime.now(UTC), sa_column_kwargs={"server_default": func.now()})`
  - `updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC), sa_column_kwargs={"onupdate": lambda: datetime.now(UTC)})` — el `sa_column_kwargs={"onupdate": ...}` es OBLIGATORIO (corrección P-06): sin él, `updated_at` nunca se refresca en UPDATE y queda igual a `created_at` para siempre
  - `deleted_at: datetime | None = Field(default=None)`
- [x] 5.2 NO redefinir metadata ni naming_convention en `Base`. SQLModel comparte el `MetaData` global vía `SQLModel.metadata`, ya configurado en `app/db/base.py` (paso 4.1). Documentar en docstring que el orden de imports importa: `app.db.base` antes que cualquier modelo
- [x] 5.3 Agregar propiedad `is_deleted: bool` que retorna `self.deleted_at is not None`
- [x] 5.4 Agregar método `soft_delete(self) -> None` que setea `self.deleted_at = datetime.now(UTC)` (la persistencia es responsabilidad del repositorio en Change 04, este método solo muta el atributo en memoria)
- [x] 5.5 Actualizar `app/models/__init__.py` para exponer `Base`

## 6. Schemas base (app/schemas/base.py)

- [x] 6.1 Crear `app/schemas/base.py` con `class Page(BaseModel, Generic[T])` con campos: `items: list[T]`, `total: int`, `page: int`, `size: int`, `pages: int`
- [x] 6.2 Implementar `create_pagination_meta(total: int, page: int, size: int) -> dict[str, int]` que calcula `pages = ceil(total / size) if size > 0 else 0` (manejar `size=0` como caso límite explícito)
- [x] 6.3 Crear `class ProblemDetail(BaseModel)` con campos RFC 7807: `type: str`, `title: str`, `status: int`, `detail: str`, `instance: str`, `code: str | None = None`. Para errores de validación de campos se usa una extensión `errors: list[dict] | None = None` (decisión D-08: un único `ProblemDetail` con extensión, en lugar de un `field` plano que solo soporta un error). Configurar `model_config = ConfigDict(extra="allow")` para permitir extensiones RFC 7807 arbitrarias
- [x] 6.4 Actualizar `app/schemas/__init__.py` para exponer `Page`, `ProblemDetail`, `create_pagination_meta`

## 7. Excepciones de dominio base (app/core/exceptions.py)

- [x] 7.1 Crear `app/core/exceptions.py` con clase raíz `AppError(Exception)` que acepta `detail: str`, `code: str | None = None`, `status_code: int = 500`, `title: str = "Internal Server Error"`
- [x] 7.2 Implementar `NotFoundError(AppError)` con `status_code = 404` y `title = "Not Found"`
- [x] 7.3 Implementar `ConflictError(AppError)` con `status_code = 409` y `title = "Conflict"`
- [x] 7.4 Implementar `AppValidationError(AppError)` con `status_code = 422` y `title = "Validation Error"` (nombre `App*` para no chocar con `pydantic.ValidationError`)
- [x] 7.5 Implementar `UnauthorizedError(AppError)` con `status_code = 401` y `title = "Unauthorized"`
- [x] 7.6 Implementar `ForbiddenError(AppError)` con `status_code = 403` y `title = "Forbidden"`

## 8. Error handlers RFC 7807 (app/api/errors.py)

- [x] 8.1 Crear `app/api/errors.py` con función `app_error_handler(request: Request, exc: AppError) -> JSONResponse` que construye un `ProblemDetail(type=f"about:blank", title=exc.title, status=exc.status_code, detail=exc.detail, instance=str(request.url.path), code=exc.code)` y retorna `JSONResponse(status_code=exc.status_code, content=problem.model_dump(exclude_none=True), media_type="application/problem+json")`
- [x] 8.2 Implementar `validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse` que construye UN ÚNICO `ProblemDetail` con `status=422`, `title="Validation Error"`, `detail="One or more fields failed validation"`, y la extensión `errors=[{"loc": list(e["loc"]), "msg": e["msg"], "type": e["type"]} for e in exc.errors()]`. Decisión D-08: un solo response con todos los errores, no un response por cada error de campo
- [x] 8.3 Implementar `unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse` que loguea el traceback completo via `get_logger(__name__).exception("unhandled_exception")` y devuelve `ProblemDetail` HTTP 500 con `detail="An unexpected error occurred"` (sin exponer el mensaje original al cliente)
- [x] 8.4 Implementar `rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse` que devuelve HTTP 429 con `Content-Type: application/problem+json` y `ProblemDetail(title="Too Many Requests", status=429, detail=str(exc.detail))`
- [x] 8.5 Crear función `register_error_handlers(app: FastAPI) -> None` que registra los cuatro handlers en la app: `app.add_exception_handler(AppError, app_error_handler)`, `app.add_exception_handler(RequestValidationError, validation_error_handler)`, `app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)`, `app.add_exception_handler(Exception, unhandled_error_handler)` (este último al final como catch-all)

## 9. Rate limiting (app/core/rate_limit.py)

- [x] 9.1 Crear `app/core/rate_limit.py` con `get_limiter() -> Limiter` decorada con `@lru_cache(maxsize=1)` que llama a `get_settings()` y construye `Limiter(key_func=get_remote_address, default_limits=[settings.RATE_LIMIT_DEFAULT])`. PROHIBIDO instanciar `limiter` a nivel de módulo (corrección P-02): cualquier import de este módulo en tests dispararía la lectura de Settings antes de poder hacer override
- [x] 9.2 Verificar que `get_limiter()` retorna una instancia válida cuando `Settings` está disponible

## 10. Router API v1 (app/api/v1/router.py)

- [x] 10.1 Crear `app/api/v1/__init__.py` (vacío)
- [x] 10.2 Crear `app/api/v1/router.py` exportando un factory `build_v1_router(settings: Settings) -> APIRouter` que construye `router = APIRouter(prefix=settings.API_V1_PREFIX)`, registra los endpoints definidos en este módulo y retorna el router. PROHIBIDO instanciar `api_v1_router` a nivel de módulo (corrección P-02): el prefix depende de Settings, que debe poder ser overrideado en tests
- [x] 10.3 Dentro del factory, registrar el endpoint `GET /health` (ruta relativa `/health` → absoluta `/api/v1/health`) que ejecuta `await session.execute(select(1))` via `Depends(get_session)` y devuelve `{"status": "ok", "database": "ok", "version": get_app_version()}` o HTTP 503 si la BD falla. **Excepción documentada (D-13)**: este endpoint accede directo a la sesión saltando el patrón Router → Service → UoW → Repo porque es una probe de readiness, no lógica de dominio. Agregar comentario inline `# noqa: D-13` o equivalente que linkee a la decisión

## 11. Middleware

- [x] 11.1 Crear `app/core/middleware.py` (ubicación canónica del middleware, evita confusión sobre dónde vive — corrección de la auditoría) con clase `RequestIDMiddleware(BaseHTTPMiddleware)` que: (a) lee el header `X-Request-ID` del request o genera `str(uuid.uuid4())` si no existe, (b) llama a `set_request_id(request_id)` desde `app/core/context.py` para escribirlo en la `ContextVar` (ÚNICA, definida en 3.1 — NO crear otra), (c) procesa el request, (d) inyecta el `request_id` en el header `X-Request-ID` de la respuesta antes de retornarla
- [x] 11.2 NO duplicar la `ContextVar`. El middleware DEBE importar `request_id_ctx` y `set_request_id` desde `app/core/context.py`. El processor de structlog (paso 3.3) DEBE importar `get_request_id` del MISMO módulo. Una sola fuente de verdad (corrección P-04)
- [x] 11.3 Resetear el `Token` retornado por `set_request_id` en un `try/finally` para evitar leak de la ContextVar entre requests si el event loop reutiliza el contexto

## 12. Lifespan y wire-up de main.py

- [x] 12.1 Definir `@asynccontextmanager async def lifespan(app: FastAPI)` en `app/main.py` que: (a) en startup, llama `configure_logging(settings.LOG_LEVEL, settings.ENVIRONMENT)`, (b) en shutdown (`yield` y luego), llama `await get_engine().dispose()` para cerrar el pool de conexiones limpiamente. SIN el dispose, los workers quedan con conexiones colgadas en shutdown (nueva tarea exigida por D-05)
- [x] 12.2 En `app/main.py`, obtener `settings = get_settings()` UNA SOLA VEZ al construir la app y construir `app = FastAPI(title="Food Store API", version=get_app_version(), lifespan=lifespan)`
- [x] 12.3 Registrar `CORSMiddleware` con `allow_origins=settings.BACKEND_CORS_ORIGINS`, `allow_credentials=True`, `allow_methods=["*"]`, `allow_headers=["*"]`, `expose_headers=["X-Request-ID"]`
- [x] 12.4 Registrar `RequestIDMiddleware` (importado desde `app.core.middleware`) en la app
- [x] 12.5 Adjuntar el limiter de slowapi a `app.state.limiter = get_limiter()` y agregar `app.add_middleware(SlowAPIMiddleware)`
- [x] 12.6 Llamar `register_error_handlers(app)` para registrar los handlers de `app/api/errors.py`
- [x] 12.7 Construir e incluir el router v1 invocando el factory: `app.include_router(build_v1_router(settings))`
- [x] 12.8 Verificar que `GET /health` (liveness, sin BD) sigue respondiendo 200. **Excepción documentada (D-13)**: este endpoint vive en `main.py` y NO usa el router v1 — es una probe de liveness pura, sin acceso a BD ni dependencias

## 13. Tests de infraestructura (backend/tests/)

- [x] 13.1 Crear `backend/tests/conftest.py` con fixture `override_settings` que: (a) define una función `_override() -> Settings` que retorna `Settings(DATABASE_URL=os.environ["TEST_DATABASE_URL"], ENVIRONMENT="test", ...)`, (b) ejecuta el protocolo de override invalidando los `lru_cache` afectados:
  ```
  get_settings.cache_clear()
  get_engine.cache_clear()
  get_session_factory.cache_clear()
  get_limiter.cache_clear()
  app.dependency_overrides[get_settings] = _override
  yield
  app.dependency_overrides.clear()
  get_settings.cache_clear()
  get_engine.cache_clear()
  get_session_factory.cache_clear()
  get_limiter.cache_clear()
  ```
  Razón: sin invalidar los caches lazy, las llamadas siguientes devuelven la instancia vieja (corrección P-03 / D-16)
- [x] 13.2 Agregar fixture `async_client` que crea el cliente con `AsyncClient(transport=ASGITransport(app=app), base_url="http://test")` (el parámetro `app=` directo está deprecado en httpx — corrección P-05). Importar `ASGITransport` desde `httpx`
- [x] 13.3 Agregar fixture `test_db_session` que abre una transacción de test contra `TEST_DATABASE_URL`, hace `yield session` y rollback al finalizar para garantizar aislamiento entre tests
- [x] 13.4 Crear `backend/tests/test_infrastructure.py` con tests atómicos (uno por test, no agrupados):
  - [x] 13.4.1 `test_settings_database_url_loaded`: `get_settings().DATABASE_URL` no es None ni vacío cuando `.env` tiene valor
  - [x] 13.4.2 `test_health_liveness`: `GET /health` → 200 con `{"status": "ok"}` (sin BD)
  - [x] 13.4.3 `test_health_readiness`: `GET /api/v1/health` → 200 con `"database": "ok"` (requiere PostgreSQL test running)
  - [x] 13.4.4 `test_not_found_error_returns_problem_json`: endpoint que lanza `NotFoundError` → 404 con `Content-Type: application/problem+json` y body conforme RFC 7807
  - [x] 13.4.5 `test_conflict_error_returns_problem_json`: endpoint que lanza `ConflictError` → 409 con `Content-Type: application/problem+json`
  - [x] 13.4.6 `test_validation_error_returns_single_problem_with_errors_extension`: request con body inválido → 422 con `Content-Type: application/problem+json`, body con extensión `errors: [...]` (no múltiples responses)
  - [x] 13.4.7 `test_cors_headers_present`: request con `Origin: http://localhost:5173` → respuesta incluye `Access-Control-Allow-Origin`
  - [x] 13.4.8 `test_request_id_header_present`: respuesta incluye header `X-Request-ID` con formato UUID v4 válido
  - [x] 13.4.9 `test_request_id_propagated_when_provided`: request con header `X-Request-ID: <uuid>` → respuesta retorna el MISMO valor en `X-Request-ID`

## 14. Verificación final

- [x] 14.1 Ejecutar `ruff check app/` desde `backend/` → exit code 0 sin errores
- [x] 14.2 Ejecutar `mypy app/` desde `backend/` → exit code 0 o solo errores de stubs externos (no errores de lógica propia)
- [x] 14.3 Ejecutar `pytest -v` desde `backend/` → todos los tests de infraestructura pasan
- [x] 14.4 Ejecutar `pytest --cov=app --cov-report=term-missing` y verificar cobertura ≥ 80% de los módulos nuevos (`app/core/*`, `app/db/*`, `app/api/errors.py`, `app/api/v1/router.py`)
- [x] 14.5 Arrancar `uvicorn app.main:app --reload` desde `backend/` → sin errores de importación al inicio, log estructurado emitido en formato Console (development)
- [x] 14.6 Verificar `GET http://localhost:8000/health` → `{"status": "ok"}` con HTTP 200
- [x] 14.7 Verificar `GET http://localhost:8000/api/v1/health` → `{"status": "ok", "database": "ok", "version": "..."}` con HTTP 200
- [x] 14.8 Verificar `GET http://localhost:8000/docs` → Swagger UI disponible (HTTP 200)
- [x] 14.9 Verificar `GET http://localhost:8000/redoc` → ReDoc disponible (HTTP 200)
- [x] 14.10 Apagar `uvicorn` con Ctrl+C → log de shutdown sin warnings de conexiones colgadas (validación visual del lifespan + engine dispose, paso 12.1)
- [ ] 14.11 Commit con mensaje convencional: `feat(backend): core foundation — config, db async lazy, error handling RFC 7807, middlewares, lifespan`
