# backend-migrations — Delta Spec (Change 11)

## ADDED Requirements

### Requirement: Migration 0005_add_producto_indexes — performance indexes on existing producto table
The system SHALL have a migration `0005_add_producto_indexes` that adds performance indexes to the existing `producto` table (singular — created by migration 0001). This is NOT a CREATE TABLE migration. This migration does NOT add new columns.

**Migration chain**: `6ebe5e787bdd` (0001) → `a1b2c3d4e5f6` (0002) → `c9d8e7f6a5b4` (0003) → `8212a24ee1b0` (0004). The `down_revision` for 0005 SHALL be `'8212a24ee1b0'` (actual revision hash of `0004_ingredientes_table` — verified in the repository).

**Background**: Migration 0001 created the `producto` table with `CHECK` constraints on `precio_base` and `stock_cantidad`, but without filtered indexes for the catalog read paths. Migration 0005 adds two partial indexes that optimize the public catalog listing and search queries introduced in Change 11 (and heavily used in Change 12).

The `upgrade()` function SHALL:
1. Create the availability filter index:
   ```python
   op.execute(
       "CREATE INDEX ix_producto_disponible "
       "ON producto (disponible) WHERE deleted_at IS NULL"
   )
   ```
2. Create the name search index with `text_pattern_ops` for ILIKE prefix optimization:
   ```python
   op.execute(
       "CREATE INDEX ix_producto_nombre_search "
       "ON producto (nombre text_pattern_ops) WHERE deleted_at IS NULL"
   )
   ```

The `downgrade()` function SHALL:
1. `op.execute("DROP INDEX IF EXISTS ix_producto_nombre_search")`
2. `op.execute("DROP INDEX IF EXISTS ix_producto_disponible")`

The migration SHALL NOT create new tables. The migration SHALL NOT modify column definitions on `producto`. The migration SHALL NOT touch `producto_categoria` or `producto_ingrediente` tables.

After applying migration 0005, run `alembic check` to confirm no spurious changes are detected between the models and the database.

#### Scenario: upgrade creates ix_producto_disponible partial index
- **WHEN** `alembic upgrade 0005_add_producto_indexes` runs on a DB with `0004` applied
- **THEN** index `ix_producto_disponible` exists on `producto (disponible)` with condition `WHERE deleted_at IS NULL`
- **THEN** `EXPLAIN ANALYZE` on `SELECT * FROM producto WHERE disponible = true AND deleted_at IS NULL` shows index scan on `ix_producto_disponible`

#### Scenario: upgrade creates ix_producto_nombre_search partial index
- **WHEN** migration `0005` is applied
- **THEN** index `ix_producto_nombre_search` exists on `producto (nombre text_pattern_ops)` with condition `WHERE deleted_at IS NULL`
- **THEN** ILIKE queries with prefix patterns can use this index

#### Scenario: existing producto table columns are unchanged
- **WHEN** migration `0005` is applied
- **THEN** table `producto` still has all original columns from migration 0001: `id` (UUID PK), `nombre`, `descripcion`, `imagen_url`, `precio_base` (DECIMAL 10,2), `stock_cantidad` (INTEGER), `disponible` (BOOLEAN), `created_at`, `updated_at`, `deleted_at`
- **THEN** CHECK constraints `ck_producto_precio_base` and `ck_producto_stock_cantidad` remain unchanged
- **THEN** no columns are added or removed by migration 0005
- **THEN** `alembic_version` shows `0005` as the current head

#### Scenario: downgrade drops both indexes cleanly
- **WHEN** `alembic downgrade -1` (from `0005` to `0004`) runs
- **THEN** both indexes `ix_producto_disponible` and `ix_producto_nombre_search` are dropped
- **THEN** `alembic_version` shows `0004` as the current head
- **THEN** other tables (`categoria`, `ingrediente`, `usuario`) are unaffected

#### Scenario: upgrade + downgrade + upgrade round-trip is reproducible
- **WHEN** `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` is executed
- **THEN** all three steps complete without errors
- **THEN** after the final upgrade, both indexes exist on `producto`
- **THEN** `alembic check` reports no pending migration

#### Scenario: 0005 migration tests pass in CI
- **WHEN** `pytest tests/test_migrations.py -k "0005"` runs with test DB accessible
- **THEN** the test verifies upgrade creates both indexes with correct conditions
- **THEN** the test verifies downgrade drops both indexes
- **THEN** the test verifies round-trip reproducibility
- **THEN** the test verifies `alembic check` reports no spurious changes after upgrade
