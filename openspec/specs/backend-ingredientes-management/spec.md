# backend-ingredientes-management Specification

## Purpose
Backend ingredient management capability: Pydantic schemas, SQLModel, repository, service, and REST endpoints for the `ingrediente` domain. Introduced in Change 10 (catalog-ingredients-management).

## ADDED Requirements

### Requirement: Pydantic schemas for Ingrediente
The system SHALL provide Pydantic v2 schemas in `backend/app/schemas/ingrediente.py` for all ingredient API operations: `IngredienteBase`, `IngredienteCreate`, `IngredienteUpdate`, and `IngredienteRead`.

`IngredienteBase` SHALL enforce:
- `nombre: str` — `Field(min_length=1, max_length=100)` with a `@field_validator` that strips whitespace before validation, ensuring the final value is not empty after stripping.
- `es_alergeno: bool = False`

`IngredienteCreate(IngredienteBase)` SHALL inherit `IngredienteBase` with no additional fields.

`IngredienteUpdate` SHALL be a flat `BaseModel` (no inheritance) with all fields optional:
- `nombre: str | None = None`
- `es_alergeno: bool | None = None`
The `model_fields_set` mechanism SHALL be used by the service to distinguish "field not sent" (do not touch) from "field sent as None/False/True" (apply change). The router MUST pass the Pydantic model instance directly to the service — NOT a dict from `model_dump()`.

`IngredienteRead` SHALL include:
- `id: UUID` — inherits `id: uuid.UUID` from `Base` (UUID PK, NOT `int` or `BIGSERIAL`)
- All `IngredienteBase` fields (`nombre`, `es_alergeno`)
- `created_at: datetime` — matches `Base` class field name (NOT `creado_en`)
- `updated_at: datetime` — matches `Base` class field name (NOT `actualizado_en`)
- `model_config = ConfigDict(from_attributes=True)`

`IngredienteRead` SHALL NOT expose `deleted_at` — soft-deleted records are never returned to API consumers.

#### Scenario: IngredienteCreate validates nombre length
- **WHEN** an `IngredienteCreate` payload has `nombre` exceeding 100 characters
- **THEN** Pydantic raises `ValidationError` with a field error on `nombre`

#### Scenario: IngredienteCreate strips whitespace from nombre
- **WHEN** an `IngredienteCreate` payload has `nombre` equal to `"  Sal  "` (with leading/trailing spaces)
- **THEN** the validated value for `nombre` is `"Sal"` (stripped)

#### Scenario: IngredienteCreate rejects empty nombre after strip
- **WHEN** an `IngredienteCreate` payload has `nombre` equal to `"   "` (whitespace only)
- **THEN** Pydantic raises `ValidationError` because stripped length is 0 (below min_length=1)

#### Scenario: IngredienteUpdate with absent es_alergeno does not change it
- **WHEN** `PUT /api/v1/ingredientes/{id}` is called with body `{"nombre": "Sal marina"}`
- **THEN** the service reads `"es_alergeno" not in data.model_fields_set` as `True`
- **THEN** the ingredient's `es_alergeno` is unchanged

#### Scenario: IngredienteUpdate with explicit es_alergeno updates it
- **WHEN** `PUT /api/v1/ingredientes/{id}` is called with body `{"es_alergeno": true}`
- **THEN** the service reads `"es_alergeno" in data.model_fields_set` as `True` with value `True`
- **THEN** the ingredient's `es_alergeno` is updated to `true`

---

### Requirement: Ingrediente SQLModel
The system SHALL use the `Ingrediente` SQLModel that ALREADY EXISTS in `backend/app/models/catalog.py` (D-17 convention: all catalog models in one file). There is NO `app/models/ingrediente.py` file — do NOT create one.

Change 10 SHALL modify `catalog.py` only: change `Ingrediente.nombre` field from `unique=True` to `unique=False`. Uniqueness is enforced by the migration partial index only; `unique=False` in the model prevents Alembic autogenerate drift.

