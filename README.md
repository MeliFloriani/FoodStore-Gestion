# Food Store

[![CI](https://github.com/MeliFloriani/FoodStore-Gestion/actions/workflows/ci.yml/badge.svg)](https://github.com/MeliFloriani/FoodStore-Gestion/actions/workflows/ci.yml)

Plataforma de e-commerce de productos alimenticios desarrollada como Trabajo Práctico Integrador (TPI). Monorepo con backend **FastAPI** (Python 3.11) y frontend **React + TypeScript** (Node 20 / Vite 5), sin tooling especial de monorepo.

**Stack resumido**: FastAPI · SQLModel · PostgreSQL 15 · Alembic · python-jose · passlib · slowapi · MercadoPago SDK | React 19 · TypeScript 6 · Vite 8 · TailwindCSS 3 · TanStack Query/Form · Zustand 5 · Axios · Vitest · pnpm 10

---

## Prerrequisitos

| Herramienta | Versión mínima | Instalación |
|-------------|----------------|-------------|
| Python | 3.11 | [python.org](https://www.python.org/) o `pyenv install 3.11` |
| Node.js | 20 | [nodejs.org](https://nodejs.org/) o `nvm install 20` |
| pnpm | 10.32.1 | `npm i -g pnpm` o `corepack enable && corepack prepare pnpm@10.32.1 --activate` |
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

### Docker (opcional, para deploy)

| Herramienta | Versión mínima | Instalación |
|-------------|----------------|-------------|
| Docker | 24+ | [docker.com](https://www.docker.com/) — Docker Desktop para Windows/Mac |
| Railway CLI | latest | `npm i -g @railway/cli` (solo si deployás desde CLI) |

---

## Build de imágenes Docker

```bash
# Backend (python:3.11-slim)
docker build -t foodstore-backend ./backend
# → ~489MB, HEALTHCHECK via Python, EXPOSE 8000

# Frontend (node:22-alpine → nginx:alpine, pnpm via corepack)
docker build \
  --build-arg VITE_API_BASE_URL=http://localhost:8000/api/v1 \
  -t foodstore-frontend ./frontend
# → ~75MB, nginx:alpine, SPA fallback + Brotli/gzip, EXPOSE 80
```

> **Importante**: `VITE_API_BASE_URL` se pasa como **build arg** (no runtime env) porque Vite incrusta las variables `VITE_*` en el bundle estático durante el build. El frontend usa **pnpm** con corepack (versión pineada en `package.json` → `packageManager`).

---

## Deploy en Railway

Este proyecto está dockerizado para deploy en **Railway**. Los servicios se configuran desde el Dashboard:

1. Crear proyecto Railway conectando el repositorio GitHub
2. Agregar servicio **backend** → Root Directory = `backend/` → Railway detecta el Dockerfile
3. Agregar servicio **frontend** → Root Directory = `frontend/` → Railway detecta el Dockerfile
4. Provisionar **PostgreSQL plugin** desde el Dashboard
5. Configurar variables de entorno en cada servicio (ver sección [Variables de entorno](#variables-de-entorno))
6. Ejecutar migraciones: `railway run alembic upgrade head`
7. Ejecutar seed data: `railway run python -m app.db.seed`

> Railway provee HTTPS automático con dominio `.railway.app`. No requiere configuración de SSL.

### Variables de entorno

**Backend** (setear en Railway Dashboard como **Environment Variables**):

| Variable | Descripción |
|----------|-------------|
| `ENVIRONMENT=production` | Modo producción |
| `DATABASE_URL` | Inyectada automáticamente por Railway PostgreSQL plugin |
| `BACKEND_CORS_ORIGINS` | URL del frontend (ej: `https://frontend.up.railway.app`) |
| `SECRET_KEY` | Random 64-char hex — generar con `python -c "import secrets; print(secrets.token_hex(32))"` |
| `MP_ACCESS_TOKEN` | Token de MercadoPago (sandbox o producción) |
| `MP_PUBLIC_KEY` | Public key de MercadoPago |
| `MP_WEBHOOK_SECRET` | Webhook secret desde MercadoPago Dashboard |
| `MP_NOTIFICATION_URL` | `https://<backend-url>/api/v1/pagos/webhook` |
| `FRONTEND_BASE_URL` | `https://<frontend-url>` |
| `BCRYPT_COST=12` | Costo de hashing bcrypt |
| `API_V1_PREFIX=/api/v1` | Prefijo de API |

**Frontend** (setear en Railway Dashboard como **Build Variable**, NO como environment variable):

| Variable | Descripción |
|----------|-------------|
| `VITE_API_BASE_URL` | `https://<backend-url>/api/v1` |

> **⚠️ Importante**: Las variables `VITE_*` deben configurarse como **Build Variables** en Railway porque se incrustan en el bundle estático durante el build de Vite. No funcionan como runtime env vars.

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
corepack enable && pnpm install

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
| `dev` | `pnpm run dev` | Servidor Vite en puerto 5173 |
| `build` | `pnpm run build` | Build de producción en `dist/` |
| `test` | `pnpm run test` | Ejecutar tests con Vitest |
| `lint` | `pnpm run lint` | Linting con ESLint |
| `preview` | `pnpm run preview` | Preview del build de producción |

### Coverage

| Capa | Comando | Descripción |
|------|---------|-------------|
| Backend | `pytest --cov=app --cov-report=term-missing` | Ejecutar tests con reporte de cobertura en terminal |
| Backend | `pytest --cov=app --cov-report=html` | Generar reporte HTML en `backend/htmlcov/index.html` |
| Frontend | `pnpm exec vitest run --coverage` | Ejecutar tests con reporte de cobertura (HTML + lcov) |

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
pnpm exec tsc --noEmit

# Lint
pnpm run lint

# Build (nota: saltea tsc-b hasta que se corrijan errores TS pre-existentes)
pnpm exec vite build
# → genera dist/ sin errores
```

---

## Screenshots del sistema en producción

> Las capturas se encuentran en `docs/screenshots/` y están mapeadas contra los criterios de la rúbrica (CE-01 a CE-14).

| Criterio | Descripción | Archivo |
|----------|-------------|---------|
| CE-01 | Catálogo público con productos | *(pendiente)* |
| CE-02 | Detalle de producto | *(pendiente)* |
| CE-03 | Registro de usuario | *(pendiente)* |
| CE-04 | Inicio de sesión | *(pendiente)* |
| CE-05 | Carrito de compras | *(pendiente)* |
| CE-06 | Checkout con dirección | *(pendiente)* |
| CE-07 | Pago MercadoPago | *(pendiente)* |
| CE-08 | Documentación Swagger | *(pendiente)* |
| CE-09 | Confirmación de pedido | *(pendiente)* |
| CE-10 | Historial de pedidos | *(pendiente)* |
| CE-11 | Timeline de estados | *(pendiente)* |
| CE-12 | Dashboard admin | *(pendiente)* |
| CE-13 | Gestión de productos | *(pendiente)* |
| CE-14 | Gestión de pedidos | *(pendiente)* |

---

## Video demo

> Video demostrativo del flujo completo (registro → login → catálogo → carrito → checkout → pago MP → seguimiento → admin).

Link: *(pendiente — grabar y subir a YouTube como no listado)*

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
│   ├── Dockerfile           ← Multi-stage build (python:3.11-slim, HEALTHCHECK)
│   ├── .dockerignore
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
│   ├── Dockerfile           ← Multi-stage (node:20-alpine → nginx:alpine)
│   ├── nginx.conf            ← SPA fallback, Brotli, caching
│   ├── .dockerignore
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

---

## Branch didáctico — `clase-demo`

El branch [`clase-demo`](../../tree/clase-demo) tiene el flujo completo de la clase ensayado paso a paso, con **9 tags** que marcan el estado del repositorio en cada hito del proceso SDD. Sirve como referencia para revisar cómo queda el repo después de cada paso.

```bash
git fetch --tags
git checkout clase-demo
```

| Tag | Estado del repo |
|-----|-----------------|
| `step-0-clean` | Repo recién clonado |
| `step-2-skills-installed` | Después de instalar las skills (las skills viven en `~/.agents/skills/`, no en el repo) |
| `step-3-kb-generated` | Base de conocimiento generada en `knowledge-base/` (10 archivos canónicos + README) |
| `step-4-openspec-init` | OpenSpec inicializado: `openspec/`, `.opencode/`, `.claude/` |
| `step-5-agents-configured` | `AGENTS.md` y `openspec/config.yaml` con context y rules del proyecto |
| `step-6-roadmap-done` | `openspec/roadmap.md` con los 10 changes y sus dependencias |
| `step-7a-proposed` | `us-000-setup` propuesto: proposal + design + 4 specs + tasks |
| `step-7b-applied` | `us-000-setup` implementado: backend FastAPI + frontend Vite + tests |
| `step-7c-archived` | `us-000-setup` archivado: specs sincronizados, change cerrado |

Para saltar a un estado específico:

```bash
git checkout step-3-kb-generated     # ver cómo queda con la KB completa
git checkout step-7c-archived        # ver el repo después del primer change
git checkout clase-demo              # volver al estado final
```

### Skills usadas en la clase

- **kb-creator** — genera la base de conocimiento en `knowledge-base/`. Repo: [JuanCruzRobledo/kb-creator](https://github.com/JuanCruzRobledo/kb-creator).
- **roadmap-generator** — genera `openspec/roadmap.md` desde la KB. Repo: [JuanCruzRobledo/roadmap-generator](https://github.com/JuanCruzRobledo/roadmap-generator).

Instalación:

```bash
npx skills add https://github.com/JuanCruzRobledo/kb-creator
npx skills add https://github.com/JuanCruzRobledo/roadmap-generator
```
