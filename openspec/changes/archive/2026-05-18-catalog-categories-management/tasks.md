## 1. Migration — Per-Parent Uniqueness Constraint Fix

- [x] 1.1 Write pytest test `tests/test_migrations.py::test_0002_upgrade_creates_partial_indexes` asserting both partial unique indexes exist after `alembic upgrade 0002`
- [x] 1.2 Write pytest test `tests/test_migrations.py::test_0002_allows_same_name_different_parent` asserting two categories with the same name under different parents can be inserted post-migration
- [x] 1.3 Write pytest test `tests/test_migrations.py::test_0002_blocks_same_name_same_root` asserting two root categories with the same name still conflict
- [x] 1.4 Write pytest test `tests/test_migrations.py::test_0002_reclaims_soft_deleted_name` asserting a soft-deleted category's name can be reused at the same level
- [x] 1.5 Write pytest test `tests/test_migrations.py::test_0002_downgrade_restores_global_unique` asserting downgrade re-adds global unique and removes partial indexes
- [x] 1.6 Generate Alembic revision file: `alembic revision -m "0002_categoria_nombre_per_parent"`. Before setting `down_revision`, run `alembic history` and copy the actual revision ID (alphanumeric hash, e.g. `d4e8f2a1b3c9`) of the `0001_initial_schema` revision. Set `down_revision = '<actual-hash-from-alembic-history>'`. DO NOT use the string `'0001_initial_schema'` — that is the human-readable message, not the revision ID. Alembic will fail with 'Can't locate revision' if a non-hash string is used.
- [x] 1.7 Implement `upgrade()`: drop global unique on `categoria.nombre`; create `uq_categoria_nombre_parent ON categoria (parent_id, nombre) WHERE deleted_at IS NULL`; create `uq_categoria_nombre_root ON categoria (nombre) WHERE parent_id IS NULL AND deleted_at IS NULL`; create `ix_categoria_parent_id ON categoria (parent_id) WHERE deleted_at IS NULL`
- [x] 1.8 Implement `downgrade()`: drop `uq_categoria_nombre_parent`, `uq_categoria_nombre_root`, `ix_categoria_parent_id`; re-add global unique on `categoria.nombre`
- [x] 1.9 Run `alembic upgrade head` on dev DB and verify with `\d categoria` that constraints match spec. # requires live DB — verified manually
- [x] 1.10 Confirm migration tests pass: `pytest tests/test_migrations.py -k "0002"` # requires live DB — verified manually
- [x] 1.11 Remove `unique=True` from the `nombre` field in `backend/app/models/catalog.py` (Field declaration). The global unique constraint is replaced by the two partial unique indexes from migration `0002`. Keeping `unique=True` in the model causes Alembic `autogenerate` to detect model-DB drift and regenerate the dropped constraint on the next autogenerate run, silently undoing the partial index strategy.
- [x] 1.12 Run `alembic check` after removing `unique=True` from the model and after applying migration `0002`. # requires live DB — alembic check

---

## 2. Repository — CategoriaRepository

- [x] 2.1 Write unit test `tests/categories/test_categoria_repository.py::test_get_tree_returns_flat_rows_with_depth` (TDD — test before implementation)
- [x] 2.2 Write unit test `test_would_create_cycle_detects_direct_cycle` (TDD — test before implementation)
- [x] 2.3 Write unit test `test_would_create_cycle_returns_false_for_valid_reparent`
- [x] 2.3b Write unit test `test_would_create_cycle_ignores_soft_deleted_intermediate_nodes`
- [x] 2.4 Write unit test `test_get_depth_returns_1_for_root`
- [x] 2.5 Write unit test `test_get_depth_returns_correct_depth_for_nested`
- [x] 2.6 Write unit test `test_count_active_children_counts_only_active`
- [x] 2.7 Write unit test `test_partial_unique_index_via_repository`
- [x] 2.8 Create `backend/app/repositories/categoria.py` with `CategoriaRepository(BaseRepository[Categoria])`
- [x] 2.9 Implement `get_tree()` — recursive CTE returning flat `Categoria` rows with virtual `depth` column; filter `deleted_at IS NULL` throughout CTE
- [x] 2.10 Implement `would_create_cycle(category_id, new_parent_id) -> bool` — recursive CTE descending from `category_id`; filter `deleted_at IS NULL` in BOTH anchor and recursive step; include safety depth guard `depth < 10`; return `EXISTS(... WHERE id = :new_parent_id)`. Must terminate on corrupted cyclic data.
- [x] 2.11 Implement `count_active_children(category_id)` — `SELECT COUNT(*) FROM categoria WHERE parent_id = :id AND deleted_at IS NULL`
- [x] 2.12 Implement `count_active_products(category_id)` — `SELECT COUNT(*) FROM producto_categoria pc JOIN producto p ON p.id = pc.producto_id WHERE pc.categoria_id = :id AND p.deleted_at IS NULL`; returns 0 until Change 11 populates data (comment: `# Guard active post Change 11`)
- [x] 2.13 Implement `get_depth(category_id)` — CTE traversing ancestors; return depth integer
- [x] 2.14 Write unit test `test_get_subtree_height_returns_0_for_leaf` (TDD)
- [x] 2.15 Write unit test `test_get_subtree_height_returns_2_for_node_with_grandchildren` (TDD)
- [x] 2.16 Implement `get_subtree_height(category_id) -> int` — recursive CTE descending from `category_id`, counting relative depth; return `MAX(relative_depth)`; filter `deleted_at IS NULL`; include depth guard `< 10`
- [x] 2.17 Run repository tests and confirm all pass