The existing model has:
- `id: uuid.UUID` — inherited from `Base` (`Field(default_factory=uuid.uuid4, primary_key=True)`) — UUID PK, NOT `int` or `BIGSERIAL`
- `nombre: str = Field(max_length=100, nullable=False, unique=False)` — after Change 10 modification
- `es_alergeno: bool = Field(default=False, nullable=False)`
- `created_at: datetime` — inherited from `Base` (NOT `creado_en`)
- `updated_at: datetime` — inherited from `Base` (NOT `actualizado_en`)
- `deleted_at: datetime | None = Field(default=None, nullable=True)` — soft delete sentinel

The `__tablename__` is already `"ingrediente"` (SINGULAR — consistent with `categoria`, `producto`, `usuario`). Do NOT change the table name.

#### Scenario: Ingrediente model maps to ingrediente table (singular)
- **WHEN** `SQLModel.metadata` is inspected after importing `app.models.catalog`
- **THEN** a table named `ingrediente` (singular) exists in the metadata
- **THEN** the table has columns `id` (UUID), `nombre`, `es_alergeno`, `created_at`, `updated_at`, `deleted_at`

#### Scenario: Ingrediente unique=False prevents autogenerate drift
- **WHEN** `alembic check` is run after applying migration `0004`
- **THEN** Alembic does not detect a pending `UNIQUE` constraint on `ingrediente.nombre`
- **THEN** no spurious migration is generated

---

### Requirement: IngredienteRepository with duplicate-detection
The system SHALL provide `IngredienteRepository(BaseRepository[Ingrediente])` at `backend/app/repositories/ingrediente.py` with these methods beyond `BaseRepository`:

- `get_by_nombre_active(nombre: str) -> Ingrediente | None`: Returns the active ingredient with the given `nombre` (case-sensitive), or `None` if not found. Query: `SELECT * FROM ingrediente WHERE nombre = :nombre AND deleted_at IS NULL LIMIT 1`.
- `list_active(es_alergeno: bool | None = None) -> list[Ingrediente]`: Returns all active ingredients. If `es_alergeno` is not `None`, filters by that value. Always ordered by `nombre ASC`.

The `BaseRepository` methods `get_by_id`, `create`, `update`, `soft_delete` SHALL be inherited without override. `BaseRepository.update()` signature is `update(id: uuid.UUID, data: dict[str, Any]) -> T | None` — takes `(id, dict)`, NOT `(entity)`.

#### Scenario: list_active returns all active ingredients ordered by nombre
- **WHEN** 3 active ingredients exist: "Sal", "Azúcar", "Harina"
- **THEN** `list_active()` returns them in order: ["Azúcar", "Harina", "Sal"]
- **THEN** no soft-deleted ingredient appears in the result

#### Scenario: list_active filters by es_alergeno=True
- **WHEN** 4 active ingredients exist: "Sal" (no alergeno), "Gluten" (alergeno), "Maní" (alergeno), "Azúcar" (no alergeno)
- **THEN** `list_active(es_alergeno=True)` returns only ["Gluten", "Maní"]

#### Scenario: list_active filters by es_alergeno=False
- **WHEN** same 4 active ingredients
- **THEN** `list_active(es_alergeno=False)` returns only ["Azúcar", "Sal"]

#### Scenario: get_by_nombre_active returns None for soft-deleted ingredient
- **WHEN** ingredient "Lactosa" has `deleted_at IS NOT NULL`
- **THEN** `get_by_nombre_active("Lactosa")` returns `None`

#### Scenario: get_by_nombre_active returns ingredient when active
- **WHEN** ingredient "Sal" has `deleted_at IS NULL`
- **THEN** `get_by_nombre_active("Sal")` returns the Ingrediente instance

---

### Requirement: IngredienteService with full business rule enforcement
The system SHALL provide `IngredienteService` at `backend/app/services/ingrediente.py` orchestrating all business rules.

The service SHALL import: `from app.core.exceptions import NotFoundError, ConflictError`

