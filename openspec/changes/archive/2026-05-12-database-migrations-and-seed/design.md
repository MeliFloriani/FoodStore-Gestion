## Context

Change 02 (`backend-core-foundation`) dejó el backend con:
- `app/db/base.py`: `SQLModel.metadata.naming_convention` aplicado globalmente (D-12/P-07).
- `app/db/session.py`: `get_engine()`, `get_session_factory()`, `get_session()` lazy con `@lru_cache`.
- `app/models/base.py`: `Base(SQLModel, table=False)` con `id UUID v4`, `created_at`, `updated_at` (onupdate), `deleted_at`.
- `pyproject.toml`: `alembic` ya declarado como dependencia; **`passlib[bcrypt]`/`bcrypt` NO** están declarados.
- `backend/.env.example`: tiene `DATABASE_URL`, `ENVIRONMENT`, `BACKEND_CORS_ORIGINS`, `API_V1_PREFIX`, `LOG_LEVEL`, `RATE_LIMIT_DEFAULT`. Le faltan `SECRET_KEY`, `ADMIN_EMAIL`, `ADMIN_PASSWORD`, `ACCESS_TOKEN_EXPIRE_MINUTES`, `REFRESH_TOKEN_EXPIRE_DAYS`.
- Bases de datos PostgreSQL (`foodstore_dev`, `foodstore_test`) existentes pero completamente vacías — sin schema Alembic.

El Integrador v5.0 define el ERD completo con 16 tablas distribuidas en 3 dominios. Las notas críticas de `docs/CHANGES.md` L79–91 identifican variantes importantes respecto a versiones anteriores del spec que deben materializarse exactamente en este change.

**Restricciones de orden de imports (crítico)**:
El módulo `app/db/base.py` aplica `SQLModel.metadata.naming_convention` **antes** de cualquier modelo. El módulo `app/models/base.py` lo importa primero (línea 25: `import app.db.base`). Todos los modelos de dominio deben importar `app.models.base` o `app.db.base` como primer paso antes de declarar su clase SQLModel con `table=True`. Alembic `env.py` debe importar `app.db.base` y todos los modelos antes de usar `target_metadata = SQLModel.metadata`.

---

## Goals / Non-Goals

**Goals:**

- Inicializar Alembic con `env.py` async que use `get_settings().DATABASE_URL` (patrón lazy D-05).
- Definir el ERD v5 completo en SQLModel (`table=True`) con todos los constraints, índices, FKs y tipos de datos correctos.
- Generar migration `0001_initial_schema` reproducible, reversible (upgrade + downgrade completo).
- Implementar script de seed idempotente (`app/db/seed.py`) que cargue catálogos obligatorios y usuario admin.
- Agregar `passlib[bcrypt]` a `pyproject.toml` y actualizar `.env.example` con variables pendientes.
- Tests de migrations (upgrade/downgrade) y de idempotencia del seed.

**Non-Goals:**

- `BaseRepository[T]` y `UnitOfWork` → Change 04.
- Services y endpoints de dominio → Change 05+.
- Lógica JWT/auth (sign, verify, refresh) → Change 06+. El modelo `RefreshToken` se define aquí porque el ERD lo exige, pero la lógica de auth no se implementa.
- Schemas Pydantic Read/Create/Update por entidad → diferidos a Changes de dominio (ver D-11).
- Cambios al lifespan de `app/main.py`.
- Modelos para features fuera del ERD v5 (Rol pivot, por ejemplo, ya tiene su especificación exacta).
- Frontend: 0 cambios.

---

## Decisions

### D-17: Estructura de archivos de modelos — un archivo por dominio (no por entidad)

**Decisión**: los modelos se organizan en 4 archivos bajo `backend/app/models/`:

```
app/models/
├── base.py          ← ya existe (Base, timestamps, soft delete)
├── user.py          ← Usuario, Rol, UsuarioRol, RefreshToken
├── address.py       ← DireccionEntrega
├── catalog.py       ← Categoria, Producto, Ingrediente, ProductoCategoria, ProductoIngrediente, FormaPago
└── order.py         ← EstadoPedido, Pedido, DetallePedido, HistorialEstadoPedido, Pago
```

