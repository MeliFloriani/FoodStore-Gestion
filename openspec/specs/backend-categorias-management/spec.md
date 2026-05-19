## ADDED Requirements

### Requirement: Pydantic schemas for Categoria
The system SHALL provide Pydantic v2 schemas in `backend/app/schemas/categoria.py` for all category API operations: `CategoriaBase`, `CategoriaCreate`, `CategoriaUpdate`, `CategoriaRead`, and `CategoriaTreeNode`.

`CategoriaBase` SHALL enforce `nombre: str` with min length 1 and max length 100, and `descripcion: str | None = None`.

`CategoriaCreate` SHALL inherit `CategoriaBase` and add `parent_id: UUID | None = None`.

`CategoriaUpdate` SHALL be a flat `BaseModel` (no inheritance) with all fields optional: `nombre: str | None = None`, `descripcion: str | None = None`, `parent_id` handled via `model_fields_set` sentinel — if `parent_id` is absent from the payload, the field is not touched; if present and `None`, the category is promoted to root.

`CategoriaRead` SHALL include `id: UUID`, `parent_id: UUID | None`, `created_at: datetime`, `updated_at: datetime` in addition to `CategoriaBase` fields, with `model_config = ConfigDict(from_attributes=True)`.

`CategoriaTreeNode` SHALL include `id: UUID`, `nombre: str`, `descripcion: str | None`, and `subcategorias: list["CategoriaTreeNode"] = []`. The forward reference SHALL be resolved via `CategoriaTreeNode.model_rebuild()` called at MODULE LEVEL immediately after the class definition. This call MUST occur at module import time, not inside a function or conditional block. Failure to call it at module level will cause Pydantic to fail to resolve the forward reference at runtime when serializing nested trees.

#### Scenario: CategoriaCreate validates nombre length
- **WHEN** a `CategoriaCreate` payload has `nombre` exceeding 100 characters
- **THEN** Pydantic raises `ValidationError` with a field error on `nombre`

#### Scenario: CategoriaUpdate with absent parent_id does not affect parent
- **WHEN** `PUT /api/v1/categorias/{id}` is called with a body containing only `{"nombre": "Nuevo"}` (no `parent_id` key)
- **THEN** the service reads `"parent_id" not in data.model_fields_set` as `True`
- **THEN** the category's `parent_id` is unchanged

#### Scenario: CategoriaUpdate with explicit null parent_id promotes to root
- **WHEN** `PUT /api/v1/categorias/{id}` is called with `{"parent_id": null}`
- **THEN** the service reads `"parent_id" in data.model_fields_set` as `True` with value `None`
- **THEN** the category's `parent_id` is set to `NULL` (promoted to root)

#### Scenario: CategoriaTreeNode forward reference resolves
- **WHEN** `CategoriaTreeNode.model_rebuild()` is called after the class definition
- **THEN** a `CategoriaTreeNode` with nested `subcategorias` can be instantiated and serialized without error

---

### Requirement: CategoriaRepository with tree and cycle-detection CTE
The system SHALL provide `CategoriaRepository(BaseRepository[Categoria])` at `backend/app/repositories/categoria.py` with these additional methods beyond `BaseRepository`:

- `get_tree() -> list[Categoria]`: Executes a recursive CTE fetching all active categories with a virtual `depth` integer column. Root categories have `depth = 1`. The CTE SHALL include only rows where `deleted_at IS NULL`.
- `would_create_cycle(category_id: UUID, new_parent_id: UUID) -> bool`: Returns `True` if assigning `new_parent_id` as the parent of `category_id` would create a cycle. Executes a recursive CTE starting from `category_id` and traversing descendants. Filters `deleted_at IS NULL` in BOTH the anchor and the recursive step. Includes a safety depth guard `depth < 10` to terminate even on corrupted cyclic data. Returns `True` if `new_parent_id` appears in the descendant set (via `EXISTS`).
- `count_active_children(category_id: UUID) -> int`: Counts direct active subcategories.
- `count_active_products(category_id: UUID) -> int`: Counts active products in `producto_categoria` linked to this category (returns 0 until Change 11 populates data).
- `get_depth(category_id: UUID) -> int`: Returns the depth of the given category (1 = root) using the recursive CTE.
- `get_subtree_height(category_id: UUID) -> int`: Returns the maximum depth of the subtree rooted at `category_id` relative to itself. A leaf node returns 0. A node with children returns 1. A node with children and grandchildren returns 2. Executes a recursive CTE descending from `category_id`, computing `relative_depth`; returns `COALESCE(MAX(relative_depth), 0)`. Filters `deleted_at IS NULL`; includes safety depth guard `relative_depth < 10`.

