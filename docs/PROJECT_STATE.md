# PROJECT_STATE — Food Store

> Documento de estado operativo y arquitectónico. Optimizado para retomar el proyecto en una nueva sesión sin depender del historial del chat. Última actualización: **2026-05-09**.

---

## 1. Estado actual (snapshot)

| Item | Estado |
|------|--------|
| Metodología | OpenSpec / OPSX (workflow fluido: explore → propose → apply → archive) |
| Roadmap total | 26 changes planificados (ver `docs/CHANGES.md`) |
| Changes archivados | **2** (Change 01 — bootstrap-monorepo-structure, Change 02 — backend-core-foundation) |
| Changes activos | **0** (sin changes activos — listo para propose Change 03) |
| Backend operativo | Foundation completa (config, DB async lazy, RFC 7807, middlewares, structlog, rate limiting) — 23/23 tests infra, 92% coverage |
| Frontend operativo | Bootstrap React + Vite + Tailwind + ESLint v9 — sin features |
| BD | PostgreSQL local healthy; `foodstore_dev` y `foodstore_test` reachable; sin schema Alembic |
| Auditorías ejecutadas | 2 (tasks de Change 01 y Change 02) |
| Próxima acción | Propose Change 03 (`/opsx:propose backend-alembic-init`) |

---

## 2. Changes completados

### ✅ Change 01 — bootstrap-monorepo-structure

- **Archivo**: `openspec/changes/archive/2026-05-09-bootstrap-monorepo-structure/`
- **Resultado**: Monorepo con workspaces `backend/` y `frontend/` validados.
- **Entregables**:
  - `backend/`: `pyproject.toml`, venv, FastAPI app esqueleto, `app/{core,db,models,schemas,api,services,repositories}/__init__.py`, ruff/mypy config, hello-world `GET /health`.
  - `frontend/`: Vite + React 18 + TS5 strict + Tailwind 3 + ESLint v9 flat config, App.tsx mínimo.
  - Root: `.gitignore`, `README.md`, `docs/CHANGES.md`.
- **Verificaciones pasadas**: 67 tasks completadas.
- **Lecciones aprendidas que persisten**:
  - ESLint v9 requiere flat config (`eslint.config.js`), NO `.eslintrc.*`.
  - Tailwind 3 (no 4) por estabilidad.
  - Pydantic v2 + pydantic-settings (no Pydantic v1).

### ✅ Change 02 — backend-core-foundation

- **Archivo**: `openspec/changes/archive/2026-05-09-backend-core-foundation/`
- **Resultado**: Foundation backend completa con config tipada, DB async lazy, error handling RFC 7807, middleware stack y logging estructurado.
- **Entregables**:
  - `app/core/config.py` — `Settings(BaseSettings)` + `get_settings()` con `@lru_cache`
  - `app/core/context.py` — ContextVar única para `request_id`
  - `app/core/exceptions.py` — jerarquía `AppError` → `NotFoundError`, `ConflictError`, `AppValidationError`, `UnauthorizedError`, `ForbiddenError`
  - `app/core/logging.py` — structlog (JSON prod / Console dev) + processor `request_id`
  - `app/core/middleware.py` — `RequestIDMiddleware`
  - `app/core/rate_limit.py` — `get_limiter()` lazy con slowapi
  - `app/db/base.py` — `MetaData` con `NAMING_CONVENTION` SQLAlchemy
  - `app/db/session.py` — `get_engine()`, `get_session_factory()`, `get_session()` lazy
  - `app/models/base.py` — `Base(SQLModel, table=False)` con id/created_at/updated_at/deleted_at
  - `app/schemas/base.py` — `Page[T]`, `ProblemDetail`, `create_pagination_meta`
  - `app/api/errors.py` — `register_error_handlers` RFC 7807
  - `app/api/v1/router.py` — `build_v1_router(settings)` + `GET /api/v1/health`
  - `app/main.py` — lifespan + CORS + middlewares + error handlers + wire-up
  - `backend/tests/test_infrastructure.py` — 23 tests de infraestructura
- **Tasks completadas**: 78/78 (87 checkboxes en tasks.md contando sub-ítems).
- **Cobertura**: 92%.
- **Commit apply**: `fa375df` — `feat(backend): core foundation — config, db async lazy, error handling RFC 7807, middlewares, lifespan`

---

## 3. Changes activos

Sin changes activos — listo para propose Change 03 (`/opsx:propose backend-alembic-init`).

---

## 4. Estado por sprint / roadmap

> Fuente canónica del roadmap: `docs/CHANGES.md`

