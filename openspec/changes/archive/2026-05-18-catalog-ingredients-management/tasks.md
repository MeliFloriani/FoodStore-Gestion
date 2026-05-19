## 1. Model + Migration

- [x] 1.1 Write pytest test `tests/test_migrations.py::test_0004_upgrade_alters_ingrediente_table` asserting the `ingrediente` table (SINGULAR) still exists after `alembic upgrade 0004` and no `uq_ingrediente_nombre` constraint exists
- [x] 1.2 Write pytest test `tests/test_migrations.py::test_0004_upgrade_creates_ix_ingrediente_nombre_activo` asserting the partial unique index `ix_ingrediente_nombre_activo` exists on `ingrediente(nombre)` with condition `WHERE deleted_at IS NULL`
- [x] 1.3 Write pytest test `tests/test_migrations.py::test_0004_upgrade_creates_ix_ingrediente_es_alergeno` asserting the partial index `ix_ingrediente_es_alergeno` exists on `ingrediente(es_alergeno) WHERE deleted_at IS NULL`
- [x] 1.4 Write pytest test `tests/test_migrations.py::test_0004_blocks_duplicate_active_nombre` asserting two active ingredients with the same `nombre` cannot coexist (IntegrityError from partial unique index)
- [x] 1.5 Write pytest test `tests/test_migrations.py::test_0004_reclaims_soft_deleted_nombre` asserting a soft-deleted ingredient's name can be reused (new active row with same nombre succeeds)
- [x] 1.6 Write pytest test `tests/test_migrations.py::test_0004_downgrade_drops_indexes_and_restores_constraint` asserting downgrade removes both indexes and restores `uq_ingrediente_nombre` constraint
- [x] 1.7 Write pytest test `tests/test_migrations.py::test_0004_round_trip_reproducible` asserting `upgrade + downgrade + upgrade` completes without errors
- [x] 1.8 Write pytest test `tests/test_migrations.py::test_0004_no_spurious_constraint_after_upgrade` asserting `alembic check` finds no pending migration after 0004 is applied (no stale unique constraint on `ingrediente.nombre`)
- [x] 1.9 Generate Alembic revision file: `alembic revision -m "0004_ingredientes_table"`. Set `down_revision = 'c9d8e7f6a5b4'` (actual hash of 0003_categoria_nombre_per_parent — verified correct). DO NOT use the string `'0003_categoria_nombre_per_parent'`.
- [x] 1.10 Implement `upgrade()` — ALTER on existing `ingrediente` table (DO NOT CREATE TABLE):
  ```python
  # 1. Drop global unique constraint from migration 0001 — MUST come first
  op.drop_constraint("uq_ingrediente_nombre", "ingrediente", type_="unique")
  # 2. Create partial unique index (nombre among active records only)
  op.execute("CREATE UNIQUE INDEX ix_ingrediente_nombre_activo ON ingrediente (nombre) WHERE deleted_at IS NULL")
  # 3. Create allergen filter index
  op.execute("CREATE INDEX ix_ingrediente_es_alergeno ON ingrediente (es_alergeno) WHERE deleted_at IS NULL")
  ```
- [x] 1.11 Implement `downgrade()`:
  ```python
  op.execute("DROP INDEX IF EXISTS ix_ingrediente_es_alergeno")
  op.execute("DROP INDEX IF EXISTS ix_ingrediente_nombre_activo")
  op.create_unique_constraint("uq_ingrediente_nombre", "ingrediente", ["nombre"])
  ```
- [x] 1.12 Modify `backend/app/models/catalog.py` — change `Ingrediente.nombre` field from `unique=True` to `unique=False` to prevent Alembic autogenerate drift. DO NOT create a new `app/models/ingrediente.py`. The `Ingrediente` model already exists in `catalog.py` (D-17). The `__tablename__` is already `"ingrediente"` (singular) — do NOT change it.
- [ ] 1.13 Run `alembic check` after migration `0004` is applied — confirm no spurious unique constraint detected on `ingrediente.nombre`. # requires live DB
- [ ] 1.14 Run migration round-trip on dev DB: `alembic upgrade head && alembic downgrade -1 && alembic upgrade head`. # requires live DB

---

## 2. Schemas — Pydantic v2

