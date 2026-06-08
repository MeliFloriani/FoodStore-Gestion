## ADDED Requirements

### Requirement: Modelo DireccionEntrega con soft-delete

> **Nota de paths**: El proyecto usa estructura Layer-First (no Feature-First). Los paths `app/modules/direcciones/` en esta spec son referencias conceptuales. El executor SHALL usar: `backend/app/models/direccion_entrega.py` (model), `backend/app/schemas/direccion_entrega.py` (schemas), `backend/app/repositories/direccion_entrega.py` (repository), `backend/app/services/direccion_entrega.py` (service), `backend/app/api/v1/direcciones.py` (router) — siguiendo el patrón establecido en Changes anteriores.

El sistema SHALL tener un modelo SQLModel `DireccionEntrega` en `backend/app/models/direccion_entrega.py` que mapee a la tabla `direccion_entrega`. La tabla SHALL incluir los campos: `id` (BIGSERIAL PK), `usuario_id` (BIGINT FK → `usuario.id`, NN, NOT NULL), `alias` (VARCHAR(50) NULL), `linea1` (TEXT NN), `linea2` (TEXT NULL), `ciudad` (VARCHAR(100) NULL), `provincia` (VARCHAR(100) NULL), `codigo_postal` (VARCHAR(10) NULL), `referencia` (TEXT NULL), `es_principal` (BOOLEAN NN DEFAULT FALSE), `created_at` (TIMESTAMPTZ NN DEFAULT NOW()), `updated_at` (TIMESTAMPTZ NN DEFAULT NOW()), `deleted_at` (TIMESTAMPTZ NULL). El modelo NOT SHALL importar de ninguna capa superior (Service, Router).

#### Scenario: Tabla creada con todos los campos
- **WHEN** se ejecuta la migración Alembic de este change
- **THEN** la tabla `direccion_entrega` existe con todos los campos descritos
- **THEN** `linea1` tiene restricción NOT NULL
- **THEN** `es_principal` tiene DEFAULT FALSE
- **THEN** `deleted_at` es nullable

#### Scenario: Índice parcial único garantiza una sola principal por usuario
- **WHEN** se intenta insertar una segunda fila con `es_principal=true` para el mismo `usuario_id` (con `deleted_at IS NULL`)
- **THEN** la BD rechaza el insert con un error de unicidad
- **THEN** ninguna fila adicional queda persistida

#### Scenario: Índice sobre usuario_id para performance
- **WHEN** se ejecuta una query `SELECT * FROM direccion_entrega WHERE usuario_id = ?`
- **THEN** el query planner usa el índice `ix_direccion_entrega_usuario_id`

---

### Requirement: Schemas Pydantic v2 para DireccionEntrega
El sistema SHALL tener schemas Pydantic v2 en `backend/app/schemas/direccion_entrega.py`:
- `DireccionEntregaCreate`: `linea1` (str, NN, min=3, max=255), `alias` (str|None, max=50), `linea2` (str|None, max=255), `ciudad` (str|None, max=100), `provincia` (str|None, max=100), `codigo_postal` (str|None, max=10), `referencia` (str|None, max=255). El campo `es_principal` NO SHALL estar en Create (lo controla la lógica de servicio).
- `DireccionEntregaUpdate`: todos los campos opcionales excepto `es_principal` (excluido del schema — no editable vía PATCH general).
- `DireccionEntregaRead` SHALL incluir explícitamente: `id`, `usuario_id`, `alias`, `linea1`, `linea2`, `ciudad`, `provincia`, `codigo_postal`, `referencia`, `es_principal`, `created_at`, `updated_at`. NOT SHALL incluir: `deleted_at` (campo de auditoría interna, nunca exponer al cliente).

#### Scenario: Create sin linea1 falla validación
- **WHEN** se envía `POST /api/v1/direcciones` sin el campo `linea1`
- **THEN** el sistema retorna HTTP 422 con detalle del campo requerido

#### Scenario: linea1 con menos de 3 caracteres falla validación
- **WHEN** se envía `POST /api/v1/direcciones` con `linea1 = "AB"`
- **THEN** el sistema retorna HTTP 422

#### Scenario: alias mayor a 50 caracteres falla validación
- **WHEN** se envía `POST /api/v1/direcciones` con `alias` de 51 caracteres
- **THEN** el sistema retorna HTTP 422

#### Scenario: Update parcial sin linea1 es válido
- **WHEN** se envía `PATCH /api/v1/direcciones/{id}` con solo `{"alias": "Trabajo"}`
- **THEN** el sistema acepta el request (HTTP 200) y actualiza solo el campo enviado

---

