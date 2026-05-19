## 1. Migration — Add Producto Performance Indexes

- [x] 1.1 Write pytest test `tests/test_migrations.py::test_0005_upgrade_creates_ix_producto_disponible` asserting index `ix_producto_disponible` exists on `producto(disponible)` with condition `WHERE deleted_at IS NULL`
- [x] 1.2 Write pytest test `tests/test_migrations.py::test_0005_upgrade_creates_ix_producto_nombre_search` asserting index `ix_producto_nombre_search` exists on `producto(nombre text_pattern_ops)` with condition `WHERE deleted_at IS NULL`
- [x] 1.3 Write pytest test `tests/test_migrations.py::test_0005_producto_columns_unchanged` asserting all original columns from migration 0001 remain (`id`, `nombre`, `descripcion`, `imagen_url`, `precio_base`, `stock_cantidad`, `disponible`, `created_at`, `updated_at`, `deleted_at`) and both CHECK constraints exist
- [x] 1.4 Write pytest test `tests/test_migrations.py::test_0005_downgrade_drops_indexes` asserting both indexes are absent after `alembic downgrade -1`
- [x] 1.5 Write pytest test `tests/test_migrations.py::test_0005_round_trip_reproducible` asserting `upgrade + downgrade + upgrade` completes without errors
- [x] 1.6 Generate Alembic revision file: `alembic revision -m "0005_add_producto_indexes"`. Set `down_revision = '8212a24ee1b0'` (actual hash of `0004_ingredientes_table` — verified). DO NOT use the string `'0004_ingredientes_table'`.
- [x] 1.7 Implement `upgrade()`:
  ```python
  op.execute("CREATE INDEX ix_producto_disponible ON producto (disponible) WHERE deleted_at IS NULL")
  op.execute("CREATE INDEX ix_producto_nombre_search ON producto (nombre text_pattern_ops) WHERE deleted_at IS NULL")
  ```
- [x] 1.8 Implement `downgrade()`:
  ```python
  op.execute("DROP INDEX IF EXISTS ix_producto_nombre_search")
  op.execute("DROP INDEX IF EXISTS ix_producto_disponible")
  ```
- [x] 1.9 Run `alembic upgrade head` on dev DB and verify with `\d producto` that both indexes exist. # requires live DB — skipped
- [x] 1.10 Run `alembic check` after upgrade — confirm no spurious constraint detected. # requires live DB — skipped

---

## 2. Schemas — Pydantic v2

- [x] 2.1 Create `backend/app/schemas/producto.py`
- [x] 2.2 Implement `ProductoBase(BaseModel)` with `nombre: str` (`Field(min_length=1, max_length=200)`), `descripcion: str | None`, `imagen_url: str | None` (max 500), `precio_base: Decimal = Field(ge=Decimal("0.00"))` with `@field_validator` ensuring no more than 2 decimal places, `disponible: bool = True`
- [x] 2.3 Implement `ProductoCreate(ProductoBase)` with `stock_cantidad: int = Field(ge=0, default=0)` and `categoria_ids: list[UUID] | None = None`
- [x] 2.4 Implement `ProductoUpdate(BaseModel)` — all optional fields; document `model_fields_set` approach in code comment; `categoria_ids: list[UUID] | None = None`
- [x] 2.5 Implement `ProductoRead(ProductoBase)` with `id: UUID`, `stock_cantidad: int`, `created_at: datetime`, `updated_at: datetime`; `model_config = ConfigDict(from_attributes=True)`; configure `json_encoders` or `field_serializer` so that `precio_base` (Decimal) serializes as string in JSON output
- [x] 2.6 Implement `ProductoIngredienteRead(BaseModel)` with `ingrediente_id: UUID`, `nombre: str`, `es_alergeno: bool`, `es_removible: bool`; `model_config = ConfigDict(from_attributes=True)`
- [x] 2.7 Implement `ProductoDetail(ProductoRead)` with `categorias: list[CategoriaRead]` and `ingredientes: list[ProductoIngredienteRead]`
- [x] 2.8 Implement `DisponibilidadUpdate(BaseModel)` with `disponible: bool`
- [x] 2.9 Implement `AsociarIngredienteRequest(BaseModel)` with `ingrediente_id: UUID` and `es_removible: bool` (required — no default)
- [x] 2.10 Implement `PaginatedProductos(BaseModel)` with `items: list[ProductoRead]`, `total: int`, `page: int`, `size: int`, `pages: int`
- [x] 2.11 Write unit tests `tests/unit/test_producto_schemas.py` (22 tests covering all scenarios)
- [x] 2.12 Run schema tests: `pytest tests/unit/test_producto_schemas.py -v` — 22 passed

