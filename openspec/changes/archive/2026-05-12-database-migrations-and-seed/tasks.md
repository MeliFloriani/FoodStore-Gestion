## 1. Preparación de dependencias y configuración

- [x] 1.1 Agregar `passlib[bcrypt]>=1.7.4` a `[project.dependencies]` en `backend/pyproject.toml`
- [x] 1.2 Ejecutar `pip install -e ".[dev]"` en el venv para instalar la nueva dependencia
- [x] 1.3 Actualizar `backend/.env.example` con las variables: `SECRET_KEY=change-me-min-32-chars`, `ACCESS_TOKEN_EXPIRE_MINUTES=30`, `REFRESH_TOKEN_EXPIRE_DAYS=7`, `ADMIN_EMAIL=admin@foodstore.com`, `ADMIN_PASSWORD=Admin1234!`
- [x] 1.4 Verificar que `backend/.env` local tiene `DATABASE_URL` válida apuntando a `foodstore_dev`
- [x] 1.5 Verificar que PostgreSQL está corriendo y `foodstore_dev` + `foodstore_test` son accesibles

## 2. Inicialización de Alembic

- [x] 2.1 Ejecutar `alembic init -t async alembic` desde `backend/` para generar la estructura base
- [x] 2.2 Editar `backend/alembic.ini`: limpiar `sqlalchemy.url` (dejarlo vacío o con placeholder); ajustar `script_location = alembic`
- [x] 2.3 Reescribir `backend/alembic/env.py` con patrón async: importar `app.db.base` + `app.models`, usar `get_settings().DATABASE_URL`, `target_metadata = SQLModel.metadata`, función `run_async_migrations()` con `asyncio.run()`
- [x] 2.4 Verificar que `alembic current` no lanza errores de import (las dependencias de `app.db.base` y `app.models` deben poder importarse desde el contexto de Alembic)

## 3. Modelos SQLModel — Dominio Identidad y Acceso

- [x] 3.1 Crear `backend/app/models/user.py` con modelo `Rol`: hereda de `Base`, campo `codigo VARCHAR(20) unique not null`, campo `nombre VARCHAR(80) not null`
- [x] 3.2 Agregar modelo `Usuario` en `user.py`: hereda de `Base`, `email VARCHAR(254) unique not null`, `password_hash CHAR(60) not null`, `nombre VARCHAR(80) not null`, `apellido VARCHAR(80) not null`; importar `app.db.base` primero
- [x] 3.3 Agregar modelo `UsuarioRol` en `user.py`: hereda de `Base` completo (UUID v4 PK + `created_at` + `updated_at` + `deleted_at` — sin excepción; ver D-29), FK `usuario_id → usuario.id ON DELETE CASCADE` `nullable=False`, FK `rol_id → rol.id ON DELETE CASCADE` `nullable=False`, FK `asignado_por_id → usuario.id` nullable (NULL permitido para bootstrap system-generated — ver task 8.4), `UniqueConstraint(usuario_id, rol_id)` para impedir duplicados lógicos; `deleted_at` heredado queda dormant (ver D-31)
- [x] 3.4 Agregar modelo `RefreshToken` en `user.py`: hereda de `Base`, `token_hash CHAR(64) unique not null` (Column explícito con `CHAR`), FK `usuario_id → usuario.id ON DELETE CASCADE` con `index=True` (`sa_column_kwargs={"index": True}` — PostgreSQL no indexa FK automáticamente), `expires_at TIMESTAMPTZ not null`, `revoked_at TIMESTAMPTZ null`

## 4. Modelos SQLModel — Dominio Catálogo