- [x] 2.1 Create `backend/app/schemas/ingrediente.py`
- [x] 2.2 Implement `IngredienteBase(BaseModel)` with `nombre: str` (`Field(min_length=1, max_length=100)` + `@field_validator` that strips whitespace and checks non-empty post-strip) and `es_alergeno: bool = False`
- [x] 2.3 Implement `IngredienteCreate(IngredienteBase)` — inherits base with no additional fields
- [x] 2.4 Implement `IngredienteUpdate(BaseModel)` — flat model, all fields optional (`nombre: str | None = None`, `es_alergeno: bool | None = None`); document `model_fields_set` approach in code comment
- [x] 2.5 Implement `IngredienteRead(IngredienteBase)` — adds `id: UUID` (inherits `id: uuid.UUID` from `Base`, NOT `id: int`), `created_at: datetime`, `updated_at: datetime`; set `model_config = ConfigDict(from_attributes=True)`. Do NOT include `deleted_at`. Do NOT use `creado_en`/`actualizado_en` — use `created_at`/`updated_at` matching the `Base` class field names.
- [x] 2.6 Write unit tests `tests/schemas/test_ingrediente_schemas.py`:
  - `test_create_rejects_nombre_over_100_chars` — `IngredienteCreate(nombre="a"*101)` raises `ValidationError`
  - `test_create_strips_whitespace_from_nombre` — `IngredienteCreate(nombre="  Sal  ").nombre == "Sal"`
  - `test_create_rejects_whitespace_only_nombre` — `IngredienteCreate(nombre="   ")` raises `ValidationError`
  - `test_update_model_fields_set_absent_field` — `IngredienteUpdate(es_alergeno=True)` has `"nombre" not in model_fields_set`
  - `test_update_model_fields_set_present_field` — `IngredienteUpdate(nombre="Sal")` has `"nombre" in model_fields_set`
  - `test_read_id_is_uuid` — `IngredienteRead.id` is typed as `uuid.UUID`
- [x] 2.7 Run schema tests: `pytest tests/schemas/test_ingrediente_schemas.py -v` — all pass

---

## 3. Repository — IngredienteRepository

- [x] 3.1 Write unit test `tests/ingredientes/test_ingrediente_repository.py::test_list_active_returns_ordered_by_nombre` — 3 active ingredients, verify ASC order
- [x] 3.2 Write unit test `test_list_active_filters_by_es_alergeno_true` — returns only allergen ingredients
- [x] 3.3 Write unit test `test_list_active_filters_by_es_alergeno_false` — returns only non-allergen ingredients
- [x] 3.4 Write unit test `test_list_active_excludes_soft_deleted` — soft-deleted ingredient does not appear in results
- [x] 3.5 Write unit test `test_get_by_nombre_active_returns_none_for_deleted` — soft-deleted ingredient returns None
- [x] 3.6 Write unit test `test_get_by_nombre_active_returns_ingredient_when_active` — active ingredient found by exact nombre
- [x] 3.7 Create `backend/app/repositories/ingrediente.py` with `IngredienteRepository(BaseRepository[Ingrediente])`
- [x] 3.8 Implement `get_by_nombre_active(nombre: str) -> Ingrediente | None` — `SELECT * FROM ingrediente WHERE nombre = :nombre AND deleted_at IS NULL LIMIT 1`
- [x] 3.9 Implement `list_active(es_alergeno: bool | None = None) -> list[Ingrediente]` — build conditions list with `deleted_at IS NULL`; add `es_alergeno = :val` if not None; `ORDER BY nombre ASC`
- [x] 3.10 Confirm `BaseRepository` methods `get_by_id`, `create`, `update`, `soft_delete` work for `Ingrediente` — write smoke test if not covered by base tests. Note: `BaseRepository.update()` signature is `update(id: uuid.UUID, data: dict[str, Any]) -> T | None` — takes `(id, dict)`, NOT `(entity)`.
- [ ] 3.11 Run repository tests: `pytest tests/ingredientes/test_ingrediente_repository.py -v` — all pass

---

## 4. Service — IngredienteService

