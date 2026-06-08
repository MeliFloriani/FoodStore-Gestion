## Context

El módulo `DireccionEntrega` es el paso previo al flujo de creación de pedidos (Change 17). Los clientes necesitan guardar, editar y seleccionar una dirección principal antes de realizar un pedido; sin este módulo, la FK `Pedido.direccion_id` no tiene entidad a referenciar. El módulo es Client-scoped: solo el propietario (por `usuario_id` del JWT) puede ver y operar sus propias direcciones. La auth está provista por Change 07 (`get_current_user`, `require_role`).

**Estado actual**: no existen los archivos de backend (`backend/app/models/direccion_entrega.py`, `backend/app/schemas/direccion_entrega.py`, `backend/app/repositories/direccion_entrega.py`, `backend/app/services/direccion_entrega.py`, `backend/app/api/v1/direcciones.py`) ni los de frontend en `frontend/src/entities/direccion-entrega/`. La tabla `direccion_entrega` no existe en la base de datos.

**Constraints**: ERD v5 define la tabla con soft-delete (`deleted_at TIMESTAMPTZ NULL`) y la FK `Pedido.direccion_id` con `ON DELETE SET NULL`. Cualquier diseño debe ser compatible con esa FK ya planificada en Change 17.

## Goals / Non-Goals

**Goals:**
- CRUD completo de `DireccionEntrega` con validación de ownership (usuario_id del JWT).
- Garantizar invariante de una sola dirección principal por usuario mediante transacción + índice parcial único (doble red de seguridad).
- Primera dirección del usuario se marca automáticamente como principal (RN-DI01).
- Al eliminar la principal, promover automáticamente la más reciente activa (si existe) en la misma transacción.
- Endpoint dedicado idempotente `PATCH /{id}/principal`.
- Soft-delete para preservar integridad referencial con pedidos históricos.
- Página frontend `/addresses` con lista, formulario crear/editar, marcar principal y eliminar con confirmación.
- Soporte explícito del flujo "sin dirección" (retiro en local): la dirección es opcional en el modelo de Pedido.

**Non-Goals:**
- Integración con creación de pedido (Change 17).
- Snapshot de dirección en pedido (Change 17).
- Cambios al modelo `Pedido` o su FK `direccion_id` (ya definida en ERD v5).
- Carrito de compras (Change 15).
- Gestión de zonas de envío o costos variables por dirección (futuro).
- CRUD de direcciones desde el panel de administración.
- **Validación de pedidos activos al eliminar dirección (US-027)**: el criterio de aceptación de US-027 requiere validar que la dirección no tenga pedidos activos antes de eliminar. Esta validación está out-of-scope para Change 14 porque: el módulo `Pedido` no existe en BD en el momento de este change; la FK `Pedido.direccion_id` con `ON DELETE SET NULL` (ERD v5 §3.3) gestiona la integridad referencial. La validación de pedidos activos se implementará en Change 17 (`order-creation-with-snapshots`) o como extensión del endpoint DELETE en ese sprint.

## Decisions

### D-01: Ownership — 404 en lugar de 403

**Decisión**: cuando una dirección existe pero no pertenece al usuario autenticado, el service retorna `HTTPException(404)`, nunca `403`.

**Rationale**: devolver `403` confirma la existencia del recurso, lo que filtra información a actores maliciosos (information leakage). Retornar `404` trata las direcciones ajenas como si no existieran desde la perspectiva del usuario que consulta, sin revelar si el `id` es válido para otro usuario.

**Implementación**: el repositorio hace `SELECT ... WHERE id = ? AND usuario_id = ? AND deleted_at IS NULL`. Si no retorna resultado, el service lanza `HTTPException(status_code=404, detail="Dirección no encontrada")`.

---

### D-02: Transacción para `es_principal` — lógica + índice parcial (doble red)

**Decisión**: implementar DOS capas de garantía para la invariante "solo una dirección principal por usuario":