- [x] 4.1 Crear `backend/app/models/catalog.py` con modelo `Categoria`: hereda de `Base` con soft delete, `nombre VARCHAR(100) unique not null`, `descripcion TEXT null`, FK self-ref `parent_id → categoria.id ON DELETE SET NULL nullable`
- [x] 4.2 Agregar modelo `FormaPago` en `catalog.py`: hereda de `Base`, `codigo VARCHAR(20) unique not null`, `nombre VARCHAR(100) not null`, `habilitado BOOLEAN not null default True`
- [x] 4.3 Agregar modelo `Producto` en `catalog.py`: hereda de `Base` con soft delete, `nombre VARCHAR(200) not null`, `precio_base DECIMAL(10,2) not null CHECK >=0`, `stock_cantidad INTEGER not null default 0 CHECK >=0`, `disponible BOOLEAN not null default True`, `descripcion TEXT null`, `imagen_url VARCHAR(500) null`
- [x] 4.4 Agregar modelo `Ingrediente` en `catalog.py`: hereda de `Base` con soft delete, `nombre VARCHAR(100) unique not null`, `es_alergeno BOOLEAN not null default False`
- [x] 4.5 Agregar modelo `ProductoCategoria` en `catalog.py`: hereda de `Base`, FK `producto_id → producto.id ON DELETE CASCADE`, FK `categoria_id → categoria.id ON DELETE CASCADE`, `es_principal BOOLEAN not null default False`, UniqueConstraint `(producto_id, categoria_id)`
- [x] 4.6 Agregar modelo `ProductoIngrediente` en `catalog.py`: hereda de `Base`, FK `producto_id → producto.id ON DELETE CASCADE`, FK `ingrediente_id → ingrediente.id ON DELETE CASCADE`, `es_removible BOOLEAN not null` (sin default — explícito), UniqueConstraint `(producto_id, ingrediente_id)`

## 5. Modelos SQLModel — Dominio Ventas y Pagos

- [x] 5.1 Crear `backend/app/models/address.py` con modelo `DireccionEntrega`: hereda de `Base` con soft delete, FK `usuario_id → usuario.id ON DELETE CASCADE`, `alias VARCHAR(50) null`, `linea1 TEXT not null`, `linea2 TEXT null`, `ciudad VARCHAR(100) not null`, `provincia VARCHAR(100) not null`, `codigo_postal VARCHAR(20) null`, `es_principal BOOLEAN not null default False` (campo `es_principal`, NO `es_predeterminada`)
- [x] 5.2 Crear `backend/app/models/order.py` con modelo `EstadoPedido`: hereda de `Base`, `codigo VARCHAR(20) unique not null`, `descripcion VARCHAR(200) null`, `es_terminal BOOLEAN not null default False`, `orden INTEGER null`
- [x] 5.3 Agregar modelo `Pedido` en `order.py`: hereda de `Base` con soft delete, FK `usuario_id → usuario.id ON DELETE RESTRICT` con `index=True`, FK `estado_codigo VARCHAR(20) → estado_pedido.codigo not null` con `index=True` (hot path panel admin — consultas frecuentes por estado), FK `forma_pago_codigo VARCHAR(20) → forma_pago.codigo not null`, FK `direccion_id → direccion_entrega.id ON DELETE SET NULL nullable`, `total DECIMAL(10,2) not null CHECK >=0`, `costo_envio DECIMAL(10,2) not null default 50.00`, `notas TEXT null`
- [x] 5.4 Agregar modelo `DetallePedido` en `order.py`: hereda de `Base`, FK `pedido_id → pedido.id ON DELETE CASCADE` con `index=True`, FK `producto_id → producto.id ON DELETE RESTRICT`, `nombre_snapshot VARCHAR(200) not null`, `precio_snapshot DECIMAL(10,2) not null CHECK >=0`, `cantidad INTEGER not null CHECK >=1`, `personalizacion ARRAY(Integer) null` (usando `Column(ARRAY(Integer), nullable=True)` explícito)
- [x] 5.5 Agregar modelo `HistorialEstadoPedido` en `order.py`: hereda de `Base`, FK `pedido_id → pedido.id ON DELETE CASCADE` con `index=True`, FK `estado_desde VARCHAR(20) → estado_pedido.codigo nullable` (NULL = transición inicial RN-02) con `foreign_keys` explícito, FK `estado_hasta VARCHAR(20) → estado_pedido.codigo not null` con `foreign_keys` + `primaryjoin` explícito (dos FKs a la misma tabla — D-30), FK `cambiado_por_id → usuario.id nullable`, `motivo TEXT null`; agregar comentario `# APPEND-ONLY: never UPDATE or DELETE (RN-03)`
- [x] 5.6 Agregar modelo `Pago` en `order.py`: hereda de `Base`, FK `pedido_id → pedido.id ON DELETE RESTRICT` con `index=True`, `mp_payment_id BIGINT unique null`, `mp_status VARCHAR(30) not null`, `external_reference VARCHAR(100) unique not null`, `idempotency_key VARCHAR(100) unique not null`, `monto DECIMAL(10,2) null`

