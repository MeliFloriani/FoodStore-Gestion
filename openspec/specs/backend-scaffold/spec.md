# backend-scaffold Specification

## Purpose
TBD - created by archiving change bootstrap-monorepo-structure. Update Purpose after archive.
## Requirements
### Requirement: Estructura de capas backend inicializada
El workspace `backend/` SHALL contener la estructura de carpetas de capas definida en el design, con archivos `__init__.py` en cada paquete. Los directorios vacíos que recibirán módulos en changes futuros SHALL tener un `__init__.py` mínimo.

#### Scenario: Estructura de carpetas backend presente
- **WHEN** se inspecciona `backend/app/`
- **THEN** existen los directorios: `api/`, `services/`, `repositories/`, `models/`, `schemas/`, `core/`, `db/`
- **THEN** cada directorio contiene al menos un archivo `__init__.py`
- **WHEN** se inspecciona `backend/`
- **THEN** existe el directorio `tests/` con `conftest.py` y `__init__.py`

### Requirement: Dependencias Python declaradas en pyproject.toml
El workspace backend SHALL declarar todas las dependencias core en `pyproject.toml` (sección `[project.dependencies]`) y las dependencias de desarrollo en `[project.optional-dependencies.dev]`. SHALL existir también un `requirements.txt` generado con versiones pinneadas.

#### Scenario: pyproject.toml contiene dependencias core
- **WHEN** se lee `backend/pyproject.toml`
- **THEN** la sección `[project.dependencies]` incluye: `fastapi`, `uvicorn[standard]`, `sqlmodel`, `alembic`, `pydantic[email]`, `passlib[bcrypt]`, `python-jose[cryptography]`, `slowapi`, `python-dotenv`, `asyncpg`
- **THEN** la sección `[project.optional-dependencies.dev]` incluye: `pytest`, `pytest-asyncio`, `httpx`, `ruff`, `black`, `mypy`

#### Scenario: requirements.txt existe como fallback
- **WHEN** se lee `backend/requirements.txt`
- **THEN** contiene versiones pinneadas de todas las dependencias declaradas en pyproject.toml

### Requirement: Linting y formateo backend configurado y operativo
El workspace backend SHALL tener `ruff` y `mypy` configurados en `pyproject.toml` con reglas mínimas. El script `lint` SHALL ejecutar ambas herramientas sin errores en el código del bootstrap.

#### Scenario: ruff lint pasa sin errores
- **WHEN** se ejecuta `python -m ruff check app/` desde `backend/`
- **THEN** el proceso termina con exit code 0

#### Scenario: mypy pasa sin errores en el módulo main
- **WHEN** se ejecuta `python -m mypy app/main.py` desde `backend/`
- **THEN** el proceso termina con exit code 0 (o con errores de missing stubs ignorados explícitamente)

### Requirement: Health check backend operativo
El archivo `backend/app/main.py` SHALL instanciar una aplicación FastAPI y registrar `GET /health` que devuelva `{"status": "ok"}` con HTTP 200 sin depender de base de datos ni autenticación.

#### Scenario: Health check responde 200
- **WHEN** se ejecuta `uvicorn app.main:app --reload` desde `backend/`
- **THEN** `GET http://localhost:8000/health` devuelve HTTP 200 con body `{"status": "ok"}`

#### Scenario: Script dev arranca el servidor
- **WHEN** se ejecuta el script `dev` definido en `pyproject.toml` o `Makefile` desde `backend/`
- **THEN** uvicorn arranca en `http://localhost:8000`

### Requirement: Scripts backend operativos
El workspace backend SHALL exponer al menos los scripts: `dev` (arranca uvicorn en reload mode), `test` (ejecuta pytest), `lint` (ejecuta ruff + mypy).

#### Scenario: Script test ejecuta sin errores en base vacía
- **WHEN** se ejecuta `pytest` desde `backend/` sin ningún test de negocio escrito
- **THEN** el proceso termina con exit code 0 (sin tests = éxito, no falla)

