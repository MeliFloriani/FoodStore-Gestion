# backend-database-core Specification

## Purpose
Async PostgreSQL engine, session factory, SQLAlchemy metadata conventions, and base SQLModel model with soft delete. Introduced in Change 02 (backend-core-foundation).

## Requirements

### Requirement: Motor async PostgreSQL configurado
El sistema SHALL proveer un `AsyncEngine` creado con `create_async_engine` usando `asyncpg` como driver. El pool SHALL configurarse con `pool_size=5`, `max_overflow=10`, `pool_pre_ping=True` y `echo` activado solo en `ENVIRONMENT=development`.

#### Scenario: Engine creado con URL asyncpg
- **WHEN** `DATABASE_URL` tiene formato `postgresql+asyncpg://user:pass@host/db`
- **THEN** `create_async_engine` crea el engine sin excepción
- **THEN** el engine está disponible como variable de módulo en `app/db/session.py`

#### Scenario: pool_pre_ping evita conexiones stale
- **WHEN** una conexión del pool está inactiva y el servidor BD la cerró
- **THEN** `pool_pre_ping=True` detecta la conexión inválida y la reemplaza transparentemente antes de entregarla al caller

### Requirement: AsyncSessionLocal y dependency get_session
El sistema SHALL proveer una `AsyncSession` factory (`AsyncSessionLocal`) y una función generadora async `get_session()` apta para inyección con `Depends()` en FastAPI. La sesión SHALL cerrarse automáticamente al finalizar el request, incluso si ocurre una excepción.

#### Scenario: get_session() cede una sesión válida
- **WHEN** `get_session()` se usa como dependency en un endpoint FastAPI
- **THEN** el endpoint recibe un objeto `AsyncSession` activo
- **THEN** la sesión se cierra al salir del scope del request

#### Scenario: get_session() cierra sesión ante excepción
- **WHEN** el handler del endpoint lanza una excepción no capturada
- **THEN** la sesión es cerrada (no leaked) antes de que el error se propague

### Requirement: Metadata con naming conventions de constraints
El sistema SHALL proveer una instancia `metadata = MetaData(naming_convention={...})` en `app/db/base.py` con la convention estándar SQLAlchemy para `ix`, `uq`, `ck`, `fk`, `pk`. Todos los modelos SQLModel SHALL usar este metadata.

#### Scenario: Naming convention aplicada a constraint único
- **WHEN** un modelo SQLModel define un campo con `unique=True` usando el metadata de `app/db/base.py`
- **THEN** Alembic genera un nombre de constraint con formato `uq_<tabla>_<columna>` en la migración

#### Scenario: Naming convention aplicada a foreign key
- **WHEN** un modelo SQLModel define una FK usando el metadata de `app/db/base.py`
- **THEN** Alembic genera un nombre con formato `fk_<tabla>_<columna>_<tabla_referenciada>`

### Requirement: Modelo base con columnas comunes y soft delete
El sistema SHALL proveer una clase `Base(SQLModel)` en `app/models/base.py` con los campos: `id` (UUID v4, PK, generado automáticamente), `created_at` (datetime UTC, default ahora), `updated_at` (datetime UTC, actualizable), `deleted_at` (datetime UTC, nullable, default None). Todos los modelos de dominio SHALL heredar de `Base`.

#### Scenario: id generado automáticamente
- **WHEN** se instancia un modelo que hereda de `Base` sin proveer `id`
- **THEN** `instance.id` es un UUID v4 único, no None

#### Scenario: created_at con timezone UTC
- **WHEN** se instancia un modelo que hereda de `Base`
- **THEN** `instance.created_at` es un `datetime` con timezone UTC (aware)

#### Scenario: soft delete mediante deleted_at
- **WHEN** se establece `instance.deleted_at = datetime.now(UTC)`
- **THEN** `instance.deleted_at` no es None
- **THEN** la fila persiste en la BD (no se ejecuta DELETE físico)

#### Scenario: registro no eliminado por defecto
- **WHEN** se instancia un modelo que hereda de `Base` sin asignar `deleted_at`
- **THEN** `instance.deleted_at` es None

### Requirement: Dependencias Python actualizadas en pyproject.toml
`backend/pyproject.toml` SHALL declarar en `[project.dependencies]` las dependencias nuevas introducidas por Change 02: `sqlmodel`, `asyncpg`, `alembic`, `pydantic-settings`, `slowapi`, `structlog`. En `[project.optional-dependencies.dev]` SHALL agregar `pytest-cov` y `anyio[trio]`.

#### Scenario: sqlmodel y asyncpg presentes en dependencies
- **WHEN** se lee `backend/pyproject.toml`
- **THEN** `sqlmodel` y `asyncpg` están listados en `[project.dependencies]`

#### Scenario: alembic presente en dependencies
- **WHEN** se lee `backend/pyproject.toml`
- **THEN** `alembic` está listado en `[project.dependencies]` (disponible para Change 03)