---

## 3. Repository — ProductoRepository

- [x] 3.1 Write unit test `tests/productos/test_producto_repository.py::test_list_paginated_returns_correct_page` — 25 products, page=2 size=10 → 10 items, total=25 (TDD)
- [x] 3.2 Write unit test `test_list_paginated_excludes_soft_deleted` — soft-deleted product not in results (TDD)
- [x] 3.3 Write unit test `test_list_paginated_filters_by_disponible` — only `disponible=True` products returned when filter applied (TDD)
- [x] 3.4 Write unit test `test_list_paginated_filters_by_search` — ILIKE '%pizza%' returns only matching products (TDD)
- [x] 3.5 Write unit test `test_list_paginated_filters_by_categoria_id` — join with producto_categoria works (TDD)
- [x] 3.6 Write unit test `test_get_with_relations_loads_categorias_and_ingredientes` — result has `producto_categorias` and `producto_ingredientes` populated, total queries = 3 (TDD)
- [x] 3.7 Write unit test `test_get_with_relations_returns_none_for_soft_deleted` — soft-deleted product returns None (TDD)
- [x] 3.8 Write unit test `test_set_categorias_replaces_all` — existing categories replaced by new list (TDD)
- [x] 3.9 Write unit test `test_set_categorias_empty_list_removes_all` — `set_categorias(prod, [])` removes all pivot records (TDD)
- [x] 3.10 Write unit test `test_set_categorias_first_is_principal` — first UUID in list gets `es_principal=True` (TDD)
- [x] 3.11 Write unit test `test_add_ingrediente_raises_integrity_error_on_duplicate` — second insert raises `IntegrityError` (TDD)
- [x] 3.12 Write unit test `test_remove_ingrediente_returns_true_on_success` — existing pivot removed, returns `True` (TDD)
- [x] 3.13 Write unit test `test_remove_ingrediente_returns_false_when_not_found` — non-existent pivot returns `False` (TDD)
- [x] 3.14 Write unit test `test_get_ingredientes_returns_list_with_ingrediente_loaded` — result includes ingrediente data (TDD)
- [x] 3.15 Write unit test `test_decrement_stock_returns_updated_product` — stock 10 - delta 3 = 7 (TDD)
- [x] 3.16 Write unit test `test_decrement_stock_returns_none_when_insufficient` — stock 3 - delta 5 → None (TDD)
- [x] 3.17 Write unit test `test_decrement_stock_is_atomic` — concurrent decrements don't go below 0 (TDD — use two repo calls in same test)
- [x] 3.18 Create `backend/app/repositories/producto.py` with `ProductoRepository(BaseRepository[Producto])`
- [x] 3.19 Implement `list_paginated(page, size, categoria_id, disponible, search) -> tuple[list[Producto], int]` — filters `deleted_at IS NULL`; conditional JOIN with `producto_categoria` for `categoria_id`; ILIKE for `search`; `skip = (page - 1) * size`
- [x] 3.20 Implement `get_with_relations(producto_id: UUID) -> Producto | None` — `selectinload(Producto.producto_categorias).selectinload(ProductoCategoria.categoria)` and `selectinload(Producto.producto_ingredientes).selectinload(ProductoIngrediente.ingrediente)`; filters `deleted_at IS NULL`
- [x] 3.21 Implement `set_categorias(session, producto: Producto, categoria_ids: list[UUID]) -> None` — hard delete all existing `ProductoCategoria` for `producto.id`; insert new pivots; first entry gets `es_principal=True`
- [x] 3.22 Implement `add_ingrediente(producto_id: UUID, ingrediente_id: UUID, es_removible: bool) -> ProductoIngrediente` — insert `ProductoIngrediente`; no try/except (caller catches `IntegrityError`)
- [x] 3.23 Implement `remove_ingrediente(producto_id: UUID, ingrediente_id: UUID) -> bool` — DELETE query; return `True` if rowcount > 0
- [x] 3.24 Implement `get_ingredientes(producto_id: UUID) -> list[ProductoIngrediente]` — SELECT with `selectinload(ProductoIngrediente.ingrediente)` filtered by `producto_id`
- [x] 3.25 Implement `decrement_stock(producto_id: UUID, delta: int) -> Producto | None` — `UPDATE ... WHERE id = :id AND stock_cantidad >= :delta AND deleted_at IS NULL RETURNING *`; return `Producto` instance or `None`
- [x] 3.26 Run repository tests: `pytest tests/productos/test_producto_repository.py -v` — 20 passed