Service methods SHALL be `@staticmethod`, receive `uow: UnitOfWork` parameter — identical pattern to `CategoriaService`.

**`list_ingredientes(es_alergeno: bool | None, uow: UnitOfWork) -> list[IngredienteRead]`**: Calls `uow.ingredientes.list_active(es_alergeno)`. Returns `list[IngredienteRead]` mapped from ORM objects.

**`get_ingrediente(ingrediente_id: UUID, uow: UnitOfWork) -> IngredienteRead`**: Calls `uow.ingredientes.get_by_id(ingrediente_id)`. Raises `NotFoundError("Ingrediente not found", code="INGREDIENT_NOT_FOUND")` if `None` or soft-deleted.

**`create_ingrediente(data: IngredienteCreate, uow: UnitOfWork) -> IngredienteRead`**: Constructs an `Ingrediente` ORM entity from the schema fields, then calls `uow.ingredientes.create(ingrediente_obj)` — identical pattern to `CategoriaService.create_categoria`. `BaseRepository.create()` calls `session.flush()` internally; the `IntegrityError` (from the partial unique index on `nombre`) is raised during that flush and must be caught here:
```python
try:
    entity = await uow.ingredientes.create(
        Ingrediente(nombre=data.nombre, es_alergeno=data.es_alergeno)
    )
except IntegrityError:
    raise ConflictError("Nombre already exists", code="INGREDIENT_NAME_DUPLICATE")
return IngredienteRead.model_validate(entity)
```
**Critical**: `data` MUST NOT be passed directly to `create()` — `BaseRepository.create(obj: T)` expects an `Ingrediente` ORM instance, not an `IngredienteCreate` Pydantic schema.

**`update_ingrediente(ingrediente_id: UUID, data: IngredienteUpdate, uow: UnitOfWork) -> IngredienteRead`**: Loads entity via `get_by_id` (raises `NotFoundError` if not found OR soft-deleted). Builds `update_data: dict` from `data.model_fields_set`, then calls `uow.ingredientes.update(ingrediente_id, update_data)` — identical pattern to `CategoriaService.update_categoria`:
```python
update_data: dict = {}
if "nombre" in data.model_fields_set and data.nombre is not None:
    update_data["nombre"] = data.nombre
if "es_alergeno" in data.model_fields_set and data.es_alergeno is not None:
    update_data["es_alergeno"] = data.es_alergeno
updated = await uow.ingredientes.update(ingrediente_id, update_data)
```
Catches `IntegrityError` → `ConflictError(code="INGREDIENT_NAME_DUPLICATE")`.

**`delete_ingrediente(ingrediente_id: UUID, uow: UnitOfWork) -> None`**: FIRST calls `uow.ingredientes.get_by_id(ingrediente_id)` to verify existence (raises `NotFoundError` if not found OR already soft-deleted). THEN calls `uow.ingredientes.soft_delete(ingrediente_id)`. The prior `get_by_id` check is mandatory — without it, double-deletes would silently succeed instead of returning 404 (the `BaseRepository.soft_delete` uses `include_deleted=True` internally).

The service SHALL be stateless — it receives `uow` as a FastAPI dependency injection parameter.

#### Scenario: create_ingrediente with valid data succeeds
- **WHEN** `POST /api/v1/ingredientes` is called with `{"nombre": "Sal", "es_alergeno": false}`
- **THEN** service creates the ingredient
- **THEN** response is `IngredienteRead` with HTTP 201

#### Scenario: create_ingrediente with duplicate nombre raises 409
- **WHEN** an active ingredient named "Sal" already exists
- **THEN** `POST /api/v1/ingredientes` with `{"nombre": "Sal"}` raises HTTP 409 with `code="INGREDIENT_NAME_DUPLICATE"`

#### Scenario: create_ingrediente with same nombre as soft-deleted succeeds
- **WHEN** an ingredient named "Sal" has been soft-deleted (`deleted_at IS NOT NULL`)
- **THEN** `POST /api/v1/ingredientes` with `{"nombre": "Sal"}` succeeds (partial index excludes deleted rows)
- **THEN** response is HTTP 201

