# backend-migrations Specification

## Purpose
Alembic initialization with async env.py, and the initial schema migration `0001_initial_schema` that creates the complete ERD v5. Introduced in Change 03 (database-migrations-and-seed).

## ADDED Requirements

### Requirement: Alembic inicializado con env.py async
El sistema SHALL tener Alembic configurado en `backend/` con soporte async completo. El archivo `env.py` SHALL usar `asyncio.run()` + `create_async_engine` + `run_sync()` y leer la URL de `get_settings().DATABASE_URL`.

#### Scenario: alembic.ini no contiene la DATABASE_URL en claro
- **WHEN** se lee `backend/alembic.ini`
- **THEN** `sqlalchemy.url` está vacío o contiene un placeholder (`%(DB_URL)s` o similar)
- **THEN** la URL real se inyecta en `env.py` via `get_settings().DATABASE_URL`

#### Scenario: env.py importa todos los modelos antes de target_metadata
- **WHEN** se ejecuta `alembic upgrade head`
- **THEN** `env.py` importa `app.db.base` (activa naming_convention)
- **THEN** `env.py` importa `app.models` (registra todas las tablas en `SQLModel.metadata`)
- **THEN** `target_metadata = SQLModel.metadata` está disponible antes de la ejecución de la migración

#### Scenario: env.py funciona en modo online con engine async
- **WHEN** se ejecuta `alembic upgrade head` con PostgreSQL accesible
- **THEN** la migración se ejecuta sin errores
- **THEN** `alembic_version` se actualiza correctamente en la BD

#### Scenario: alembic check detecta el estado correcto tras upgrade
- **WHEN** se ejecuta `alembic upgrade head` seguido de `alembic check`
- **THEN** `alembic check` reporta que no hay migraciones pendientes

---

### Requirement: Migration 0001_initial_schema — reproducible y reversible
El sistema SHALL tener una única migration `0001_initial_schema` que cree todas las tablas del ERD v5 en `upgrade()` y las elimine en orden inverso en `downgrade()`.

#### Scenario: upgrade crea las 16 tablas del ERD v5
- **WHEN** se ejecuta `alembic upgrade head` sobre una BD vacía
- **THEN** se crean las tablas: `rol`, `usuario`, `usuario_rol`, `refresh_token`, `direccion_entrega`, `categoria`, `producto`, `ingrediente`, `producto_categoria`, `producto_ingrediente`, `forma_pago`, `estado_pedido`, `pedido`, `detalle_pedido`, `historial_estado_pedido`, `pago`
- **THEN** todas las FKs y constraints están presentes
- **THEN** la tabla `alembic_version` tiene una fila con el revision ID de `0001`

#### Scenario: upgrade es idempotente sobre BD ya migrada
- **WHEN** se ejecuta `alembic upgrade head` dos veces consecutivas
- **THEN** la segunda ejecución no genera errores (no intenta recrear tablas)
- **THEN** `alembic_version` sigue teniendo una sola fila

#### Scenario: downgrade elimina todas las tablas en orden correcto
- **WHEN** se ejecuta `alembic downgrade base`
- **THEN** todas las tablas del ERD v5 se eliminan sin errores de FK
- **THEN** la tabla `alembic_version` queda vacía
- **THEN** la BD queda en el estado inicial (sin tablas de dominio)

#### Scenario: ciclo upgrade + downgrade + upgrade es reproducible
- **WHEN** se ejecuta `alembic upgrade head && alembic downgrade base && alembic upgrade head`
- **THEN** los tres pasos completan sin errores
- **THEN** al final, la BD tiene las 16 tablas del ERD v5

---

### Requirement: Tests de migrations en CI
El sistema SHALL incluir tests pytest que ejecuten el ciclo completo de migration en `foodstore_test`.

#### Scenario: test_migration_upgrade_downgrade pasa en CI
- **WHEN** se ejecuta `pytest tests/test_migrations.py` con `foodstore_test` disponible
- **THEN** el test verifica `alembic upgrade head` sin errores
- **THEN** el test verifica `alembic downgrade base` sin errores
- **THEN** el test deja la BD en estado limpio al finalizar

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

---

## ADDED Requirements

