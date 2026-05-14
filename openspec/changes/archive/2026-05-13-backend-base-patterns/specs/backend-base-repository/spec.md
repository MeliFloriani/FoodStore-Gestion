# backend-base-repository Specification

## Purpose
Generic typed data-access layer for all SQLModel entities. Introduced in Change 04 (`backend-base-patterns`). All concrete repositories MUST inherit from `BaseRepository[T]`.

## Requirements

### Requirement: Generic CRUD contract
`BaseRepository[T]` SHALL be a Python generic class parametrized with `TypeVar T` bound to `app.models.base.Base`. It SHALL be located at `backend/app/repositories/base.py` and expose the following async methods:

| Method | Signature | Returns |
|---|---|---|
| `get_by_id` | `(self, id: UUID) → T \| None` | Entity or None if not found or soft-deleted |
| `list_all` | `(self, skip: int = 0, limit: int = 100, filters: dict \| None = None, include_deleted: bool = False) → list[T]` | Paginated list |
| `count` | `(self, filters: dict \| None = None, include_deleted: bool = False) → int` | Total matching rows |
| `create` | `(self, obj: T) → T` | Persisted entity (after flush) |
| `update` | `(self, id: UUID, data: dict) → T \| None` | Updated entity or None |
| `soft_delete` | `(self, id: UUID) → bool` | True if deleted, False if not found |
| `hard_delete` | `(self, id: UUID) → bool` | True if deleted, False if not found |

#### Scenario: get_by_id returns entity for valid active record
- **WHEN** `get_by_id(id)` is called with a UUID that exists in the database and has `deleted_at IS NULL`
- **THEN** the method returns the corresponding entity instance of type `T`
- **THEN** the returned entity's `id` matches the requested UUID

#### Scenario: get_by_id returns None for soft-deleted record
- **WHEN** `get_by_id(id)` is called with a UUID that exists but has `deleted_at IS NOT NULL`
- **THEN** the method returns `None` (not the entity, not an exception)

#### Scenario: get_by_id returns None for non-existent record
- **WHEN** `get_by_id(id)` is called with a UUID that does not exist in the database
- **THEN** the method returns `None`

#### Scenario: get_by_id with include_deleted=True returns soft-deleted entity
- **WHEN** `get_by_id(id, include_deleted=True)` is called for a soft-deleted record
- **THEN** the method returns the entity (not None), with `deleted_at` set to a non-null timestamp

#### Scenario: list_all excludes soft-deleted records by default
- **WHEN** `list_all()` is called without arguments
- **THEN** the returned list contains ONLY entities where `deleted_at IS NULL`
- **THEN** any entity with `deleted_at IS NOT NULL` is absent from the result

#### Scenario: list_all with include_deleted=True includes all records
- **WHEN** `list_all(include_deleted=True)` is called
- **THEN** the result includes both active and soft-deleted records

#### Scenario: list_all pagination via skip and limit
- **WHEN** `list_all(skip=5, limit=10)` is called on a table with 20 active records
- **THEN** the method returns exactly 10 records starting from offset 5

#### Scenario: create persists entity and returns it after flush
- **WHEN** `create(obj)` is called with a new entity instance
- **THEN** the method calls `session.add(obj)` and `session.flush()`
- **THEN** the method returns the entity (with any server-side defaults populated by flush)
- **THEN** `session.commit()` is NOT called inside `create`

#### Scenario: update applies dict fields to entity
- **WHEN** `update(id, {"nombre": "Nuevo nombre"})` is called for an existing active entity
- **THEN** the field `nombre` is updated on the entity
- **THEN** `session.flush()` is called
- **THEN** the updated entity is returned

#### Scenario: update returns None for non-existent entity
- **WHEN** `update(id, data)` is called with a UUID that does not exist
- **THEN** the method returns `None` (no exception)

#### Scenario: count returns correct total matching active records
- **WHEN** `count()` is called on a table with 7 active and 3 soft-deleted records
- **THEN** the method returns `7` (soft-deleted excluded by default)

---

### Requirement: Filter contract for `list_all` and `count`
`filters` SHALL be a dict of shape `{column_name: exact_value}`. Only equality comparisons are supported in `BaseRepository`. Operators such as `>=`, `<`, `LIKE`, `IN` SHALL be implemented in concrete repository methods, never via `filters`. The set of PROTECTED COLUMNS — `{'id', 'created_at', 'updated_at', 'deleted_at'}` — SHALL be silently ignored if present in `filters`, preventing bypass of soft-delete semantics or PK tampering. Columns not present on the model SHALL cause `BaseRepository` to raise `ValueError('unknown filter column: <name>')` to prevent silent typos.

#### Scenario: filters equality on a valid column
- **WHEN** `list_all(filters={'email': 'a@b.com'})` is called
- **THEN** the query applies `WHERE email = 'a@b.com'` AND the implicit `deleted_at IS NULL` filter

#### Scenario: deleted_at in filters is silently ignored
- **WHEN** `list_all(filters={'deleted_at': None})` is called
- **THEN** the `deleted_at` key is ignored and the implicit `deleted_at IS NULL` filter still applies (soft-deleted rows remain excluded)

