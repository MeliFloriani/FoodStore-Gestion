## Why

The Food Store catalog needs a functional category hierarchy before products can be organized and browsed. Without categories, the catalog page is a placeholder and customers cannot discover products by department. Change 09 delivers the full categories foundation — backend CRUD (ADMIN+STOCK writes, public reads), a two-migration PostgreSQL schema fix (per-parent uniqueness instead of global), and the minimal frontend entity layer that powers the public `/catalog` page.

## What Changes

- **NEW** backend layer-first modules: `backend/app/repositories/categoria.py`, `backend/app/services/categoria.py`, `backend/app/api/v1/categorias.py`; schemas at `backend/app/schemas/categoria.py` (already correct path).
- **SCHEMA FIX** Alembic migration `0002_categoria_nombre_per_parent`: drop global `UNIQUE(nombre)` on `categoria`, add two partial unique indexes for per-parent uniqueness.
- **WIRING** `UnitOfWork` gains `uow.categorias: CategoriaRepository` accessor (lazy).
- **WIRING** `build_v1_router` registers `categorias_router` under `/api/v1/categorias`.
- **NEW** Pydantic schemas: `CategoriaBase`, `CategoriaCreate`, `CategoriaUpdate`, `CategoriaRead`, `CategoriaTreeNode`.
- **NEW** `CategoriaRepository` with `get_tree()` (recursive CTE), `would_create_cycle()` (CTE with depth guard), `get_subtree_height()` (CTE), custom `create` / `update` / `soft_delete` overrides for tree-integrity enforcement.
- **NEW** `CategoriaService` with business rules: cycle detection, max-depth enforcement (subtree-aware for update), soft-delete guard (active children + active products), `IntegrityError → ConflictError` translation.
- **NEW** 5 REST endpoints (`GET /categorias`, `GET /categorias/{id}`, `POST /categorias`, `PUT /categorias/{id}`, `DELETE /categorias/{id}`). Write endpoints require `require_role("ADMIN", "STOCK")`.
- **FRONTEND NEW** `frontend/src/entities/categories/` entity slice: types (`model/types.ts`), fetcher (`api/getCategoriesTree.ts`), `useCategoriesTree` hook (`model/useCategoriesTree.ts`).
- **FRONTEND UPDATE** `frontend/src/pages/catalog/ui/CatalogPage.tsx`: replace placeholder with minimal nested-list render of category tree.
- **FRONTEND UPDATE** `frontend/src/shared/api/endpoints.ts`: add `CATEGORIAS` constant.

## Capabilities

### New Capabilities

- `backend-categorias-management`: Full CRUD API for the hierarchical category tree (5 endpoints, `require_role("ADMIN", "STOCK")` for writes, public reads, cycle detection with depth-guarded CTE, subtree-aware depth limit on update, soft-delete guards, RFC 7807 errors).
- `frontend-categories-entity`: Frontend entity layer — TypeScript types, fetcher, `useCategoriesTree` hook, minimal `CatalogPage` tree render.

### Modified Capabilities

- `backend-unit-of-work`: REPLACE the existing `NotImplementedError` stub for the `categorias` lazy property with real `CategoriaRepository` instantiation — wired into the shared transaction context.
- `backend-api-v1-router`: Register `categorias_router` inside `build_v1_router` — new domain router mounted at `/api/v1/categorias`.
- `backend-migrations`: Register migration `0002_categoria_nombre_per_parent` — drop global unique constraint on `categoria.nombre`, add two partial unique indexes for per-parent uniqueness semantics.

## Impact

- **Backend**: New layer-first files: `backend/app/repositories/categoria.py`, `backend/app/services/categoria.py`, `backend/app/api/v1/categorias.py`, `backend/app/schemas/categoria.py` (4 files, layer-first layout). Migration touches `categoria` table constraint only (no column changes). UoW and router files receive minimal additions.
- **Frontend**: New `frontend/src/entities/categories/` directory (3 files). `CatalogPage.tsx` updated. `endpoints.ts` updated.
- **Database**: Migration `0002` modifies constraint on existing `categoria` table — no data loss, safe on empty table.
- **Dependencies (upstream)**: Requires Change 03 (Categoria model + 0001 migration), Change 04 (BaseRepository, UoW), Change 07 (auth deps + error handlers).
- **Dependencies (downstream)**: Change 10 (product search/filter by category), Change 11 (product-category association), Change 12 (rich catalog navigation) all depend on the foundation established here.
- **No breaking changes** to existing endpoints or specs.
