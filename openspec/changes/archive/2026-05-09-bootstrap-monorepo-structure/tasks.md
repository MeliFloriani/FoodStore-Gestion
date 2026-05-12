## 0. Prerrequisitos del entorno

- [x] 0.1 Verificar que la raíz del repositorio está inicializada como repo Git (`git rev-parse --is-inside-work-tree`); si no lo está, ejecutar `git init`
- [x] 0.2 Verificar versiones de runtime locales: `python --version` ≥ 3.11 y `node --version` ≥ 20; documentar en el README cómo instalar pyenv/nvm si no están disponibles
- [x] 0.3 Crear directorios vacíos `backend/` y `frontend/` en la raíz

## 1. Raíz del monorepo

- [x] 1.1 Crear `.gitignore` raíz con exclusiones para: `.env`, `__pycache__/`, `*.pyc`, `.venv/`, `node_modules/`, `dist/`, `build/`, `.mypy_cache/`, `.ruff_cache/`, `.pytest_cache/`, `*.egg-info/`, `coverage/`, `.DS_Store`
- [x] 1.2 Crear `.editorconfig` con `indent_size=4` para Python e `indent_size=2` para TS/JS/JSON/YAML
- [x] 1.3 Crear `.nvmrc` con contenido `20`
- [x] 1.4 Crear `.python-version` con contenido `3.11`
- [x] 1.5 Crear `LICENSE` (MIT) en la raíz
- [x] 1.6 Crear `README.md` raíz — sección "Descripción del proyecto" (1 párrafo + stack resumido)
- [x] 1.7 Agregar al `README.md` sección "Prerrequisitos" (Python 3.11, Node 20, PostgreSQL 15, instrucciones para pyenv/nvm)
- [x] 1.8 Agregar al `README.md` sección "Bootstrap backend" (clonar → crear venv → instalar deps → copiar `.env.example` → arrancar)
- [x] 1.9 Agregar al `README.md` sección "Bootstrap frontend" (`npm install` → copiar `.env.example` → `npm run dev`)
- [x] 1.10 Agregar al `README.md` sección "Scripts disponibles" (tabla con `dev`, `build`, `test`, `lint` por workspace)
- [x] 1.11 Agregar al `README.md` sección "Convenciones de commits" con la especificación Conventional Commits y 3 ejemplos (`feat`, `fix`, `chore`)

## 2. Workspace backend — estructura de carpetas

- [x] 2.1 Crear `backend/app/__init__.py`, `backend/app/api/__init__.py`, `backend/app/services/__init__.py`, `backend/app/repositories/__init__.py`, `backend/app/models/__init__.py`, `backend/app/schemas/__init__.py`
- [x] 2.2 Crear `backend/app/core/__init__.py`, `backend/app/db/__init__.py`
- [x] 2.3 Crear `backend/tests/__init__.py` y `backend/tests/conftest.py` con docstring de módulo (vacío de fixtures en este change)

## 3. Workspace backend — declarar dependencias en pyproject

- [x] 3.1 Crear `backend/pyproject.toml` con bloque `[project]` (name="foodstore-backend", version="0.1.0", requires-python=">=3.11", description corta)
- [x] 3.2 Agregar `[project.dependencies]` con: `fastapi`, `uvicorn[standard]`, `python-dotenv` (mínimo viable para servir `/health`; las dependencias de auth, BD, JWT y MercadoPago se agregan en sus changes correspondientes — Change 02, 06 y 19)
- [x] 3.3 Agregar `[project.optional-dependencies]` con sección `dev`: `pytest`, `pytest-asyncio`, `httpx`, `ruff`, `mypy`

## 4. Workspace backend — configuración de calidad

> **Decisión cerrada (resuelve Open Question 2 de design.md)**: se usa **`ruff`** como linter y formatter (`ruff format` reemplaza a `black`). No se declara `black` para evitar dos formateadores en cadena.