## 6. Registro de modelos en __init__.py

- [x] 6.1 Actualizar `backend/app/models/__init__.py` para importar y re-exportar todas las clases de dominio: `from app.models.user import Usuario, Rol, UsuarioRol, RefreshToken`, `from app.models.address import DireccionEntrega`, `from app.models.catalog import Categoria, Producto, Ingrediente, ProductoCategoria, ProductoIngrediente, FormaPago`, `from app.models.order import EstadoPedido, Pedido, DetallePedido, HistorialEstadoPedido, Pago`
- [x] 6.2 Verificar que `python -c "import app.models; from sqlmodel import SQLModel; print(len(SQLModel.metadata.sorted_tables))"` imprime `16`

## 7. Generación y validación de la migration 0001_initial_schema

- [x] 7.1 Ejecutar `alembic revision --autogenerate -m "0001_initial_schema"` desde `backend/` y verificar que el archivo generado contiene todas las tablas
- [x] 7.2 Revisar manualmente el archivo de migration generado: confirmar tablas presentes, tipos de datos correctos (`CHAR(64)` para `token_hash`, `DECIMAL(10,2)` para precios, `ARRAY(Integer)` para `personalizacion`), FKs con `ondelete` correcto
- [x] 7.3 Verificar constraints: `uq_usuario_email`, `fk_pedido_usuario_id_usuario`, `ck_producto_precio_base`, etc. siguen el naming_convention
- [x] 7.4 Agregar o corregir manualmente en la migration el `downgrade()` con orden de `DROP TABLE` inverso a las FK (empezar por `pago`, `historial_estado_pedido`, `detalle_pedido`, `pedido`, luego pivots, luego entidades base)
- [x] 7.5 Ejecutar `alembic upgrade head` sobre `foodstore_dev` y confirmar que no hay errores
- [x] 7.6 Verificar tablas con `psql foodstore_dev -c "\dt"` — deben aparecer las 16 tablas del ERD v5

## 8. Script de seed idempotente

- [x] 8.1 Crear `backend/app/db/seed.py` con función `async def seed_estados_pedido(session)` que inserta los 6 `EstadoPedido` usando `INSERT ... ON CONFLICT (codigo) DO NOTHING`
- [x] 8.2 Agregar función `async def seed_formas_pago(session)` que inserta `MERCADOPAGO`, `EFECTIVO`, `TRANSFERENCIA` (todos `habilitado=True`) con `ON CONFLICT DO NOTHING`
- [x] 8.3 Agregar función `async def seed_roles(session)` que inserta `ADMIN`, `STOCK`, `PEDIDOS`, `CLIENT` con `ON CONFLICT DO NOTHING`
- [x] 8.4 Agregar función `async def seed_admin(session)` que: lee `ADMIN_EMAIL` y `ADMIN_PASSWORD` de `os.getenv` (defaults `admin@foodstore.com` / `Admin1234!`); imprime WARNING si usa default; hashea con `CryptContext(schemes=["bcrypt"], bcrypt__rounds=12)`; inserta usuario con `ON CONFLICT (email) DO NOTHING`; asigna rol ADMIN si no lo tiene. **Crítico**: al crear el registro `UsuarioRol` para el admin bootstrap, usar `asignado_por_id=None` (NULL). Esta asignación es system-generated — no hay actor humano. Evitar auto-asignación artificial (`asignado_por_id=admin.id`) que introduciría semántica falsa; evitar crear un "system user" sintético solo para satisfacer la FK (overengineering). La columna es nullable precisamente para este caso.
- [x] 8.5 Implementar función `async def main()` que abre sesión async con `get_session_factory()`, llama las 4 funciones de seed en orden, y hace commit
- [x] 8.6 Agregar `if __name__ == "__main__": asyncio.run(main())` y el módulo `__main__` equivalente para `python -m app.db.seed`
- [x] 8.7 Ejecutar `python -m app.db.seed` sobre `foodstore_dev` y verificar que no hay errores
- [x] 8.8 Ejecutar `python -m app.db.seed` una segunda vez y verificar idempotencia (sin errores, sin duplicados)