#### Scenario: id in filters is silently ignored
- **WHEN** `list_all(filters={'id': uuid})` is called
- **THEN** the `id` key is ignored (use `get_by_id` instead)

#### Scenario: unknown column in filters raises ValueError
- **WHEN** `filters` contains a column not present on the model
- **THEN** `BaseRepository` raises `ValueError('unknown filter column: <name>')` to prevent silent typos

---

### Requirement: Soft-delete contract
`BaseRepository.soft_delete(id)` SHALL implement the two-step soft-delete pattern: (1) call `Base.soft_delete()` on the in-memory entity to set `deleted_at = now(UTC)`, (2) call `session.flush()` to propagate the change to the DB within the current transaction. It SHALL NOT call `session.commit()`.

#### Scenario: soft_delete sets deleted_at and flushes
- **WHEN** `soft_delete(id)` is called for an existing active entity
- **THEN** the entity's `deleted_at` is set to the current UTC timestamp
- **THEN** `session.flush()` is called (the change is visible within the current transaction)
- **THEN** `session.commit()` is NOT called
- **THEN** the method returns `True`

#### Scenario: soft_delete returns False for non-existent entity
- **WHEN** `soft_delete(id)` is called with a UUID that does not exist
- **THEN** the method returns `False` without raising an exception

#### Scenario: hard_delete removes row from database
- **WHEN** `hard_delete(id)` is called for an existing entity (active or soft-deleted)
- **THEN** the row is deleted from the database via `session.delete(obj)` + `session.flush()`
- **THEN** a subsequent `get_by_id(id, include_deleted=True)` returns `None`
- **THEN** `session.commit()` is NOT called inside `hard_delete`

---

### Requirement: Immutable field protection in `update`
The `update(id, data)` method SHALL silently skip any key in `data` that belongs to PROTECTED COLUMNS — `{'id', 'created_at', 'updated_at', 'deleted_at'}`. This prevents resurrection of soft-deleted entities via `data={'deleted_at': None}`, PK reassignment via `data={'id': ...}`, and timestamp tampering. `updated_at` is refreshed by the SQLAlchemy `onupdate` hook (see P-06 / `models/base.py`), never by user data.

#### Scenario: deleted_at in update data does not resurrect soft-deleted entity
- **WHEN** `update(id, {'deleted_at': None})` is called on a soft-deleted entity
- **THEN** `deleted_at` is NOT modified and the entity remains soft-deleted

#### Scenario: id in update data is silently ignored
- **WHEN** `update(id, {'id': new_uuid, 'nombre': 'X'})` is called
- **THEN** `id` is ignored, only `nombre` is updated

#### Scenario: created_at in update data is silently ignored
- **WHEN** `update(id, {'created_at': earlier_date})` is called
- **THEN** `created_at` is ignored

#### Scenario: empty update data flushes without setting fields
- **WHEN** `update(id, {})` is called
- **THEN** the row is fetched but no fields are set; `updated_at` is still refreshed via the `onupdate` hook

---

### Requirement: Session injection invariant
`BaseRepository` SHALL receive an `AsyncSession` via its constructor. It SHALL NOT create sessions internally, SHALL NOT call `Depends(get_session)`, and SHALL NOT import from `app.db.session` directly.

#### Scenario: Repository constructed with injected session
- **WHEN** `UsuarioRepository(session=async_session)` is instantiated
- **THEN** `repository.session` is the same object as `async_session` (identity, not copy)
- **THEN** no new session is created during instantiation

#### Scenario: Repository does not import get_session
- **WHEN** `backend/app/repositories/base.py` is statically analyzed
- **THEN** there is no import of `get_session` or `AsyncSession` factory from `app.db.session`
- **THEN** `AsyncSession` is imported only from `sqlalchemy.ext.asyncio` as a type annotation

---

### Requirement: Flush-only semantics (no commit inside repositories)
All write methods in `BaseRepository` (`create`, `update`, `soft_delete`, `hard_delete`) SHALL use `session.flush()` to stage changes and SHALL NOT call `session.commit()` at any point. Commit authority belongs exclusively to `UnitOfWork`.

#### Scenario: No session.commit() in BaseRepository source
- **WHEN** `backend/app/repositories/base.py` is scanned for `session.commit`
- **THEN** zero matches are found
- **THEN** the file contains one or more calls to `session.flush()` in write methods

---

### Requirement: Static typing — Pyright strict compliance
`BaseRepository[T]` SHALL pass Pyright strict mode with zero errors. All public method signatures SHALL be fully annotated. No `Any` types in method signatures or return types.

#### Scenario: Generic parameter flows through method signatures
- **WHEN** `UsuarioRepository(BaseRepository[Usuario])` is analyzed by Pyright
- **THEN** `repository.get_by_id(id)` has inferred return type `Usuario | None`
- **THEN** `repository.list_all()` has inferred return type `list[Usuario]`
- **THEN** `repository.create(obj)` accepts `Usuario` and rejects `Producto` at type-check time
