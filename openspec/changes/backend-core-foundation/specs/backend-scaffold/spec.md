## MODIFIED Requirements

### Requirement: Dependencias Python declaradas en pyproject.toml
El workspace backend SHALL declarar todas las dependencias core en `pyproject.toml` (sección `[project.dependencies]`) y las dependencias de desarrollo en `[project.optional-dependencies.dev]`.

#### Scenario: pyproject.toml contiene dependencias core de Change 02
- **WHEN** se lee `backend/pyproject.toml`
- **THEN** la sección `[project.dependencies]` incluye: `fastapi`, `uvicorn[standard]`, `python-dotenv`, `sqlmodel`, `asyncpg`, `alembic`, `pydantic-settings`, `slowapi`, `structlog`
- **THEN** la sección `[project.optional-dependencies.dev]` incluye: `pytest`, `pytest-asyncio`, `httpx`, `ruff`, `mypy`, `pytest-cov`, `anyio[trio]`

#### Scenario: pip install -e instala todas las dependencias
- **WHEN** se ejecuta `pip install -e ".[dev]"` desde `backend/`
- **THEN** el proceso termina con exit code 0
- **THEN** `import sqlmodel`, `import asyncpg`, `import structlog`, `import slowapi` no generan `ModuleNotFoundError`
