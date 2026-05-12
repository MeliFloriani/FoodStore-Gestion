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
