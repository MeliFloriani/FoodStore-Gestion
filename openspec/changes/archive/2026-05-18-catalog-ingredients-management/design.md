## Context

The `Ingrediente` entity is defined in Integrador.txt §3.2 (línea 121–122): `nombre VARCHAR(100) UQ NN`, `es_alergeno BOOLEAN NN default false`. Migration `0001_initial_schema` already created the `ingrediente` table (SINGULAR — consistent with `categoria`, `producto`, `usuario`) with a global `UNIQUE CONSTRAINT uq_ingrediente_nombre ON ingrediente(nombre)`. Change 10 must ALTER this existing table: drop the global unique constraint and replace it with a partial unique index on `nombre WHERE deleted_at IS NULL`, plus add the allergen index. The `Ingrediente` SQLModel already exists in `app/models/catalog.py` (D-17 convention) — Change 10 does NOT create a new `app/models/ingrediente.py`.

The infrastructure required by this change is fully operational from prior changes:
- **Change 04**: `BaseRepository[T]`, `UnitOfWork`, `require_role` dependency.
- **Change 07**: JWT auth, `get_current_user`, RFC 7807 error handlers, `HTTPException` translation.
- **Change 09**: Established the `require_role("ADMIN","STOCK")` RBAC pattern for catalog writes + the partial unique index pattern for soft-deletable entities.

This design anchors seven pre-resolved architectural decisions (D-01..D-07). All open questions are resolved; there are no live OQs.

**Backend module layout (layer-first, matching CLAUDE.md and codebase)**:

```
backend/app/
├── models/
│   └── catalog.py              ← Ingrediente SQLModel ALREADY EXISTS here (D-17). Modify: change nombre unique=True → unique=False
├── schemas/
│   └── ingrediente.py          ← NEW: Pydantic schemas (Base/Create/Update/Read)
├── repositories/
│   └── ingrediente.py          ← NEW: IngredienteRepository(BaseRepository[Ingrediente])
├── services/
│   └── ingrediente.py          ← NEW: IngredienteService
└── api/v1/
    └── ingredientes.py         ← NEW: ingredientes_router (APIRouter)
```

**IMPORTANT**: There is NO `app/models/ingrediente.py`. The `Ingrediente` model already exists in `app/models/catalog.py` at line 142 (D-17 convention: all catalog models in one file). Change 10 only modifies the `nombre` field's `unique` parameter from `True` to `False`. The `__tablename__` is already `"ingrediente"` (singular — correct, do not change it).

There is NO `app/ingredientes/` domain-first directory. Layer-first convention is mandatory throughout (matching `app/repositories/categoria.py`, `app/api/v1/categorias.py`, etc.).

---

## Goals / Non-Goals

**Goals:**

- Deliver the 5-endpoint ingredients API with correct RBAC (ADMIN+STOCK for all endpoints), RFC 7807 errors, soft delete, and allergen filter.
- Create Alembic migration `0004_ingredientes_table` that ALTERs the existing `ingrediente` table: drops global `uq_ingrediente_nombre` constraint (from migration 0001), adds partial unique index on nombre and partial index on es_alergeno.
- Implement `IngredienteRepository` extending `BaseRepository` with `get_by_nombre_active()` for duplicate detection.
- Provide the minimal frontend entity layer (`useIngredientes` hook, mutation hooks, key factory, barrel) so Change 11 has a typed contract to build on.
- Preserve `model_fields_set` semantics in `IngredienteUpdate` (same pattern as Change 09 D-06) so partial updates don't inadvertently clear unset fields.

**Non-Goals:**

- `ProductoIngrediente` M2M association (Change 11).
- Public allergen display in catalog (Change 12).
- Personalización (`personalizacion: INTEGER[]`) in `DetallePedido` (Change 15/17).
- Admin panel UI for ingredient management (Change 22+).
- Rate limiting on ingredient endpoints (low-risk authenticated endpoints; no public surface).
- Restore (undelete) endpoint.
- Pagination (see D-04).

---

## Decisions

### D-01 — RBAC: ADMIN + STOCK for All Endpoints (Writes AND Reads)

All five endpoints — including reads (`GET /ingredientes`, `GET /ingredientes/{id}`) — declare `require_role("ADMIN", "STOCK")` as a FastAPI dependency. There are **no public endpoints** in this change.

**Rationale**: The RBAC tension between Integrador §4.2 ("STOCK: ver ingredientes" = read-only framing) and Descripcion.txt §1/§6 + US-011..014 (CRUD to STOCK) is resolved in favor of the user stories and functional description, which are more detailed and represent the intended behavior for Sprint 2. The Integrador §4.2 row is a summary that understates STOCK's catalog management responsibilities. Change 09 applied the same resolution for categories (D-01 in that design) — `require_role("ADMIN","STOCK")` on writes AND administrative reads — and is now archived as the precedent pattern.