**Alternativas consideradas**:
- Un archivo por entidad (16 archivos): máxima atomicidad, pero genera overhead de imports y problemas de forward references entre entidades del mismo dominio (p.ej. `Pedido` ↔ `DetallePedido`). El Integrador agrupa por dominio, no por entidad.
- Un solo `models.py`: viola SRP, dificulta navegación en proyectos medianos.

**Rationale**: la granularidad por dominio equilibra cohesión y navegabilidad. Las entidades del mismo dominio tienen FK cruzadas y es más simple resolver forward references dentro del mismo módulo. Esta estructura prepara el terreno para que Change 04 cree `repositories/user_repository.py`, `repositories/catalog_repository.py`, etc., con correspondencia 1:1.

---

### D-18: PKs UUID v4 para TODAS las entidades (incluyendo catálogos)

**Decisión**: todas las entidades heredan de `Base` y tienen PK UUID v4. Esto incluye catálogos como `Rol`, `EstadoPedido`, `FormaPago`.

**Nota sobre el Integrador v5.0**: el spec usa `BIGSERIAL` para `Usuario.id` y `BIGINT` para FK. Sin embargo, la decisión D-04 de Change 02 establece UUID v4 como estándar de PK para todo el proyecto, y ese design está archivado y no puede contradecirse. Los catálogos semánticos (Rol, EstadoPedido, FormaPago) tienen **código semántico como PK natural** (string) y su UUID es la PK técnica — coexisten sin conflicto.

**Aclaración importante**: `Rol.codigo` es `VARCHAR(20)` con `unique=True` (PK semántica para referencias en código); `Rol.id` es UUID (PK técnica de BD). Lo mismo aplica a `EstadoPedido.codigo` y `FormaPago.codigo`.

**Alternativas consideradas**:
- BIGSERIAL para entidades de alto volumen (Pedido, DetallePedido): UUID v4 tiene overhead en índices btree. Aceptable para volumen de TPI; en producción se mitigaría con `gen_random_uuid()` nativo de PostgreSQL o ULIDs.

---

### D-19: `DetallePedido.personalizacion` — `INTEGER[]` (array de IDs de ingredientes removidos)

**Decisión**: `personalizacion: list[int] | None` mapeado a `ARRAY[INTEGER]` en PostgreSQL.

**Razonamiento**: El Integrador v5.0 sección 3.3 especifica explícitamente `INTEGER[]` (no `UUID[]`). Aunque `Ingrediente` tiene PK UUID, el campo `personalizacion` almacena un snapshot de los IDs en un formato desnormalizado para máxima portabilidad y simplicidad de consulta. Este es un array opaco de referencia, no una FK con integridad referencial. Si `Ingrediente` se elimina (soft delete), el snapshot en `DetallePedido` permanece inmutable — esto es correcto por diseño (Snapshot Pattern, RN-04).

**Alternativas consideradas**:
- `UUID[]`: requeriría cast explícito entre el tipo Python (`uuid.UUID`) y el array PostgreSQL; agrega complejidad sin beneficio funcional dado que el array es un snapshot inmutable.
- JSONB: mayor overhead, sin ventaja para un array plano de enteros.

---

### D-20: `RefreshToken.token_hash` — `CHAR(64)`, SHA-256, no UUID en claro

**Decisión**: `token_hash: str = Field(sa_column=Column(CHAR(64), unique=True, nullable=False))`. El backend almacena `hashlib.sha256(token.encode()).hexdigest()` — nunca el token en claro.

**Rationale**: si la BD se compromete, los token_hash no son reutilizables (no son los valores de token originales). `CHAR(64)` es exactamente el tamaño de un hex-digest SHA-256. El campo tiene `unique=True` y `NOT NULL`. Esto es un requerimiento crítico de `docs/CHANGES.md` L80 — **SHA-256, no UUID en claro**.

**Vinculación con Change 06**: la lógica de generación del token (UUID v4 opaco) y su hash se implementa en Change 06 (auth). Este change solo define el modelo de almacenamiento.

---

### D-21: `Pedido.direccion_id` — nullable, `ON DELETE SET NULL`

