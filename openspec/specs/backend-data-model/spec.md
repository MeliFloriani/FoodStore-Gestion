# backend-data-model Specification

## Purpose
Complete SQLModel ERD v5 — all domain entities, constraints, indexes, and relationships. Introduced in Change 03 (database-migrations-and-seed).

## ADDED Requirements

### Requirement: Dominio Identidad y Acceso — modelos SQLModel
El sistema SHALL proveer los modelos `Usuario`, `Rol`, `UsuarioRol` y `RefreshToken` como clases SQLModel con `table=True` en `app/models/user.py`. Todos heredan de `Base` (UUID PK, timestamps, soft delete), incluyendo `UsuarioRol` (ver D-29).

#### Scenario: Usuario tiene email único y password_hash CHAR(60)
- **WHEN** se define el modelo `Usuario`
- **THEN** `email` tiene `unique=True`, tipo `VARCHAR(254)`, `nullable=False`
- **THEN** `password_hash` tiene tipo `CHAR(60)`, `nullable=False`
- **THEN** `nombre` y `apellido` son `VARCHAR(80)`, `nullable=False`
- **THEN** `Usuario` hereda `id UUID`, `created_at`, `updated_at`, `deleted_at` de `Base`

#### Scenario: Rol tiene código semántico único
- **WHEN** se define el modelo `Rol`
- **THEN** `codigo` es `VARCHAR(20)`, `nullable=False`, con constraint `unique=True`
- **THEN** `nombre` es `VARCHAR(80)`, `nullable=False`
- **THEN** `Rol` hereda de `Base` (PK UUID; `codigo` es PK semántica, no PK técnica)

#### Scenario: UsuarioRol hereda de Base completo con restricción única compuesta
- **WHEN** se define el modelo `UsuarioRol`
- **THEN** `UsuarioRol` hereda de `Base` (UUID v4 PK + `created_at` + `updated_at` + `deleted_at`)
- **THEN** tiene `usuario_id UUID FK → usuario.id` con `ON DELETE CASCADE`, `nullable=False`
- **THEN** tiene `rol_id UUID FK → rol.id` con `ON DELETE CASCADE`, `nullable=False`
- **THEN** tiene `asignado_por_id UUID FK → usuario.id`, nullable (NULL permitido para bootstrap system-generated — ver task 8.4 y D-29)
- **THEN** la combinación `(usuario_id, rol_id)` tiene `UniqueConstraint` para impedir duplicados lógicos
- **THEN** `deleted_at` heredado queda dormant (la eliminación de asignaciones de rol es hard delete operacional en Change 09; ver D-29 y D-31)

#### Scenario: RefreshToken almacena SHA-256 en CHAR(64) con índice en usuario_id
- **WHEN** se define el modelo `RefreshToken`
- **THEN** `token_hash` es `CHAR(64)`, `nullable=False`, con `unique=True`
- **THEN** `usuario_id UUID FK → usuario.id` con `ON DELETE CASCADE`, `nullable=False`, con `index=True` (ver Requirement "Índices secundarios en FK de alta frecuencia")
- **THEN** `expires_at` es `TIMESTAMPTZ`, `nullable=False`
- **THEN** `revoked_at` es `TIMESTAMPTZ`, nullable (NULL = token activo)
- **THEN** `RefreshToken` hereda de `Base`

---

### Requirement: Dominio Catálogo — modelos SQLModel
El sistema SHALL proveer los modelos `Categoria`, `Producto`, `Ingrediente`, `ProductoCategoria`, `ProductoIngrediente` y `FormaPago` en `app/models/catalog.py`.

#### Scenario: Categoria tiene FK self-referencial nullable con ON DELETE SET NULL
- **WHEN** se define el modelo `Categoria`
- **THEN** `parent_id` es `UUID FK → categoria.id`, nullable, `ON DELETE SET NULL`
- **THEN** `nombre` es `VARCHAR(100)`, `nullable=False`, con `unique=True`
- **THEN** `descripcion` es `TEXT`, nullable
- **THEN** `Categoria` hereda de `Base` con soft delete