#### Scenario: get_ingrediente with non-existent UUID raises 404
- **WHEN** `GET /api/v1/ingredientes/{uuid}` is called for a UUID that doesn't exist
- **THEN** service raises HTTP 404 with `code="INGREDIENT_NOT_FOUND"`

#### Scenario: get_ingrediente with soft-deleted UUID raises 404
- **WHEN** ingredient with given UUID has `deleted_at IS NOT NULL`
- **THEN** `GET /api/v1/ingredientes/{uuid}` raises HTTP 404 with `code="INGREDIENT_NOT_FOUND"`

#### Scenario: update_ingrediente with nombre only preserves es_alergeno
- **WHEN** ingredient has `nombre="Sal", es_alergeno=true`
- **WHEN** `PUT /api/v1/ingredientes/{id}` is called with `{"nombre": "Sal marina"}`
- **THEN** the updated ingredient has `nombre="Sal marina"` and `es_alergeno=true` (unchanged)

#### Scenario: update_ingrediente on soft-deleted raises 404
- **WHEN** ingredient has `deleted_at IS NOT NULL`
- **THEN** `PUT /api/v1/ingredientes/{id}` raises HTTP 404 with `code="INGREDIENT_NOT_FOUND"`

#### Scenario: update_ingrediente with duplicate nombre raises 409
- **WHEN** active ingredient "Azúcar" exists
- **WHEN** `PUT /api/v1/ingredientes/{other_id}` sets `nombre="Azúcar"`
- **THEN** service catches IntegrityError and raises HTTP 409 with `code="INGREDIENT_NAME_DUPLICATE"`

#### Scenario: delete_ingrediente soft-deletes the record
- **WHEN** `DELETE /api/v1/ingredientes/{id}` is called for an active ingredient
- **THEN** the ingredient's `deleted_at` is set to a non-null timestamp
- **THEN** response is HTTP 204 No Content

#### Scenario: delete_ingrediente on already-deleted raises 404
- **WHEN** ingredient has `deleted_at IS NOT NULL`
- **THEN** `DELETE /api/v1/ingredientes/{id}` raises HTTP 404 with `code="INGREDIENT_NOT_FOUND"`

---

### Requirement: Ingrediente REST endpoints (5 endpoints)
The system SHALL expose 5 REST endpoints under `/api/v1/ingredientes` registered via `ingredientes_router` in `backend/app/api/v1/ingredientes.py`. The router SHALL be included in `build_v1_router` with prefix `/ingredientes` and tag `"ingredientes"`.

All endpoints SHALL require `require_role("ADMIN", "STOCK")` — there are no public ingredient endpoints in Change 10.

All path parameters `{id}` SHALL be typed as `UUID` (FastAPI validates and converts automatically).

| Method | Path | Auth | Request Body | Response |
|--------|------|------|--------------|----------|
| `GET` | `/api/v1/ingredientes` | ADMIN + STOCK | `?es_alergeno=bool` (optional) | `list[IngredienteRead]` 200 |
| `GET` | `/api/v1/ingredientes/{id}` | ADMIN + STOCK | — | `IngredienteRead` 200 |
| `POST` | `/api/v1/ingredientes` | ADMIN + STOCK | `IngredienteCreate` | `IngredienteRead` 201 |
| `PUT` | `/api/v1/ingredientes/{id}` | ADMIN + STOCK | `IngredienteUpdate` | `IngredienteRead` 200 |
| `DELETE` | `/api/v1/ingredientes/{id}` | ADMIN + STOCK | — | 204 No Content |

All endpoints SHALL declare `response_model` explicitly per project convention.

#### Scenario: GET /api/v1/ingredientes requires auth
- **WHEN** `GET /api/v1/ingredientes` is called without any Authorization header
- **THEN** response is HTTP 401

#### Scenario: GET /api/v1/ingredientes with CLIENT role returns 403
- **WHEN** `GET /api/v1/ingredientes` is called with a valid CLIENT JWT
- **THEN** response is HTTP 403