**Decisión**: `direccion_id: uuid.UUID | None = Field(default=None, foreign_key="direccion_entrega.id", sa_column_kwargs={"ondelete": "SET NULL"})`.

**Rationale**: `NULL` en `direccion_id` es un estado de negocio válido — significa retiro en local. Si la dirección se elimina (soft delete o hard delete eventual), el pedido no pierde su estado histórico: `direccion_id` pasa a NULL. Esto es un requerimiento explícito del Integrador v5.0 (L82) y de `docs/CHANGES.md` L82.

**Alternativa descartada**: `ON DELETE RESTRICT` — bloquearía la eliminación de direcciones si hay pedidos asociados, rompiendo el flujo de negocio.

---

### D-22: `Categoria.parent_id` — FK self-referencial nullable, `ON DELETE SET NULL`

**Decisión**: `parent_id: uuid.UUID | None = Field(default=None, foreign_key="categoria.id", sa_column_kwargs={"ondelete": "SET NULL"})`.

**Rationale**: si se elimina una categoría padre, las subcategorías quedan como categorías raíz (parent_id=NULL) en lugar de desaparecer en cascada. Requerimiento de `docs/CHANGES.md` L85. La CTE recursiva para árbol de categorías es responsabilidad de Change 05 (catalog domain).

---

### D-23: `HistorialEstadoPedido` — append-only, sin `updated_at` en la tabla

**Decisión**: `HistorialEstadoPedido` hereda de `Base` pero la regla append-only (RN-03) se documenta en el modelo y se refuerza en la spec. La presencia de `updated_at` en el modelo base es técnicamente inofensiva — el ORM no hará UPDATE automático a menos que se llame explícitamente. La guarda dura de no-UPDATE/DELETE a nivel DB (trigger o regla PostgreSQL) se defer a Change 18, como indica el task context.

**Rationale**: añadir un trigger en este change complicaría la migración inicial sin beneficio inmediato (aún no hay código que llame UPDATE). El comentario en el modelo es suficiente para Change 04+ que implementará el repository append-only.

---

### D-24: Alembic `env.py` async — patrón run_async_migrations

**Decisión**: `env.py` usa el patrón oficial de Alembic para async engines:

```python
async def run_async_migrations() -> None:
    from app.db.base import SQLModel  # asegura naming_convention
    import app.models  # importa todos los modelos
    connectable = create_async_engine(get_settings().DATABASE_URL)
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())
```

**Alternativa considerada**: usar `sqlalchemy.url` en `alembic.ini` con la URL hardcodeada. Rechazado — viola el patrón D-05 (lazy, sin secrets en config files).

**Rationale**: `get_settings()` ya tiene `@lru_cache` y lee de `.env`; reutilizarlo en `env.py` evita duplicar la URL y garantiza que el mismo `DATABASE_URL` usado en tests y en runtime se use en las migraciones.

#### D-24 Addendum: Engine de Alembic es independiente del engine de runtime

Alembic crea su **propio engine async** dentro de `env.py` vía `create_async_engine(get_settings().DATABASE_URL)`. Este engine es completamente independiente del engine de runtime (`get_engine()` en `app/db/session.py`). Son lifecycles separados y así deben permanecer.

**Lo que comparte**: únicamente `SQLModel.metadata` (importado vía `app.db.base` → `app.models`).

**Lo que NO comparte**:
- `alembic/env.py` NO importa `app.main` ni llama a `get_engine()` del runtime.
- NO se acopla al lifespan de FastAPI ni al `engine.dispose()` del shutdown.
- El engine de migration puede tener pool de tamaño 1 (`pool_size=1`) sin afectar el pool del runtime.

**Razones para la separación**:
1. **Evitar ciclos de import**: `alembic/env.py` no debe importar `app.main` (FastAPI app, routers, middlewares).
2. **Evitar side effects de la app**: logging estructurado, rate limiter (slowapi), y cualquier middleware NO deben activarse durante la ejecución de migrations.
3. **Evitar conflictos de event loop**: Alembic usa su propio `asyncio.run()` con un event loop nuevo; reutilizar un engine creado en un loop diferente puede causar `RuntimeError: This event loop is already running` o `attached to a different loop`.
4. **Independencia de configuración de pool**: en migrations interesa minimizar conexiones (pool=1 es suficiente); en runtime se configura según carga esperada.

