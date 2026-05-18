## Context

The `Categoria` SQLModel already exists in `backend/app/models/catalog.py` (Change 03) with columns `id`, `nombre`, `descripcion`, `parent_id` (self-ref FK), `created_at`, `updated_at`, `deleted_at`. The initial migration `0001_initial_schema` created the table with a **global** `UNIQUE(nombre)` constraint — which contradicts the user story requirement that uniqueness is per-level (US-007 AC: "nombre duplicado en el mismo nivel"). The rest of the infrastructure (BaseRepository, UoW, error handlers, RBAC dep) is operational from Changes 04 and 07.

This design anchors ten pre-resolved architectural decisions (D-01..D-10) that the orchestrator determined before implementation begins. All open questions are resolved; there are no live OQs.

**Backend module layout (layer-first, matching CLAUDE.md and the existing codebase)**:

```
backend/app/
├── repositories/
│   └── categoria.py          ← CategoriaRepository (BaseRepository[Categoria])
├── services/
│   └── categoria.py          ← CategoriaService
├── api/v1/
│   └── categorias.py         ← categorias_router (APIRouter)
├── schemas/
│   └── categoria.py          ← Pydantic schemas (already correct)
└── models/
    └── catalog.py            ← Categoria model (already exists, Change 03)
```

All imports follow the layer-first convention:
- `from app.repositories.categoria import CategoriaRepository`
- `from app.services.categoria import CategoriaService`
- `from app.api.v1.categorias import categorias_router`

There is NO `app/categories/` domain-first directory. The codebase uses layer-first layout throughout (e.g., `app/repositories/user.py`, `app/api/v1/auth.py`).

---

## Goals / Non-Goals

**Goals:**

- Deliver the 5-endpoint category API with correct RBAC, tree response shape, RFC 7807 errors.
- Fix the per-parent uniqueness constraint via migration `0002` before any data enters production.
- Implement cycle prevention, max-depth (5), and soft-delete guards in the service layer.
- Provide the minimal frontend entity layer (`useCategoriesTree` hook + `CatalogPage` basic render) so the public catalog is no longer a placeholder.
- Keep all tree-assembly logic (CTE → in-memory) cleanly separated between repository and service.

**Non-Goals:**

- Products, ingredients, search, filtering, breadcrumbs, sidebar (Changes 10/11/12).
- Admin panel mutations from the frontend (Changes 22+).
- Restore (undelete) endpoint.
- Admin flat-paginated category endpoint (Change 22).
- Rate limiting on category endpoints (low-risk public reads, no auth surface).

---

## Decisions

### D-01 — RBAC: Write = ADMIN + STOCK, Read = Public

Write endpoints (`POST /categorias`, `PUT /categorias/{id}`, `DELETE /categorias/{id}`) declare `require_role("ADMIN", "STOCK")` as a FastAPI dependency. Read endpoints (`GET /categorias`, `GET /categorias/{id}`) have **no auth dependency** at all — they are fully public.

**Rationale**: Integrador v5 §4.2 assigns category administration ("administra categorías") to the STOCK role. US-007 (create category), US-009 (edit category), and US-010 (delete category) all explicitly name "Gestor de Stock" as the primary actor for those operations. US-064 (Change 22) gives ADMIN the same permissions as STOCK for these endpoints — it extends ADMIN access to cover what STOCK can already do; it does NOT replace STOCK's pre-existing access. The prior D-01 version incorrectly cited §5.2 (which covers `disponible`/`stock_cantidad` on products, not categories) as the RBAC tiebreaker; §4.2 is the correct section for category management. No deviation record is needed — `require_role("ADMIN", "STOCK")` is the correct reading of the spec.

**Alternatives considered**: Give only ADMIN write access to categories → rejected. §4.2 and US-007/009/010 unambiguously assign category CRUD to Gestor de Stock; excluding STOCK would contradict the official spec. Give only STOCK write access → rejected for the same reason Change 22 exists: ADMIN must be able to perform all operations.

---

### D-02 — Nombre Uniqueness: Per-Parent Scope via Partial Indexes

The global `UNIQUE(nombre)` constraint on `categoria` must be replaced. Alembic migration `0002_categoria_nombre_per_parent` performs:

1. `DROP CONSTRAINT` on the global unique index.
2. `CREATE UNIQUE INDEX CONCURRENTLY uq_categoria_nombre_parent ON categoria (parent_id, nombre) WHERE deleted_at IS NULL` — covers all non-root categories.
3. `CREATE UNIQUE INDEX CONCURRENTLY uq_categoria_nombre_root ON categoria (nombre) WHERE parent_id IS NULL AND deleted_at IS NULL` — covers root categories (PostgreSQL treats `NULL != NULL` in standard unique indexes so roots would not be covered by the compound index).

