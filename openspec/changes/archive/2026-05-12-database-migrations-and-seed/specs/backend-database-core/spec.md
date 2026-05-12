# backend-database-core — Delta Spec (Change 03)

## Purpose
Delta specification for the `backend-database-core` capability introduced in Change 02. This delta adds one new requirement that documents the Alembic ↔ SQLModel.metadata integration contract.

## MODIFIED Requirements

### Requirement: Dependencias Python actualizadas en pyproject.toml
`backend/pyproject.toml` SHALL declarar en `[project.dependencies]` las dependencias nuevas introducidas por Change 02 (`sqlmodel`, `asyncpg`, `alembic`, `pydantic-settings`, `slowapi`, `structlog`) **y por Change 03** (`passlib[bcrypt]`). En `[project.optional-dependencies.dev]` SHALL incluir `pytest-cov` y `anyio`.

#### Scenario: sqlmodel y asyncpg presentes en dependencies
- **WHEN** se lee `backend/pyproject.toml`
- **THEN** `sqlmodel` y `asyncpg` están listados en `[project.dependencies]`

#### Scenario: alembic presente en dependencies
- **WHEN** se lee `backend/pyproject.toml`
- **THEN** `alembic` está listado en `[project.dependencies]`

#### Scenario: passlib[bcrypt] presente en dependencies (nuevo en Change 03)
- **WHEN** se lee `backend/pyproject.toml`
- **THEN** `passlib[bcrypt]` está listado en `[project.dependencies]`
- **THEN** la versión especificada es `>=1.7.4`

## ADDED Requirements

### Requirement: SQLModel.metadata alimenta Alembic target_metadata
El sistema SHALL garantizar que el `SQLModel.metadata` configurado en `app/db/base.py` (con naming_convention) sea el `target_metadata` utilizado por el `env.py` de Alembic. Esta integración permite que `alembic revision --autogenerate` detecte todas las tablas de dominio con nombres de constraint deterministas.

#### Scenario: autogenerate detecta todas las tablas tras importar modelos
- **WHEN** Alembic ejecuta `autogenerate` con `target_metadata = SQLModel.metadata`
- **THEN** el script detecta las 16 tablas del ERD v5 (no 0 tablas)
- **THEN** los nombres de constraint generados siguen la naming_convention de `app/db/base.py`

#### Scenario: naming_convention de Change 02 persiste en migraciones de Change 03
- **WHEN** se genera la migration `0001_initial_schema`
- **THEN** los constraints tienen nombres con prefijos `uq_`, `fk_`, `ck_`, `ix_`, `pk_`
- **THEN** ningún constraint tiene nombre implícito generado por PostgreSQL (como `usuario_email_key`)