**Verificación en apply**: confirmar en `alembic/env.py` que no hay `from app.main import app` ni `from app.db.session import get_engine`.

---

### D-25: `app/models/__init__.py` — re-exports de todos los modelos

**Decisión**: `app/models/__init__.py` importa explícitamente todas las clases de dominio de `user.py`, `address.py`, `catalog.py`, `order.py`. Alembic `env.py` importa `app.models` (este módulo) para que `autogenerate` detecte todas las tablas en `SQLModel.metadata`.

**Rationale**: sin importar los modelos antes de `target_metadata = SQLModel.metadata`, Alembic genera una migración vacía (no detecta las tablas). Este es el error más común con SQLModel + Alembic. El `__init__.py` actúa como registro centralizado de modelos.

---

### D-26: Seed — passlib[bcrypt], no bcrypt puro

**Decisión**: agregar `passlib[bcrypt]` a `[project.dependencies]` en `pyproject.toml`. El seed usa `passlib.context.CryptContext(schemes=["bcrypt"], bcrypt__rounds=12)` para hashear `Admin1234!`.

**Alternativas consideradas**:
- `bcrypt` puro: API de bajo nivel, requiere manejo manual de salt. `passlib[bcrypt]` es el wrapper estándar en proyectos FastAPI, alinea con la rúbrica (sección 12, criterio "Passlib (bcrypt)").
- `argon2-cffi`: más moderno, pero no es el stack declarado en el Integrador v5.0.

**Nota**: `passlib[bcrypt]` también será usado en Change 06 (auth service) para verificar contraseñas en login. Agregarlo ahora evita que Change 06 modifique `pyproject.toml`.

---

### D-27: Schemas Pydantic Read/Create/Update — diferidos a los changes de dominio

**Decisión**: este change NO crea schemas Pydantic por entidad. Los schemas se definen en cada change de dominio (Change 05+) junto con los endpoints que los usan.

**Rationale**: crear schemas en Change 03 sin los endpoints ni los services que los consumen genera código muerto que podría divergir antes de ser usado. La regla de no inflar el change con artefactos que no son estrictamente necesarios para el objetivo del change (ERD + migraciones + seed) aplica aquí. Change 04 (UoW + BaseRepository) tampoco necesita schemas tipados por entidad — solo los tipos SQLModel.

---

### D-28: FK a columna semántica `codigo` con UUID PK preservado

**Decisión** (confirmada por el usuario al resolver OQ-05): los catálogos `EstadoPedido`, `FormaPago` y `Rol` mantienen `id UUID v4` como PK técnica (heredada de `Base`) y exponen `codigo VARCHAR(20) NOT NULL UNIQUE` como clave semántica. Las FK que viajan en la lógica de dominio referencian la columna `codigo`, no el UUID:

- `Pedido.forma_pago_codigo` → `forma_pago.codigo` (UNIQUE, NOT NULL).
- `Pedido.estado_codigo` → `estado_pedido.codigo` (UNIQUE, NOT NULL).
- `HistorialEstadoPedido.estado_desde` → `estado_pedido.codigo` (UNIQUE, NULLABLE).
- `HistorialEstadoPedido.estado_hasta` → `estado_pedido.codigo` (UNIQUE, NOT NULL).

**Rationale**:
- Alineación estricta con `docs/CHANGES.md` L84 y L87: `Pedido.forma_pago_codigo VARCHAR(20) FK semántica` + `EstadoPedido.codigo` con códigos canónicos PENDIENTE/CONFIRMADO/EN_PREP/EN_CAMINO/ENTREGADO/CANCELADO.
- Permite leer payloads y filas de BD sin joins (`SELECT estado_codigo FROM pedido` ya es legible y trazable a la FSM del Change 18).
- Preserva el contrato de `Base` (UUID PK universal — D-04 de Change 02) sin excepción.
- Estable frente a renombres futuros del UUID y sin colisiones con el seed idempotente.