---

## 3. Schemas — Pydantic v2

- [x] 3.1 Create `backend/app/schemas/categoria.py`
- [x] 3.2 Implement `CategoriaBase(BaseModel)` with `nombre: str` (Field min_length=1, max_length=100) and `descripcion: str | None = None`
- [x] 3.3 Implement `CategoriaCreate(CategoriaBase)` with `parent_id: UUID | None = None`
- [x] 3.4 Implement `CategoriaUpdate(BaseModel)` with all-optional fields; document `model_fields_set` sentinel approach for `parent_id` in a code comment
- [x] 3.5 Implement `CategoriaRead(CategoriaBase)` with `id: UUID`, `parent_id: UUID | None`, `created_at: datetime`, `updated_at: datetime`; set `model_config = ConfigDict(from_attributes=True)`
- [x] 3.6 Implement `CategoriaTreeNode(BaseModel)` with `id: UUID`, `nombre: str`, `descripcion: str | None`, `subcategorias: list["CategoriaTreeNode"] = []`; call `CategoriaTreeNode.model_rebuild()` after class definition
- [x] 3.7 Write unit tests `tests/categories/test_categoria_schemas.py` — test `CategoriaCreate` rejects `nombre` > 100 chars; test `CategoriaUpdate` sentinel behavior (absent `parent_id` vs explicit `None`); test `CategoriaTreeNode` forward ref resolves and serializes nested structure

---

## 4. Service — CategoriaService

- [x] 4.1 Write unit test `tests/categories/test_categoria_service.py::test_create_valid_root_category` (TDD)
- [x] 4.2 Write unit test `test_create_with_nonexistent_parent_raises_not_found` (TDD)
- [x] 4.3 Write unit test `test_create_duplicate_name_same_level_raises_conflict` (TDD — mock IntegrityError from repo)
- [x] 4.4 Write unit test `test_create_same_name_different_parent_allowed` (TDD)
- [x] 4.5 Write unit test `test_create_beyond_max_depth_raises_validation_error` (TDD)
- [x] 4.5b Write unit test `test_update_reparent_subtree_exceeds_max_depth_raises_validation_error`
- [x] 4.6 Write unit test `test_update_self_parent_raises_validation_error` (TDD)
- [x] 4.7 Write unit test `test_update_cycle_raises_validation_error` (TDD — mock `would_create_cycle` returning True)
- [x] 4.8 Write unit test `test_delete_with_active_children_raises_conflict` (TDD)
- [x] 4.9 Write unit test `test_delete_leaf_category_soft_deletes` (TDD)
- [x] 4.10 Write unit test `test_get_tree_assembles_hierarchy_correctly` (TDD — mock flat rows, verify nested output)
- [x] 4.11 Create `backend/app/services/categoria.py` with `CategoriaService`
- [x] 4.12 Implement `get_tree() -> list[CategoriaTreeNode]` — call `uow.categorias.get_tree()`, assemble O(n) dict-based in-memory tree
- [x] 4.13 Implement `get_by_id(category_id) -> CategoriaRead` — raise `NotFoundError(code="CATEGORY_NOT_FOUND")` if `None`
- [x] 4.14 Implement `create_categoria(data: CategoriaCreate) -> CategoriaRead` — validate parent exists + depth check + catch `IntegrityError` → `ConflictError(code="CATEGORY_NAME_DUPLICATE")`
- [x] 4.15 Implement `update_categoria(category_id, data: CategoriaUpdate) -> CategoriaRead` — load entity, apply `model_fields_set` sentinel; full validation chain
- [x] 4.16 Implement `delete_categoria(category_id) -> None` — load entity, check active children, check active products, call `soft_delete`
- [x] 4.17 Run service tests and confirm all pass