#### Scenario: get_tree returns all active categories flat with depth
- **WHEN** `get_tree()` is called with 3 root categories, one having 2 children
- **THEN** the method returns 5 `Categoria` rows
- **THEN** root categories have `depth = 1`; their direct children have `depth = 2`
- **THEN** no soft-deleted categories appear in the result

#### Scenario: get_tree excludes soft-deleted categories
- **WHEN** one active category has been soft-deleted (non-null `deleted_at`)
- **THEN** `get_tree()` does not include that category in the result
- **THEN** children of the soft-deleted category also do not appear (they have a ghost parent)

#### Scenario: would_create_cycle detects direct cycle
- **WHEN** category A is the parent of category B
- **THEN** `would_create_cycle(A, B)` returns `True` (making B the parent of A creates A→B→A)

#### Scenario: would_create_cycle returns False for valid reparent
- **WHEN** categories A and B are unrelated (no ancestor-descendant relationship)
- **THEN** `would_create_cycle(A, B)` returns `False`

#### Scenario: would_create_cycle terminates on corrupted cyclic data
- **GIVEN** corrupted data with an active cycle in the DB (created via direct DB insert bypassing the service)
- **WHEN** `would_create_cycle` is called
- **THEN** the CTE terminates within 10 recursive steps and returns `True`

#### Scenario: get_subtree_height returns 0 for leaf node
- **WHEN** a category has no children
- **THEN** `get_subtree_height(category_id)` returns `0`

#### Scenario: get_subtree_height returns 2 for node with grandchildren
- **GIVEN** category C at depth 2 with children at depth 3 and grandchildren at depth 4
- **WHEN** `get_subtree_height(C)` is called
- **THEN** it returns `2`

#### Scenario: update_categoria blocks reparenting subtree that would exceed max depth
- **GIVEN** category C at depth 2 with grandchildren at depth 4 (subtree_height=2)
- **WHEN** `PUT /api/v1/categorias/{C_id}` sets `parent_id` to a node at depth 3
- **THEN** the service raises `AppValidationError(code='CATEGORY_MAX_DEPTH_EXCEEDED')` because 3+1+2=6>5

#### Scenario: get_depth returns 1 for root category
- **WHEN** a category has `parent_id IS NULL`
- **THEN** `get_depth(category_id)` returns `1`

#### Scenario: get_depth returns correct depth for nested category
- **WHEN** a category is 3 levels deep (root → child → grandchild)
- **THEN** `get_depth(grandchild_id)` returns `3`

---

### Requirement: CategoriaService with full business rule enforcement
The system SHALL provide `CategoriaService` at `backend/app/services/categoria.py` orchestrating all business rules:

**`get_tree() -> list[CategoriaTreeNode]`**: Calls `uow.categorias.get_tree()`, assembles the in-memory tree (O(n) dict pass), returns list of root `CategoriaTreeNode` objects.

**`get_by_id(category_id) -> CategoriaRead`**: Calls `uow.categorias.get_by_id(category_id)`. Raises `NotFoundError` if `None`.

**`create_categoria(data: CategoriaCreate) -> CategoriaRead`**: Validates `parent_id` exists if provided (raises `NotFoundError`). Validates depth would not exceed 5 (raises `AppValidationError(code="CATEGORY_MAX_DEPTH_EXCEEDED")`). Calls `uow.categorias.create(...)`. Catches `IntegrityError` and re-raises as `ConflictError(code="CATEGORY_NAME_DUPLICATE")`.

**`update_categoria(category_id, data: CategoriaUpdate) -> CategoriaRead`**: Loads entity (raises `NotFoundError` if missing). The router SHALL pass the `CategoriaUpdate` Pydantic model instance directly to `service.update_categoria(category_id, data)`. The router SHALL NOT call `data.model_dump()` before passing to service — passing a dict loses `model_fields_set` information, which the service uses to distinguish 'parent_id not sent' from 'parent_id explicitly set to None'. If `parent_id` in `data.model_fields_set`: (1) checks self-parent (`AppValidationError(code="CATEGORY_SELF_PARENT")`), (2) calls `would_create_cycle` (`AppValidationError(code="CATEGORY_CYCLE_DETECTED")`), (3) MUST call `await uow.categorias.get_depth(new_parent_id)` to retrieve the new parent's depth — the service SHALL NOT call `get_tree()` for depth validation (`get_tree()` loads the entire tree and is O(n); `get_depth` uses an ancestor-traversal CTE and is O(depth)), (4) MUST call `get_subtree_height(category_id)` and validate `parent_depth + 1 + subtree_height ≤ 5` (`AppValidationError(code="CATEGORY_MAX_DEPTH_EXCEEDED")`). Calls `uow.categorias.update(...)`. Catches `IntegrityError` → `ConflictError(code="CATEGORY_NAME_DUPLICATE")`.