#### Scenario: Producto tiene precio DECIMAL y stock INTEGER con CHECKs
- **WHEN** se define el modelo `Producto`
- **THEN** `nombre` es `VARCHAR(200)`, `nullable=False`
- **THEN** `precio_base` es `DECIMAL(10,2)`, `nullable=False`, con `CHECK precio_base >= 0`
- **THEN** `stock_cantidad` es `INTEGER`, `nullable=False`, `default=0`, con `CHECK stock_cantidad >= 0`
- **THEN** `disponible` es `BOOLEAN`, `nullable=False`, `default=True`
- **THEN** `descripcion` es `TEXT`, nullable
- **THEN** `imagen_url` es `VARCHAR(500)`, nullable
- **THEN** `Producto` hereda de `Base` con soft delete

#### Scenario: Ingrediente tiene nombre único y flag es_alergeno
- **WHEN** se define el modelo `Ingrediente`
- **THEN** `nombre` es `VARCHAR(100)`, `nullable=False`, con `unique=True`
- **THEN** `es_alergeno` es `BOOLEAN`, `nullable=False`, `default=False`
- **THEN** `Ingrediente` hereda de `Base` con soft delete

#### Scenario: ProductoCategoria es tabla pivot con flag es_principal
- **WHEN** se define el modelo `ProductoCategoria`
- **THEN** tiene `producto_id UUID FK → producto.id` con `ON DELETE CASCADE`
- **THEN** tiene `categoria_id UUID FK → categoria.id` con `ON DELETE CASCADE`
- **THEN** tiene `es_principal BOOLEAN`, `nullable=False`, `default=False`
- **THEN** la combinación `(producto_id, categoria_id)` tiene constraint `unique`

#### Scenario: ProductoIngrediente es tabla pivot con flag es_removible
- **WHEN** se define el modelo `ProductoIngrediente`
- **THEN** tiene `producto_id UUID FK → producto.id` con `ON DELETE CASCADE`
- **THEN** tiene `ingrediente_id UUID FK → ingrediente.id` con `ON DELETE CASCADE`
- **THEN** `es_removible` es `BOOLEAN`, `nullable=False` (sin default — siempre explícito)
- **THEN** la combinación `(producto_id, ingrediente_id)` tiene constraint `unique`

#### Scenario: FormaPago tiene codigo semántico como PK natural y flag habilitado
- **WHEN** se define el modelo `FormaPago`
- **THEN** `codigo` es `VARCHAR(20)`, `nullable=False`, con `unique=True`
- **THEN** `nombre` es `VARCHAR(100)`, `nullable=False`
- **THEN** `habilitado` es `BOOLEAN`, `nullable=False`, `default=True`
- **THEN** `FormaPago` hereda de `Base`

---

### Requirement: Dominio Ventas — modelos SQLModel
El sistema SHALL proveer los modelos `EstadoPedido`, `Pedido`, `DetallePedido`, `HistorialEstadoPedido` y `Pago` en `app/models/order.py`.

#### Scenario: EstadoPedido tiene codigo semántico y flag es_terminal
- **WHEN** se define el modelo `EstadoPedido`
- **THEN** `codigo` es `VARCHAR(20)`, `nullable=False`, con `unique=True`
- **THEN** `descripcion` es `VARCHAR(200)`, nullable
- **THEN** `es_terminal` es `BOOLEAN`, `nullable=False`, `default=False`
- **THEN** `orden` es `INTEGER`, nullable (para ordenamiento UI)
- **THEN** `EstadoPedido` hereda de `Base`

#### Scenario: Pedido tiene total immutable, costo_envio default 50.00, y forma_pago FK semántica
- **WHEN** se define el modelo `Pedido`
- **THEN** `usuario_id UUID FK → usuario.id`, `nullable=False`, `ON DELETE RESTRICT`, con `index=True` (ver Requirement "Índices secundarios en FK de alta frecuencia")
- **THEN** `estado_codigo VARCHAR(20) FK → estado_pedido.codigo`, `nullable=False`, con `index=True` (hot path panel admin)
- **THEN** `forma_pago_codigo VARCHAR(20) FK → forma_pago.codigo`, `nullable=False`
- **THEN** `direccion_id UUID FK → direccion_entrega.id`, nullable, `ON DELETE SET NULL`
- **THEN** `total` es `DECIMAL(10,2)`, `nullable=False`, con `CHECK total >= 0`
- **THEN** `costo_envio` es `DECIMAL(10,2)`, `nullable=False`, `default=50.00`
- **THEN** `notas` es `TEXT`, nullable
- **THEN** `Pedido` hereda de `Base` con soft delete