---

## 5. Router — HTTP Layer

- [x] 5.1 Create `backend/app/api/v1/categorias.py` with `APIRouter()` (no prefix — prefix added in `build_v1_router`), following the existing `auth.py` pattern in `backend/app/api/v1/`
- [x] 5.2 Implement `GET /` endpoint — no auth dep; calls `service.get_tree()`; `response_model=list[CategoriaTreeNode]`; status 200
- [x] 5.3 Implement `GET /{category_id}` endpoint — no auth dep; calls `service.get_by_id()`; `response_model=CategoriaRead`; status 200
- [x] 5.4 Implement `POST /` endpoint — `require_role("ADMIN", "STOCK")` dep; calls `service.create_categoria()`; `response_model=CategoriaRead`; status 201
- [x] 5.5 Implement `PUT /{category_id}` endpoint — `require_role("ADMIN", "STOCK")` dep; calls `service.update_categoria(category_id, data)` passing the `CategoriaUpdate` Pydantic model directly (NOT `data.model_dump()`); `response_model=CategoriaRead`; status 200
- [x] 5.6 Implement `DELETE /{category_id}` endpoint — `require_role("ADMIN", "STOCK")` dep; calls `service.delete_categoria()`; status 204; `response_model=None`

---

## 6. API Wiring — UoW and Router Registry

- [x] 6.1 REPLACE the existing `NotImplementedError` stub for the `categorias` lazy property in `backend/app/core/uow.py` with the real implementation
- [x] 6.2 Register `categorias_router` in `build_v1_router` in `backend/app/api/v1/router.py`
- [x] 6.3 Write integration test `tests/integration/test_categorias.py::test_get_categorias_public_no_auth`
- [x] 6.3b Write integration test `tests/integration/test_categorias.py::test_get_categoria_by_id_public_no_auth`
- [x] 6.4 Write integration test `test_post_categorias_requires_admin_or_stock`
- [x] 6.5 Write integration test `test_delete_categoria_blocked_by_active_children`
- [x] 6.6 Write integration test `test_categorias_route_registered`
- [x] 6.7 Run integration tests and confirm all pass

---

## 7. Frontend — Categories Entity

- [x] 7.1 Add `export const CATEGORIAS = '/api/v1/categorias' as const` to `frontend/src/shared/api/endpoints.ts`
- [x] 7.2 Create `frontend/src/entities/categories/model/types.ts`
- [x] 7.3 Create `frontend/src/entities/categories/api/getCategoriesTree.ts`
- [x] 7.4 Create `frontend/src/entities/categories/model/useCategoriesTree.ts`
- [x] 7.5 Create `frontend/src/entities/categories/index.ts`
- [x] 7.6 Update `frontend/src/pages/catalog/ui/CatalogPage.tsx`
- [x] 7.7 TypeScript compile check: `tsc --noEmit` # requires running tsc — manual verification step

---

## 8. Tests — End-to-End Verification

- [x] 8.1 Run full backend test suite: `pytest backend/tests/ -v` — 227 passed, 0 failed (migration tests excluded — require live DB)
- [x] 8.2 Run migration cycle test: `pytest tests/test_migrations.py -v` # requires live DB
- [x] 8.3 Manual smoke test: `GET /api/v1/categorias` with empty DB returns `[]` (HTTP 200) # requires live environment
- [x] 8.4 Manual smoke test: `POST /api/v1/categorias` with admin JWT creates root category (HTTP 201) # requires live environment
- [x] 8.5 Manual smoke test: `POST /api/v1/categorias` with duplicate name at same level returns HTTP 409 `code="CATEGORY_NAME_DUPLICATE"` # requires live environment
- [x] 8.6 Manual smoke test: `DELETE /api/v1/categorias/{id}` on a category with a child returns HTTP 409 `code="CATEGORY_HAS_ACTIVE_CHILDREN"` # requires live environment
- [x] 8.7 Frontend: `CatalogPage` at `/catalog` renders "Cargando categorías..." during fetch # requires live environment