#### Scenario: GET /api/v1/ingredientes returns list for ADMIN
- **WHEN** `GET /api/v1/ingredientes` is called with valid ADMIN JWT
- **THEN** response is HTTP 200 with `list[IngredienteRead]`
- **THEN** only active ingredients appear

#### Scenario: GET /api/v1/ingredientes returns list for STOCK
- **WHEN** `GET /api/v1/ingredientes` is called with valid STOCK JWT
- **THEN** response is HTTP 200 with `list[IngredienteRead]`

#### Scenario: GET /api/v1/ingredientes filters by es_alergeno
- **WHEN** `GET /api/v1/ingredientes?es_alergeno=true` is called with valid ADMIN JWT
- **THEN** response contains only ingredients with `es_alergeno=true`

#### Scenario: GET /api/v1/ingredientes/{id} returns 404 for non-existent
- **WHEN** `GET /api/v1/ingredientes/{uuid}` is called with a non-existent UUID
- **THEN** response is HTTP 404 RFC 7807 with `code="INGREDIENT_NOT_FOUND"`

#### Scenario: POST /api/v1/ingredientes requires ADMIN or STOCK role
- **WHEN** `POST /api/v1/ingredientes` is called without a JWT token
- **THEN** response is HTTP 401
- **WHEN** `POST /api/v1/ingredientes` is called with a CLIENT JWT
- **THEN** response is HTTP 403
- **WHEN** `POST /api/v1/ingredientes` is called with valid ADMIN JWT and valid body
- **THEN** response is HTTP 201 with `IngredienteRead`
- **WHEN** `POST /api/v1/ingredientes` is called with valid STOCK JWT and valid body
- **THEN** response is HTTP 201 with `IngredienteRead`

#### Scenario: POST /api/v1/ingredientes with duplicate nombre returns 409
- **WHEN** ingredient "Sal" already exists
- **WHEN** `POST /api/v1/ingredientes` is called with `{"nombre": "Sal"}`
- **THEN** response is HTTP 409 with `code="INGREDIENT_NAME_DUPLICATE"`

#### Scenario: PUT /api/v1/ingredientes/{id} requires ADMIN or STOCK role
- **WHEN** `PUT /api/v1/ingredientes/{id}` is called with valid ADMIN JWT
- **THEN** response is HTTP 200 with updated `IngredienteRead`
- **WHEN** called with valid STOCK JWT
- **THEN** response is HTTP 200 with updated `IngredienteRead`
- **WHEN** called with CLIENT JWT
- **THEN** response is HTTP 403
- **WHEN** called without JWT
- **THEN** response is HTTP 401

#### Scenario: DELETE /api/v1/ingredientes/{id} requires ADMIN or STOCK and returns 204
- **WHEN** `DELETE /api/v1/ingredientes/{id}` is called with valid ADMIN JWT for an active ingredient
- **THEN** response is HTTP 204 No Content
- **WHEN** called with valid STOCK JWT
- **THEN** response is HTTP 204 No Content
- **WHEN** called with CLIENT JWT
- **THEN** response is HTTP 403
- **WHEN** called without JWT
- **THEN** response is HTTP 401

---

### Requirement: Business rules RN-ING-01 through RN-ING-06
The system SHALL enforce the following business rules for ingredients:

- **RN-ING-01** — `nombre` SHALL be unique among active ingredients (partial unique index `WHERE deleted_at IS NULL` on `ingrediente` table, replacing the global `uq_ingrediente_nombre` constraint from migration 0001).
- **RN-ING-02** — `nombre` SHALL have length 1–100 characters after whitespace stripping (Pydantic validation + DB CHECK constraint).
- **RN-ING-03** — `es_alergeno` is a required boolean field; defaults to `false`.
- **RN-ING-04** — Soft-deleted ingredient names SHALL be immediately reclaimable (`ix_ingrediente_nombre_activo` partial index excludes deleted rows).
- **RN-ING-05** — All read operations (`GET /ingredientes`, `GET /ingredientes/{id}`) SHALL return only active records (`deleted_at IS NULL`).
- **RN-ING-06** — `PUT` and `DELETE` on a soft-deleted ingredient SHALL return 404 (not a recoverable update or double-delete).