#### Scenario: DetallePedido tiene snapshots de nombre y precio, y personalizacion como INTEGER[]
- **WHEN** se define el modelo `DetallePedido`
- **THEN** `pedido_id UUID FK → pedido.id` con `ON DELETE CASCADE`, `nullable=False`, con `index=True` (ver Requirement "Índices secundarios en FK de alta frecuencia")
- **THEN** `producto_id UUID FK → producto.id` con `ON DELETE RESTRICT`, `nullable=False`
- **THEN** `nombre_snapshot` es `VARCHAR(200)`, `nullable=False`
- **THEN** `precio_snapshot` es `DECIMAL(10,2)`, `nullable=False`, con `CHECK precio_snapshot >= 0`
- **THEN** `cantidad` es `INTEGER`, `nullable=False`, con `CHECK cantidad >= 1`
- **THEN** `personalizacion` es `ARRAY(Integer)`, nullable (IDs de ingredientes removidos)
- **THEN** `DetallePedido` hereda de `Base`

#### Scenario: HistorialEstadoPedido es append-only con estado_desde nullable
- **WHEN** se define el modelo `HistorialEstadoPedido`
- **THEN** `pedido_id UUID FK → pedido.id` con `ON DELETE CASCADE`, `nullable=False`, con `index=True` (ver Requirement "Índices secundarios en FK de alta frecuencia")
- **THEN** `estado_desde VARCHAR(20) FK → estado_pedido.codigo`, nullable (NULL = transición inicial, RN-02); exige `foreign_keys` explícito por múltiples FKs a `estado_pedido.codigo` (ver D-30)
- **THEN** `estado_hasta VARCHAR(20) FK → estado_pedido.codigo`, `nullable=False`; exige `foreign_keys` + `primaryjoin` explícito (ver D-30)
- **THEN** `motivo` es `TEXT`, nullable
- **THEN** `cambiado_por_id UUID FK → usuario.id`, nullable
- **THEN** el modelo lleva comentario `# APPEND-ONLY: never UPDATE or DELETE (RN-03)`
- **THEN** `HistorialEstadoPedido` hereda de `Base`
- **NOTA arquitectónica**: `updated_at` heredado de `Base` no tiene semántica funcional en esta entidad append-only. Su presencia es por coherencia estructural y uniformidad de la jerarquía (D-23, D-31). La guarda dura que impide `UPDATE`/`DELETE` a nivel DB se implementa en Change 18 (state machine).

#### Scenario: Pago tiene campos MercadoPago con constraints actualizados (Change 19)
- **WHEN** se define el modelo `Pago`
- **THEN** `pedido_id UUID FK → pedido.id` con `ON DELETE RESTRICT`, `nullable=False`, con `index=True` (ver Requirement "Índices secundarios en FK de alta frecuencia")
- **THEN** `mp_payment_id` es `BIGINT`, nullable, con `unique=True` (NULL hasta que el webhook llega)
- **THEN** `mp_preference_id` es `VARCHAR(100)`, nullable, con `unique=True`, indexado — NUEVA COLUMNA (migración 0011, Change 19) — Checkout Pro preference ID. Se asigna al crear la preferencia con `POST /api/v1/pagos`; NULL en filas anteriores a la migración
- **THEN** `mp_status` es `VARCHAR(30)`, `nullable=False` (pending/approved/rejected/in_process/cancelled)
- **THEN** `mp_status_detail` es `VARCHAR(100)`, nullable — NUEVA COLUMNA (migración 0010, Change 19) — almacena el `status_detail` de MP
- **THEN** `external_reference` es `VARCHAR(100)`, `nullable=False`, **SIN** constraint `unique` (MODIFICADO en Change 19 — era UQ, ahora tiene índice no único únicamente; soporta 1:N Pago por Pedido para reintentos — RN-PA08, US-048)
- **THEN** `idempotency_key` es `VARCHAR(100)`, `nullable=False`, con `unique=True` (cada intento de pago tiene clave única)
- **THEN** `monto` es `DECIMAL(10,2)`, nullable
- **THEN** `Pago` hereda de `Base`