**Capa 1 — Lógica de servicio (operación normal)**:
```python
# Dentro del mismo UoW (misma sesión de BD):
# Paso 1: desactivar principal anterior
await uow.direcciones.limpiar_principal(usuario_id=current_user.id)
# Paso 2: activar la nueva
await uow.direcciones.set_principal(direccion_id=id)
# UoW hace COMMIT atómico al salir del context manager
```

**Capa 2 — Índice parcial único en PostgreSQL (red de seguridad)**:
```sql
CREATE UNIQUE INDEX ix_direccion_entrega_principal_unico
    ON direccion_entrega (usuario_id)
    WHERE es_principal AND deleted_at IS NULL;
```

**Justificación**: la lógica del service es la ruta normal de ejecución, eficiente y clara. El índice parcial es la red de seguridad que hace imposible violar la invariante incluso bajo condiciones de carrera (race conditions), bugs en migraciones futuras o acceso directo a la BD. La combinación es la práctica recomendada para invariantes críticas de unicidad.

---

### D-03: Primera dirección = principal automática (RN-DI01)

**Decisión**: al crear una dirección, el service verifica si el usuario ya tiene direcciones activas. Si no tiene ninguna (`COUNT(*) WHERE usuario_id = ? AND deleted_at IS NULL == 0`), fuerza `es_principal = True` independientemente del valor enviado en el body.

**Implementación**: la verificación ocurre DENTRO del UoW (misma transacción), antes del INSERT, para evitar race conditions con creaciones concurrentes (el índice parcial único es la última línea de defensa).

---

### D-04: Eliminación de la principal — auto-promote (US-027 / RN-DI01)

**Decisión**: si el cliente elimina su dirección principal y tiene otras direcciones activas, el sistema promueve automáticamente la de `created_at` más reciente como nueva principal, dentro de la misma transacción UoW.

**Rationale**: mantener la experiencia fluida — el usuario no queda en estado inconsistente. Si no quedan otras direcciones activas, el campo `es_principal` queda vacío (ninguna dirección es principal), lo cual es válido porque la dirección es opcional en el modelo de Pedido (retiro en local).

**Flujo `eliminar_direccion(direccion_id, usuario_id)`** (todo en el mismo UoW):
1. Obtener la dirección. Verificar ownership (404 si no existe o es de otro usuario).
2. Capturar `era_principal = direccion.es_principal` ANTES de cualquier modificación.
3. Ejecutar soft-delete: `direccion.deleted_at = now()`.
4. Si `era_principal == True`:
   a. Buscar candidata: dirección activa del usuario más reciente (`deleted_at IS NULL AND id != direccion_id`, ordenar por `created_at DESC`, tomar la primera).
   b. Si existe candidata: ejecutar `repo.set_principal(candidata.id)` directamente (sin `limpiar_principal` — es no-op post-soft-delete y puede omitirse).
   c. Si NO existe candidata: no promover nadie. El usuario queda sin dirección principal (válido — retiro en local).
5. COMMIT en UoW. Retornar 204.

---

### D-05: Soft delete vs hard delete

**Decisión**: **soft delete** con campo `deleted_at TIMESTAMPTZ NULL`.

**Política FK usuario_id → ON DELETE RESTRICT**
- Las direcciones usan soft-delete (`deleted_at`). No deben borrarse físicamente por CASCADE.
- `RESTRICT` protege trazabilidad y consistencia histórica.
- Si en el futuro se necesita purgar un usuario hard-deleted, el proceso debe primero soft-delete o reasignar sus direcciones manualmente.

**Pros del soft delete**:
- Preserva trazabilidad y auditoría (se puede ver qué dirección se usó en pedidos históricos).
- Compatible con la FK `Pedido.direccion_id ON DELETE SET NULL` (ERD v5 §3.3) — el hard delete activaría el SET NULL en pedidos existentes, lo cual es correcto a nivel BD pero pierde la referencia de qué dirección se usó.
- Permite recuperación de direcciones eliminadas por error (UX).
- Patrón consistente con otros módulos del proyecto (Categoría, Producto, Usuario).

