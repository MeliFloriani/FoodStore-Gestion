## ADDED Requirements

### Requirement: Migration 0002_categoria_nombre_per_parent — per-parent uniqueness
The system SHALL have a migration `0002_categoria_nombre_per_parent` that corrects the uniqueness constraint on `categoria.nombre` from global to per-parent scope.

The `upgrade()` function SHALL:
1. Drop the existing global unique constraint on `categoria.nombre`.
2. Create a partial unique index `uq_categoria_nombre_parent` on `(parent_id, nombre)` where `deleted_at IS NULL` — covering all non-root categories.
3. Create a second partial unique index `uq_categoria_nombre_root` on `(nombre)` where `parent_id IS NULL AND deleted_at IS NULL` — covering root categories (PostgreSQL does not treat `NULL == NULL` in standard indexes, so roots require an explicit partial index).
4. Create a partial index `ix_categoria_parent_id` on `(parent_id)` where `deleted_at IS NULL` — optimizing the CTE JOIN `ON c.parent_id = t.id` and `count_active_children` queries. Note: PostgreSQL creates an implicit B-tree index for the FK constraint but it is not filtered; this explicit partial index is required for performance on the hot read path.

The `downgrade()` function SHALL reverse these operations: drop both partial unique indexes and the `ix_categoria_parent_id` index, then re-add the global unique constraint on `categoria.nombre`.

This migration depends on `0001_initial_schema` and is the second revision in the Alembic chain. The `down_revision` field MUST reference the actual revision hash of `0001_initial_schema` obtained via `alembic history` (an alphanumeric hash like `d4e8f2a1b3c9`). DO NOT use the string `'0001_initial_schema'` as `down_revision` — that is the human-readable message, not the revision ID. Alembic will fail with 'Can't locate revision' if a non-hash string is used.

#### Scenario: upgrade replaces global unique with two partial indexes
- **WHEN** `alembic upgrade 0002_categoria_nombre_per_parent` runs on a DB with `0001` applied
- **THEN** no global unique constraint exists on `categoria.nombre`
- **THEN** index `uq_categoria_nombre_parent` exists with condition `WHERE deleted_at IS NULL` on `(parent_id, nombre)`
- **THEN** index `uq_categoria_nombre_root` exists with condition `WHERE parent_id IS NULL AND deleted_at IS NULL` on `(nombre)`
- **THEN** `alembic_version` shows `0002` as the current head

#### Scenario: categories with same name under different parents are insertable after 0002
- **WHEN** migration `0002` is applied
- **THEN** two rows with `nombre = 'Frutas'` but different non-null `parent_id` values can be inserted without constraint violation

#### Scenario: categories with same name at root level still conflict after 0002
- **WHEN** migration `0002` is applied
- **THEN** two rows with `nombre = 'Bebidas'` and `parent_id IS NULL` cannot coexist — constraint violation on `uq_categoria_nombre_root`

#### Scenario: soft-deleted category name is reclaimable after 0002
- **WHEN** a root category `nombre = 'Carnes'` is soft-deleted (non-null `deleted_at`)
- **THEN** a new root category `nombre = 'Carnes'` can be inserted without constraint violation (partial index excludes deleted rows)

#### Scenario: downgrade restores global unique constraint
- **WHEN** `alembic downgrade 0001` runs
- **THEN** both partial indexes are dropped
- **THEN** the global unique constraint on `categoria.nombre` is restored
- **THEN** `alembic_version` shows `0001` as the current head

#### Scenario: ix_categoria_parent_id partial index exists after upgrade
- **WHEN** `alembic upgrade 0002_categoria_nombre_per_parent` runs
- **THEN** index `ix_categoria_parent_id` exists on column `(parent_id)` with condition `WHERE deleted_at IS NULL`
- **THEN** `EXPLAIN ANALYZE` on the CTE JOIN condition shows index scan on `ix_categoria_parent_id`

#### Scenario: 0002 migration tests pass in CI
- **WHEN** `pytest tests/test_migrations.py` runs with test DB accessible
- **THEN** the test verifies upgrade to `0002` applies both partial unique indexes and `ix_categoria_parent_id` correctly
- **THEN** the test verifies downgrade from `0002` removes all three indexes and restores the global constraint
- **THEN** the test verifies the full upgrade+downgrade+upgrade cycle is reproducible
