## Context

El proyecto Food Store es un e-commerce modular con backend FastAPI y frontend React que coexisten en el mismo repositorio. En este punto no existe ninguna estructura de carpetas, ningún archivo de configuración ni dependencias instaladas. Este change crea la base desde la que todos los changes posteriores construyen.

La rúbrica del TPI (Integrador.txt v5.0) exige: estructura limpia de capas en backend, Feature-Sliced Design en frontend, calidad/linting verificable y un README claro con instrucciones de arranque. Los criterios CE-01, CE-02 y CE-03 del checklist de entrega comienzan aquí.

## Goals / Non-Goals

**Goals:**
- Estructura de monorepo simple (dos workspaces, sin tooling especial) ejecutable desde el día 1
- Backend Python levantable con `uvicorn` devolviendo `GET /health → 200 OK`
- Frontend React levantable con Vite en `http://localhost:5173` con página index vacía
- Linting y formateo configurados y operativos en ambos workspaces
- Variables de entorno gestionadas con `.env.example` versionado y `.env` ignorado
- Versiones de runtime pinneadas y reproducibles (`.python-version`, `.nvmrc`)
- README raíz con instrucciones de bootstrap paso a paso para un desarrollador nuevo

**Non-Goals:**
- Endpoints de negocio (auth, productos, pedidos, pagos, etc.)
- Modelos de dominio o migraciones Alembic
- Componentes de UI funcionales
- Configuración de base de datos activa (solo el driver instalado, sin conexión real)
- Integración con MercadoPago ni otras librerías de features posteriores
- CI/CD ni Docker (pospuesto a Change 26)
- TanStack Router / react-router (pospuesto a Change 05)

## Decisions

### D-01: Monorepo simple sin tooling especial

**Decisión**: Dos carpetas independientes (`backend/` y `frontend/`) en la raíz, cada una con su propio gestor de paquetes y scripts. Sin turborepo, nx ni workspaces de npm.

**Rationale**: El TPI es un proyecto académico con equipo de 1-3 personas. La complejidad de un monorepo orquestado (turborepo/nx) no aporta valor frente a su costo de configuración y aprendizaje. Dos carpetas independientes son suficientes para la escala del proyecto y evitan problemas de versiones cruzadas.

**Alternativas descartadas**:
- `turborepo`: overhead de configuración innecesario para equipos pequeños
- `nx`: curva de aprendizaje alta, plugins específicos difíciles de mantener
- Repositorios separados: viola el requisito de "mismo repositorio" del enunciado

---

### D-02: npm como gestor de paquetes frontend

**Decisión**: Se usa **npm** (incluido con Node 20) en lugar de pnpm.

**Rationale**: npm 10+ (bundled con Node 20) resuelve el problema histórico de rendimiento de npm. El equipo no tiene experiencia específica con pnpm y la ganancia de velocidad no justifica la fricción de un gestor adicional en un proyecto académico. npm es el gestor predeterminado conocido por todos y no requiere instalación separada.

**Alternativas descartadas**:
- `pnpm`: levemente más rápido en monorepos grandes; innecesario aquí y requiere `npm install -g pnpm` como paso previo que puede confundir a evaluadores
- `yarn`: relegado en popularidad; Berry (v2+) tiene configuración más compleja

---

### D-03: Estructura de capas backend (Feature-first dentro de capas)

**Decisión**: Estructura de carpetas en `backend/app/`:

```
app/
├── api/          ← routers FastAPI (uno por dominio en changes futuros)
├── services/     ← lógica de negocio (un módulo por dominio)
├── repositories/ ← acceso a datos (un módulo por entidad)
├── models/       ← entidades SQLModel
├── schemas/      ← Pydantic v2 (separados en Read / Create / Update)
├── core/         ← config.py, security.py, db.py, uow.py
├── db/           ← sessions.py (fábrica de sesiones async)
└── main.py       ← entrypoint FastAPI con health check
tests/            ← espejo de app/, conftest.py raíz
```

**Rationale**: La rúbrica exige separación explícita de capas. Este layout es el más directo para FastAPI + SQLModel y permite a cada change posterior agregar un módulo sin tocar la estructura base.

---

### D-04: Estructura frontend Feature-Sliced Design (FSD)

**Decisión**: Estructura `frontend/src/` con las 6 capas FSD:

```
src/
├── app/          ← providers, router stub, global styles
├── pages/        ← composición de página (HomePage vacía en este change)
├── widgets/      ← bloques reutilizables multi-feature (vacío en este change)
├── features/     ← casos de uso (vacío en este change)
├── entities/     ← tipos de dominio (vacío en este change)
└── shared/       ← UI kit, utilidades, tipos compartidos, constantes, api client base
```