**Contras y mitigación**:
- Requiere filtrar `deleted_at IS NULL` en todas las queries → el índice parcial único ya lo incluye; el repositorio aplica el filtro en el método `get_activos_por_usuario`.
- Aumenta levemente el tamaño de la tabla → aceptable dado el volumen esperado.

---

### D-06: Validaciones de schema (Pydantic v2)

| Campo | Tipo | Restricciones |
|-------|------|---------------|
| `alias` | `str \| None` | `max_length=50`, opcional |
| `linea1` | `str` | `min_length=3`, `max_length=255`, NN |
| `linea2` | `str \| None` | `max_length=255`, opcional |
| `ciudad` | `str \| None` | `max_length=100`, opcional |
| `provincia` | `str \| None` | `max_length=100`, opcional |
| `codigo_postal` | `str \| None` | `max_length=10`, opcional |
| `referencia` | `str \| None` | `max_length=255`, opcional |
| `es_principal` | `bool` | NN, default `False` — gestionado internamente por el service (NO incluido en `DireccionEntregaCreate`, NO editable vía PATCH general) |

El schema `DireccionEntregaUpdate` tiene todos los campos opcionales (PATCH parcial). `es_principal` no es editable vía PATCH general — se usa el endpoint dedicado `PATCH /{id}/principal`. El campo `es_principal` tampoco está en `DireccionEntregaCreate` — el service lo fuerza internamente según la lógica de primera dirección.

---

### D-07: PATCH parcial vs PUT para edición

**Decisión**: PATCH parcial con `DireccionEntregaUpdate` (todos los campos opcionales). No implementar PUT.

**Rationale**: el cliente puede editar solo el `alias` sin necesidad de reenviar toda la dirección. PATCH es más eficiente en red y reduce errores de sobrescritura inadvertida.

**Regla adicional**: el campo `es_principal` está EXCLUIDO del schema `DireccionEntregaUpdate`. Intentar setearlo vía PATCH general retornará `422`. Solo el endpoint dedicado `PATCH /{id}/principal` gestiona este flag.

---

### D-08: Sin obligatoriedad en Pedido

**Decisión**: este change NO altera el modelo `Pedido`. El campo `Pedido.direccion_id` es `NULLABLE` con `ON DELETE SET NULL`, ya definido en ERD v5 §3.3, y será consumido por Change 17.

**Implicación de UX**: la página `/addresses` incluye un banner informativo cuando el usuario no tiene direcciones: "Sin dirección guardada. Podés retirar tu pedido en nuestro local." Esto elimina la ansiedad del usuario que no quiere o no puede registrar una dirección.

---

### D-09: Extensibilidad futura (coordenadas, zona de envío)

**Decisión**: el modelo actual NO incluye campos de logística (lat, lon, zona_envio_id). Se documentan como campos futuros añadibles vía `ALTER TABLE` sin breaking changes.

**Future-proofing**: la tabla se crea con columnas de auditoría estándar (`created_at`, `updated_at`) y soft-delete (`deleted_at`). Los campos adicionales de logística son `NULLABLE` por naturaleza, por lo que su adición futura no requiere downtime (PostgreSQL ADD COLUMN NULL es instantáneo).

---

### D-10: Rate limiting — máximo de direcciones por usuario

**Decisión**: soft-limit en service de **20 direcciones activas** por usuario.

**Implementación**: al intentar crear una nueva dirección, el service cuenta `SELECT COUNT(*) WHERE usuario_id = ? AND deleted_at IS NULL`. Si `count >= 20`, lanza `HTTPException(400, detail="Límite máximo de direcciones alcanzado (20).")`.

**Rationale**: previene abuso de la API y el almacenamiento. El valor 20 es pragmático (ningún usuario real necesita más de 20 direcciones guardadas). Configurable a futuro via env var o tabla de configuración.

---

## API Contract