- [x] 4.1 Write unit test `tests/ingredientes/test_ingrediente_service.py::test_create_valid_ingrediente` — mock UoW, service creates and returns `IngredienteRead`
- [x] 4.2 Write unit test `test_create_duplicate_nombre_raises_409` — mock IntegrityError from repo flush → service raises `ConflictError(code="INGREDIENT_NAME_DUPLICATE")` from `app.core.exceptions`
- [x] 4.3 Write unit test `test_create_soft_deleted_nombre_allowed` — same nombre as soft-deleted → succeeds (no IntegrityError from partial index)
- [x] 4.4 Write unit test `test_get_ingrediente_not_found_raises_404` — repo returns None → service raises `NotFoundError(code="INGREDIENT_NOT_FOUND")` from `app.core.exceptions`
- [x] 4.5 Write unit test `test_get_ingrediente_soft_deleted_raises_404` — repo returns deleted record → service raises `NotFoundError`
- [x] 4.6 Write unit test `test_update_ingrediente_nombre_only_preserves_es_alergeno` — `IngredienteUpdate(nombre="Sal marina")` only updates nombre; `es_alergeno` unchanged in repo call
- [x] 4.7 Write unit test `test_update_ingrediente_on_deleted_raises_404` — update target has `deleted_at IS NOT NULL` → `NotFoundError`
- [x] 4.8 Write unit test `test_update_ingrediente_duplicate_nombre_raises_409` — IntegrityError on flush → `ConflictError`
- [x] 4.9 Write unit test `test_delete_ingrediente_calls_soft_delete` — service calls `uow.ingredientes.get_by_id` first (not None), then `uow.ingredientes.soft_delete(id)`
- [x] 4.10 Write unit test `test_delete_ingrediente_not_found_raises_404` — ingredient absent → `NotFoundError`
- [x] 4.11 Write unit test `test_list_ingredientes_no_filter` — returns all active ingredients
- [x] 4.12 Write unit test `test_list_ingredientes_with_es_alergeno_filter` — passes filter to repo
- [x] 4.13 Create `backend/app/services/ingrediente.py` with `IngredienteService`. Add: `from app.core.exceptions import NotFoundError, ConflictError`. Service methods are `@staticmethod`, receive `uow: UnitOfWork` parameter — identical pattern to `CategoriaService`.
- [x] 4.14 Implement `list_ingredientes(es_alergeno: bool | None, uow: UnitOfWork) -> list[IngredienteRead]`
- [x] 4.15 Implement `get_ingrediente(ingrediente_id: UUID, uow: UnitOfWork) -> IngredienteRead` — raises `NotFoundError("...", code="INGREDIENT_NOT_FOUND")` if None or soft-deleted
- [x] 4.16 Implement `create_ingrediente(data: IngredienteCreate, uow: UnitOfWork) -> IngredienteRead` — catches `sqlalchemy.exc.IntegrityError` → raises `ConflictError("...", code="INGREDIENT_NAME_DUPLICATE")`
- [x] 4.17 Implement `update_ingrediente(ingrediente_id: UUID, data: IngredienteUpdate, uow: UnitOfWork) -> IngredienteRead` — loads entity via `get_by_id` (raises `NotFoundError` if not found OR soft-deleted); applies only fields from `data.model_fields_set` using `update(id, dict)` pattern:
  ```python
  update_data: dict = {}
  if "nombre" in data.model_fields_set and data.nombre is not None:
      update_data["nombre"] = data.nombre
  if "es_alergeno" in data.model_fields_set and data.es_alergeno is not None:
      update_data["es_alergeno"] = data.es_alergeno
  updated = await uow.ingredientes.update(ingrediente_id, update_data)
  ```
  Catches `IntegrityError` → `ConflictError`. Identical pattern to `CategoriaService.update_categoria`.
- [x] 4.18 Implement `delete_ingrediente(ingrediente_id: UUID, uow: UnitOfWork) -> None` — FIRST calls `uow.ingredientes.get_by_id(ingrediente_id)` to verify existence (raises `NotFoundError` if None or soft-deleted); THEN calls `uow.ingredientes.soft_delete(ingrediente_id)`. The prior `get_by_id` check is mandatory — without it, double-deletes silently succeed instead of returning 404.
- [x] 4.19 Run service tests: `pytest tests/ingredientes/test_ingrediente_service.py -v` — all pass

---

