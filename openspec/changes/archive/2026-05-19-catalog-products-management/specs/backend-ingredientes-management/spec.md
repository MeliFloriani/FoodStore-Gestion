# backend-ingredientes-management — Delta Spec (Change 11)

## ADDED Requirements

### Requirement: Ingrediente M2M inverse reference via producto_ingrediente pivot
Change 11 introduces `ProductoIngrediente` pivot records linking ingredients to products. The `Ingrediente` model already has a `producto_ingredientes: list[ProductoIngrediente]` relationship (declared in `catalog.py`). This requirement documents the behavior when an ingredient is soft-deleted while product associations exist.

#### Scenario: Soft-deleted ingrediente still linked via pivot — product detail filters it out
- **GIVEN** an ingredient I1 associated to product P1 via `producto_ingrediente`
- **WHEN** `DELETE /api/v1/ingredientes/{I1_id}` soft-deletes the ingredient
- **THEN** the `producto_ingrediente` pivot record remains (D-31 — hard delete on pivots only via explicit management)
- **WHEN** `GET /api/v1/productos/{P1_id}/ingredientes` is called
- **THEN** the ingredient I1 does NOT appear in the response (because the `ProductoRepository.get_ingredientes` query filters by `ingrediente.deleted_at IS NULL`)

#### Scenario: Soft-deleted ingrediente prevents add_ingrediente from succeeding
- **GIVEN** an ingredient I1 that has been soft-deleted
- **WHEN** `POST /api/v1/productos/{id}/ingredientes` is called with `{ "ingrediente_id": I1_id, "es_removible": true }`
- **THEN** `ProductoService.add_ingrediente` validates that `I1` exists and is active
- **THEN** `uow.ingredientes.get_by_id(I1_id)` returns `None` (soft-deleted records are excluded by `BaseRepository` default filter)
- **THEN** service raises `NotFoundError(code="INGREDIENT_NOT_FOUND")`
- **THEN** response is HTTP 404 RFC 7807

#### Scenario: Removing ingredient association does not soft-delete the ingredient
- **WHEN** `DELETE /api/v1/productos/{id}/ingredientes/{ing_id}` is called
- **THEN** only the `ProductoIngrediente` pivot record is hard-deleted
- **THEN** the `ingrediente` record is unaffected (`deleted_at` remains NULL)
- **THEN** `GET /api/v1/ingredientes/{ing_id}` still returns the ingredient (HTTP 200)

---

### Requirement: es_removible flag semantics in ProductoIngrediente
The `es_removible` boolean in `ProductoIngrediente` determines whether a customer can exclude this ingredient during ordering (used in Change 15 cart personalization and Change 17 order creation). This flag lives in the pivot table, not in the `Ingrediente` entity.

#### Scenario: es_removible=true enables ingredient exclusion in cart (context for Change 15)
- **GIVEN** product P1 has ingredient I1 with `es_removible=True` and ingredient I2 with `es_removible=False`
- **WHEN** `GET /api/v1/productos/{P1_id}/ingredientes` is called
- **THEN** I1 appears with `"es_removible": true`
- **THEN** I2 appears with `"es_removible": false`
- **THEN** Change 15 (cart) will only allow excluding ingredients where `es_removible=true`

#### Scenario: es_removible is always explicitly set when adding ingredient association
- **WHEN** `POST /api/v1/productos/{id}/ingredientes` is called without `es_removible` in the body
- **THEN** Pydantic raises `ValidationError` (field is required — no default value)
- **THEN** response is HTTP 422

#### Scenario: es_removible can be updated by deleting and re-adding the association
- **GIVEN** ingredient I1 is associated to product P1 with `es_removible=False`
- **WHEN** `DELETE /api/v1/productos/{P1_id}/ingredientes/{I1_id}` is called (removes pivot)
- **THEN** response is HTTP 204
- **WHEN** `POST /api/v1/productos/{P1_id}/ingredientes` is called with `{ "ingrediente_id": I1_id, "es_removible": true }`
- **THEN** response is HTTP 201 with `"es_removible": true`
- **THEN** the pivot now shows `es_removible=True`
