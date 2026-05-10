## Why

El proyecto Food Store necesita una base ejecutable desde la que cualquier desarrollador pueda clonar el repositorio y arrancar los entornos de backend y frontend sin escribir código de negocio. Sin esta estructura de monorepo unificada, cada change posterior (02–05 y todos los de Sprint 1+) tendría que resolver problemas de tooling y convenciones de forma ad-hoc, generando deuda técnica desde el inicio.

## What Changes

- Se crea la estructura raíz del monorepo con dos workspaces (`backend/` y `frontend/`) sin tooling especial (no turborepo, no nx).
- Se inicializa el proyecto backend Python con `pyproject.toml`, entorno virtual, dependencias core y scripts `dev`, `test`, `lint`.
- Se inicializa el proyecto frontend con `package.json`, TypeScript 5 estricto, Vite 5, TailwindCSS 3 y scripts `dev`, `build`, `test`, `lint`.
- Se configura el linting y formateo en ambos lados (ruff + black + mypy en backend; ESLint + Prettier en frontend).
- Se crean los archivos de configuración de entorno (`.env.example` backend y frontend) y se asegura que `.env` esté ignorado.
- Se añade un health check trivial `GET /health` en backend y una página `index.tsx` vacía en frontend únicamente para validar que el bootstrap funciona.
- Se versiona el runtime con `.python-version` (3.11) y `.nvmrc` (20) para reproducibilidad.
- Se establece `.editorconfig` y `.gitignore` raíz con convenciones de Conventional Commits.
- Se crea `README.md` raíz con instrucciones de bootstrap paso a paso.

## Capabilities

### New Capabilities

- `monorepo-workspace`: Define la estructura de carpetas del monorepo, convenciones de raíz, archivos de configuración compartidos y documentación de bootstrap.
- `backend-scaffold`: Establece el workspace Python/FastAPI con estructura de capas, dependencias core, linting y scripts operativos (sin endpoints de negocio, solo `/health`).
- `frontend-scaffold`: Establece el workspace React/TypeScript/Vite con estructura Feature-Sliced Design, dependencias core, Tailwind, linting y scripts operativos (sin componentes de negocio, solo página index vacía).

### Modified Capabilities

<!-- Ninguna: este es el change inicial; no existen specs previas en openspec/specs/ -->

## Impact

- **Archivos creados en raíz**: `.gitignore`, `.editorconfig`, `.nvmrc`, `.python-version`, `README.md`
- **Workspace backend** (`backend/`): `pyproject.toml`, `requirements.txt` (pin), `.env.example`, estructura de carpetas `app/` con `api/`, `services/`, `repositories/`, `models/`, `schemas/`, `core/`, `db/` y `tests/`; archivo `app/main.py` con health check
- **Workspace frontend** (`frontend/`): `package.json`, `tsconfig.json`, `vite.config.ts`, `tailwind.config.js`, `postcss.config.js`, `.env.example`, estructura FSD `src/` con `app/`, `pages/`, `widgets/`, `features/`, `entities/`, `shared/`; página `src/pages/home/ui/HomePage.tsx` vacía
- **Dependencias afectadas**: Python 3.11+, FastAPI, Uvicorn, SQLModel, Alembic, Pydantic v2, pytest, ruff, black, mypy; Node 20+, React 18, TypeScript 5, Vite 5, TailwindCSS 3, ESLint, Prettier, Vitest
- **No afecta**: ningún endpoint de negocio, ningún modelo de dominio, ningún componente de UI funcional
- **Habilita**: Change 02 (backend-core-foundation) y Change 05 (frontend-core-foundation)