| # | Change | Estado | Sprint |
|---|--------|--------|--------|
| 01 | bootstrap-monorepo-structure | ✅ Archivado | Sprint 0 |
| 02 | backend-core-foundation | ✅ Archivado | Sprint 0 |
| 03 | backend-alembic-init | ⏳ Pendiente | Sprint 0 |
| 04 | backend-uow-baserepository | ⏳ Pendiente | Sprint 0 |
| 05+ | (features de dominio) | ⏳ Pendiente | Sprint 1+ |

Sprint 0 (foundation) finaliza al cerrar Change 04. A partir del 05 comienzan features de dominio.

---

## 5. Decisiones arquitectónicas (snapshot)

### Backend
- **Layered architecture**: `Router → Service → UoW → Repository → Model`
- **Excepción documentada (D-13)**: endpoints de health (`GET /health` y `GET /api/v1/health`) saltean el patrón porque son probes de infraestructura, no lógica de dominio.
- **Lazy initialization** (D-05): `get_engine`, `get_session_factory`, `get_limiter`, `get_settings` con `@lru_cache(maxsize=1)`. PROHIBIDO instanciar a nivel de módulo.
- **Lifespan FastAPI** (D-05): `await get_engine().dispose()` en shutdown.
- **Errores RFC 7807** (D-08): `ProblemDetail` con `Content-Type: application/problem+json`. Validation handler retorna **un solo** `ProblemDetail` con extensión `errors: [...]`, no múltiples responses.
- **Soft delete**: campo `deleted_at: datetime | None` en `Base`.
- **Auto-update timestamps** (D-04): `updated_at` con `sa_column_kwargs={"onupdate": lambda: datetime.now(UTC)}` — sin esto, nunca se refresca.
- **Naming convention SQLModel** (D-12, P-07): `SQLModel.metadata.naming_convention = NAMING_CONVENTION` aplicado en `app/db/base.py` ANTES de cualquier import de modelos.
- **Versión del paquete** (D-14): `importlib.metadata.version("foodstore-backend")`. NO incluir `APP_VERSION` en Settings.
- **`anyio` sin `[trio]`** (D-15): pytest-anyio usa asyncio backend por default.
- **ContextVar única** (D-16, P-04): `request_id_ctx` vive solo en `app/core/context.py`. Logging y middleware la importan desde ahí. No duplicar.
- **Override Settings en tests** (D-16): protocolo obligatorio `get_settings.cache_clear() + get_engine.cache_clear() + get_session_factory.cache_clear() + get_limiter.cache_clear()` antes y después del override.
- **httpx en tests** (P-05): `AsyncClient(transport=ASGITransport(app=app), base_url=...)`. El parámetro `app=` directo está deprecado.
- **API prefix**: `/api/v1` (configurable via `Settings.API_V1_PREFIX`).
- **PKs**: UUID v4 (no autoincremental).

### Frontend
- **Feature-Sliced Design (FSD)**: capas `app/`, `pages/`, `widgets/`, `features/`, `entities/`, `shared/`.
- **TypeScript strict** desde día 0.
- **Tailwind 3** (no Tailwind 4 por inestabilidad de plugins en 04/2026).
- **ESLint v9 flat config** obligatorio.

---

## 6. Stack tecnológico

### Backend
- Python 3.11+
- FastAPI
- SQLModel (sobre SQLAlchemy 2.x async)
- asyncpg
- PostgreSQL 15+
- Alembic (init en Change 03)
- Pydantic v2 + pydantic-settings
- slowapi (rate limiting)
- structlog (logging estructurado)
- pytest + pytest-asyncio + httpx + anyio (sin extra `[trio]`)
- ruff + mypy

### Frontend
- React 18
- TypeScript 5 strict
- Vite 5
- Tailwind 3
- ESLint v9 (flat config)

### Tooling
- OpenSpec / OPSX (CLI: `openspec`)
- Engram (memoria persistente entre sesiones)

---

## 7. Convenciones técnicas

### Estructura backend
```
backend/
├── app/
│   ├── core/
│   │   ├── config.py        ← Settings + get_settings (lru_cache)
│   │   ├── context.py       ← request_id ContextVar (única fuente)
│   │   ├── exceptions.py    ← AppError jerarquía
│   │   ├── logging.py       ← structlog config + processors
│   │   ├── middleware.py    ← RequestIDMiddleware
│   │   └── rate_limit.py    ← get_limiter (lru_cache)
│   ├── db/
│   │   ├── base.py          ← MetaData + naming_convention
│   │   └── session.py       ← get_engine, get_session_factory, get_session (todas lazy)
│   ├── models/
│   │   └── base.py          ← Base(SQLModel, table=False)
│   ├── schemas/
│   │   └── base.py          ← Page[T], ProblemDetail, create_pagination_meta
│   ├── api/
│   │   ├── errors.py        ← register_error_handlers
│   │   └── v1/
│   │       └── router.py    ← build_v1_router(settings) factory
│   ├── services/            ← (vacío hasta Change 04+)
│   ├── repositories/        ← (vacío hasta Change 04)
│   └── main.py              ← lifespan + wire-up
└── tests/
    ├── conftest.py          ← override_settings, async_client, test_db_session
    └── test_infrastructure.py
```