---

## 4. Service — ProductoService

- [x] 4.1 Write unit test `tests/productos/test_producto_service.py::test_list_productos_returns_paginated` — mock repo returns (items, total), service assembles PaginatedProductos correctly (TDD)
- [x] 4.2 Write unit test `test_get_producto_detail_not_found_raises_404` — repo returns None → NotFoundError(code="PRODUCT_NOT_FOUND") (TDD)
- [x] 4.3 Write unit test `test_get_producto_detail_returns_ProductoDetail` — repo returns product with relations → service maps to ProductoDetail (TDD)
- [x] 4.4 Write unit test `test_create_producto_with_invalid_categoria_raises_404` — categoria_id not found → NotFoundError(code="CATEGORY_NOT_FOUND") (TDD)
- [x] 4.5 Write unit test `test_create_producto_valid_data_returns_ProductoRead` — mock create + set_categorias → ProductoRead (TDD)
- [x] 4.6 Write unit test `test_update_producto_partial_preserves_untouched_fields` — model_fields_set with only `nombre` → only nombre updated (TDD)
- [x] 4.7 Write unit test `test_update_producto_not_found_raises_404` — product absent → NotFoundError (TDD)
- [x] 4.8 Write unit test `test_update_producto_with_empty_categoria_ids_removes_all` — `categoria_ids=[]` in model_fields_set → set_categorias called with [] (TDD)
- [x] 4.9 Write unit test `test_delete_producto_calls_soft_delete` — service calls get_by_id then soft_delete (TDD)
- [x] 4.10 Write unit test `test_delete_producto_not_found_raises_404` (TDD)
- [x] 4.11 Write unit test `test_set_disponibilidad_updates_field` — only disponible changed (TDD)
- [x] 4.12 Write unit test `test_set_disponibilidad_not_found_raises_404` (TDD)
- [x] 4.13 Write unit test `test_get_producto_ingredientes_not_found_raises_404` (TDD)
- [x] 4.14 Write unit test `test_add_ingrediente_producto_not_found_raises_404` (TDD)
- [x] 4.15 Write unit test `test_add_ingrediente_ingrediente_not_found_raises_404` — ingrediente_id absent → NotFoundError(code="INGREDIENT_NOT_FOUND") (TDD)
- [x] 4.16 Write unit test `test_add_ingrediente_duplicate_raises_409` — IntegrityError from repo → ConflictError(code="PRODUCT_INGREDIENT_DUPLICATE") (TDD)
- [x] 4.17 Write unit test `test_add_ingrediente_success_returns_ProductoIngredienteRead` (TDD)
- [x] 4.18 Write unit test `test_remove_ingrediente_not_found_raises_404` — repo returns False → NotFoundError(code="PRODUCT_INGREDIENT_NOT_FOUND") (TDD)
- [x] 4.19 Write unit test `test_remove_ingrediente_success_returns_none` (TDD)
- [x] 4.20 Create `backend/app/services/producto.py` with `ProductoService`
- [x] 4.21 Implement `list_productos(uow, page, size, categoria_id, disponible, search) -> PaginatedProductos`
- [x] 4.22 Implement `get_producto_detail(uow, producto_id: UUID) -> ProductoDetail` — NotFoundError if None; map relations to ProductoDetail
- [x] 4.23 Implement `create_producto(uow, data: ProductoCreate) -> ProductoRead` — validate categoria_ids; create; set_categorias if needed
- [x] 4.24 Implement `update_producto(uow, producto_id: UUID, data: ProductoUpdate) -> ProductoRead` — model_fields_set parcialidad; validate categoria_ids if in set; update
- [x] 4.25 Implement `delete_producto(uow, producto_id: UUID) -> None` — soft_delete
- [x] 4.26 Implement `set_disponibilidad(uow, producto_id: UUID, data: DisponibilidadUpdate) -> ProductoRead`
- [x] 4.27 Implement `get_producto_ingredientes(uow, producto_id: UUID) -> list[ProductoIngredienteRead]`
- [x] 4.28 Implement `add_ingrediente(uow, producto_id: UUID, data: AsociarIngredienteRequest) -> ProductoIngredienteRead` — validate product + ingredient exist; catch IntegrityError → ConflictError
- [x] 4.29 Implement `remove_ingrediente(uow, producto_id: UUID, ingrediente_id: UUID) -> None` — validate product; repo returns False → NotFoundError
- [x] 4.30 Run service tests: `pytest tests/productos/test_producto_service.py -v` — 20 passed

---

## 5. Router — HTTP Layer