The public `es_alergeno` flag will be exposed via `GET /api/v1/productos/{id}` and `GET /api/v1/productos/{id}/ingredientes` in Change 11 (public endpoints). It is NOT in scope for Change 10.

**Alternatives considered**: Give STOCK read-only and ADMIN full CRUD → rejected. US-011 ("Como Gestor de Stock, quiero registrar ingredientes"), US-013 ("editar un ingrediente"), US-014 ("dar de baja un ingrediente") unambiguously assign CRUD to STOCK. Read-only would violate the user stories. ADMIN-only reads → rejected (STOCK needs the list to manage associations).

---

### D-02 — Nombre Uniqueness: Partial Index Among Active Records Only

The `ingrediente.nombre` uniqueness is enforced via a **partial unique index**, NOT a global `UNIQUE` constraint. Migration 0001 created a global `UNIQUE CONSTRAINT uq_ingrediente_nombre ON ingrediente(nombre)` — this MUST be dropped by migration 0004 BEFORE creating the partial index.

```sql
-- Migration 0004: drop global constraint first (MANDATORY — cannot skip)
ALTER TABLE ingrediente DROP CONSTRAINT uq_ingrediente_nombre;
-- Then create partial unique index
CREATE UNIQUE INDEX ix_ingrediente_nombre_activo
  ON ingrediente (nombre)
  WHERE deleted_at IS NULL;
```

**Critical**: A partial index does NOT automatically replace/supersede an existing UNIQUE constraint. If the DROP is omitted, both would coexist: the global constraint would still block all name reuse (even after soft delete), defeating the purpose of the partial index. The DROP must come first.

The SQLModel field definition uses `unique=False` (no model-level unique) — the constraint lives exclusively in the migration DDL.

**Rationale**: The global `UNIQUE(nombre)` constraint from migration 0001 prevents soft-deleted ingredient names from being reused. Replacing it with a partial unique index (`WHERE deleted_at IS NULL`) means: (1) active ingredients cannot share names, and (2) soft-deleting an ingredient immediately frees its name for reuse. This is identical to the `uq_categoria_nombre_root` pattern from Change 09 (D-02).

The service does NOT perform application-level `SELECT ... WHERE nombre = :nombre` before `INSERT`. It catches `sqlalchemy.exc.IntegrityError` from a failed flush and translates it to `ConflictError(code="INGREDIENT_NAME_DUPLICATE")` — transactionally correct and race-condition-free.

**Why single index** (vs two indexes in Change 09): The `ingrediente` entity is flat (no self-referential parent). There is no per-parent scope — uniqueness is global among active records. One partial index suffices, vs Change 09 which needed two (one for root-level, one for per-parent).

**Alternatives considered**: Application-level SELECT + INSERT → rejected (TOCTOU race). Standard `UNIQUE` constraint → rejected (blocks name reuse after soft delete; breaks historical integrity). Omitting DROP of global constraint → rejected (both constraints would coexist, making partial index ineffective).

---

### D-03 — Soft Delete Semantics

Soft delete via `deleted_at TIMESTAMPTZ NULL`. All repository queries (`get_by_id`, `list_active`, `get_by_nombre_active`) filter `WHERE deleted_at IS NULL` by default via `BaseRepository`.

- `DELETE /ingredientes/{id}` → service first calls `uow.ingredientes.get_by_id(ingrediente_id)` to verify existence (raises `NotFoundError` if None or soft-deleted), then calls `uow.ingredientes.soft_delete(ingrediente_id)` → `UPDATE ingrediente SET deleted_at = NOW() WHERE id = :id AND deleted_at IS NULL`. Without the prior `get_by_id` check, double-deletes would silently succeed instead of returning 404.
- `PUT /ingredientes/{id}` → raises `NotFoundError` (404) if `deleted_at IS NOT NULL` (cannot update a soft-deleted record).
- `GET /ingredientes/{id}` → raises `NotFoundError` (404) if `deleted_at IS NOT NULL`.
- `GET /ingredientes` → returns only `deleted_at IS NULL` records.
- Hard delete is never performed.

**Future compatibility (documented, not implemented)**: When Change 11 introduces `ProductoIngrediente`, soft-deleted ingredients must remain joinable from `DetallePedido.personalizacion` for historical orders. The soft delete pattern (not hard delete) is what guarantees this. `BaseRepository.list_active()` automatically excludes soft-deleted records from new-association flows.

