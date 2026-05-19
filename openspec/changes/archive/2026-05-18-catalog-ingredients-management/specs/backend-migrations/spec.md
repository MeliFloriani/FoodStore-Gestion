## ADDED Requirements

### Requirement: Migration 0004_ingredientes_table — ALTER existing ingrediente table
The system SHALL have a migration `0004_ingredientes_table` that ALTERs the existing `ingrediente` table (singular — created by migration 0001). This is NOT a CREATE TABLE migration.

**Migration chain**: `6ebe5e787bdd` (0001) → `a1b2c3d4e5f6` (0002) → `c9d8e7f6a5b4` (0003). The `down_revision` for 0004 SHALL be `'c9d8e7f6a5b4'`.

**Background**: Migration 0001 created the `ingrediente` table with a global `UNIQUE CONSTRAINT uq_ingrediente_nombre ON ingrediente(nombre)`. This global constraint prevents name reuse after soft delete (RN-ING-04 violation). Migration 0004 replaces it with a partial unique index that excludes soft-deleted rows.

The `upgrade()` function SHALL:
1. Drop the global unique constraint created by migration 0001:
   ```python
   op.drop_constraint("uq_ingrediente_nombre", "ingrediente", type_="unique")
   ```
   **CRITICAL**: This DROP MUST come first. A partial index does NOT automatically replace/supersede an existing UNIQUE constraint. If the DROP is omitted, both constraints would coexist: the global constraint would still block all name reuse (even after soft delete), making the partial index completely ineffective. The two would produce different (unintended) uniqueness behavior.
2. Create partial unique index:
   ```python
   op.execute("CREATE UNIQUE INDEX ix_ingrediente_nombre_activo ON ingrediente (nombre) WHERE deleted_at IS NULL")
   ```
3. Create partial allergen index:
   ```python
   op.execute("CREATE INDEX ix_ingrediente_es_alergeno ON ingrediente (es_alergeno) WHERE deleted_at IS NULL")
   ```

The `downgrade()` function SHALL reverse in order:
1. `op.execute("DROP INDEX IF EXISTS ix_ingrediente_es_alergeno")`
2. `op.execute("DROP INDEX IF EXISTS ix_ingrediente_nombre_activo")`
3. `op.create_unique_constraint("uq_ingrediente_nombre", "ingrediente", ["nombre"])` — restore original global constraint

This migration depends on `0003_categoria_nombre_per_parent` and is the fourth revision in the Alembic chain. The `down_revision` field MUST be `'c9d8e7f6a5b4'` (actual revision hash of `0003_categoria_nombre_per_parent`). DO NOT use the string `'0003_categoria_nombre_per_parent'` as `down_revision` — that is the human-readable message, not the revision ID. Alembic will fail with 'Can't locate revision' if a non-hash string is used.

The migration SHALL NOT create a new table. The migration SHALL NOT modify column definitions on `ingrediente` — it only changes indexes and constraints.

After applying migration 0004, run `alembic check` to confirm no spurious unique constraint remains on `ingrediente.nombre`. This validates that the DROP was successful and no drift exists between model and DB.

#### Scenario: upgrade drops uq_ingrediente_nombre constraint
- **WHEN** `alembic upgrade 0004_ingredientes_table` runs on a DB with `0003` applied
- **THEN** constraint `uq_ingrediente_nombre` no longer exists on table `ingrediente`
- **THEN** `alembic check` reports no pending migration (no spurious constraint detected)

#### Scenario: upgrade creates ix_ingrediente_nombre_activo partial unique index
- **WHEN** migration `0004` is applied
- **THEN** index `ix_ingrediente_nombre_activo` exists on `ingrediente (nombre)` with condition `WHERE deleted_at IS NULL`
- **THEN** two active ingredients with the same `nombre` cannot coexist — raises IntegrityError
- **THEN** a soft-deleted ingredient's `nombre` does not block a new active ingredient with the same name
- **THEN** the global `uq_ingrediente_nombre` constraint is GONE (not just supplemented)

#### Scenario: upgrade creates ix_ingrediente_es_alergeno partial index
- **WHEN** migration `0004` is applied
- **THEN** index `ix_ingrediente_es_alergeno` exists on `ingrediente (es_alergeno)` with condition `WHERE deleted_at IS NULL`

#### Scenario: soft-deleted nombre is reclaimable after 0004
- **WHEN** migration `0004` is applied and ingredient `nombre = 'Gluten'` is soft-deleted (`deleted_at IS NOT NULL`)
- **THEN** a new row with `nombre = 'Gluten'` and `deleted_at IS NULL` can be inserted without constraint violation

#### Scenario: existing ingrediente table columns are unchanged
- **WHEN** migration `0004` is applied
- **THEN** table `ingrediente` still has all original columns: `id` (UUID PK), `nombre`, `es_alergeno`, `created_at`, `updated_at`, `deleted_at`
- **THEN** no columns are added or removed by migration 0004
- **THEN** `alembic_version` shows `0004` as the current head

#### Scenario: downgrade restores uq_ingrediente_nombre and drops indexes
- **WHEN** `alembic downgrade -1` (from `0004` to `0003`) runs
- **THEN** both indexes `ix_ingrediente_nombre_activo` and `ix_ingrediente_es_alergeno` are dropped
- **THEN** global constraint `uq_ingrediente_nombre` is restored on `ingrediente(nombre)`
- **THEN** `alembic_version` shows `0003` as the current head

#### Scenario: upgrade + downgrade + upgrade round-trip is reproducible
- **WHEN** `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` is executed
- **THEN** all three steps complete without errors
- **THEN** after the final upgrade, both indexes exist and `uq_ingrediente_nombre` is absent
- **THEN** other existing tables (e.g., `categoria`, `usuario`) are unaffected

#### Scenario: 0004 migration tests pass in CI
- **WHEN** `pytest tests/test_migrations.py -k "0004"` runs with test DB accessible
- **THEN** the test verifies upgrade drops global constraint and creates both indexes
- **THEN** the test verifies `alembic check` reports no spurious constraint after upgrade
- **THEN** the test verifies downgrade removes indexes and restores global constraint
- **THEN** the test verifies round-trip reproducibility
- **THEN** the test verifies nombre reclaimability (soft-delete + re-insert)