## 9. Tests de migrations y seed

- [x] 9.0 **Infraestructura de testing DB — precondiciones** (debe completarse antes de 9.1–9.5):
  - Validar que `backend/.env.example` declara `TEST_DATABASE_URL` apuntando a `foodstore_test` con driver `asyncpg` (ej: `postgresql+asyncpg://user:pass@localhost:5432/foodstore_test`)
  - Validar que `backend/.env` local tiene `TEST_DATABASE_URL` poblada con valor real; verificar accesibilidad con `psql $TEST_DATABASE_URL -c "SELECT 1"`
  - Validar que `backend/tests/conftest.py` (Change 02) expone fixtures `override_settings`, `async_client`, `test_db_session` y respeta el protocolo de `cache_clear()` de D-16
  - Verificar que `foodstore_test` está accesible (PostgreSQL local up)
  - Especificar **estrategia de aislamiento por test**:
    - **Opción A (preferida para tests de seed)**: cada test corre dentro de una transacción que hace `ROLLBACK` al final — la fixture `test_db_session` envuelve en `BEGIN`/`ROLLBACK`; garantiza aislamiento sin tocar el schema
    - **Opción B (para tests de ciclo Alembic en `test_migrations.py`)**: `alembic upgrade head` + `alembic downgrade base` por test — más lento, usar solo en `test_migrations.py` donde se testea el schema completo
  - Especificar **estrategia de recreate**: si un test deja la BD en estado sucio (ej: downgrade falló a mitad), el siguiente test debe poder recuperarse — implementar fixture session-scoped que ejecuta `alembic downgrade base && alembic upgrade head` al iniciar la suite de tests de migration
  - Garantizar que los 23 tests del Change 02 (`test_infrastructure.py`) siguen pasando tras introducir el schema completo; el `SQLModel.metadata` ahora contiene 16 tablas pero los tests de infraestructura no deben depender del conteo de tablas

- [x] 9.1 Crear `backend/tests/test_migrations.py` con test `test_upgrade_downgrade_upgrade` que ejecuta el ciclo completo `upgrade head → downgrade base → upgrade head` sobre `foodstore_test` usando subprocess o Alembic API
- [x] 9.2 Crear `backend/tests/test_seed.py` con test `test_seed_idempotent` que ejecuta `seed.main()` dos veces y verifica que las tablas de catálogo tienen exactamente 6 `EstadoPedido`, 3 `FormaPago`, 4 `Rol`, 1 admin
- [x] 9.3 Agregar test `test_seed_estados_terminales` que verifica que `ENTREGADO` y `CANCELADO` tienen `es_terminal=True`, y el resto `False`
- [x] 9.4 Ejecutar `pytest tests/test_migrations.py tests/test_seed.py -v` y confirmar que todos los tests pasan
- [x] 9.5 Ejecutar el suite completo `pytest -v` para asegurar que los 23 tests de infraestructura existentes siguen pasando (no regresión)

## 10. Verificación final y documentación

- [x] 10.1 Ejecutar `alembic downgrade base` sobre `foodstore_dev` y verificar que todas las tablas se eliminan sin errores de FK
- [x] 10.2 Ejecutar `alembic upgrade head` de nuevo sobre `foodstore_dev` para restaurar el schema
- [x] 10.3 Ejecutar `python -m app.db.seed` de nuevo para restaurar los datos de catálogo
- [x] 10.4 Verificar con `psql foodstore_dev -c "SELECT codigo, es_terminal FROM estado_pedido ORDER BY orden;"` que los 6 estados están presentes con los flags correctos
- [x] 10.5 Verificar con `psql foodstore_dev -c "SELECT email FROM usuario WHERE deleted_at IS NULL;"` que `admin@foodstore.com` existe
- [x] 10.6 Verificar (D-28) que las FK semánticas referencian `codigo` y no `id`: `psql foodstore_dev -c "\d pedido"` debe mostrar `fk_pedido_forma_pago_codigo_forma_pago` apuntando a `forma_pago(codigo)` y `fk_pedido_estado_codigo_estado_pedido` apuntando a `estado_pedido(codigo)`; idem para `historial_estado_pedido.estado_desde/hasta`