### Naming
- Constraints DB: `ix_*`, `uq_*_*`, `ck_*_*`, `fk_*_*_*`, `pk_*` (SQLModel metadata).
- Excepciones de dominio: sufijo `Error`. La de validación es `AppValidationError` para no chocar con `pydantic.ValidationError`.
- Endpoints: `/api/v1/<recurso>` con verbos HTTP semánticos.
- Headers: `X-Request-ID` propagado en request y response.

### Logging
- Dev: `ConsoleRenderer` (legible).
- Prod: `JSONRenderer` (parseable).
- Todo log incluye `request_id` automáticamente vía processor.

### Errores
- Toda response de error usa `application/problem+json`.
- Validation: un solo response con extensión `errors: list[dict]`.
- Unhandled: log con traceback + response 500 sin exponer mensaje.

---

## 8. Riesgos detectados y auditorías

### Auditoría Change 01 (tasks.md)
- ✅ Resuelta antes de apply.
- Hallazgos menores: ambigüedad en versiones de dependencias.

### Auditoría Change 02 (tasks.md + design.md)
- ✅ Resuelta. 8 bloqueantes (P-01 a P-07 + R-A-05) corregidos:
  - **P-01**: engine eager → lazy con `lru_cache`.
  - **P-02**: limiter y router eager → factory + lazy.
  - **P-03**: tests sin invalidar caches → protocolo `cache_clear()`.
  - **P-04**: ContextVar duplicada → única en `app/core/context.py`.
  - **P-05**: `AsyncClient(app=...)` deprecado → `ASGITransport`.
  - **P-06**: `updated_at` sin auto-update → `sa_column_kwargs={"onupdate": ...}`.
  - **P-07**: `SQLModel.metadata` no vinculado → naming convention aplicado en `app/db/base.py` antes de imports de modelos.
  - **R-A-05**: consecuencias de no tener `onupdate` documentadas.

### Riesgos abiertos
- **Migrations**: hasta Change 03, no hay control de schema. NO crear modelos de dominio antes de tener Alembic.
- **Persistencia de sesión**: hasta Change 04, no hay UoW. Cualquier servicio escrito antes mezclará persistencia y lógica.
- **Test DB**: requiere Postgres local en `foodstore_test`. Sin esto, los readiness tests fallan.

---

## 9. Próximos pasos recomendados

### Inmediato
1. **Propose Change 03**: `/opsx:propose backend-alembic-init`
   - Alembic init + primera migration (tabla técnica / `alembic_version`).
   - Prerequisito: foundation Change 02 archivada (✅ hecho).

### Corto plazo (Sprint 0)
2. Apply Change 03 — Alembic + primera migration.
3. Propose + apply Change 04 — UoW + BaseRepository genérico.
4. Cerrar Sprint 0 con foundation completa.

### Mediano plazo (Sprint 1)
7. Comenzar features de dominio (Change 05+): User, Product, Cart, etc.
8. Frontend: incorporar React Router + estado global + integración con `/api/v1`.

---

## 10. Comandos OPSX relevantes

```bash
# Ver estado completo del workspace
openspec list --json

# Ver estado de un change concreto
openspec status --change "<name>" --json

# Ver instrucciones para crear/regenerar un artefacto
openspec instructions <artifact-id> --change "<name>" --json

# Ver instrucciones de apply (contexto de implementación)
openspec instructions apply --change "<name>" --json

# Crear un nuevo change
openspec new change "<name>"
```

### Slash commands (Claude Code)
- `/opsx:explore [topic]` — sesión de pensamiento, sin código
- `/opsx:propose [change-name]` — crea change + todos los artefactos
- `/opsx:apply [change-name]` — implementa tareas
- `/opsx:archive [change-name]` — sincroniza specs y archiva

---

## 11. Dependencias entre changes

```
01 bootstrap-monorepo-structure    (✅ archivado)
        │
        ▼
02 backend-core-foundation         (✅ archivado)
        │
        ▼
03 backend-alembic-init            (⏳ requiere 02)
        │
        ▼
04 backend-uow-baserepository      (⏳ requiere 02 + 03)
        │
        ▼
05+ features de dominio            (⏳ requiere 04)
```

