## Why

The Food Store catalog requires a standalone ingredients registry before products can declare their composition and allergen status. The `ingrediente` table (singular) already exists from migration 0001, but lacks a CRUD API and has only a global unique constraint on `nombre` — which blocks name reuse after soft delete. Without Change 10, there is no CRUD API and no way for the Gestor de Stock to maintain the allergen data that informs customer decisions and satisfies regulatory requirements. Change 10 delivers the full ingredients foundation — backend CRUD (ADMIN+STOCK for all endpoints), the minimal frontend entity layer, and the PostgreSQL schema changes (replace global unique constraint with partial unique index + allergen index) — so that Change 11 can introduce the `ProductoIngrediente` M2M association and Change 12 can surface allergen warnings in the public catalog.

## What Changes

- **MODIFIED** `backend/app/models/catalog.py` — change `Ingrediente.nombre` field from `unique=True` to `unique=False` (uniqueness now enforced by migration partial index only). There is NO `app/models/ingrediente.py` file. `Ingrediente` already exists in `app/models/catalog.py` (D-17). Change 10 only modifies the `nombre` field's `unique` parameter from `True` to `False`.
- **NEW** backend layer-first modules: `backend/app/schemas/ingrediente.py`, `backend/app/repositories/ingrediente.py`, `backend/app/services/ingrediente.py`, `backend/app/api/v1/ingredientes.py`.
- **NEW** Alembic migration `0004_ingredientes_table.py` (next revision after `0003_categoria_nombre_per_parent`, `down_revision = 'c9d8e7f6a5b4'`): ALTER operation on existing `ingrediente` table — drops global `uq_ingrediente_nombre` constraint (created by migration 0001), creates partial unique index on `nombre WHERE deleted_at IS NULL`, creates partial index on `es_alergeno WHERE deleted_at IS NULL`.
- **NEW** Pydantic schemas: `IngredienteBase`, `IngredienteCreate`, `IngredienteUpdate`, `IngredienteRead`.
- **NEW** `IngredienteRepository(BaseRepository[Ingrediente])` — inherits CRUD + soft delete + `list_active`; adds `get_by_nombre_active(nombre)` for duplicate detection.
- **NEW** `IngredienteService` — stateless; receives `uow` via DI; raises `NotFoundError` (404 not found) and `ConflictError` (409 nombre duplicado) from `app.core.exceptions` — identical pattern to `CategoriaService`.
- **NEW** 5 REST endpoints under `/api/v1/ingredientes` — all require `require_role("ADMIN", "STOCK")`.
- **WIRING** `UnitOfWork` gains `uow.ingredientes: IngredienteRepository` lazy accessor.
- **WIRING** `build_v1_router` registers `ingredientes_router` under `/api/v1/ingredientes`.
- **NEW** Frontend entity layer: `frontend/src/entities/ingrediente/` — types, fetchers, TanStack Query key factory, mutation hooks, barrel export.

## Capabilities

### New Capabilities

- `backend-ingredientes-management`: Full CRUD API for the ingredients registry (5 endpoints, `require_role("ADMIN", "STOCK")` for all, soft delete, partial unique index on nombre, allergen filter, RFC 7807 errors). No FK coupling to categories or products — flat standalone entity.
- `frontend-ingredientes-entity`: Frontend entity layer — TypeScript types, Axios fetchers, TanStack Query key factory, query and mutation hooks, public barrel. No pages or features in this change.

### Modified Capabilities

- `backend-unit-of-work`: Add `uow.ingredientes: IngredienteRepository` lazy property — wired into the shared transaction context. Replaces the existing `NotImplementedError` stub (or adds if stub absent).
- `backend-api-v1-router`: Register `ingredientes_router` inside `build_v1_router` — new domain router mounted at `/api/v1/ingredientes`.
- `backend-migrations`: Register migration `0004_ingredientes_table` — ALTER on existing `ingrediente` table (singular, consistent with `categoria`, `producto`, `usuario`): drops global `uq_ingrediente_nombre` constraint, creates partial unique index on `nombre WHERE deleted_at IS NULL`, and partial index on `es_alergeno WHERE deleted_at IS NULL`. `down_revision = 'c9d8e7f6a5b4'`.

## Reconciliación de Documentación y Decisiones RBAC

**Tensión detectada**: Integrador.txt §4.2 (línea 181) describe el rol STOCK como "Leer productos, actualizar stock_cantidad y disponible, **ver ingredientes**" — lo que sugeriría solo lectura para STOCK. Sin embargo, Descripcion.txt §1 (línea 13) indica que el Gestor de Stock puede "**gestionar** los ingredientes asociados a cada producto incluyendo la identificación de alérgenos", y §6 (línea 229) confirma "gestionar ingredientes y alérgenos". Las historias de usuario US-011 a US-014 (Historias_de_usuario.txt líneas 671–740) asignan explícitamente el CRUD completo (crear, listar, editar, eliminar) al Gestor de Stock.

**Resolución (consistente con Change 09 archivado)**: Todos los endpoints de `/api/v1/ingredientes` — incluyendo lecturas administrativas — requieren `require_role("ADMIN", "STOCK")`. La frase "ver ingredientes" en §4.2 del Integrador es una descripción resumida e incompleta del rol STOCK; el Sprint 2 (US-011..014) y la Descripción §1/§6 constituyen la fuente de verdad funcional completa. La lectura pública del flag `es_alergeno` se materializará en Change 11/12 vía endpoints de productos — NO en este change.

Este razonamiento es idéntico al aplicado en Change 09 para el RBAC de categorías y queda documentado como D-01 en design.md.

## Impact

- **Backend**: 4 nuevos archivos layer-first (`schemas/ingrediente.py`, `repositories/ingrediente.py`, `services/ingrediente.py`, `api/v1/ingredientes.py`). 1 archivo modificado (`models/catalog.py` — campo `unique` de `Ingrediente.nombre`). UoW y router reciben adiciones mínimas. Migración `0004` es un ALTER sobre tabla `ingrediente` existente — no crea tabla nueva.
- **Frontend**: Nuevo directorio `frontend/src/entities/ingrediente/` (5 archivos). Sin páginas ni features — solo entity layer.
- **Database**: Migración `0004` es un ALTER sobre tabla `ingrediente` ya existente (creada en migración 0001). Drops constraint global `uq_ingrediente_nombre`, crea dos índices parciales. No crea tablas nuevas.
- **Dependencies (upstream)**: Requiere Change 04 (BaseRepository, UoW), Change 07 (auth deps + error handlers). Paralelo a Change 09 (categorías) — sin dependencia cruzada (sin FK a `categoria`, sin coupling).
- **Dependencies (downstream)**: Change 11 (ProductoIngrediente M2M, `es_removible`), Change 12 (catálogo público con filtro `excluirAlergenos`), Change 15/17 (personalización de pedidos con `personalizacion: INTEGER[]`).
- **No breaking changes** a endpoints ni specs existentes.