### Requirement: Repositorio DireccionEntregaRepository
El sistema SHALL tener `DireccionEntregaRepository` en `backend/app/repositories/direccion_entrega.py` que herede de `BaseRepository[DireccionEntrega]`. SHALL implementar los métodos:
- `get_activos_por_usuario(usuario_id: int) -> list[DireccionEntrega]`: filtra `usuario_id = ? AND deleted_at IS NULL`.
- `get_by_id_and_usuario(id: int, usuario_id: int) -> DireccionEntrega | None`: filtra por id + ownership + `deleted_at IS NULL`.
- `count_activos_por_usuario(usuario_id: int) -> int`: cuenta direcciones activas del usuario.
- `limpiar_principal(usuario_id: int) -> None`: `UPDATE SET es_principal=false WHERE usuario_id=? AND es_principal=true AND deleted_at IS NULL`. Los UPDATE deben incluir `updated_at = now()` explícitamente si el ORM no gestiona `onupdate` automáticamente. Preferir actualizar via ORM (SQLModel) para que el trigger `onupdate` funcione; evitar SQL raw directo que bypasee el ORM en estas operaciones.
- `set_principal(id: int) -> None`: `UPDATE SET es_principal=true WHERE id=?`. Misma regla: incluir `updated_at = now()` si no hay `onupdate` automático; preferir ORM sobre SQL raw.
- `get_mas_reciente_activa(usuario_id: int) -> DireccionEntrega | None`: retorna la dirección activa con `created_at` más reciente (para auto-promote).

El repositorio NOT SHALL contener lógica de negocio. NOT SHALL hacer commit ni rollback.

#### Scenario: get_activos_por_usuario excluye soft-deleted
- **WHEN** un usuario tiene 3 direcciones, una con `deleted_at` seteado
- **THEN** `get_activos_por_usuario` retorna solo las 2 activas

#### Scenario: get_by_id_and_usuario retorna None para dirección ajena
- **WHEN** se consulta una dirección que existe pero pertenece a otro usuario
- **THEN** el método retorna `None` (sin levantar excepción)

#### Scenario: limpiar_principal actualiza todas las activas del usuario
- **WHEN** el usuario tiene 2 direcciones con `es_principal=true` (estado de error)
- **THEN** `limpiar_principal` deja ambas con `es_principal=false`

---

### Requirement: Servicio DireccionEntregaService con lógica de negocio
El sistema SHALL tener `DireccionEntregaService` en `backend/app/services/direccion_entrega.py` con lógica de negocio. El service SHALL lanzar `HTTPException`, NEVER el repositorio ni el router. SHALL implementar:

**`crear_direccion(uow, usuario_id, data)`**:
- Verificar que el usuario tiene < 20 direcciones activas; si no, lanzar `HTTPException(400)`.
- El service fuerza `es_principal=True` **internamente** (el campo NO viene del body — `DireccionEntregaCreate` no lo incluye). Lógica:
  1. Contar direcciones activas del usuario: `count = repo.count_activos_por_usuario(usuario_id)`.
  2. Si `count == 0`: forzar `data.es_principal = True` internamente; ejecutar `repo.limpiar_principal(usuario_id)` como medida defensiva (debería ser no-op, pero protege contra estados inconsistentes previos); insertar la nueva dirección.
  3. Si `count > 0`: `data.es_principal` queda en `False` (default); insertar la nueva dirección directamente (NO ejecutar `limpiar_principal` — hacerlo aquí desactivaría la dirección principal existente del usuario sin promover ninguna nueva, violando la invariante RN-DI01).
- Retornar `DireccionEntregaRead`.

**`listar_direcciones(uow, usuario_id)`**: retornar lista de `DireccionEntregaRead`.

**`obtener_direccion(uow, usuario_id, id)`**: obtener por ownership; si no existe, `HTTPException(404)`.

**`actualizar_direccion(uow, usuario_id, id, data)`**: verificar ownership (404 si falla), aplicar update parcial, retornar `DireccionEntregaRead`.

**`marcar_principal(uow, usuario_id, id)`**: verificar ownership (404 si falla). Si ya es principal, retornar idempotentemente. Ejecutar `limpiar_principal` + `set_principal` en el mismo UoW. Retornar `DireccionEntregaRead`.

**`eliminar_direccion(uow, usuario_id, id)`**: verificar ownership (404 si falla). Capturar `era_principal = direccion.es_principal` ANTES de cualquier modificación. Ejecutar soft-delete (`deleted_at=now()`). Si `era_principal == True`: buscar candidata activa más reciente (`deleted_at IS NULL AND id != direccion_id`, orden `created_at DESC`); si existe, ejecutar `repo.set_principal(candidata.id)` directamente (no usar `limpiar_principal` — es no-op post-soft-delete); si no existe candidata, no promover nadie (válido — retiro en local). Retornar `None` (204).