Un índice no único `ix_pago_pedido_id_created_at` sobre `(pedido_id, created_at DESC)` SHALL existir para soporte eficiente de `get_latest_by_pedido_id`.

**Alembic migración 0010** (relaja constraint external_reference, agrega mp_status_detail):
```sql
ALTER TABLE pago DROP CONSTRAINT IF EXISTS uq_pago_external_reference;
ALTER TABLE pago ADD COLUMN IF NOT EXISTS mp_status_detail VARCHAR(100);
CREATE INDEX IF NOT EXISTS ix_pago_pedido_id_created_at ON pago(pedido_id, created_at DESC);
```

**Alembic migración 0011** (agrega mp_preference_id para Checkout Pro):
```sql
ALTER TABLE pago ADD COLUMN mp_preference_id VARCHAR(100);
ALTER TABLE pago ADD CONSTRAINT uq_pago_mp_preference_id UNIQUE (mp_preference_id);
CREATE INDEX ix_pago_mp_preference_id ON pago(mp_preference_id);
```

> **Downgrade safety pre-check (MANDATORY)**: Antes de ejecutar el downgrade de 0010, la función `downgrade()` SHALL verificar que no existen valores duplicados en `external_reference`. Si se encuentran duplicados, el downgrade DEBE abortar con excepción.

> **Rationale**: El ERD del Integrador v5 marca `external_reference` como `UQ`. Sin embargo, RN-PA08 exige "Un pedido puede tener múltiples intentos de pago (1:N)" y US-048 exige reintentar pago rechazado. El requerimiento funcional (reintento) tiene precedencia. La idempotencia se preserva via `idempotency_key` UNIQUE y `mp_payment_id` UNIQUE.

#### Scenario: Multiple Pago rows for same pedido_id are allowed (Change 19)
- **GIVEN** an existing `Pago` row with `external_reference = "pedido-uuid-123"`
- **WHEN** a second `Pago` row is inserted with `external_reference = "pedido-uuid-123"` and a different `idempotency_key`
- **THEN** the INSERT succeeds without UNIQUE constraint violation
- **THEN** both rows exist in the `pago` table with the same `external_reference`

#### Scenario: idempotency_key UNIQUE constraint is preserved
- **GIVEN** an existing `Pago` row with `idempotency_key = "ik-abc-123"`
- **WHEN** a second INSERT is attempted with the same `idempotency_key = "ik-abc-123"`
- **THEN** the INSERT fails with a UNIQUE constraint violation on `idempotency_key`

#### Scenario: mp_preference_id UNIQUE constraint exists (Change 19)
- **GIVEN** an existing `Pago` row with `mp_preference_id = "MP-PREF-123"`
- **WHEN** a second INSERT is attempted with the same `mp_preference_id = "MP-PREF-123"`
- **THEN** the INSERT fails with a UNIQUE constraint violation on `mp_preference_id`

#### Scenario: ix_pago_pedido_id_created_at index exists after migration (Change 19)
- **WHEN** Alembic migration 0010 is applied
- **THEN** the index `ix_pago_pedido_id_created_at` exists on the `pago` table
- **THEN** `SELECT ... FROM pago WHERE pedido_id = :id ORDER BY created_at DESC LIMIT 1` uses an index scan

#### Scenario: mp_status_detail column exists and is nullable (Change 19)
- **WHEN** Alembic migration 0010 is applied
- **THEN** the `pago` table has a column `mp_status_detail VARCHAR(100)` that allows NULL values
- **THEN** existing rows have `mp_status_detail = NULL` (no data loss)

---

### Requirement: DireccionEntrega con campos alias y es_principal
El sistema SHALL proveer el modelo `DireccionEntrega` en `app/models/address.py` con los campos exactos del Integrador v5.0.

