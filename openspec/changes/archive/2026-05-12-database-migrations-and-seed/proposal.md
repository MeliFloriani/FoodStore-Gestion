## Why

Change 02 entregó una foundation backend completa (config tipada, motor async lazy, `Base` con soft-delete, naming conventions, 23 tests infra), pero sin ninguna tabla real en PostgreSQL. Sin el schema definido, no pueden existir modelos de dominio, migraciones versionadas ni datos de catálogo obligatorios (roles, estados de pedido, formas de pago, admin). Change 03 materializa el ERD v5 completo del Integrador en SQLModel, inicializa Alembic con `env.py` async y genera el seed idempotente que el sistema requiere para funcionar. Cubre la historia US-000b.

## What Changes

- **Alembic init**: estructura `backend/alembic/` con `env.py` async que usa `get_settings().DATABASE_URL` y `target_metadata = SQLModel.metadata`. Archivo `alembic.ini` con `script_location = alembic` y `sqlalchemy.url` vacío (la URL se inyecta en `env.py` dinámicamente).
- **ERD v5 completo en SQLModel**: todos los modelos `table=True` distribuidos en archivos por dominio bajo `backend/app/models/`:
  - `user.py` — `Usuario`, `Rol`, `UsuarioRol`, `RefreshToken`
  - `address.py` — `DireccionEntrega`
  - `catalog.py` — `Categoria`, `Producto`, `Ingrediente`, `ProductoCategoria`, `ProductoIngrediente`, `FormaPago`
  - `order.py` — `EstadoPedido`, `Pedido`, `DetallePedido`, `HistorialEstadoPedido`, `Pago`
- **Migration `0001_initial_schema`**: una sola migración que crea TODAS las tablas del ERD v5. Contiene `upgrade()` completo y `downgrade()` que revierte en orden inverso. Completamente reproducible sobre cualquier PostgreSQL 15+ vacío.
- **Seed idempotente** (`backend/app/db/seed.py`): script Python invocable como módulo (`python -m app.db.seed`) que inserta:
  - 6 `EstadoPedido`: `PENDIENTE`, `CONFIRMADO`, `EN_PREP`, `EN_CAMINO`, `ENTREGADO`, `CANCELADO` (con `es_terminal` correcto)
  - 3 `FormaPago`: `MERCADOPAGO`, `EFECTIVO`, `TRANSFERENCIA` (todos `habilitado=true`)
  - 4 `Rol`: `ADMIN`, `STOCK`, `PEDIDOS`, `CLIENT`
  - 1 usuario admin: `admin@foodstore.com` / `Admin1234!` con contraseña bcrypt (cost≥12) y rol `ADMIN` asignado
  - Idempotencia via `INSERT ... ON CONFLICT DO NOTHING` o equivalente async
- **`backend/.env.example` actualizado**: variables `SECRET_KEY`, `ACCESS_TOKEN_EXPIRE_MINUTES`, `REFRESH_TOKEN_EXPIRE_DAYS`, `ADMIN_EMAIL`, `ADMIN_PASSWORD` añadidas (necesarias para el seed y futuros changes de auth).
- **Tests de migrations**: `pytest` verifica `alembic upgrade head` + `alembic downgrade base` sobre `foodstore_test`.
- **Tests de seed**: verifican idempotencia (dos ejecuciones consecutivas no duplican filas).

## Capabilities

### New Capabilities

- `backend-data-model`: Modelos SQLModel `table=True` del ERD v5 completo. Todos los agregados, relaciones, constraints (UQ, FK, CK), índices y tipos de datos alineados al Integrador v5.0. Esta capability es la fuente de verdad de la estructura de la base de datos.
- `backend-migrations`: Alembic configurado con `env.py` async. Migration `0001_initial_schema` reproducible y reversible. Naming convention de Change 02 aplicada automáticamente.
- `backend-seed-data`: Script de seed idempotente que carga catálogos estáticos obligatorios (roles, estados, formas de pago) y usuario administrador. Prerequisito para que cualquier feature de dominio funcione.

### Modified Capabilities

- `backend-database-core`: Se extiende para documentar que `SQLModel.metadata` (ya configurado con naming convention en `app/db/base.py`) es el `target_metadata` que alimenta Alembic. No hay cambio de requirements funcionales — se agrega un nuevo scenario que verifica la integración Alembic ↔ metadata.

## Impact

**Backend**:
- Archivos nuevos: `backend/alembic/`, `backend/alembic.ini`, `backend/app/models/user.py`, `backend/app/models/address.py`, `backend/app/models/catalog.py`, `backend/app/models/order.py`, `backend/app/db/seed.py`.
- Archivos modificados: `backend/.env.example` (nuevas variables de seed y auth futuro), `backend/app/models/__init__.py` (re-exports de los modelos para que Alembic los descubra).
- Sin cambios a `app/main.py` (lifespan intacto), `app/db/base.py`, `app/db/session.py`, `app/core/`.

**Base de datos**: `foodstore_dev` y `foodstore_test` pasan de estar vacías a tener el schema completo del ERD v5 tras `alembic upgrade head`.

**Dependencias nuevas**:
- `passlib[bcrypt]` o `bcrypt` — hashing del admin en el seed (costo ≥ 12). Verificar si ya está en `pyproject.toml` (actualmente no está).
- `alembic` ya está declarado en `pyproject.toml`.

**Frontend**: ningún cambio frontend en este change. El schema materializado habilita los modelos TypeScript que los changes de dominio (Change 05+) expondrán como API REST y que el frontend consumirá.

**Siguientes changes desbloqueados**:
- Change 04 (`backend-base-patterns`): `BaseRepository[T]` y `UnitOfWork` pueden construirse sobre los modelos ya existentes.
- Change 05+ (features de dominio): services y endpoints tienen las tablas y el seed disponibles.