**Reglas de orden**:
- Ningún modelo de dominio puede entrar antes de Change 03 (sin migrations no hay schema controlado).
- Ningún servicio puede entrar antes de Change 04 (sin UoW se mezcla persistencia y lógica).
- Frontend puede avanzar en paralelo a partir del Sprint 1, pero requiere Change 02 mergeado para tener endpoints reales.

---

## 12. Qué NO debe implementarse todavía

| Cosa | Cuándo | Por qué |
|------|--------|---------|
| UoW pattern | Change 04 | Foundation aún no completa |
| BaseRepository genérico | Change 04 | Depende de UoW |
| Alembic init / migrations | Change 03 | Aún no hay infra DB completa |
| Modelos de dominio (User, Product…) | Change 05+ | Requiere migrations |
| Service layer concreto | Change 05+ | Requiere UoW + repos |
| JWT / autenticación | Change 06+ | Requiere modelo User |
| Endpoints de negocio | Change 05+ | Requiere stack completo |
| Caché Redis | Sprint 2+ | Optimización prematura |
| WebSockets / SSE | Sprint 2+ | Fuera de scope inicial |
| OpenTelemetry / tracing | Sprint 2+ | Logs estructurados son suficientes para foundation |

---

## 13. Estado exacto de Change 02 (backend-core-foundation)

**Change 02 archivado.** Ver detalles completos en:

- `openspec/changes/archive/2026-05-09-backend-core-foundation/`
  - `proposal.md` — propuesta original
  - `design.md` — diseño técnico (decisiones D-01 a D-16)
  - `tasks.md` — 78/78 tasks completadas
  - `specs/` — delta specs sincronizadas a `openspec/specs/`

Specs canónicas resultantes en:
- `openspec/specs/backend-scaffold/spec.md` (actualizado)
- `openspec/specs/backend-config/spec.md`
- `openspec/specs/backend-database-core/spec.md`
- `openspec/specs/backend-error-handling/spec.md`
- `openspec/specs/backend-middleware-stack/spec.md`
- `openspec/specs/backend-api-v1-router/spec.md`
- `openspec/specs/backend-pagination-schema/spec.md`
- `openspec/specs/backend-structured-logging/spec.md`

---

## 14. Recomendaciones para retomar el proyecto en un nuevo chat

### Bootstrap mínimo en una nueva sesión
```
1. Leer este archivo: docs/PROJECT_STATE.md
2. Leer roadmap: docs/CHANGES.md
3. Validar estado live: openspec list --json
4. Confirmar sin changes activos (Change 02 archivado)
```

Con eso ya hay contexto suficiente para retomar sin reconstruir el chat.

### El siguiente paso es Propose Change 03 (backend-alembic-init)
1. Confirmar Postgres local up (`foodstore_dev` y `foodstore_test` creadas).
2. Confirmar `.env` poblado en `backend/`.
3. Invocar `/opsx:propose backend-alembic-init`.
4. Seguir ciclo: apply → archive → propose Change 04.

### Reglas de oro a respetar siempre
- **Nunca** alterar artefactos ya validados (proposal.md de un change aprobado).
- **Nunca** saltearse las correcciones de auditoría: están documentadas como D-XX en `design.md`.
- **Nunca** introducir UoW, repos o modelos de dominio antes de Change 04 — están reservados a 04 y 05+.
- **Siempre** validar con `openspec status` antes de asumir el estado de un change.
- **Siempre** correr el grupo de verificación antes de archivar.

### Arquitectos/colaboradores nuevos: lectura sugerida
1. `docs/PROJECT_STATE.md` (este archivo) — overview operativo
2. `docs/CHANGES.md` — roadmap completo
3. `docs/Descripcion.txt`, `docs/Historias_de_usuario.txt`, `docs/Integrador.txt` — contexto de negocio
4. `openspec/changes/archive/2026-05-09-backend-core-foundation/proposal.md` y `design.md` — fundamento arquitectónico (Change 02)
5. `openspec/changes/archive/2026-05-09-bootstrap-monorepo-structure/` — referencia de cómo se ejecutó Change 01

---

## Mantenimiento de este documento

Actualizar este archivo:
- Tras cada **apply** completado (mover entrada de "activos" a "completados").
- Tras cada **archive** (actualizar fecha y dependencias).
- Tras cada **propose** nuevo (agregar a "activos").
- Tras cada **decisión arquitectónica** (sección 5).
- Tras cada **auditoría** (sección 8).

No actualizar este archivo para:
- Tareas en progreso dentro de un change (eso vive en `tasks.md` del change).
- Detalles de implementación line-by-line (eso vive en el código).
- Sesiones de exploración (eso vive en engram).