**`delete_categoria(category_id) -> None`**: Loads entity (raises `NotFoundError`). Checks `count_active_children > 0` → `ConflictError(code="CATEGORY_HAS_ACTIVE_CHILDREN")`. Checks `count_active_products > 0` → `ConflictError(code="CATEGORY_HAS_ACTIVE_PRODUCTS")`. Calls `uow.categorias.soft_delete(category_id)`.

#### Scenario: create_categoria with valid root category succeeds
- **WHEN** `POST /api/v1/categorias` is called with `{"nombre": "Bebidas"}` (no parent_id)
- **THEN** service creates the category with `parent_id = NULL`
- **THEN** response is `CategoriaRead` with HTTP 201

#### Scenario: create_categoria with non-existent parent_id raises 404
- **WHEN** `POST /api/v1/categorias` is called with `parent_id` set to a UUID that doesn't exist
- **THEN** service raises `NotFoundError`
- **THEN** response is HTTP 404 RFC 7807 error

#### Scenario: create_categoria with duplicate nombre in same level raises 409
- **WHEN** a category named "Bebidas" already exists at root level
- **THEN** `POST /api/v1/categorias` with `{"nombre": "Bebidas"}` (root) raises `ConflictError(code="CATEGORY_NAME_DUPLICATE")`
- **THEN** response is HTTP 409 RFC 7807 error

#### Scenario: create_categoria with same nombre in different parent is allowed
- **WHEN** "Frutas" exists under parent A
- **THEN** `POST /api/v1/categorias` with `{"nombre": "Frutas", "parent_id": B_id}` (under different parent B) succeeds
- **THEN** response is HTTP 201

#### Scenario: create_categoria beyond max depth raises 422
- **WHEN** the proposed parent category is at depth 5 (leaf of maximum depth)
- **THEN** `POST /api/v1/categorias` with that `parent_id` raises `AppValidationError(code="CATEGORY_MAX_DEPTH_EXCEEDED")`
- **THEN** response is HTTP 422 RFC 7807 error

#### Scenario: update_categoria with self-parent raises 422
- **WHEN** `PUT /api/v1/categorias/{id}` sets `parent_id` equal to the category's own `id`
- **THEN** service raises `AppValidationError(code="CATEGORY_SELF_PARENT")`
- **THEN** response is HTTP 422 RFC 7807 error

#### Scenario: update_categoria creating cycle raises 422
- **WHEN** category A is ancestor of category B and `PUT /api/v1/categorias/A` sets `parent_id = B`
- **THEN** `would_create_cycle(A, B)` returns `True`
- **THEN** service raises `AppValidationError(code="CATEGORY_CYCLE_DETECTED")`
- **THEN** response is HTTP 422 RFC 7807 error

#### Scenario: delete_categoria with active children raises 409
- **WHEN** category has at least one active subcategory
- **THEN** `DELETE /api/v1/categorias/{id}` raises `ConflictError(code="CATEGORY_HAS_ACTIVE_CHILDREN")`
- **THEN** response is HTTP 409 RFC 7807 error

#### Scenario: delete_categoria with no children succeeds
- **WHEN** category has zero active subcategories and zero active products
- **THEN** `DELETE /api/v1/categorias/{id}` soft-deletes the category
- **THEN** response is HTTP 204 No Content

#### Scenario: get_tree assembles in-memory hierarchy correctly
- **WHEN** repository returns flat rows [root(depth=1), child1(depth=2,parent=root), child2(depth=2,parent=root)]
- **THEN** service returns `[CategoriaTreeNode(id=root, subcategorias=[child1, child2])]`
- **THEN** root node has exactly 2 subcategorias
- **THEN** child nodes have empty subcategorias lists

---