**Soporte ORM/DB**: SQLAlchemy permite FK a cualquier columna con `UNIQUE` (PostgreSQL exige índice único en la columna referenciada, que `unique=True` garantiza). SQLModel propaga `unique=True` correctamente a la migration de Alembic. **Verificación obligatoria en apply** (incorporada como task): `\d pedido` en `psql` debe mostrar las constraints `fk_pedido_forma_pago_codigo_forma_pago` y `fk_pedido_estado_codigo_estado_pedido` apuntando a las columnas `codigo`, no a `id`.

**Trade-off aceptado**: el join por `codigo` cuesta marginalmente más que por UUID indexado, pero es un patrón ya estandarizado para catálogos de baja cardinalidad (< 10 filas cada uno). Aceptable.

**Implicancia en seed**: el seed inserta `EstadoPedido` y `FormaPago` con `codigo` semántico ANTES de cualquier `Pedido`. La idempotencia se valida sobre `codigo` (no UUID): `INSERT ... ON CONFLICT (codigo) DO NOTHING`.

---

---

### D-29: `UsuarioRol` hereda de `Base` completo — sin `BasePivot` ni composite PK

**Decisión**: `UsuarioRol` hereda de `Base` (UUID v4 PK + `created_at` + `updated_at` + `deleted_at`). NO se usa composite PK `(usuario_id, rol_id)`. NO se convierte en pure association table.

**Rationale**:
- **Coherencia con D-04** (UUID PK universal): toda entidad gestionada por el ORM tiene UUID como PK técnica.
- **Uniformidad de la jerarquía de entidades**: `BaseRepository[T]` genérico (Change 04) opera sobre cualquier entidad con PK UUID; si `UsuarioRol` tuviera composite PK, requeriría un `BasePivotRepository` especializado — fragmentación injustificada.
- **Compatibilidad con SQLAlchemy 2.x**: composite PK en SQLModel tiene edge cases con `update()` y `merge()` que no aplican con UUID único.
- **Reducción de excepciones en el ORM**: tener un tipo de PK uniforme simplifica introspección, logging y serialización.
- **Evitar `BasePivot` no justificado**: crear un sub-tipo de `Base` para esta única entidad pivot introduce complejidad sin beneficio observable dada la cardinalidad esperada.

**Trade-off aceptado**: overhead de ~96 bytes/fila por UUID (16 bytes) + `created_at` (8) + `updated_at` (8) + `deleted_at` (8) + nullbitmask. Aceptable — la tabla `usuario_rol` tendrá cardinalidad de pocas decenas de filas (usuarios × roles ≤ 4).

**Implicancia funcional**:
- `deleted_at` queda **dormant** en esta entidad.
- La eliminación de asignaciones de rol es **hard delete operacional** en Change 09 (gestión de roles de usuario): `DELETE FROM usuario_rol WHERE id = ?`.
- La columna `asignado_por_id` es nullable para soportar el caso de bootstrap system-generated (ver D-29 y task 8.4).

**Nota sobre `UniqueConstraint`**: aunque `UsuarioRol` tiene UUID PK, la combinación `(usuario_id, rol_id)` mantiene `UniqueConstraint` explícito para impedir duplicados lógicos — un usuario no puede tener el mismo rol dos veces.

---

### D-30: Relationships SQLModel con parámetros explícitos — política de no-inferencia

**Decisión**: todas las `Relationship()` declaradas en los modelos de este change deben especificar `back_populates`, `foreign_keys`, `primaryjoin` y estrategia `lazy` de forma explícita. No se permite dependencia de la inferencia automática de SQLAlchemy.

**Rationale**:
- **Evitar joins ambiguos**: SQLAlchemy lanza `AmbiguousForeignKeysError` cuando hay múltiples FKs entre dos tablas. Casos críticos en este change:
  - `HistorialEstadoPedido` → `EstadoPedido`: dos FKs (`estado_desde`, `estado_hasta`) a la misma tabla.
  - `HistorialEstadoPedido.cambiado_por` → `Usuario` coexiste con `Pedido.usuario` → `Usuario` en el mismo dominio.
  - `Categoria.parent` → self-reference.
  - `UsuarioRol.asignado_por` → `Usuario` self-reference FK.