### Requirement: Migración Alembic para tabla direccion_entrega
El sistema SHALL tener una nueva migración Alembic en `backend/alembic/versions/` que cree la tabla `direccion_entrega` con todos sus campos, índices y constraints. La migración SHALL:
- Ser la siguiente en la cadena (`down_revision` apunta a la migración anterior activa).
- Crear la tabla con: `id` BIGSERIAL PK, `usuario_id` BIGINT NN FK → `usuario.id` ON DELETE RESTRICT, `alias` VARCHAR(50) NULL, `linea1` TEXT NN, `linea2` TEXT NULL, `ciudad` VARCHAR(100) NULL, `provincia` VARCHAR(100) NULL, `codigo_postal` VARCHAR(10) NULL, `referencia` TEXT NULL, `es_principal` BOOLEAN NN DEFAULT FALSE, `created_at` TIMESTAMPTZ NN DEFAULT NOW(), `updated_at` TIMESTAMPTZ NN DEFAULT NOW(), `deleted_at` TIMESTAMPTZ NULL.
- Crear el índice estándar `ix_direccion_entrega_usuario_id ON direccion_entrega (usuario_id)`.
- Crear el índice parcial único `ix_direccion_entrega_principal_unico ON direccion_entrega (usuario_id) WHERE es_principal AND deleted_at IS NULL` usando `op.execute()` (Alembic no tiene API nativa para índices parciales condicionales).

> Nota: Este índice parcial solo puede validarse con PostgreSQL real. Tests unitarios que usen SQLite no pueden probar la invariante de unicidad — reservar para tests de integración.
- Implementar `downgrade()` que:
  ```python
  op.execute("DROP INDEX IF EXISTS ix_direccion_entrega_principal_unico")
  op.drop_table("direccion_entrega")
  ```
  Aunque PostgreSQL elimina índices automáticamente al hacer DROP TABLE, el DROP INDEX explícito documenta la intención y protege contra implementaciones alternativas de downgrade.

La migración NOT SHALL usar `op.execute("DROP ...")` en `upgrade()`. NOT SHALL usar `op.execute` para la creación de la tabla (usar `op.create_table`).

#### Scenario: upgrade crea tabla con índices
- **WHEN** se ejecuta `alembic upgrade head` desde la revisión anterior
- **THEN** la tabla `direccion_entrega` existe con todos los campos
- **THEN** el índice `ix_direccion_entrega_usuario_id` existe
- **THEN** el índice parcial único `ix_direccion_entrega_principal_unico` existe
- **THEN** `alembic_version` se actualiza al revision ID de esta migración

#### Scenario: downgrade elimina la tabla sin errores de FK
- **WHEN** se ejecuta `alembic downgrade -1` desde esta revisión
- **THEN** la tabla `direccion_entrega` se elimina
- **THEN** no quedan índices huérfanos
- **THEN** `alembic_version` regresa a la revisión anterior

#### Scenario: migración es idempotente (no se aplica dos veces)
- **WHEN** se ejecuta `alembic upgrade head` en una BD que ya tiene esta migración aplicada
- **THEN** Alembic no intenta recrear la tabla
- **THEN** no se genera ningún error

#### Scenario: índice parcial único garantiza invariante en BD
- **WHEN** se ejecuta `INSERT INTO direccion_entrega (usuario_id, linea1, es_principal, ...) VALUES (1, '...', true, ...)` con otra fila ya existente con `usuario_id=1`, `es_principal=true`, `deleted_at=NULL`
- **THEN** PostgreSQL rechaza el insert con error de unique constraint
## Requirements
### Requirement: Migration 0014 — admin_metrics_indexes
The system SHALL have a migration `0014_admin_metrics_indexes` at `backend/alembic/versions/<hash>_0014_admin_metrics_indexes.py` with:
- `down_revision = 'd1e2f3a4b5c6'` (migration 0013 — admin_usuarios_search_indexes)
- `upgrade()` creates two indexes:
  1. `ix_pedido_created_at_estado_codigo` — composite B-tree index on `pedido(created_at, estado_codigo)`
  2. `ix_detalle_pedido_producto_id` — B-tree index on `detalle_pedido(producto_id)`
- `downgrade()` drops both indexes using `DROP INDEX IF EXISTS`

**Verification**: Neither `ix_pedido_created_at_estado_codigo` nor `ix_detalle_pedido_producto_id` exist in any prior migration (migrations 0001–0013 inspected). The `ix_detalle_pedido_pedido_id` index exists (migration 0001) but `ix_detalle_pedido_producto_id` does not.

#### Scenario: Migration 0014 creates both indexes
- **WHEN** `alembic upgrade head` runs migration 0014
- **THEN** `ix_pedido_created_at_estado_codigo` exists on table `pedido`
- **THEN** `ix_detalle_pedido_producto_id` exists on table `detalle_pedido`

#### Scenario: Migration 0014 is reversible
- **WHEN** `alembic downgrade -1` runs from migration 0014
- **THEN** both indexes are dropped without error
- **THEN** pre-existing indexes from migrations 0001–0013 are unaffected

#### Scenario: Migration chain is unbroken after 0014
- **WHEN** `alembic history` is inspected
- **THEN** 0014 chain: `0014 → 0013 (d1e2f3a4b5c6) → 0012 (c0d1e2f3a4b5) → ...`