#### Scenario: RN-ING-04 — soft-deleted nombre is reclaimable
- **WHEN** ingredient "Gluten" is soft-deleted
- **THEN** `POST /api/v1/ingredientes` with `{"nombre": "Gluten"}` succeeds
- **THEN** response is HTTP 201 (not 409)

#### Scenario: RN-ING-02 — DB CHECK constraint rejects whitespace-only nombre
- **WHEN** a raw INSERT into `ingrediente` with `nombre = '   '` is attempted
- **THEN** the `CHECK (length(trim(nombre)) > 0)` constraint prevents the insert
- **THEN** an IntegrityError is raised

---

### Requirement: RFC 7807 error codes for Ingrediente
The system SHALL return RFC 7807-compliant error responses for all ingredient business rule violations.

| HTTP Status | `code` | Trigger |
|---|---|---|
| 404 | `INGREDIENT_NOT_FOUND` | Ingredient UUID does not exist or is soft-deleted |
| 409 | `INGREDIENT_NAME_DUPLICATE` | `nombre` already exists among active ingredients |
| 422 | (Pydantic validation) | `nombre` too long, too short, or only whitespace |

#### Scenario: 404 error matches RFC 7807 shape
- **WHEN** `GET /api/v1/ingredientes/{id}` returns 404
- **THEN** body contains `{"type": "...", "title": "...", "status": 404, "detail": "...", "code": "INGREDIENT_NOT_FOUND"}`

#### Scenario: 409 INGREDIENT_NAME_DUPLICATE matches RFC 7807 shape
- **WHEN** a duplicate nombre is submitted
- **THEN** body contains `{"status": 409, "code": "INGREDIENT_NAME_DUPLICATE"}`

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
## Requirements
### Requirement: ADMIN RBAC ratification for ingredientes endpoints — cross-reference
The `backend-ingredientes-management` spec SHALL ratify the ADMIN access matrix for all ingredient endpoints as defined in `backend-admin-aggregated-permissions`. All ingredient endpoints (including reads) MUST require ADMIN or STOCK role per the D-01 decision in Change 09 (ingredients are an internal catalog resource).

The following MUST hold:
- `GET /api/v1/ingredientes/` SHALL accept `require_role("ADMIN", "STOCK")`. Both roles can list ingredients.
- `GET /api/v1/ingredientes/{id}` SHALL accept `require_role("ADMIN", "STOCK")`. Both roles can retrieve a single ingredient.
- `POST /api/v1/ingredientes/` SHALL accept `require_role("ADMIN", "STOCK")`. Both roles can create ingredients.
- `PUT /api/v1/ingredientes/{id}` SHALL accept `require_role("ADMIN", "STOCK")`. Both roles can update ingredients.
- `DELETE /api/v1/ingredientes/{id}` SHALL accept `require_role("ADMIN", "STOCK")`. Both roles can soft-delete ingredients.

See `backend-admin-aggregated-permissions` for the canonical RBAC matrix.

#### Scenario: ADMIN RBAC smoke test — all ingredient endpoints return non-403 for ADMIN
- **WHEN** `GET /api/v1/ingredientes/`, `GET /api/v1/ingredientes/{id}`, `POST /api/v1/ingredientes/`, `PUT /api/v1/ingredientes/{id}`, `DELETE /api/v1/ingredientes/{id}` are each called with a valid ADMIN JWT
- **THEN** none of these endpoints return HTTP 403 (authorization does not block ADMIN)

#### Scenario: ADMIN can create an ingredient (ratification)
- **WHEN** `POST /api/v1/ingredientes/` is called with a valid ADMIN JWT and valid body
- **THEN** response is HTTP 201 with `IngredienteRead`