- **Evitar N+1 en contexto async**: `lazy="select"` clásico realiza una query SQL síncrona implícita por cada acceso a la relación, lo cual **falla silenciosamente** en sesiones async de SQLAlchemy 2.x (genera `MissingGreenlet` o `greenlet_spawn` error). Solo las estrategias `"selectin"`, `"joined"`, `"noload"` y `"raise"` son seguras en async.
- **No depender de back-population implícita**: `backref=` crea la relación inversa de forma mágica y dificulta el rastreo estático del código.

**Política por tipo de relación**:
- `lazy="selectin"`: para relaciones a-muchos de baja cardinalidad que se acceden frecuentemente (ej: `Usuario.roles`, `Pedido.detalles`).
- `lazy="noload"` o `lazy="raise"`: para relaciones de alto volumen que deben cargarse explícitamente (ej: `Pedido.historial`, `Producto.categorias`).
- `lazy="joined"` (solo para relaciones muchos-a-uno que siempre se incluyen): ej: `DetallePedido.producto` si siempre se serializa junto al detalle.

**Nota**: esta decisión es una política de diseño/spec, no código. Las implementaciones concretas de `Relationship()` se definen en apply (Change 03).

---

### D-31: Campos heredados dormant en entidades pivot y append-only — trade-off de uniformidad

**Decisión**: los campos `updated_at` y `deleted_at` heredados de `Base` quedan dormant (sin semántica funcional) en las entidades pivot (`UsuarioRol`, `ProductoCategoria`, `ProductoIngrediente`) y en la entidad append-only (`HistorialEstadoPedido`). NO se crea `BaseAppendOnly` ni `BasePivot`.

**Entidades afectadas y comportamiento de campos dormant**:

| Entidad | Campo dormant | Por qué dormant |
|---------|--------------|-----------------|
| `UsuarioRol` | `deleted_at` | La eliminación de asignaciones de rol es hard delete (Change 09) |
| `UsuarioRol` | `updated_at` | El registro de rol no se actualiza; se elimina y re-crea |
| `ProductoCategoria` | `deleted_at`, `updated_at` | Mismo patrón: eliminación es hard delete |
| `ProductoIngrediente` | `deleted_at`, `updated_at` | Mismo patrón |
| `HistorialEstadoPedido` | `updated_at` | Entidad append-only: nunca se hace UPDATE (RN-03) |

**Por qué NO se fragmenta la jerarquía**:
- Crear `BaseAppendOnly` para `HistorialEstadoPedido` (la única entidad append-only de todo el ERD) introduce un sub-tipo que no justifica su overhead de documentación y mantenimiento.
- Crear `BasePivot` para 3 entidades pivot introduce complejidad de herencia múltiple con SQLModel que tiene edge cases no documentados oficialmente.
- El costo real del campo dormant es marginal (8 bytes por `NULL` timestamp en PostgreSQL).
- La "guarda dura" de append-only (trigger PostgreSQL) se implementa en Change 18 con la entidad tal como está.

**Implicancia operativa**: el equipo que implemente Change 09 (gestión de roles) debe saber que la eliminación de `UsuarioRol` es siempre `DELETE` (nunca soft delete via `deleted_at`). Esta decisión se documenta en la spec de Change 09.

---

## Risks / Trade-offs