### Requirement: Categoria REST endpoints (5 endpoints)
The system SHALL expose 5 REST endpoints under `/api/v1/categorias` registered via `categorias_router` in `backend/app/api/v1/categorias.py`. The router SHALL be included in `build_v1_router` with prefix `/categorias` and tag `"categorias"`.

#### Scenario: GET /api/v1/categorias returns tree (public, no auth)
- **WHEN** `GET /api/v1/categorias` is called without any Authorization header
- **THEN** response is HTTP 200 with body `list[CategoriaTreeNode]`
- **THEN** only active categories appear
- **THEN** root categories are at the top level; their children are in `subcategorias`

#### Scenario: GET /api/v1/categorias/{id} returns flat read (public)
- **WHEN** `GET /api/v1/categorias/{id}` is called for an existing active category
- **THEN** response is HTTP 200 with body `CategoriaRead`
- **WHEN** `GET /api/v1/categorias/{id}` is called for a non-existent or soft-deleted ID
- **THEN** response is HTTP 404 RFC 7807

#### Scenario: POST /api/v1/categorias requires ADMIN or STOCK role
- **WHEN** `POST /api/v1/categorias` is called without a JWT token
- **THEN** response is HTTP 401
- **WHEN** `POST /api/v1/categorias` is called with a JWT for a CLIENT role
- **THEN** response is HTTP 403
- **WHEN** `POST /api/v1/categorias` is called with valid ADMIN JWT and valid body
- **THEN** response is HTTP 201 with `CategoriaRead`
- **WHEN** `POST /api/v1/categorias` is called with valid STOCK JWT and valid body
- **THEN** response is HTTP 201 with `CategoriaRead`

#### Scenario: PUT /api/v1/categorias/{id} requires ADMIN or STOCK role
- **WHEN** `PUT /api/v1/categorias/{id}` is called with valid ADMIN JWT and valid body
- **THEN** response is HTTP 200 with updated `CategoriaRead`
- **WHEN** `PUT /api/v1/categorias/{id}` is called with valid STOCK JWT and valid body
- **THEN** response is HTTP 200 with updated `CategoriaRead`
- **WHEN** called with a CLIENT JWT
- **THEN** response is HTTP 403
- **WHEN** called without any JWT
- **THEN** response is HTTP 401

#### Scenario: DELETE /api/v1/categorias/{id} requires ADMIN or STOCK role and returns 204
- **WHEN** `DELETE /api/v1/categorias/{id}` is called with valid ADMIN JWT for a leaf category
- **THEN** response is HTTP 204 No Content
- **WHEN** `DELETE /api/v1/categorias/{id}` is called with valid STOCK JWT for a leaf category
- **THEN** response is HTTP 204 No Content
- **WHEN** called with a CLIENT JWT
- **THEN** response is HTTP 403
- **WHEN** called without any JWT
- **THEN** response is HTTP 401

---

### Requirement: Business rules RN-CA01 through RN-CA09
The system SHALL enforce the following business rules for categories:

- **RN-CA01** — `nombre` SHALL be unique per parent level (per D-02 partial indexes).
- **RN-CA02** — `nombre` SHALL have length 1–100 characters (Pydantic validation).
- **RN-CA03** — A category with active products SHALL NOT be soft-deleted (`code="CATEGORY_HAS_ACTIVE_PRODUCTS"`).
- **RN-CA04** — A category with active subcategories SHALL NOT be soft-deleted (`code="CATEGORY_HAS_ACTIVE_CHILDREN"`).
- **RN-CA05** — A category SHALL NOT reference itself as `parent_id` (`code="CATEGORY_SELF_PARENT"`).
- **RN-CA06** — A category SHALL NOT have `parent_id` pointing to a descendant (`code="CATEGORY_CYCLE_DETECTED"`).
- **RN-CA07** — Tree depth SHALL NOT exceed 5 levels (`code="CATEGORY_MAX_DEPTH_EXCEEDED"`).
- **RN-CA08** — Read endpoints SHALL return only active categories (`deleted_at IS NULL`).
- **RN-CA09** — Soft-deleted category names SHALL be immediately reclaimable (enforced by `WHERE deleted_at IS NULL` on partial unique indexes).

#### Scenario: RN-CA09 — soft-deleted name is reclaimable
- **WHEN** a category named "Lácteos" is soft-deleted
- **THEN** `POST /api/v1/categorias` with `{"nombre": "Lácteos"}` at the same level succeeds
- **THEN** response is HTTP 201 (not 409)

---

