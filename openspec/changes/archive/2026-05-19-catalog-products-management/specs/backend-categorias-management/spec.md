# backend-categorias-management — Delta Spec (Change 11)

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