#### Scenario: DireccionEntrega tiene alias y es_principal (no es_predeterminada)
- **WHEN** se define el modelo `DireccionEntrega`
- **THEN** `usuario_id UUID FK → usuario.id` con `ON DELETE CASCADE`, `nullable=False`
- **THEN** `alias` es `VARCHAR(50)`, nullable (ej: 'Casa', 'Trabajo')
- **THEN** `linea1` es `TEXT`, `nullable=False`
- **THEN** `linea2` es `TEXT`, nullable
- **THEN** `ciudad` es `VARCHAR(100)`, `nullable=False`
- **THEN** `provincia` es `VARCHAR(100)`, `nullable=False`
- **THEN** `codigo_postal` es `VARCHAR(20)`, nullable
- **THEN** `es_principal` es `BOOLEAN`, `nullable=False`, `default=False`
- **THEN** el campo se llama `es_principal`, NO `es_predeterminada`
- **THEN** `DireccionEntrega` hereda de `Base` con soft delete

---

### Requirement: Todos los modelos de dominio usan el metadata con naming convention
El sistema SHALL garantizar que todos los modelos `table=True` declarados en los archivos de dominio usen el `SQLModel.metadata` ya configurado en `app/db/base.py`.

#### Scenario: Naming convention aplicada a modelos de dominio
- **WHEN** Alembic genera la migration `0001_initial_schema` con autogenerate
- **THEN** los nombres de constraints siguen el patrón: `uq_usuario_email`, `fk_pedido_usuario_id_usuario`, `ck_producto_precio_base`
- **THEN** no existen constraints con nombres implícitos (que no sigan la naming_convention)

#### Scenario: app/models/__init__.py exporta todos los modelos
- **WHEN** se hace `import app.models`
- **THEN** todas las clases de dominio (`Usuario`, `Rol`, `Producto`, `Pedido`, etc.) están disponibles
- **THEN** `SQLModel.metadata.sorted_tables` contiene las 16 tablas del ERD v5

---

### Requirement: Relationships SQLModel con parámetros explícitos
El sistema SHALL declarar todas las `Relationship()` de SQLModel en este change con parámetros explícitos. No se permite inferencia implícita de joins ni back-population automática (ver D-30).

#### Scenario: Todas las Relationship definen back_populates
- **WHEN** se declara cualquier `Relationship()` bidireccional en los modelos de este change
- **THEN** ambos lados definen `back_populates=` apuntando al campo del modelo opuesto
- **THEN** no se usa `backref=` mágico
- **THEN** ninguna relación queda con solo un lado declarado (unidireccional debe documentarse explícitamente)

#### Scenario: Relaciones con múltiples FKs hacia la misma tabla declaran foreign_keys
- **WHEN** un modelo tiene dos o más FKs apuntando a la misma tabla objetivo
- **THEN** cada `Relationship()` declara `foreign_keys=` con la lista de columnas exacta que resuelve el join
- **THEN** se declara `primaryjoin=` explícito para relaciones ambiguas
- **Casos críticos**:
  - `HistorialEstadoPedido.estado_desde_rel` y `HistorialEstadoPedido.estado_hasta_rel` → dos FKs a `estado_pedido.codigo`: cada relación declara `foreign_keys` + `primaryjoin` separados
  - `HistorialEstadoPedido.cambiado_por` → FK a `usuario.id` en el mismo dominio que `Pedido.usuario_id`: declarar `foreign_keys` para evitar join ambiguo con `Pedido → Usuario`
  - `UsuarioRol.asignado_por` → FK self-reference a `Usuario`: declarar `foreign_keys=[UsuarioRol.asignado_por_id]` explícito

#### Scenario: Self-references declaran remote_side
- **WHEN** se declara una relación self-referencial
- **THEN** la `Relationship()` declara `sa_relationship_kwargs={"remote_side": [...]}` (o equivalente SQLModel)
- **Caso crítico**: `Categoria.subcategorias` ↔ `Categoria.parent` requiere `remote_side=[Categoria.id]` en la relación `parent`