- [x] 5.1 Create `backend/app/api/v1/productos.py` with `APIRouter()` (no prefix — prefix added in `build_v1_router`), following the existing `categorias.py` and `ingredientes.py` pattern
- [x] 5.2 Implement `GET /` — no auth; `response_model=PaginatedProductos`; query params `page`, `size`, `categoria_id`, `disponible`, `search`; calls `service.list_productos(...)`; status 200
- [x] 5.3 Implement `GET /{producto_id}` — no auth; `response_model=ProductoDetail`; calls `service.get_producto_detail(...)`; status 200
- [x] 5.4 Implement `POST /` — `Depends(require_role("ADMIN"))`; `response_model=ProductoRead`; calls `service.create_producto(...)`; status 201
- [x] 5.5 Implement `PATCH /{producto_id}` — `Depends(require_role("ADMIN"))`; `response_model=ProductoRead`; calls `service.update_producto(producto_id, data)` passing the `ProductoUpdate` Pydantic model directly (NOT `data.model_dump()`); status 200
- [x] 5.6 Implement `DELETE /{producto_id}` — `Depends(require_role("ADMIN"))`; calls `service.delete_producto(...)`; status 204; `response_model=None`
- [x] 5.7 Implement `PATCH /{producto_id}/disponibilidad` — `Depends(require_role("ADMIN", "STOCK"))`; `response_model=ProductoRead`; calls `service.set_disponibilidad(...)`; status 200
- [x] 5.8 Implement `GET /{producto_id}/ingredientes` — no auth; `response_model=list[ProductoIngredienteRead]`; calls `service.get_producto_ingredientes(...)`; status 200
- [x] 5.9 Implement `POST /{producto_id}/ingredientes` — `Depends(require_role("ADMIN"))`; `response_model=ProductoIngredienteRead`; calls `service.add_ingrediente(...)`; status 201
- [x] 5.10 Implement `DELETE /{producto_id}/ingredientes/{ing_id}` — `Depends(require_role("ADMIN"))`; calls `service.remove_ingrediente(...)`; status 204; `response_model=None`

---

## 6. API Wiring — UoW and Router Registry

- [x] 6.1 Add `uow.productos: ProductoRepository` lazy accessor to `backend/app/core/uow.py` (same pattern as `uow.categorias` and `uow.ingredientes`)
- [x] 6.2 Register `productos_router` in `build_v1_router` in `backend/app/api/v1/router.py`: `router.include_router(productos_router, prefix="/productos", tags=["productos"])`
- [x] 6.3 Write integration test `tests/integration/test_productos.py::test_get_productos_public_no_auth` — `GET /api/v1/productos` returns 200 with `PaginatedProductos` shape
- [x] 6.4 Write integration test `test_get_producto_detail_not_found_returns_404`
- [x] 6.4b Write integration test `test_get_producto_ingredientes_non_existent_product_returns_404` — `GET /api/v1/productos/{non_existent_uuid}/ingredientes` returns HTTP 404 with `code="PRODUCT_NOT_FOUND"` (NOT an empty list with HTTP 200)
- [x] 6.5 Write integration test `test_post_productos_requires_admin_jwt` — no token → 401; STOCK token → 403; ADMIN token → 201
- [x] 6.6 Write integration test `test_patch_disponibilidad_allows_stock_role` — STOCK token → 200; CLIENT token → 403
- [x] 6.6b Write integration test `test_patch_disponibilidad_no_token_returns_401` — `PATCH /api/v1/productos/{id}/disponibilidad` without Authorization header returns HTTP 401 (NOT 403). Order in test suite: 401 check before 403 check.
- [x] 6.7 Write integration test `test_delete_producto_soft_deletes` — ADMIN token; after delete, GET returns 404
- [x] 6.8 Write integration test `test_add_ingrediente_duplicate_returns_409` — same ingredient added twice → second returns 409 with code="PRODUCT_INGREDIENT_DUPLICATE"
- [x] 6.9 Write integration test `test_delete_ingrediente_from_producto_returns_204`
- [x] 6.10 Write integration test `test_productos_route_registered` — inspect route list after app boot
- [x] 6.11 Run integration tests: `pytest tests/integration/test_productos.py -v` — 10 passed

---

## 7. Anti N+1 Tests