### Requirement: RFC 7807 error codes for Categoria
The system SHALL return RFC 7807-compliant error responses for all category business rule violations.

| HTTP Status | `code` | Trigger |
|---|---|---|
| 404 | `CATEGORY_NOT_FOUND` | Category ID does not exist or is soft-deleted |
| 409 | `CATEGORY_NAME_DUPLICATE` | `nombre` already exists at the same parent level |
| 409 | `CATEGORY_HAS_ACTIVE_CHILDREN` | Soft-delete blocked by active subcategories |
| 409 | `CATEGORY_HAS_ACTIVE_PRODUCTS` | Soft-delete blocked by active linked products |
| 422 | `CATEGORY_SELF_PARENT` | `parent_id` equals the category's own `id` |
| 422 | `CATEGORY_CYCLE_DETECTED` | New `parent_id` is a descendant of the category |
| 422 | `CATEGORY_MAX_DEPTH_EXCEEDED` | New depth would exceed 5 levels |

#### Scenario: 404 error matches RFC 7807 shape
- **WHEN** `GET /api/v1/categorias/{id}` returns 404
- **THEN** body contains `{"type": "...", "title": "...", "status": 404, "detail": "...", "code": "CATEGORY_NOT_FOUND"}`

#### Scenario: 409 CATEGORY_NAME_DUPLICATE matches RFC 7807 shape
- **WHEN** a duplicate name is submitted
- **THEN** body contains `{"status": 409, "code": "CATEGORY_NAME_DUPLICATE"}`

#### Scenario: 422 CATEGORY_CYCLE_DETECTED matches RFC 7807 shape
- **WHEN** a cycle is detected during update
- **THEN** body contains `{"status": 422, "code": "CATEGORY_CYCLE_DETECTED"}`

## ADDED Requirements

### Requirement: Categoria soft-delete guard for active products — now active
The `count_active_products(category_id: UUID) -> int` method in `CategoriaRepository` (introduced in Change 09 with a comment `# Guard active post Change 11`) SHALL now be fully effective. The `ProductoCategoria` pivot table is populated by Change 11, so the guard that previously returned 0 for all categories now returns the actual count of active products linked to each category.

No code changes are required in `backend/app/repositories/categoria.py` — the guard is already implemented. This requirement documents that the behavior is now active and testable.

#### Scenario: DELETE /api/v1/categorias/{id} is blocked when active products exist (now active)
- **GIVEN** a category with at least one associated active product (via `producto_categoria`)
- **WHEN** `DELETE /api/v1/categorias/{id}` is called with valid ADMIN or STOCK JWT
- **THEN** `count_active_products(category_id)` returns a value > 0
- **THEN** service raises `ConflictError(code="CATEGORY_HAS_ACTIVE_PRODUCTS")`
- **THEN** response is HTTP 409 RFC 7807 with `code="CATEGORY_HAS_ACTIVE_PRODUCTS"`

#### Scenario: DELETE /api/v1/categorias/{id} succeeds when category has no active products
- **GIVEN** a category with no associated active products (only soft-deleted products, or no products at all)
- **WHEN** `DELETE /api/v1/categorias/{id}` is called with valid ADMIN or STOCK JWT and no active children
- **THEN** `count_active_products(category_id)` returns 0
- **THEN** soft delete proceeds normally
- **THEN** response is HTTP 204 No Content

#### Scenario: Soft-deleted products do not block category deletion
- **GIVEN** a category linked only to soft-deleted products (`producto.deleted_at IS NOT NULL`)
- **WHEN** `DELETE /api/v1/categorias/{id}` is called
- **THEN** `count_active_products` returns 0 (soft-deleted products excluded by `p.deleted_at IS NULL` filter)
- **THEN** soft delete proceeds if no active children exist

---

### Requirement: Producto inverse reference via producto_categoria pivot
When a product is soft-deleted, its `producto_categoria` pivot records remain (D-31 — hard delete on pivots only occurs on explicit category list replacement). The `count_active_products` method in `CategoriaRepository` filters by `producto.deleted_at IS NULL`, so soft-deleted products do not count as "active" for the guard.

#### Scenario: Soft-deleted product does not appear in category active product count
- **GIVEN** a category linked to product P1 (active) and product P2 (soft-deleted)
- **WHEN** `count_active_products(category_id)` is called
- **THEN** the count is 1 (only P1 is counted)
- **THEN** `DELETE /api/v1/categorias/{id}` with no active children returns HTTP 409 (blocked by P1)
