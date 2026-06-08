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