## 5. Router — HTTP Layer

- [x] 5.1 Create `backend/app/api/v1/ingredientes.py` with `APIRouter()` (no prefix — prefix added in `build_v1_router`), following the existing `categorias.py` pattern
- [x] 5.2 Implement `GET /` endpoint — `require_role("ADMIN","STOCK")` dep; `es_alergeno: bool | None = Query(default=None)`; calls `service.list_ingredientes(es_alergeno, uow)`; `response_model=list[IngredienteRead]`; status 200
- [x] 5.3 Implement `GET /{ingrediente_id}` endpoint — `require_role("ADMIN","STOCK")` dep; `ingrediente_id: UUID`; calls `service.get_ingrediente(ingrediente_id, uow)`; `response_model=IngredienteRead`; status 200
- [x] 5.4 Implement `POST /` endpoint — `require_role("ADMIN","STOCK")` dep; calls `service.create_ingrediente(data, uow)`; `response_model=IngredienteRead`; status 201
- [x] 5.5 Implement `PUT /{ingrediente_id}` endpoint — `require_role("ADMIN","STOCK")` dep; `ingrediente_id: UUID`; calls `service.update_ingrediente(ingrediente_id, data, uow)` passing the `IngredienteUpdate` Pydantic model directly (NOT `data.model_dump()`); `response_model=IngredienteRead`; status 200
- [x] 5.6 Implement `DELETE /{ingrediente_id}` endpoint — `require_role("ADMIN","STOCK")` dep; `ingrediente_id: UUID`; calls `service.delete_ingrediente(ingrediente_id, uow)`; status 204; `response_model=None`

---

## 6. API Wiring — UoW and Router Registry

- [x] 6.1 Add `IngredienteRepository` to `UnitOfWork` in `backend/app/core/uow.py` — 3 required changes:
  - 6.1a Add `TYPE_CHECKING` import: inside `if TYPE_CHECKING:` block, add `from app.repositories.ingrediente import IngredienteRepository`
  - 6.1b Add to `__init__`: `self._ingredientes: IngredienteRepository | None = None`
  - 6.1c Add to `__aenter__` reset block: `self._ingredientes = None`
  - 6.1d Add lazy `@property ingredientes` following the exact pattern of `categorias` property
  - NOTE: A stub `@property ingredientes -> NoReturn` may already exist in `uow.py` — REPLACE it, do not add a duplicate
- [x] 6.2 Register `ingredientes_router` in `build_v1_router` in `backend/app/api/v1/router.py` with `prefix="/ingredientes"` and `tags=["ingredientes"]`
- [x] 6.3 Write integration test `tests/integration/test_ingredientes.py::test_get_ingredientes_requires_auth` — no JWT → 401
- [x] 6.4 Write integration test `test_get_ingredientes_client_role_forbidden` — CLIENT JWT → 403
- [x] 6.5 Write integration test `test_get_ingredientes_admin_succeeds` — ADMIN JWT → 200, returns list
- [x] 6.6 Write integration test `test_get_ingredientes_stock_succeeds` — STOCK JWT → 200, returns list
- [x] 6.7 Write integration test `test_post_ingrediente_admin_creates_201` — ADMIN JWT + valid body → 201 with `IngredienteRead`
- [x] 6.8 Write integration test `test_post_ingrediente_stock_creates_201` — STOCK JWT + valid body → 201
- [x] 6.9 Write integration test `test_post_ingrediente_duplicate_nombre_409` — duplicate nombre → 409 `INGREDIENT_NAME_DUPLICATE`
- [x] 6.10 Write integration test `test_get_ingrediente_by_id_not_found_404` — non-existent UUID (e.g. `str(uuid.uuid4())`) → 404 `INGREDIENT_NOT_FOUND`
- [x] 6.11 Write integration test `test_put_ingrediente_nombre_only_preserves_es_alergeno` — update nombre only; verify `es_alergeno` unchanged in response
- [x] 6.12 Write integration test `test_delete_ingrediente_admin_204` — ADMIN JWT → 204
- [x] 6.13 Write integration test `test_delete_ingrediente_stock_204` — STOCK JWT → 204
- [x] 6.14 Write integration test `test_delete_ingrediente_not_found_404` — delete non-existent UUID → 404
- [x] 6.15 Write integration test `test_get_ingredientes_filter_es_alergeno_true` — `?es_alergeno=true` returns only allergens
- [x] 6.16 Write integration test `test_ingredientes_route_registered` — verify all 5 routes exist in app route table
- [ ] 6.17 Run integration tests: `pytest tests/integration/test_ingredientes.py -v` — all pass

