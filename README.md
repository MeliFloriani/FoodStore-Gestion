# Food Store

Plataforma de e-commerce de productos alimenticios desarrollada como Trabajo Práctico Integrador (TPI). Monorepo con backend **FastAPI** (Python 3.11) y frontend **React + TypeScript** (Node 20 / Vite 5), sin tooling especial de monorepo.

**Stack resumido**: FastAPI · SQLModel · PostgreSQL 15 · Alembic · python-jose · passlib · slowapi · MercadoPago SDK | React 18 · TypeScript 5 · Vite 5 · TailwindCSS 3 · TanStack Query/Form · Zustand · Axios · Vitest

---

## Prerrequisitos

| Herramienta | Versión mínima | Instalación |
|-------------|----------------|-------------|
| Python | 3.11 | [python.org](https://www.python.org/) o `pyenv install 3.11` |
| Node.js | 20 | [nodejs.org](https://nodejs.org/) o `nvm install 20` |
| PostgreSQL | 15 | [postgresql.org](https://www.postgresql.org/) |
| Git | cualquiera | [git-scm.com](https://git-scm.com/) |

**pyenv** (Linux/macOS): `curl https://pyenv.run | bash`  
**nvm** (Linux/macOS): `curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash`  
**nvm** (Windows): [nvm-windows](https://github.com/coreybutler/nvm-windows/releases)

Verificar versiones activas:
```bash
python --version   # debe ser ≥ 3.11
node --version     # debe ser ≥ 20
npm --version      # debe ser ≥ 10
```

---

## Bootstrap backend

```bash
# 1. Clonar el repositorio
git clone <url-del-repo> food-store
cd food-store

# 2. Crear y activar el entorno virtual
cd backend
python -m venv .venv

# Linux/macOS:
source .venv/bin/activate

# Windows (PowerShell):
.venv\Scripts\Activate.ps1

# Windows (cmd/bash):
.venv/Scripts/activate

# 3. Instalar dependencias (incluyendo dev)
pip install -e ".[dev]"

# 4. Copiar variables de entorno
cp .env.example .env
# Editar .env con los valores reales (DATABASE_URL, SECRET_KEY, etc.)

# 5. Arrancar el servidor de desarrollo
uvicorn app.main:app --reload
# → API disponible en http://localhost:8000
# → Swagger en http://localhost:8000/docs
# → Health check en http://localhost:8000/health
```

---

## Bootstrap frontend

```bash
# Desde la raíz del repositorio:
cd frontend

# 1. Instalar dependencias
npm install

# 2. Copiar variables de entorno
cp .env.example .env
# Editar .env si es necesario (por defecto apunta a localhost:8000)

# 3. Arrancar el servidor de desarrollo
npm run dev
# → App disponible en http://localhost:5173
```

---

## Scripts disponibles

### Backend (`cd backend`)

| Script | Comando | Descripción |
|--------|---------|-------------|
| `dev` | `uvicorn app.main:app --reload` | Servidor de desarrollo con hot-reload |
| `test` | `pytest` | Ejecutar suite de tests |
| `lint` | `ruff check app/ && mypy app/main.py` | Linting + type checking |
| `format` | `ruff format app/` | Formateo de código |

### Frontend (`cd frontend`)

| Script | Comando npm | Descripción |
|--------|-------------|-------------|
| `dev` | `npm run dev` | Servidor Vite en puerto 5173 |
| `build` | `npm run build` | Build de producción en `dist/` |
| `test` | `npm run test` | Ejecutar tests con Vitest |
| `lint` | `npm run lint` | Linting con ESLint |
| `preview` | `npm run preview` | Preview del build de producción |

---

## Convenciones de commits

Este proyecto utiliza [Conventional Commits](https://www.conventionalcommits.org/):

```
<tipo>[ámbito opcional]: <descripción corta>

[cuerpo opcional]

[pie(s) opcional(es)]
```

**Tipos permitidos**:

| Tipo | Uso |
|------|-----|
| `feat` | Nueva funcionalidad |
| `fix` | Corrección de bug |
| `chore` | Mantenimiento, dependencias, configuración |
| `docs` | Cambios en documentación |
| `refactor` | Refactor sin cambio de comportamiento |
| `test` | Agregar o corregir tests |
| `style` | Formateo, punto y coma, etc. |

**Ejemplos**:

```bash
feat(auth): agregar endpoint POST /auth/login con JWT
fix(productos): corregir validación de stock negativo
chore(deps): actualizar fastapi a 0.115.x
```

---

## Verificación del bootstrap

Comandos para verificar que el entorno funciona correctamente (ejecutar después de completar el bootstrap):

```bash
# Backend
cd backend

# Lint
.venv/Scripts/ruff check app/          # Windows
# source .venv/bin/activate && ruff check app/  # Linux/macOS

# Type check
.venv/Scripts/mypy app/main.py

# Tests
.venv/Scripts/pytest

# Health check (con el servidor corriendo)
curl http://localhost:8000/health
# Respuesta esperada: {"status":"ok"}

# Frontend
cd ../frontend

# Type check
npx tsc --noEmit

# Lint
npm run lint

# Build
npm run build
# → genera dist/ sin errores
```

---

## Estructura del proyecto

```
food-store/
├── backend/                  ← Workspace Python/FastAPI
│   ├── app/
│   │   ├── api/             ← Routers FastAPI (por dominio)
│   │   ├── services/        ← Lógica de negocio
│   │   ├── repositories/    ← Acceso a datos
│   │   ├── models/          ← Entidades SQLModel
│   │   ├── schemas/         ← Pydantic v2 (Read/Create/Update)
│   │   ├── core/            ← config.py, security.py, uow.py
│   │   ├── db/              ← sessions.py (fábrica async)
│   │   └── main.py          ← Entrypoint + GET /health
│   ├── tests/
│   ├── pyproject.toml
│   ├── requirements.txt     ← Lockfile generado con pip freeze
│   └── .env.example
│
├── frontend/                 ← Workspace React/TS/Vite
│   ├── src/
│   │   ├── app/             ← Providers, router stub, estilos globales
│   │   ├── pages/           ← Composición de páginas (FSD layer)
│   │   ├── widgets/         ← Bloques reutilizables multi-feature
│   │   ├── features/        ← Casos de uso (FSD layer)
│   │   ├── entities/        ← Tipos de dominio (FSD layer)
│   │   └── shared/          ← UI kit, utils, tipos, api client base
│   ├── vite.config.ts
│   ├── tsconfig.app.json
│   ├── tailwind.config.js
│   └── .env.example
│
├── openspec/                 ← Artefactos OPSX (NO editar manualmente)
├── docs/                     ← Documentación del TPI
├── .gitignore
├── .editorconfig
├── .nvmrc                    ← Node 20
├── .python-version           ← Python 3.11
└── README.md
```

---

## Flujo de desarrollo OPSX

```
/opsx:explore  →  pensar antes de comprometerse (opcional)
/opsx:propose  →  generar propuesta + diseño + tareas
/opsx:apply    →  implementar tarea por tarea
/opsx:archive  →  sincronizar specs y cerrar el change
```

Orden de implementación de changes:

```
bootstrap-monorepo-structure  ← Change 01 (este change)
backend-core-foundation       ← Change 02
frontend-core-foundation      ← Change 05
...
```