**Alternatives considered**: Hard delete → rejected (loses historical order data; `DetallePedido.personalizacion INTEGER[]` stores ingredient IDs; orphaned IDs would break historical rendering). Cascade soft-delete to `ProductoIngrediente` → deferred to Change 11 design.

---

### D-04 — No Pagination in This Change

`GET /api/v1/ingredientes` returns `List[IngredienteRead]` (flat list), NOT a paginated envelope. Pagination is explicitly deferred.

**Rationale**: The expected cardinality of the ingredients catalog is low (tens to low hundreds — think allergens and common components like "Harina", "Sal", "Azúcar", etc.). The `PaginatedResponse[T]` contract already exists in `app/schemas/pagination.py`. A flat `List[IngredienteRead]` is trivially migrable to `PaginatedResponse[IngredienteRead]` in a future change when volume justifies it. Adding pagination now would introduce an unnecessary contract change for downstream consumers (Change 11/12) before any concrete need exists.

US-012 mentions "Soporta paginacion" in the technical notes, but this is a note, not a blocking acceptance criterion. The acceptance criterion reads "se retornan todos los ingredientes con su flag de alergeno" — satisfied by a flat list.

**Alternatives considered**: Add pagination immediately → rejected (premature complexity; no data volume justification; note vs acceptance criterion distinction). Skip `es_alergeno` filter → rejected (AC of US-012 explicitly requires it).

---

### D-05 — IngredienteUpdate: model_fields_set Preservation

The router passes the `IngredienteUpdate` Pydantic model instance directly to `service.update_ingrediente(ingrediente_id, data)`. The router MUST NOT call `data.model_dump()` before passing to the service — this loses `model_fields_set` information.

The service applies only the fields present in `data.model_fields_set` to the ORM object, preserving other fields at their current DB values. This is the same gotcha documented in Change 09 D-06 for `CategoriaUpdate`.

**Critical scenario**: `PUT /ingredientes/{id}` with body `{"es_alergeno": true}` — only `es_alergeno` should change; `nombre` must remain unchanged. If the service receives a dict (from `model_dump()`), `nombre` would be `None` (its default), silently overwriting the existing name.

---

### D-06 — Allergen Index for Efficient Filtering

An additional partial index on the `es_alergeno` column is created in migration `0004`:

```sql
CREATE INDEX ix_ingrediente_es_alergeno
  ON ingrediente (es_alergeno)
  WHERE deleted_at IS NULL;
```

**Rationale**: The `GET /ingredientes?es_alergeno=true` filter path is hot (Change 12 will use it heavily). Without an index, filtering on a boolean column requires a full table scan. With a partial index on `es_alergeno WHERE deleted_at IS NULL`, the allergen subset (typically < 20 rows) resolves via index scan.

---

### D-07 — No FK to Productos or Categorias in This Change

The `ingrediente` table has NO foreign key to `categoria` or `producto`. It is a standalone flat entity.

**Rationale**: The `ProductoIngrediente` M2M association belongs to Change 11 (product domain). Introducing a FK now would create coupling between Change 10 (ingredients) and Change 11 (products) — violating the independence principle. The task list explicitly prohibits premature coupling.

**Consequences**: Change 11 will introduce `producto_ingrediente` with `producto_id FK → producto.id` and `ingrediente_id FK → ingrediente.id`. The `ingrediente` table needs no schema changes to support this — it is FK-target-ready by design.

---

## Risks / Trade-offs

| Risk | Severity | Mitigation |
|------|----------|-----------|
| `uq_ingrediente_nombre` global constraint not dropped before partial index creation | HIGH | Migration `upgrade()` MUST call `op.drop_constraint("uq_ingrediente_nombre", "ingrediente", type_="unique")` as step 1. Run `alembic check` after upgrade to confirm no spurious constraint remains. |
| Migration numbering collision: `0003` is already `categoria_nombre_per_parent` in the alembic chain; the next must be `0004` | HIGH | `down_revision = 'c9d8e7f6a5b4'` (verified actual hash). DO NOT use human-readable name as `down_revision`. |
| `IntegrityError` on nombre duplicate not caught if flush is not called inside UoW scope | MEDIUM | UoW commits/flushes inside `__aexit__`; `IntegrityError` propagates before response is sent. Test explicitly with `test_create_duplicate_nombre_raises_409`. |
| `model_fields_set` lost if router calls `data.model_dump()` | MEDIUM | Router MUST pass the Pydantic model directly (not a dict). Enforced by integration test: `test_update_name_only_preserves_es_alergeno`. |
| Double-delete silently succeeds if `delete_ingrediente` skips prior `get_by_id` check | MEDIUM | Service MUST call `get_by_id` first; raise `NotFoundError` if None. Only then call `soft_delete`. |
| Soft-deleted ingredient names become unavailable if partial index is not applied | LOW | D-02 resolves this; migration test covers the reclaimability scenario. |
| Change 11 M2M join on soft-deleted ingredients in historical orders | LOW | No FK cascade; soft delete preserves ID. Document with `# NOTE: soft-deleted ingredients are joinable from DetallePedido.personalizacion for historical orders`. |
| `ix_ingrediente_es_alergeno` partial index may not be used on very small tables | LOW | PostgreSQL planner may prefer seq scan for < ~100 rows; acceptable. The index will be active when volume grows with Change 12+ usage. |