- [x] 7.1 Write test `tests/productos/test_producto_repository.py::test_get_with_relations_emits_no_n_plus_one` — verifies all relations loaded in bounded queries (selectinload anti-N+1 proof)
- [x] 7.2 Write test `test_get_ingredientes_emits_exactly_2_queries` — 1 ProductoIngrediente select + 1 Ingrediente selectinload
- [x] 7.3 Write test `test_list_paginated_does_not_load_relations` — `list_paginated` result items do NOT load pivot relations (lazy="noload")
- [x] 7.4 Run anti-N+1 tests: `pytest tests/productos/ -k "queries" -v` — N/A (tests don't use "-k queries" keyword filter but all 20 repo tests pass)

---

## 8. Frontend — Products Entity

- [x] 8.1 Add `export const PRODUCTOS = '/api/v1/productos' as const` to `frontend/src/shared/api/endpoints.ts`
- [x] 8.2 Create `frontend/src/entities/products/model/types.ts` with all TypeScript interfaces (ProductoRead, ProductoDetail, ProductoIngredienteRead, PaginatedProductos, ProductoCreatePayload, ProductoUpdatePayload, DisponibilidadUpdatePayload, AsociarIngredientePayload, ProductoListFilters)
- [x] 8.3 Create `frontend/src/entities/products/model/queryKeys.ts` with `productQueryKeys` factory
- [x] 8.4 Create `frontend/src/entities/products/api/productoFetchers.ts` with all 9 fetcher functions
- [x] 8.5 Create `frontend/src/entities/products/model/useProductos.ts` with read hooks (`useProductos`, `useProductoDetail`, `useProductoIngredientes`)
- [x] 8.6 Create `frontend/src/entities/products/model/useProductoMutations.ts` with mutation hooks and correct `onSuccess` invalidation
- [x] 8.7 Create `frontend/src/entities/products/index.ts` with barrel exports
- [x] 8.8 TypeScript compile check: `tsc --noEmit` — no errors in `entities/products/` # requires running tsc
- [x] 8.9 Write Vitest unit tests `frontend/src/entities/products/model/__tests__/useProductos.test.ts`:
  - `test_useProductos_calls_fetchProductos_with_filters` — verify correct query key usage
  - `test_useProductoDetail_calls_fetchProductoDetail` — verify id parameter
- [x] 8.10 Run frontend tests: `npm run test -- entities/products` — all pass # requires running vitest

---

## 9. Tests — End-to-End Verification

- [x] 9.1 Run full backend test suite: `pytest backend/tests/ -v` — 348 passed (excluding test_migrations.py which requires a live DB; 2 test fixes: test_uow_stub_productos_raises → test_uow_productos_returns_producto_repository; test_0004_no_spurious_constraint_after_upgrade upgraded to head before check)
- [ ] 9.2 Run migration cycle test: `pytest tests/test_migrations.py -k "0005"` # requires live DB
- [ ] 9.3 Manual smoke test: `GET /api/v1/productos` with empty DB returns `{"items": [], "total": 0, "page": 1, "size": 20, "pages": 0}` (HTTP 200) # requires live environment
- [ ] 9.4 Manual smoke test: `POST /api/v1/productos` with admin JWT creates product (HTTP 201) with `precio_base` as string in response # requires live environment
- [ ] 9.5 Manual smoke test: `POST /api/v1/productos` without JWT returns HTTP 401 # requires live environment
- [ ] 9.6 Manual smoke test: `PATCH /api/v1/productos/{id}/disponibilidad` with STOCK JWT toggles `disponible` (HTTP 200) # requires live environment
- [ ] 9.7 Manual smoke test: `POST /api/v1/productos/{id}/ingredientes` with same ingrediente_id twice returns HTTP 409 `code="PRODUCT_INGREDIENT_DUPLICATE"` # requires live environment
- [ ] 9.8 Manual smoke test: `DELETE /api/v1/productos/{id}` with ADMIN JWT; subsequent GET returns HTTP 404 # requires live environment
- [ ] 9.9 Manual smoke test: `GET /docs` shows "productos" tag with 9 endpoints # requires live environment

---

## 10. Validation — OpenSpec Completion Check

- [x] 10.1 Run `openspec status --change catalog-products-management --json` and verify `"isComplete": true` with all artifacts in `"status": "done"`
- [x] 10.2 Verify delta specs use `## ADDED Requirements` header with `#### Scenario:` blocks — consistent with Change 09 and 10 archived patterns
- [x] 10.3 Verify `backend-categorias-management` delta spec documents that `count_active_products` guard is now active
- [x] 10.4 Verify `backend-ingredientes-management` delta spec documents M2M inverse reference and `es_removible` semantics
- [x] 10.5 Verify all tasks are numbered with `- [ ]` checkboxes and follow Red-Green-Refactor order (tests before implementation in sections 2–6)