Both indexes use `WHERE deleted_at IS NULL` so soft-deleted names are immediately reclaimable.

The service does **not** validate duplicates manually. It catches `sqlalchemy.exc.IntegrityError` from a failed flush and translates it to `ConflictError` with `code="CATEGORY_NAME_DUPLICATE"`.

**Rationale**: DB-level enforcement is stronger, transactionally correct, and avoids race conditions that an application-level SELECT+INSERT check cannot prevent.

**Alternatives considered**: Application-level SELECT before INSERT → rejected (TOCTOU race; adds an extra query per mutation). Single compound index with `COALESCE(parent_id, '00000000-...')` sentinel UUID → rejected (fragile, requires injecting a magic constant; partial index is the PostgreSQL-idiomatic solution).

---

### D-03 — Cycle Detection: Service Layer, Recursive CTE

Before persisting a `parent_id` change in `update_categoria`, the service MUST first check `category_id == new_parent_id` and raise `AppValidationError(code="CATEGORY_SELF_PARENT")` immediately — this avoids calling the CTE for the trivial self-parent case. Only if the self-parent check passes does the service call `await uow.categorias.would_create_cycle(category_id, new_parent_id)`.

The repository method executes the following complete, verified SQL:

```sql
WITH RECURSIVE descendants AS (
  -- Anchor: start from the node being moved
  SELECT id, 1 AS depth
  FROM categoria
  WHERE id = :category_id
    AND deleted_at IS NULL

  UNION ALL

  -- Recursive: find active children of current set
  SELECT c.id, d.depth + 1
  FROM categoria c
  JOIN descendants d ON c.parent_id = d.id
  WHERE c.deleted_at IS NULL
    AND d.depth < 10   -- safety guard against corrupted cycles
)
SELECT EXISTS (
  SELECT 1 FROM descendants WHERE id = :new_parent_id
) AS would_cycle;
```

The depth guard `< 10` ensures the CTE terminates even if active data somehow contains a cycle (e.g., via a direct DB insert bypassing the service). `LIMIT 1` is implicit in the `EXISTS` subquery. The guard of 10 is intentionally larger than the max_depth of 5 to not interfere with legitimate tree traversal while providing a safety cap.

If the query returns `True`, `new_parent_id` is inside the subtree of `category_id` → cycle → `AppValidationError(code="CATEGORY_CYCLE_DETECTED")`.

**Where**: Service layer, not router (no HTTP concern) and not repository (business rule). The repository exposes the query; the service decides the response.

**Alternatives considered**: Trigger in PostgreSQL → rejected (complex, hard to test, opaque to application logic). Recursive Python tree walk in memory → rejected (requires full tree fetch; CTE is O(subtree) not O(total)).

---

### D-04 — Soft-Delete Guard: Block if Active Children or Active Products

`DELETE /categorias/{id}` (soft-delete) raises `ConflictError(code="CATEGORY_HAS_ACTIVE_CHILDREN")` if the category has any active (`deleted_at IS NULL`) subcategories. Similarly raises `ConflictError(code="CATEGORY_HAS_ACTIVE_PRODUCTS")` if any active products reference this category via `producto_categoria` join.

**Why block?**: The `ON DELETE SET NULL` FK action on `categoria.parent_id` only triggers on **hard** delete at the DB level. Soft-delete (`deleted_at = now()`) does not trigger FK actions — subcategories would remain with a `parent_id` pointing to a "ghost" record. Forcing the admin to repair children first keeps the tree consistent.

**Products guard**: `producto_categoria` join returns 0 rows today (Change 11 not yet complete) but the guard is implemented now and will become effective once products exist, satisfying US-010 / RN-CA03.