| Método | Ruta | Auth | Status OK | Notas |
|--------|------|------|-----------|-------|
| `POST` | `/api/v1/direcciones` | CLIENT | 201 | Crea dirección. Si es la 1ra activa del usuario → fuerza `es_principal=true`. Límite: 20 activas. |
| `GET` | `/api/v1/direcciones` | CLIENT | 200 | Lista direcciones activas del usuario autenticado (`deleted_at IS NULL`). |
| `GET` | `/api/v1/direcciones/{id}` | CLIENT | 200 / 404 | Detalle. 404 si `id` no existe o no pertenece al usuario (ownership). |
| `PATCH` | `/api/v1/direcciones/{id}` | CLIENT | 200 / 404 / 422 | Edición parcial. `es_principal` excluido del schema. |
| `PATCH` | `/api/v1/direcciones/{id}/principal` | CLIENT | 200 / 404 | Marca principal en transacción atómica. Sin body. Idempotente (si ya es principal, retorna 200 sin modificar). |
| `DELETE` | `/api/v1/direcciones/{id}` | CLIENT | 204 / 404 | Soft-delete. Si era principal y quedan activas → auto-promote en la misma transacción. |

**Errores estándar** (RFC 7807 via `backend-error-handling`):
- `404`: Dirección no encontrada (o no es del usuario).
- `422`: Validación de schema fallida.
- `400`: Límite de 20 direcciones alcanzado.

---

## Risks / Trade-offs

| Riesgo | Mitigation |
|--------|-----------|
| Race condition al crear dos direcciones simultáneamente (ambas podrían ser las "primeras") | El índice parcial único `ix_direccion_entrega_principal_unico` es la red de seguridad; una de las dos transacciones fallará con `IntegrityError` y el service retornará 400. |
| Race condition al marcar principal simultáneamente desde dos sesiones | Misma mitigación: el índice parcial único impide que dos filas tengan `es_principal=true` para el mismo usuario. La lógica en service usa UoW con transacción serializable implícita en PostgreSQL. |
| Auto-promote puede promover una dirección obsoleta al eliminar la principal | Se selecciona la más reciente (`ORDER BY created_at DESC LIMIT 1`). El usuario puede cambiarla después con `PATCH /{id}/principal`. |
| Soft-delete acumula filas históricas | Aceptable dado el límite de 20 activas. Las filas soft-deleted son auditables. Se puede añadir una tarea de purge a futuro. |
| `Pedido.direccion_id` apunta a una dirección soft-deleted | Es correcto y esperado: los pedidos históricos mantienen la referencia. `ON DELETE SET NULL` solo aplica si se hace hard-delete (que no ocurre en este diseño). |

---

## Migration Plan

1. Generar migración Alembic: `alembic revision --autogenerate -m "create_direccion_entrega"`.
2. Revisar el archivo generado — asegurarse de que incluye:
   - `CREATE TABLE direccion_entrega` con todos los campos.
   - `CREATE UNIQUE INDEX ix_direccion_entrega_principal_unico ON direccion_entrega (usuario_id) WHERE es_principal AND deleted_at IS NULL`.
   - `CREATE INDEX ix_direccion_entrega_usuario_id ON direccion_entrega (usuario_id)`.
3. Ejecutar `alembic upgrade head` en ambiente de desarrollo.
4. Rollback: `alembic downgrade -1` (ejecuta `drop_table('direccion_entrega')`).

**Zero downtime**: la tabla es nueva, no hay ALTER TABLE sobre tablas existentes. No hay data migration.

---

## Open Questions

- ¿Se necesita paginación en `GET /api/v1/direcciones`? Dado el límite de 20, la respuesta completa es siempre manejable. **Decisión: no paginar — retornar lista completa.**
- ¿El PATCH general (`/api/v1/direcciones/{id}`) puede actualizar todos los campos excepto `es_principal`? **Sí — todos los campos del schema `DireccionEntregaUpdate` son editables excepto `es_principal` (excluido del schema).**
- ¿`alias` es obligatorio? **No — es `NULL`able. El usuario puede omitirlo.**