#### Scenario: Primera dirección se marca principal automáticamente
- **WHEN** un usuario sin direcciones activas crea su primera dirección
- **THEN** la dirección se persiste con `es_principal=true`
- **THEN** no se retorna error

#### Scenario: Límite de 20 direcciones activas bloqueado
- **WHEN** un usuario con 20 direcciones activas intenta crear una más
- **THEN** el service lanza `HTTPException(400)` con mensaje de límite alcanzado

#### Scenario: Marcar principal desactiva la anterior
- **WHEN** el usuario tiene dirección A como principal y marca la dirección B
- **THEN** `es_principal` de A queda en `false`
- **THEN** `es_principal` de B queda en `true`
- **THEN** todo ocurre en la misma transacción

#### Scenario: marcar_principal es idempotente
- **WHEN** el usuario ejecuta `PATCH /{id}/principal` sobre una dirección ya principal
- **THEN** el sistema retorna HTTP 200 sin modificar la BD

#### Scenario: Eliminar principal con otras activas promueve la más reciente
- **WHEN** el usuario elimina su dirección principal y tiene otras 2 activas
- **THEN** la dirección activa con `created_at` más reciente queda como `es_principal=true`
- **THEN** la dirección eliminada tiene `deleted_at IS NOT NULL`
- **THEN** todo ocurre en la misma transacción (UoW commit único)

#### Scenario: Eliminar principal sin otras activas deja sin principal
- **WHEN** el usuario elimina su única dirección
- **THEN** la dirección queda con `deleted_at IS NOT NULL`
- **THEN** no queda ninguna dirección activa
- **THEN** no se lanza excepción

#### Scenario: Ownership violation retorna 404
- **WHEN** un usuario autenticado intenta obtener/editar/eliminar/marcar principal una dirección de otro usuario
- **THEN** el service lanza `HTTPException(404)`
- **THEN** la respuesta no revela si la dirección existe

---

### Requirement: Router de DireccionEntrega con endpoints REST
El sistema SHALL tener `router.py` en `backend/app/api/v1/direcciones.py` con los siguientes endpoints, todos con `response_model` explícito y `require_role("CLIENT")`:

| Método | Path | response_model | status_code |
|--------|------|----------------|-------------|
| POST | `/` | `DireccionEntregaRead` | 201 |
| GET | `/` | `list[DireccionEntregaRead]` | 200 |
| GET | `/{id}` | `DireccionEntregaRead` | 200 |
| PATCH | `/{id}/principal` | `DireccionEntregaRead` | 200 |
| PATCH | `/{id}` | `DireccionEntregaRead` | 200 |
| DELETE | `/{id}` | `None` | 204 |

El router NOT SHALL contener lógica de negocio. El `usuario_id` se extrae SIEMPRE del JWT (`current_user.id`), NUNCA del body ni de query params.

> IMPORTANTE: El endpoint `PATCH /{id}/principal` DEBE declararse ANTES de `PATCH /{id}` en el router para evitar ambigüedad de path matching en FastAPI. FastAPI evalúa rutas en orden de declaración.

#### Scenario: POST crea dirección y retorna 201
- **WHEN** un cliente autenticado envía `POST /api/v1/direcciones` con `linea1` válido
- **THEN** el sistema retorna HTTP 201 con `DireccionEntregaRead` incluyendo `id` y `es_principal`

#### Scenario: GET lista retorna solo las del usuario
- **WHEN** un cliente autenticado hace `GET /api/v1/direcciones`
- **THEN** el sistema retorna HTTP 200 con lista de sus propias direcciones
- **THEN** no incluye direcciones de otros usuarios ni soft-deleted

#### Scenario: PATCH /principal sin body retorna 200
- **WHEN** el cliente envía `PATCH /api/v1/direcciones/{id}/principal` sin body
- **THEN** el sistema procesa la solicitud (HTTP 200) sin error de validación de body

#### Scenario: DELETE retorna 204 sin body
- **WHEN** el cliente envía `DELETE /api/v1/direcciones/{id}`
- **THEN** el sistema retorna HTTP 204 con body vacío

#### Scenario: Endpoint rechaza acceso sin token
- **WHEN** se hace cualquier request a `/api/v1/direcciones` sin header `Authorization`
- **THEN** el sistema retorna HTTP 401

#### Scenario: Endpoint rechaza rol no CLIENT
- **WHEN** un usuario con rol `STOCK` hace `GET /api/v1/direcciones`
- **THEN** el sistema retorna HTTP 403