- [x] 4.1 Agregar a `pyproject.toml` la sección `[tool.ruff]`: `line-length=88`, `target-version="py311"`, `exclude=[".venv","migrations"]`
- [x] 4.2 Agregar a `pyproject.toml` la sección `[tool.ruff.lint]`: `select=["E","F","I","UP"]`
- [x] 4.3 Agregar a `pyproject.toml` la sección `[tool.ruff.lint.isort]`: `known-first-party=["app"]`
- [x] 4.4 Agregar a `pyproject.toml` la sección `[tool.mypy]`: `python_version="3.11"`, `strict=false` (se endurece progresivamente en changes futuros), `ignore_missing_imports=true`, `exclude=["migrations/", "tests/"]`
- [x] 4.5 Agregar a `pyproject.toml` la sección `[tool.pytest.ini_options]`: `asyncio_mode="auto"`, `testpaths=["tests"]`

## 5. Workspace backend — venv, instalación y lockfile

- [x] 5.1 Crear el entorno virtual desde `backend/`: `python -m venv .venv`
- [x] 5.2 Activar el venv (`.venv/Scripts/activate` en Windows o `source .venv/bin/activate` en POSIX) e instalar el proyecto con extras dev: `pip install -e ".[dev]"`
- [x] 5.3 Generar `backend/requirements.txt` como lockfile reproducible: `pip freeze --exclude-editable > requirements.txt`
- [x] 5.4 Crear `backend/.env.example` con variables **mínimas para bootstrap**: `ENVIRONMENT=development`, `BACKEND_CORS_ORIGINS=http://localhost:5173` (las variables de BD, JWT y secretos se agregan en Change 02/06/19)
- [x] 5.5 Copiar `backend/.env.example` a `backend/.env` (no se versiona; documentado en `.gitignore`)

## 6. Workspace backend — entrypoint y health check

- [x] 6.1 Crear `backend/app/main.py` con la instancia FastAPI: `app = FastAPI(title="Food Store API", version="0.1.0")` y comentario `# Routers de negocio se registran en changes posteriores (06+)`
- [x] 6.2 Agregar a `backend/app/main.py` el endpoint `GET /health` que devuelva `{"status": "ok"}` con HTTP 200 (sin dependencias de BD ni autenticación)
- [x] 6.3 Crear `backend/app/core/config.py` vacío con docstring `"""Settings se introducen en Change 02 — backend-core-foundation."""` (placeholder para cumplir la convención de capas sin invadir el alcance de Change 02)

## 7. Workspace frontend — inicialización con Vite

- [x] 7.1 Desde `frontend/` ejecutar `npm create vite@latest . -- --template react-ts` (acepta sobreescribir el directorio vacío)
- [x] 7.2 Ejecutar `npm install` para resolver las dependencias generadas por el template
- [x] 7.3 Verificar que `package.json` generado incluye scripts `dev`, `build`, `preview`; agregar manualmente los scripts `test` (`vitest`) y `lint` (`eslint .`)
- [x] 7.4 Limpiar archivos demo del template: vaciar `src/App.tsx` (dejar export por defecto vacío), vaciar `src/App.css`, vaciar `src/index.css`; eliminar `src/assets/react.svg` y `public/vite.svg`

## 8. Workspace frontend — dependencias mínimas adicionales

> **Alcance acotado**: este change instala únicamente lo necesario para que el bootstrap renderice y se valide. TanStack Query/Form, Zustand, Axios, react-router y similares se introducen en **Change 05 — frontend-core-foundation**.

- [x] 8.1 Instalar dependencias dev de estilo: `npm install -D tailwindcss@^3 postcss autoprefixer prettier eslint-config-prettier`
- [x] 8.2 Instalar dependencias dev de testing: `npm install -D vitest @testing-library/react @testing-library/jest-dom jsdom`

## 9. Workspace frontend — TypeScript y alias de rutas

- [x] 9.1 Editar `frontend/tsconfig.app.json` (NO `tsconfig.json`, que solo declara `references`): asegurar `"strict": true`, `"noEmit": true`, `"target": "ES2022"`, `"moduleResolution": "bundler"`, agregar `"baseUrl": "."` y `"paths": { "@/*": ["./src/*"] }`
- [x] 9.2 Editar `frontend/vite.config.ts`: importar `path` desde `node:path`, agregar `resolve.alias` con `"@": path.resolve(__dirname, "./src")`, mantener el plugin React, fijar `server.port: 5173`

## 10. Workspace frontend — TailwindCSS

- [x] 10.1 Inicializar Tailwind desde `frontend/`: `npx tailwindcss init -p` (genera `tailwind.config.js` y `postcss.config.js`)
- [x] 10.2 Editar `tailwind.config.js`: configurar `content: ["./index.html", "./src/**/*.{ts,tsx}"]`
- [x] 10.3 Agregar las directivas Tailwind a `frontend/src/index.css`: `@tailwind base;`, `@tailwind components;`, `@tailwind utilities;`