**Rationale**: FSD es el estándar requerido por el enunciado (Integrador.txt). Las capas vacías se crean con `.gitkeep` para que la estructura sea visible desde el inicio y los cambios futuros tengan un lugar claro donde ir.

---

### D-05: Pinning de versiones de runtime

**Decisión**:
- `.python-version` en raíz con `3.11` (para pyenv / asdf)
- `.nvmrc` en raíz con `20` (para nvm)

**Rationale**: Garantiza reproducibilidad sin depender de la versión global instalada en la máquina del evaluador. Es un paso que no cuesta nada y previene "funciona en mi máquina".

---

### D-06: Gestión de variables de entorno

**Decisión**:
- `.env.example` versionado en `backend/` y `frontend/` con todas las variables esperadas y valores placeholder
- `.env` agregado al `.gitignore` raíz
- Backend lee con `python-dotenv` desde `app/core/config.py` (Settings con Pydantic BaseSettings)
- Frontend usa `VITE_` prefix; `import.meta.env.VITE_*` en código

**Rationale**: Convención estándar para proyectos Python y Vite. Evita que credenciales lleguen al repositorio. El `.env.example` actúa como documentación viva de las variables requeridas.

---

### D-07: Herramientas de calidad de código

**Backend**:
- `ruff` — linter ultrarrápido que reemplaza flake8 + isort; configurado en `pyproject.toml`
- `black` — formateo determinista; integrado con ruff (ruff-format o black directamente)
- `mypy` — type checking estricto; configurado en `pyproject.toml`

**Frontend**:
- `ESLint` (v9 flat config) + plugin TypeScript — linting
- `Prettier` — formateo; integrado con ESLint via `eslint-config-prettier`

**Rationale**: Estas herramientas son las mencionadas explícitamente en el stack requerido. Configurarlas desde el bootstrap garantiza que los changes posteriores no puedan ignorarlas.

---

### D-08: Health check mínimo

**Decisión**: `GET /health` en `app/main.py` devuelve `{"status": "ok"}` con HTTP 200. No requiere base de datos ni autenticación.

**Rationale**: Permite validar que el servidor FastAPI arranca correctamente sin necesitar ninguna dependencia de infraestructura. Es el mínimo verificable para dar por "bootstrappeado" el backend.

---

### D-09: Dependencias de Python — pyproject.toml como fuente de verdad

**Decisión**: Se usa `pyproject.toml` (PEP 517/518) como fuente de verdad. Se genera `requirements.txt` via `pip freeze` para entornos que no soporten pyproject directamente (ej. algunos CIs legacy). El entorno virtual va en `backend/.venv/` (ignorado en `.gitignore`).

**Rationale**: `pyproject.toml` es el estándar moderno de Python; `requirements.txt` pin es el fallback operativo. Ambos se mantienen en sync.

---

### D-10: Convención de Conventional Commits

**Decisión**: El `.gitignore` y el `README.md` documentan la convención Conventional Commits. No se configura un hook automático en este change (pospuesto a Change 25 o configuración manual del equipo).

**Rationale**: CE-01 del checklist exige Conventional Commits. Documentarlo en el README desde el inicio establece la convención sin imponer fricción de tooling desde el día 0.

## Risks / Trade-offs

| Riesgo | Mitigación |
|--------|-----------|
| Versiones de dependencias desactualizadas al momento de implementación | Las versiones del `pyproject.toml` y `package.json` se pinnan con rangos semánticos (`^`); el apply phase usa las versiones latest estables al momento de ejecutarse |
| mypy en modo estricto puede bloquear el desarrollo inicial | Se configura con `--ignore-missing-imports` inicialmente; se endurece progresivamente en changes posteriores |
| ESLint v9 flat config tiene sintaxis diferente a v8 | Se documenta en el README; la migración a flat config es inevitable y mejor hacerla desde el inicio |
| `.venv` grande en disco si el evaluador no tiene Python 3.11 | `.nvmrc` y `.python-version` mitigan el riesgo; el README incluye instrucciones de instalación de runtime |
| Frontend sin router en este change (pospuesto a Change 05) | La página index vacía es suficiente para validar Vite; el router se agrega en Change 05 sin retrabajo |

## Migration Plan

No aplica — este es el change inicial. No existe estado previo que migrar.

Estrategia de rollback: `git revert` del commit de este change restaura el estado vacío del repositorio.

## Open Questions

1. ¿El evaluador tiene pyenv/nvm instalado o se debe documentar instalación desde cero en el README? → Documentar ambas opciones en el README para máxima compatibilidad.
2. ¿Se usa `ruff format` (reemplaza black) o se mantienen ambos separados? → Decisión de apply phase: usar `ruff format` para simplificar la cadena de herramientas, pero declarar `black` en devDependencies para compatibilidad con editores.