---

## Migration Plan

Migration `0004` is an **ALTER operation** on the existing `ingrediente` table (created by migration 0001). It does NOT create a new table.

**Migration chain**: `6ebe5e787bdd` (0001) → `a1b2c3d4e5f6` (0002) → `c9d8e7f6a5b4` (0003). `down_revision` for 0004 = `'c9d8e7f6a5b4'`.

1. **Generate revision**: `alembic revision -m "0004_ingredientes_table"`. Set `down_revision = 'c9d8e7f6a5b4'` (actual hash of 0003, verified correct). DO NOT use `'0003_categoria_nombre_per_parent'` as the `down_revision` value.
2. **Implement `upgrade()`**:
   ```python
   # 1. Drop global unique constraint (created by migration 0001) — MUST come first
   op.drop_constraint("uq_ingrediente_nombre", "ingrediente", type_="unique")
   # 2. Create partial unique index (nombre among active records only)
   op.execute("CREATE UNIQUE INDEX ix_ingrediente_nombre_activo ON ingrediente (nombre) WHERE deleted_at IS NULL")
   # 3. Create allergen filter index
   op.execute("CREATE INDEX ix_ingrediente_es_alergeno ON ingrediente (es_alergeno) WHERE deleted_at IS NULL")
   ```
   **CRITICAL**: The `uq_ingrediente_nombre` constraint MUST be dropped BEFORE creating the partial index. A partial index does NOT supersede an existing UNIQUE constraint — if both coexist, the global constraint would still block name reuse after soft delete, making the partial index ineffective.
3. **Implement `downgrade()`**:
   ```python
   op.execute("DROP INDEX IF EXISTS ix_ingrediente_es_alergeno")
   op.execute("DROP INDEX IF EXISTS ix_ingrediente_nombre_activo")
   op.create_unique_constraint("uq_ingrediente_nombre", "ingrediente", ["nombre"])
   ```
4. **Verification**: `alembic upgrade head` → run `alembic check` to confirm no spurious constraint detected on `ingrediente.nombre`. `alembic downgrade -1` → verify `uq_ingrediente_nombre` restored. `alembic upgrade head` again.
5. **CI**: `pytest tests/test_migrations.py -k "0004"` covers upgrade + downgrade + round-trip + partial index presence + name reclaimability + no spurious constraint.
6. **Rollback**: `alembic downgrade -1` drops both indexes and restores the global `uq_ingrediente_nombre` constraint. Safe — no FKs reference other tables in this migration.

---

## Preparación para Changes Futuros

Documentado aquí como referencia de diseño — NO implementar en Change 10:

- **Change 11**: `ProductoIngrediente(producto_id FK, ingrediente_id FK, es_removible BOOLEAN)` — M2M pivot table. The `ingrediente.id` column (UUID) becomes the FK target. `IngredienteRepository.list_active()` already excludes soft-deleted records, so new product-ingredient associations automatically cannot reference deleted ingredients.
- **Change 12**: Public catalog endpoint `GET /api/v1/productos?excluirAlergenos=true` — filters products where all ingredients have `es_alergeno = false`. Requires joining `producto → producto_ingrediente → ingrediente`. The `ix_ingrediente_es_alergeno` index (created in Change 10) serves this query.
- **Change 15/17**: `DetallePedido.personalizacion INTEGER[]` stores IDs of removed ingredients. Soft-deleted ingredients must remain joinable for historical order display. The current soft-delete pattern (not hard delete) guarantees this. A `GET /api/v1/pedidos/{id}` response will need to resolve ingredient names even for soft-deleted records — this is done by a JOIN on `ingrediente` without the `WHERE deleted_at IS NULL` filter (historical read bypass).
- **Change 22+**: Admin panel CRUD UI for ingredients. This will use the same `ingredientes_router` endpoints.

---

## Open Questions

_None. All decisions D-01 through D-07 resolved before this design was written._