---

## 7. Frontend — Ingrediente Entity

- [x] 7.1 Add `export const INGREDIENTES = '/api/v1/ingredientes' as const` to `frontend/src/shared/api/endpoints.ts`
- [x] 7.2 Create `frontend/src/entities/ingrediente/model/types.ts` — `Ingrediente`, `IngredienteCreate`, `IngredienteUpdate` interfaces. Use snake_case field names matching FastAPI JSON output directly (no camelCase conversion):
  ```typescript
  interface Ingrediente {
    id: string;           // UUID as string
    nombre: string;
    es_alergeno: boolean; // snake_case — FastAPI serializes as is
    created_at: string;   // ISO datetime string
    updated_at: string;
  }
  interface IngredienteCreate {
    nombre: string;
    es_alergeno?: boolean;
  }
  interface IngredienteUpdate {
    nombre?: string;
    es_alergeno?: boolean;
  }
  ```
- [x] 7.3 Create `frontend/src/entities/ingrediente/api/ingredienteApi.ts` — fetchers using shared Axios instance:
  - `listIngredientes(params?: { es_alergeno?: boolean }): Promise<Ingrediente[]>` — query param sent as `?es_alergeno=true` (snake_case)
  - `getIngrediente(id: string): Promise<Ingrediente>` — `id` is UUID string
  - `createIngrediente(data: IngredienteCreate): Promise<Ingrediente>`
  - `updateIngrediente(id: string, data: IngredienteUpdate): Promise<Ingrediente>`
  - `deleteIngrediente(id: string): Promise<void>`
- [x] 7.4 Create `frontend/src/entities/ingrediente/api/queryKeys.ts` — `ingredienteKeys` factory with `all`, `lists()`, `list(filters)`, `details()`, `detail(id: string)`
- [x] 7.5 Create `frontend/src/entities/ingrediente/api/hooks.ts` — `useIngredientes`, `useIngrediente`, `useCreateIngrediente`, `useUpdateIngrediente`, `useDeleteIngrediente` (mutations invalidate list + detail on success)
- [x] 7.6 Create `frontend/src/entities/ingrediente/index.ts` — barrel re-exporting public API (types + keys + hooks; NOT raw fetchers)
- [ ] 7.7 TypeScript compile check: `tsc --noEmit` — no errors in the `ingrediente` entity files. # requires running tsc — manual verification step

---

## 8. Validation

- [ ] 8.1 Run full backend test suite: `pytest backend/tests/ -v` — 0 failed (migration tests excluded; require live DB)
- [ ] 8.2 Run migration cycle: `pytest tests/test_migrations.py -k "0004" -v` # requires live DB
- [ ] 8.3 Run `openspec status --change catalog-ingredients-management --json` — verify `isComplete: true` and all artifacts `status: "done"`
- [ ] 8.4 Manual smoke: `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` on dev DB — all 3 steps succeed # requires live DB
- [ ] 8.5 Manual smoke: `POST /api/v1/ingredientes` with ADMIN JWT + `{"nombre": "Sal", "es_alergeno": false}` → HTTP 201 # requires live environment
- [ ] 8.6 Manual smoke: `POST /api/v1/ingredientes` with `{"nombre": "Sal"}` again → HTTP 409 `code="INGREDIENT_NAME_DUPLICATE"` # requires live environment
- [ ] 8.7 Manual smoke: `GET /api/v1/ingredientes?es_alergeno=true` with ADMIN JWT → only allergen ingredients # requires live environment
- [ ] 8.8 Manual smoke: `DELETE /api/v1/ingredientes/{id}` with ADMIN JWT → HTTP 204; then `POST /api/v1/ingredientes` with same nombre → HTTP 201 (name reclaimed) # requires live environment
- [ ] 8.9 Manual smoke: `GET /api/v1/ingredientes` without JWT → HTTP 401 # requires live environment