## 11. Workspace frontend — estructura FSD

- [x] 11.1 Crear directorios FSD raíz: `src/app/`, `src/pages/`, `src/widgets/`, `src/features/`, `src/entities/`, `src/shared/`
- [x] 11.2 Crear `.gitkeep` en `src/widgets/`, `src/features/`, `src/entities/` (vacíos en este change)
- [x] 11.3 Crear `src/shared/ui/` con `.gitkeep` (recibirá componentes base en changes posteriores)
- [x] 11.4 Crear el directorio `src/pages/home/ui/` antes de cualquier archivo (precondición de 11.5)
- [x] 11.5 Crear `src/pages/home/ui/HomePage.tsx` con un componente funcional mínimo que renderice `<h1>Food Store — bootstrap OK</h1>`
- [x] 11.6 Editar `src/App.tsx` para importar `HomePage` desde `@/pages/home/ui/HomePage` y renderizarlo
- [x] 11.7 Verificar que `src/main.tsx` (generado por Vite) monta `<App />` en `#root`; ajustar solo si es necesario

## 12. Workspace frontend — ESLint y Prettier (reemplazar generados por Vite)

> **Atención**: el template Vite ya generó `eslint.config.js` con flat config v9. Las tareas de este grupo **modifican** los archivos existentes; no los crean desde cero.

- [x] 12.1 Editar `frontend/eslint.config.js` (generado por Vite): agregar `eslint-config-prettier` como **última** entrada del array de configs para desactivar reglas conflictivas con Prettier
- [x] 12.2 Crear `frontend/.prettierrc` con: `semi: false`, `singleQuote: true`, `tabWidth: 2`, `trailingComma: "es5"`
- [x] 12.3 Crear `frontend/.prettierignore` con: `dist`, `node_modules`, `*.md`, `coverage`

## 13. Workspace frontend — Vitest y entorno

- [x] 13.1 Crear `frontend/src/test/setup.ts` con `import "@testing-library/jest-dom"` (precondición de 13.2)
- [x] 13.2 Editar `frontend/vite.config.ts`: agregar la sección `test` con `environment: "jsdom"`, `globals: true`, `setupFiles: ["./src/test/setup.ts"]`; agregar `/// <reference types="vitest" />` al inicio del archivo
- [x] 13.3 Crear `frontend/.env.example` con variables: `VITE_API_BASE_URL=http://localhost:8000/api/v1`, `VITE_APP_NAME=FoodStore`
- [x] 13.4 Copiar `frontend/.env.example` a `frontend/.env`

## 14. Verificación final

> **Precondición de todo el grupo**: las tareas 5.1–5.5 (venv backend) y 7.1–7.2 (install frontend) están completadas. Si alguna falla, NO continuar con verificación.

- [x] 14.1 Backend lint: desde `backend/` con venv activo ejecutar `ruff check app/` — exit code 0
- [x] 14.2 Backend type check: desde `backend/` con venv activo ejecutar `mypy app/main.py` — exit code 0 (warnings de stubs aceptables)
- [x] 14.3 Backend tests: desde `backend/` con venv activo ejecutar `pytest` — exit code 0 (0 tests collected es válido)
- [x] 14.4 Backend runtime: desde `backend/` con venv activo ejecutar `uvicorn app.main:app` y verificar con `curl http://localhost:8000/health` que responde `{"status":"ok"}` con HTTP 200
- [x] 14.5 Frontend type check: desde `frontend/` ejecutar `npx tsc --noEmit` — exit code 0
- [x] 14.6 Frontend lint: desde `frontend/` ejecutar `npm run lint` — exit code 0
- [x] 14.7 Frontend build: desde `frontend/` ejecutar `npm run build` — debe generar `dist/` sin errores
- [x] 14.8 Frontend runtime: desde `frontend/` ejecutar `npm run dev`, abrir `http://localhost:5173`, verificar que renderiza "Food Store — bootstrap OK" sin errores en la consola del navegador
- [x] 14.9 Documentar en el `README.md` los comandos exactos usados en 14.1–14.8 para que un evaluador externo pueda reproducir la verificación desde un clone limpio