| ID | Riesgo | Mitigación |
|----|--------|------------|
| R-A-01 | Orden de imports en `env.py` de Alembic — si los modelos no se importan antes de `target_metadata`, `autogenerate` detecta 0 tablas | Task explícita de verificación: ejecutar `alembic check` o `alembic upgrade head --sql` y confirmar que el SQL generado incluye todas las tablas |
| R-A-02 | Forward references entre modelos del mismo dominio (p.ej. `Pedido` → `DetallePedido` → `Pedido`) pueden generar errores de SQLModel si los modelos se definen en orden incorrecto | Definir todos los modelos de un dominio en el mismo archivo; usar `TYPE_CHECKING` + `from __future__ import annotations` para forward refs seguras |
| R-A-03 | `Categoria.parent_id` self-referencial puede generar un ciclo en `sqlmodel.metadata` si no se usa `use_alter=True` en la FK | Probar con `alembic upgrade head` en BD limpia; SQLAlchemy/Alembic maneja self-refs nativamente; agregar `use_alter=True` solo si hay error real |
| R-A-04 | El campo `personalizacion: list[int]` en `DetallePedido` requiere `sa_column=Column(ARRAY(Integer))` explícito — SQLModel no genera `ARRAY` automáticamente desde `list[int]` | Definir explícitamente con `from sqlalchemy import ARRAY, Integer` y `sa_column=Column(ARRAY(Integer), nullable=True)` |
| R-A-05 | Downgrade de la migration `0001` requiere `DROP TABLE` en orden inverso a las FK — si el orden es incorrecto, falla con `DependencyError` | Escribir el `downgrade()` con las tablas en orden de dependencia inverso; probar `alembic downgrade base` en CI |
| R-A-06 | `passlib[bcrypt]` puede tener conflicto de versión con `bcrypt` si existe como transitiva | Especificar `passlib[bcrypt]>=1.7.4` en `pyproject.toml`; verificar con `pip check` en CI |
| R-A-07 | El seed del admin usa `Admin1234!` hardcodeado como default — riesgo en producción | Leer de `os.getenv("ADMIN_PASSWORD", "Admin1234!")` en el seed; documentar en `.env.example` que debe cambiarse en producción; agregar warning log si se usa el valor default |
| R-A-08 | `HistorialEstadoPedido` sin guarda dura a nivel DB hasta Change 18 — riesgo de UPDATE/DELETE accidental | Comentario `# APPEND-ONLY: never UPDATE or DELETE` en el modelo; el repository de Change 04 solo expondrá `create()` para esta entidad |

---

## Migration Plan

1. Instalar nueva dependencia: `pip install -e ".[dev]"` tras actualizar `pyproject.toml` (agrega `passlib[bcrypt]`).
2. Crear `backend/.env` si no existe, copiar desde `.env.example` y completar `DATABASE_URL`.
3. Verificar PostgreSQL 15+ corriendo y `foodstore_dev` accesible.
4. Ejecutar `alembic upgrade head` desde `backend/` → crea todas las tablas.
5. Ejecutar `python -m app.db.seed` → carga catálogos y admin.
6. Verificar: `psql foodstore_dev -c "\dt"` lista 16 tablas; `SELECT codigo FROM estado_pedido;` devuelve 6 filas.
7. Test CI: `alembic upgrade head && alembic downgrade base && alembic upgrade head` sobre `foodstore_test`.

**Rollback**: `alembic downgrade base` sobre `foodstore_dev` elimina todas las tablas. La migration es completamente reversible. Los modelos Python pueden eliminarse sin efecto si la BD se revierte.

---

## Open Questions

- **OQ-01 (resuelto)**: ¿`Rol` tiene PK UUID o es solo `codigo VARCHAR(20)`? → PK UUID (hereda de `Base`, decisión D-18). `codigo` es `unique=True`.
- **OQ-02 (resuelto)**: ¿`personalizacion` en `DetallePedido` es `INTEGER[]` o `UUID[]`? → `INTEGER[]` según Integrador v5.0 L139. Los IDs se almacenan como enteros en el snapshot; no son FK reales.
- **OQ-03 (resuelto)**: ¿Los schemas Pydantic se crean en este change? → No. Diferidos a Changes de dominio (D-27).
- **OQ-04 (resuelto)**: ¿`HistorialEstadoPedido` tiene trigger append-only? → No en este change. Comentario en modelo + spec; guarda dura en Change 18.
- **OQ-05 (resuelto)**: `Pedido.forma_pago_codigo`, `Pedido.estado_codigo` y `HistorialEstadoPedido.estado_desde/hasta` son FK a columnas `VARCHAR(20)` no-PK. **Decisión confirmada por el usuario**: mantener UUID v4 como PK técnica y `codigo` como columna semántica con `unique=True`, declarando las FK contra esa columna única. Formalizado en **D-28**. No se demota la PK ni se elimina el UUID.
- **OQ-06 (resuelto)**: ¿`SECRET_KEY` se agrega a `Settings` ahora? → Solo en `.env.example` como preparación. La lógica JWT en `Settings` se implementa en Change 06.