**Alternatives considered**: Cascade soft-delete to children → rejected (surprise bulk-delete; admin should confirm intent). Orphan children at reparent → rejected (breaks tree integrity). Allow soft-delete with `parent_id IS NULL` nullification → rejected (same problem: ghost parent from child's perspective).

---

### D-05 — Max Tree Depth: 5 Levels

The tree is capped at depth 5 (root = depth 1, leaf max = depth 5). On `create` with a `parent_id`, the service validates `parent_depth + 1 ≤ 5` using `get_depth(new_parent_id)` (raises `AppValidationError(code="CATEGORY_MAX_DEPTH_EXCEEDED")` if exceeded).

On `update` with a `parent_id` change, the service uses `get_depth(new_parent_id)` — a targeted ancestor-traversal CTE — NOT `get_tree()` for this validation. `get_tree()` loads the entire tree (O(n)) and is unacceptable for a targeted depth check. `get_depth` uses an ancestor-traversal CTE (O(depth)) and is the required method.

For `update`, the service MUST call BOTH `get_depth(new_parent_id)` AND `get_subtree_height(category_id)` and validate the combined formula:

```
parent_depth + 1 + subtree_height ≤ 5
```

Moving a subtree does not just change the reparented node's depth — it shifts ALL descendants by the same delta. A subtree of height 2 reparented under a node at depth 3 would yield leaves at depth 3+1+2=6, exceeding the limit. The `get_subtree_height` check prevents this silent violation.

**`get_subtree_height` definition**: Returns the maximum depth of the subtree rooted at `category_id` relative to the root node itself. A leaf node returns 0. A node with one level of children returns 1. A node with children and grandchildren returns 2. SQL:

```sql
WITH RECURSIVE subtree AS (
  SELECT id, 0 AS relative_depth
  FROM categoria
  WHERE id = :category_id
    AND deleted_at IS NULL

  UNION ALL

  SELECT c.id, s.relative_depth + 1
  FROM categoria c
  JOIN subtree s ON c.parent_id = s.id
  WHERE c.deleted_at IS NULL
    AND s.relative_depth < 10  -- safety guard
)
SELECT COALESCE(MAX(relative_depth), 0) AS subtree_height FROM subtree;
```

**Rationale**: Prevents CTE performance degradation on pathological deep trees; limits frontend render complexity; aligns with typical e-commerce taxonomy needs (e.g., Food → Bebidas → Jugos → Jugos de Naranja → Exprimidos Artesanales = 5 levels is already generous).

**Alternatives considered**: Unlimited depth → rejected (O(n) CTE on every read; UI pagination on a tree becomes unbounded). Depth 3 → rejected (too limiting for a multi-department food store with sub-sub-categories). Validate only `parent_depth + 1 ≤ 5` on update → rejected (allows subtrees to exceed the depth limit silently when reparented).

---

### D-06 — Tree Response Shape: Flat Array of Roots, No Pagination

`GET /api/v1/categorias` returns `list[CategoriaTreeNode]` directly (not inside a pagination envelope). Each `CategoriaTreeNode` carries `{ id, nombre, descripcion, subcategorias: list[CategoriaTreeNode] }`. Only active (`deleted_at IS NULL`) nodes appear.

**Rationale**: A category tree is a single coherent structure — paginating a tree is semantically broken (page 2 of a tree?). Expected cardinality is low (< 200 nodes). The flat list of roots with nested children is the standard pattern.

**Alternatives considered**: Return nested tree under pagination envelope → rejected (meaningless). Return flat list with `parent_id` for client-side assembly → rejected (pushes assembly complexity to every consumer; breaks API contract clarity). Add `GET /admin/categorias` paginated flat list → postponed to Change 22 (out of scope).

---

### D-07 — CTE Decoupled from Response Shape

`CategoriaRepository.get_tree() → list[Categoria]` returns flat rows with a virtual `depth` column computed by the CTE. `CategoriaService.get_tree() → list[CategoriaTreeNode]` assembles the hierarchy in-memory using a `dict[UUID, CategoriaTreeNode]` (O(n) single pass, no recursion).

Assembly algorithm:
```python
nodes = {row.id: CategoriaTreeNode(..., subcategorias=[]) for row in flat_rows}
roots = []
for row in flat_rows:
    if row.parent_id is None:
        roots.append(nodes[row.id])
    else:
        nodes[row.parent_id].subcategorias.append(nodes[row.id])
return roots
```

**Rationale**: Repository owns SQL; service owns business shape. Reusing `get_tree` in a different context (e.g., admin flat export) doesn't force the tree assembly logic on the caller.

---

### D-08 — Endpoint Surface (Change 09 only)

| Method | Path | Auth | Request Body | Response |
|--------|------|------|--------------|----------|
| `GET` | `/api/v1/categorias` | Public | — | `list[CategoriaTreeNode]` 200 |
| `GET` | `/api/v1/categorias/{id}` | Public | — | `CategoriaRead` 200 |
| `POST` | `/api/v1/categorias` | ADMIN + STOCK | `CategoriaCreate` | `CategoriaRead` 201 |
| `PUT` | `/api/v1/categorias/{id}` | ADMIN + STOCK | `CategoriaUpdate` | `CategoriaRead` 200 |
| `DELETE` | `/api/v1/categorias/{id}` | ADMIN + STOCK | — | 204 No Content |

No restore endpoint. No admin paginated list endpoint.

---

### D-09 — Pydantic Schemas: Strict Separation

All schemas in `backend/app/schemas/categoria.py`:

- `CategoriaBase(BaseModel)` — `nombre: str` (min 1, max 100), `descripcion: str | None = None`
- `CategoriaCreate(CategoriaBase)` — inherits + `parent_id: UUID | None = None`
- `CategoriaUpdate(BaseModel)` — all optional: `nombre: str | None = None`, `descripcion: str | None = None`, `parent_id: UUID | None | UnsetSentinel`. **Sentinel pattern** distinguishes "field not sent" (don't touch `parent_id`) from "field sent as null" (set to root). Use `model_config = ConfigDict(use_enum_values=True)` with a custom `UNSET` sentinel or Pydantic v2 `model_fields_set` — document chosen approach in code.
- `CategoriaRead(CategoriaBase)` — adds `id: UUID`, `parent_id: UUID | None`, `created_at: datetime`, `updated_at: datetime`. `model_config = ConfigDict(from_attributes=True)`.
- `CategoriaTreeNode(BaseModel)` — `id: UUID`, `nombre: str`, `descripcion: str | None`, `subcategorias: list["CategoriaTreeNode"] = []`. Must call `model_rebuild()` after class definition for forward ref resolution.

---

### D-10 — Frontend: Minimal Entity Layer, Read-Only

Change 09 frontend scope:

- `frontend/src/shared/api/endpoints.ts` — add `export const CATEGORIAS = '/api/v1/categorias' as const` (named export, same pattern as `AUTH_LOGIN`, `AUTH_REFRESH`, etc.)
- `frontend/src/entities/categories/model/types.ts` — `Categoria`, `CategoriaTreeNode` TypeScript interfaces mirroring backend schemas
- `frontend/src/entities/categories/api/getCategoriesTree.ts` — axios fetcher calling `CATEGORIAS` endpoint constant; returns `Promise<CategoriaTreeNode[]>`
- `frontend/src/entities/categories/model/useCategoriesTree.ts` — TanStack Query v5 hook: `useQuery({ queryKey: queryKeys.catalog.categories(), queryFn: getCategoriesTree })`. Lives in `model/` (not `api/`) because it is a React hook using `useQuery`; the `api/` directory contains only non-hook fetcher functions.
- `frontend/src/pages/catalog/ui/CatalogPage.tsx` — replace placeholder with minimal recursive `<ul><li>` render of the tree, showing `isPending` and `isError` states

**No** mutation hooks (POST/PUT/DELETE) in frontend — those belong to the admin panel (Change 22+). **No** breadcrumbs, sidebar, rich navigation (Change 12). **No** Tailwind design work beyond basic readability — this is foundational plumbing, not final UI.

---

## Risks / Trade-offs

| Risk | Severity | Mitigation |
|------|----------|-----------|
| Migration `0002` runs on a DB with existing data having duplicate `(parent_id, nombre)` pairs | HIGH | Table is new and expected to be empty at migration time; add a pre-flight check in CI that asserts 0 rows with conflicts before running. |
| `would_create_cycle` CTE is expensive on very deep trees | MEDIUM | D-05 caps depth at 5; CTE worst case is 5 hops. Acceptable. Add `EXPLAIN ANALYZE` note in code comments. |
| Sentinel for `parent_id` in `CategoriaUpdate` is tricky in Pydantic v2 | MEDIUM | Use `model_fields_set` approach — if `parent_id` not in `model_fields_set`, service skips the field; if in set and value is `None`, sets to root. Document with a unit test. |
| Products guard in soft-delete returns 0 forever until Change 11 | LOW | Guard logic is correct; it will activate automatically. Document in code with a `# TODO: active after Change 11` comment. |
| Frontend `useCategoriesTree` called on public route may hit cold-start latency | LOW | TanStack Query stale-while-revalidate handles this. No additional mitigation needed at this stage. |
| Two partial unique indexes instead of one compound index | LOW | Standard PostgreSQL pattern for NULL-in-unique scenarios; well-documented. Reviewed in D-02 with rationale. |

---

## Migration Plan

1. **Development**: Run `alembic revision --autogenerate -m "0002_categoria_nombre_per_parent"`, then edit the generated file to manually drop the global unique constraint and add the two partial indexes (autogenerate may not handle partial indexes correctly).
2. **Verification**: `alembic upgrade head` on `foodstore_dev` → verify `\d categoria` shows the two new indexes and no global unique constraint.
3. **CI**: `pytest tests/test_migrations.py` runs upgrade + downgrade + re-upgrade cycle. `downgrade` on `0002` must restore the original global unique constraint.
4. **Rollback**: `alembic downgrade 0001` drops both partial indexes and re-adds the global unique constraint. Safe as long as no duplicate names exist post-rollback (same assumption as initial schema).

---

## Open Questions

_None. All decisions resolved by orchestrator before this design was written (D-01 through D-10 above)._