#### Scenario: Estrategia de lazy loading declarada explícitamente
- **WHEN** se declara cualquier `Relationship()` en los modelos de este change
- **THEN** la estrategia `lazy` se declara explícitamente vía `sa_relationship_kwargs={"lazy": "..."}` o equivalente SQLModel
- **THEN** no se usa `lazy="select"` clásico (incompatible con sesión async de SQLAlchemy 2.x)
- **Guideline**:
  - Relaciones a-muchos de baja cardinalidad (ej: `Usuario.roles`, `Pedido.detalles`): `"selectin"` por defecto
  - Relaciones de alto volumen (ej: `Pedido.historial`): `"noload"` o `"raise"` — cargar explícitamente cuando se necesite
  - Relaciones raíz (ej: `Pedido.usuario`): `"selectin"` o `"joined"` según patrón de acceso más frecuente

---

### Requirement: Índices secundarios en FK de alta frecuencia
El sistema SHALL declarar `index=True` (vía `sa_column_kwargs={"index": True}` o `Index()` explícito en `__table_args__`) en las columnas FK que son hot paths operacionales. PostgreSQL NO indexa FKs automáticamente salvo que la columna sea UNIQUE o PK. SQLModel tampoco lo hace por defecto en `ForeignKey()`. Sin estos índices, las consultas más frecuentes del sistema realizan full table scans en producción.

#### Scenario: FK de alta frecuencia tienen índice secundario declarado
- **WHEN** se definen los modelos en `user.py`, `order.py`
- **THEN** `refresh_token.usuario_id` tiene `index=True`
- **THEN** `pedido.usuario_id` tiene `index=True`
- **THEN** `pedido.estado_codigo` tiene `index=True` (hot path del panel admin: filtro por estado)
- **THEN** `detalle_pedido.pedido_id` tiene `index=True`
- **THEN** `historial_estado_pedido.pedido_id` tiene `index=True`
- **THEN** `pago.pedido_id` tiene `index=True`

#### Scenario: Naming convention genera nombres deterministas para los índices FK
- **WHEN** Alembic genera la migration con los índices secundarios
- **THEN** los índices se nombran con el patrón `ix_<tabla>_<columna>` (ej: `ix_refresh_token_usuario_id`, `ix_pedido_usuario_id`, `ix_pedido_estado_codigo`)
- **THEN** no existen índices con nombres implícitos generados por PostgreSQL

## ADDED Requirements (Change 21: admin-users-management)

### Requirement: pg_trgm GIN indexes on usuario for substring search

Alembic migration `0013_admin_usuarios_search_indexes` (revision `d1e2f3a4b5c6`) SHALL:

1. Enable `pg_trgm` extension via `CREATE EXTENSION IF NOT EXISTS pg_trgm`.
2. Create GIN trigram index on `usuario.email`: `ix_usuario_email_trgm` using `gin_trgm_ops`.
3. Create GIN trigram index on `usuario.nombre`: `ix_usuario_nombre_trgm` using `gin_trgm_ops`.
4. Create GIN trigram index on `usuario.apellido`: `ix_usuario_apellido_trgm` using `gin_trgm_ops`.

Downgrade SHALL drop the three indexes with `DROP INDEX IF EXISTS` (does NOT drop the extension).

These indexes enable efficient ILIKE substring search (`%query%`) on the users management panel (D-07).

#### Scenario: Migration 0013 creates three GIN indexes
- **WHEN** `alembic upgrade head` runs migration `0013`
- **THEN** `ix_usuario_email_trgm` exists on `usuario.email` as a GIN index
- **THEN** `ix_usuario_nombre_trgm` exists on `usuario.nombre` as a GIN index
- **THEN** `ix_usuario_apellido_trgm` exists on `usuario.apellido` as a GIN index
- **THEN** the `pg_trgm` extension is enabled in the database

#### Scenario: Migration 0013 downgrade removes indexes
- **WHEN** `alembic downgrade -1` runs for migration `0013`
- **THEN** `ix_usuario_email_trgm`, `ix_usuario_nombre_trgm`, `ix_usuario_apellido_trgm` are dropped
- **THEN** the `pg_trgm` extension is NOT dropped (shared resource)

#### Scenario: ILIKE search uses trigram index
- **WHEN** `SELECT * FROM usuario WHERE email ILIKE '%garcia%'` is executed
- **THEN** PostgreSQL query plan uses the GIN trigram index (`ix_usuario_email_trgm`) instead of a full table scan
