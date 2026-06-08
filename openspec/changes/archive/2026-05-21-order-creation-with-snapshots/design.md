## Context

Change 16 (`pre-checkout-validations`, archivado 2026-05-20) implementó un endpoint consultivo `POST /api/v1/pedidos/validar` que informa al cliente sobre el estado de su carrito (precios, stock, disponibilidad) sin crear ni reservar nada. Ese change documentó explícitamente en D-01 y D-10 que la ventana TOCTOU es intencional y que Change 17 debe re-ejecutar todas las validaciones con garantía transaccional.

Este change implementa la contraparte transaccional: `POST /api/v1/pedidos` que crea el pedido de forma atómica, re-validando todo dentro de la UoW con `SELECT FOR UPDATE` para eliminar condiciones de carrera.

**Estado actual de modelos**: Los modelos `Pedido`, `DetallePedido`, `HistorialEstadoPedido`, `EstadoPedido`, `FormaPago` ya existen en BD desde Change 03. Los repos `BaseRepository` y el patrón UoW están desde Change 04. Los repos `ProductoRepository` (con `get_by_ids`) están desde Change 11/16. Los repos de `DireccionEntrega` están desde Change 14.

## Goals / Non-Goals

**Goals:**
- `POST /api/v1/pedidos` atómico con validaciones transaccionales completas.
- Snapshots inmutables de `nombre_snapshot` + `precio_snapshot` por línea (RN-04 v5).
- Registro de FK `direccion_id` si no es NULL (sin snapshot de campos de dirección — deuda OQ-01 para Change 20).
- Retiro en local (`direccion_id = NULL`) como opción válida con `costo_envio = 0.00`.
- Primer asiento `HistorialEstadoPedido` con `estado_desde = NULL`, `estado_hacia = PENDIENTE` (RN-02).
- Limpieza del carrito en frontend post-éxito.
- Tests de concurrencia para SELECT FOR UPDATE.

**Non-Goals:**
- Pagos reales (Change 19).
- FSM posterior a PENDIENTE (Change 18).
- Cancelación (Change 18).
- Panel de pedidos (Change 20).
- Confirmación por email.

## Decisions

### D-01: Change 16 es consultivo — Change 17 NO confía en él

**Decisión**: Change 17 re-ejecuta TODAS las validaciones (stock, disponibilidad, personalización, forma de pago, dirección) dentro de su propio `UnitOfWork` con `SELECT FOR UPDATE`. No invoca ni llama el service de Change 16.

**Rationale**: La ventana TOCTOU entre la llamada a `/pedidos/validar` (Change 16) y la creación del pedido puede ser de segundos a minutos — tiempo suficiente para que otro cliente agote el stock o para que un admin desactive un producto. Confiar en el resultado de Change 16 como precondición equivaldría a asumir que el estado de la BD no cambia entre esas dos llamadas, lo cual es incorrecto en un sistema concurrente. La garantía de consistencia solo puede darse dentro de la misma transacción con `SELECT FOR UPDATE`.

**Consecuencia**: Si el frontend lleva al usuario desde `/checkout/review` (Change 16) hasta la confirmación sin re-verificar, y en ese lapso el stock se agota, `POST /api/v1/pedidos` devolverá 409 `INSUFFICIENT_STOCK`. El frontend debe manejar este error transaccional y mostrar retroalimentación al usuario.

**Alternativa considerada**: Pasar el resultado de Change 16 al body de `POST /api/v1/pedidos` como "validación pre-procesada". Rechazada: el frontend puede manipular ese resultado o simplemente ser stale. El backend no puede confiar en datos computados por el cliente.

---

### D-02: SELECT FOR UPDATE — lock pesimista en validación de stock

**Decisión**: Dentro de la UoW de creación de pedido, antes de crear cualquier entidad, el service ejecuta un `SELECT ... FOR UPDATE` sobre los registros `Producto` correspondientes a los items del carrito. El lock se mantiene hasta el `COMMIT` del UoW.

**Dónde vive**: En un método `lock_for_update(ids: list[UUID]) -> list[Producto]` del `PedidoRepository` (o en un método del `ProductoRepository` — ver D-09). Este método ejecuta `SELECT * FROM producto WHERE id IN (:ids) FOR UPDATE`.

**Cómo previene overselling**: Si dos requests concurrentes intentan crear pedidos para el mismo producto con stock = 1, la segunda transacción queda bloqueada en el `SELECT FOR UPDATE` hasta que la primera haga `COMMIT` o `ROLLBACK`. Cuando la segunda transacción avanza, ve el stock actualizado (ya decrementado por la primera) y rechaza correctamente.

**Por qué pesimista y no optimista**:

| Criterio | Pessimistic (SELECT FOR UPDATE) | Optimistic (version counter) |
|---|---|---|
| Implementación | Nativa PostgreSQL, sin cambios de modelo | Requiere campo `version` en `Producto` + lógica de retry |
| Comportamiento en contención alta | Bloquea — serializa | Falla con `StaleDataError` — requiere retry en app |
| Riesgo de starvation | Bajo (el primero siempre avanza) | Alto si muchos reintentos simultáneos |
| Complejidad | Baja — 1 query con `FOR UPDATE` | Alta — manejo de retry, exponential backoff |
| Fit con UoW | Natural — el lock se libera con `COMMIT` del UoW | Requiere 2 queries extra (read + compare version) |

**Conclusión**: Pessimistic locking es la opción correcta para este caso de uso (carrito de comida — stock limitado, contención posible en platos populares, latencia de transacción baja).

**Test specification**: Ver D-11 para la especificación del test de concurrencia.

---

### D-03: Snapshots nombre_snapshot + precio_snapshot — inmutabilidad histórica

**Decisión**: Al crear cada `DetallePedido`, se copian `producto.nombre` → `nombre_snapshot` y `producto.precio_base` → `precio_snapshot`. Estos campos son escritura única (write-once): nunca se actualizan. Las queries de lectura de detalle de pedido leen estos snapshots, no hacen JOIN a `Producto`.

**Rationale (RN-04 v5)**: Un pedido creado hoy con "Pizza Margherita" a $850.00 debe seguir mostrando ese nombre y precio aunque el producto sea renombrado a "Pizza Clásica" o su precio cambie a $950.00 mañana. La inmutabilidad del historial es un requisito funcional del sistema, no un detalle de implementación.

**Implicación en schemas**: `DetallePedidoRead` expone `nombre_snapshot` y `precio_snapshot` (string decimal), no el nombre o precio actual del producto. Los campos son `DECIMAL(10,2)` en BD → `Decimal` en Python → `string` en JSON (vía `@field_serializer` siguiendo el patrón de Change 11).

---

### D-04: direccion_id = NULL → retiro en local

**Decisión**: Si `direccion_id` es `NULL` en el request, el pedido es de retiro en local. Esta es una opción válida. El sistema NO rechaza pedidos sin dirección. `Pedido.direccion_id` se persiste como `NULL`. `Pedido.costo_envio` se persiste como `0.00`.

**Rationale**: El modelo `Pedido.direccion_id` ya es nullable con `ON DELETE SET NULL` (desde Change 03). El Integrador v5.0 documenta explícitamente "NULL = retiro en local válido". El frontend no debe obligar al usuario a tener una dirección registrada para confirmar un pedido.

**Dirección en v1 — solo FK nullable**: Si `direccion_id` es NOT NULL, se persiste únicamente la FK en `Pedido.direccion_id`. No se copian campos de dirección al pedido (no hay `direccion_linea1_snapshot`, `ciudad_snapshot`, etc.). El modelo `Pedido` de Change 03 no tiene esas columnas y Change 17 no introduce migraciones. Si la dirección es eliminada post-pedido, `Pedido.direccion_id` pasa a NULL por `ON DELETE SET NULL` — esto es aceptable en v1 y está documentado como deuda técnica OQ-01. El snapshot completo de campos de dirección es responsabilidad de Change 20.

---

### D-05: costo_envio = 50.00 (envío) vs 0.00 (retiro)

**Decisión**: El costo de envío se calcula server-side:
- `direccion_id` NOT NULL → `costo_envio = Decimal("50.00")`
- `direccion_id` IS NULL → `costo_envio = Decimal("0.00")`

El frontend no envía `costo_envio` en el request. El backend lo ignora si se envía.

**Rationale**: El Integrador v5.0 documenta `costo_envio DECIMAL(10,2) default 50.00` con la nota "Valor fijo v1. Documentado." El cálculo server-side es necesario para evitar que el frontend manipule el costo de envío. La regla es simple y testeable: retiro en local = 0.00, envío con dirección = 50.00.

**Testabilidad**: Un test puede verificar exactamente:
- Request con `direccion_id=None` → `pedido.costo_envio == Decimal("0.00")`
- Request con `direccion_id=<valid-uuid>` → `pedido.costo_envio == Decimal("50.00")`

---

### D-06: Forma de pago — validación contra catálogo habilitado=true

**Decisión**: El service valida que `forma_pago_codigo` existe en la tabla `FormaPago` y que `habilitado = true`. Si el código no existe o `habilitado = false`, se rechaza con 400 `PAYMENT_METHOD_INVALID`. Esta validación ocurre dentro de la UoW, antes de crear el `Pedido`.

**Rationale**: Un administrador puede deshabilitar `MERCADOPAGO` temporalmente (ej: mantenimiento de la integración). El sistema debe respetar esa decisión sin requerir una migración ni un deploy. La tabla `FormaPago` ya existe con seed `MERCADOPAGO | EFECTIVO | TRANSFERENCIA` (Change 03). `habilitado=true` para todos en el seed inicial.

**Importante**: No se procesa ningún pago real en este change. `forma_pago_codigo` es solo un atributo del pedido que identifica la forma de pago elegida. El procesamiento real ocurre en Change 19.

---

### D-07: Rollback — atomicidad total con UoW único

**Decisión**: Toda la operación de creación de pedido ocurre dentro de un único `async with UnitOfWork() as uow:`. Si cualquier validación falla (stock insuficiente, personalización inválida, etc.) o cualquier INSERT falla, el UoW hace rollback automático y ningún dato se persiste.

**Orden de operaciones dentro de la UoW** (contrato inmutable):
1. `lock_productos_for_update(producto_ids)` — SELECT FOR UPDATE sobre todos los productos del carrito.
2. Validar carrito no vacío (pre-check antes de abrir UoW es OK, pero la validación formal ocurre aquí).
3. Para cada producto: validar `deleted_at IS NULL`, `disponible=True`, `stock_cantidad >= cantidad`.
4. Validar personalización: `es_removible=True` y pertenencia al producto (batch query ProductoIngrediente).
5. Validar `forma_pago_codigo` contra catálogo (sin lock — `FormaPago` no tiene contención).
6. Validar `direccion_id` ownership si NOT NULL.
7. Calcular totales: `subtotal = Σ(precio_base × cantidad)`, `costo_envio = 50.00 | 0.00`, `total = subtotal + costo_envio`.
8. `CREATE Pedido` con `estado_codigo="PENDIENTE"`, totales calculados, `flush()` para obtener `pedido.id`.
9. `CREATE DetallePedido[]` por cada item con `nombre_snapshot`, `precio_snapshot`, `personalizacion` (UUID[]).
10. `DECREMENT stock_cantidad` en cada producto (UPDATE atómico).
11. `CREATE HistorialEstadoPedido` con `estado_desde=NULL`, `estado_hacia="PENDIENTE"`, `pedido_id`.
12. UoW `COMMIT` — todo persiste de una vez.

**Invariante crítico**: Si el paso 6 falla porque una dirección no pertenece al usuario, el UoW hace rollback y NINGUNO de los INSERTs del paso 8-11 ocurre.

---

### D-08: Catálogo de errores con HTTP status mapeado

| Código | HTTP | Cuándo |
|---|---|---|
| `CART_EMPTY` | 400 | `items` vacío o no enviado |
| `PRODUCT_NOT_FOUND` | 400 | `producto_id` no existe en BD |
| `PRODUCT_NOT_AVAILABLE` | 400 | `producto.deleted_at IS NOT NULL` o `disponible=False` |
| `INSUFFICIENT_STOCK` | 409 | `stock_cantidad < cantidad` (post-lock) |
| `INVALID_CUSTOMIZATION` | 400 | Ingrediente no existe, no es `es_removible=True`, o no pertenece al producto |
| `PAYMENT_METHOD_INVALID` | 400 | `forma_pago_codigo` no existe o `habilitado=False` |
| `ADDRESS_NOT_OWNED` | 403 | `direccion_id` existe pero `usuario_id` ≠ usuario del JWT |
| `ADDRESS_NOT_FOUND` | 400 | `direccion_id` no existe en BD (no es soft-deleted — es inexistente) |

Todos los errores siguen el formato RFC 7807: `{ "detail": "<mensaje>", "code": "<CODIGO>", "field": "<campo opcional>" }`.

**Elección de 409 para INSUFFICIENT_STOCK**: HTTP 409 Conflict es el status correcto para un conflicto de estado de recurso (stock insuficiente = el recurso no puede satisfacer la solicitud en su estado actual). HTTP 400 sería incorrecto porque el request está bien formado.

---

### D-09: Schemas de request y response

**Request** (`PedidoCreate`):
```
PedidoCreate {
  items: list[ItemPedidoCreate]   -- min_length=1
  forma_pago_codigo: str           -- código semántico: "MERCADOPAGO" | "EFECTIVO" | "TRANSFERENCIA"
  direccion_id: UUID | None        -- None = retiro en local
  notas: str | None                -- texto libre, optional
}

ItemPedidoCreate {
  producto_id: UUID               -- ID del producto
  cantidad: int                   -- ≥ 1
  exclusiones: list[UUID]         -- UUIDs de ingredientes excluidos — puede ser []
}
```

**Response** (`PedidoRead`):
```
PedidoRead {
  id: UUID
  usuario_id: UUID
  estado_codigo: str                        -- "PENDIENTE"
  forma_pago_codigo: str
  direccion_id: UUID | None
  subtotal: str                             -- Decimal como string "250.00"
  costo_envio: str                          -- "50.00" o "0.00"
  total: str                                -- string decimal
  notas: str | None
  items: list[DetallePedidoRead]
  historial: list[HistorialEstadoPedidoRead]
  created_at: datetime
}

DetallePedidoRead {
  id: UUID
  producto_id: UUID
  nombre_snapshot: str
  precio_snapshot: str             -- Decimal como string
  cantidad: int
  personalizacion: list[UUID]      -- UUIDs de ingredientes excluidos (puede ser [])
}

HistorialEstadoPedidoRead {
  id: UUID
  estado_desde: str | None         -- None para el primer registro
  estado_hacia: str
  motivo: str | None
  created_at: datetime
}
```

**Wire format para montos**: `DECIMAL(10,2)` en BD → `Decimal` en Python → `string` en JSON vía `@field_serializer`. Sigue el mismo patrón que `precio_base` en Change 11.

**Nota R-01 — Tipo de exclusiones (UUID, no int)**: El campo `exclusiones` en `ItemPedidoCreate` y `personalizacion` en `DetallePedidoRead` usan `UUID`, **no `int`**. Rationale: `Ingrediente.id` es UUID (hereda de `Base`) y `ProductoIngredienteRead.ingrediente_id: UUID` según la spec de Change 11. El `cartStore.personalizacion` almacena UUIDs como `string[]` desde Change 15. La columna `DetallePedido.personalizacion` del Integrador v5.0 dice `INTEGER[]` — esto es un artefacto de la spec original (BIGSERIAL era el tipo de PK antes de la migración UUID-first del proyecto). El apply de Change 17 debe implementar `personalizacion` como `ARRAY(UUID)` o equivalente para ser coherente con el modelo. Si la columna ya existe como `ARRAY(Integer)` en la BD de test, se requiere una migration de tipo en Change 17 o en Change 18 (deuda técnica). No usar `parseInt` en el frontend — convertiría UUIDs a NaN.

---

### D-10: Concurrencia — especificación del test SELECT FOR UPDATE

**Test de concurrencia (especificación)**:

```python
# test_concurrent_order_creation.py

async def test_select_for_update_prevents_overselling():
    """
    GIVEN un producto con stock_cantidad = 1
    WHEN dos transacciones concurrentes intentan crear un pedido para ese producto
    THEN solo una tiene éxito y la otra recibe INSUFFICIENT_STOCK (409)
    THEN el stock final es 0 (no negativo)
    """
    # Setup: producto con stock = 1
    # Spawn dos corutinas que llaman crear_pedido concurrentemente
    # Usar asyncio.gather() con return_exceptions=True
    # Assertion: exactamente 1 successo, exactamente 1 fallo con código INSUFFICIENT_STOCK
    # Assertion: product.stock_cantidad == 0 post-operación
```

Este test debe ejecutarse contra una BD real (no mock), usando PostgreSQL en modo test. No puede verificarse con mocks porque la garantía la da el motor de BD, no la lógica de aplicación. El test de concurrencia requiere `pytest-asyncio` y fixture de BD compartida entre corutinas (no aisladas por transacción individual).

---

### D-11: Totales calculados server-side — el frontend NO fija totales

**Decisión**: El frontend NO envía `subtotal`, `costo_envio`, `total` en el request. El backend los calcula a partir de `precio_base` del producto (no del precio que el frontend percibe en el carrito). Si el precio del producto cambió entre que el usuario lo agregó al carrito y que confirmó el pedido, el pedido se crea con el precio actualizado (y el snapshot registra ese precio actualizado, no el del carrito del frontend).

**Rationale**: Calcular totales en el backend garantiza consistencia: el total del pedido siempre coincide con los `precio_snapshot` de sus líneas. Confiar en los totales del frontend abre la puerta a manipulaciones maliciosas o simplemente a datos stale del carrito.

---

### D-12: Naming — módulos y archivos

Para coexistir con el módulo `pedidos_validar` de Change 16:

- Service de creación: `backend/app/services/pedidos_service.py` (función `crear_pedido`)
- Repository: `backend/app/repositories/pedido.py` → `PedidoRepository`
- Schemas: `backend/app/schemas/pedidos.py` (agregar `PedidoCreate`, `PedidoRead`, `DetallePedidoRead`, `HistorialEstadoPedidoRead`)
- Router: `backend/app/api/v1/pedidos.py` → `pedidos_router`
- El router se monta con `prefix="/pedidos"` y `tags=["pedidos"]` — el `pedidos_validar_router` ya montado NO se ve afectado porque su path interno es `/validar`.

---

### D-13: Frontend — clearCart() post-éxito

**Decisión**: `cartStore.clearCart()` ya existe en la spec de Change 15 (archivada). El hook `useCreateOrder()` llama `clearCart()` en el callback `onSuccess` del `useMutation`. No se requiere modificar la spec de `frontend-cart-store`.

**Rationale**: La spec de Change 15 ya documenta `clearCart(): void — resets items to []`. La action existe y tiene el comportamiento correcto. Solo hay que invocarla desde el hook de checkout en el evento de éxito.

---

## Risks / Trade-offs

**[Risk] Lock contention en productos populares**: Un plato muy demandado puede generar cola de locks. Mitigación: Las transacciones de creación de pedido son cortas (< 100ms en condiciones normales). El lock se libera inmediatamente con el COMMIT. En v1 el impacto es aceptable.

**[Risk] Deadlock entre dos transacciones que piden locks en orden diferente**: Si T1 hace FOR UPDATE en [A, B] y T2 hace FOR UPDATE en [B, A], puede haber deadlock. Mitigación: El service siempre ordena los `producto_ids` antes del `SELECT FOR UPDATE` (ORDER BY id). Esto garantiza que todos los locks se piden en el mismo orden, eliminando deadlocks.

**[Risk] Stock decrementado antes del COMMIT visible para otros SELECT FOR UPDATE**: El decremento de stock (paso 10) es visible dentro de la misma transacción antes del COMMIT, pero no para otras transacciones (isolation level `READ COMMITTED` de PostgreSQL). El FOR UPDATE garantiza que ninguna otra transacción puede leer el registro hasta que la primera haga COMMIT. Esto es correcto.

**[Risk] Snapshot de dirección incompleto (solo FK, no campos copiados)**: Si la dirección se edita post-pedido, el pedido sigue apuntando a la misma entidad pero con datos actualizados. Mitigación: `ON DELETE SET NULL` garantiza que el pedido no queda con una FK rota, pero no preserva los datos de la dirección al momento de la compra. Change 20 (visualización) puede necesitar campos de snapshot adicionales. Esto es una deuda técnica conocida y documentada para Change 20.

## Migration Plan

No hay cambios de BD en este change. Los modelos `Pedido`, `DetallePedido`, `HistorialEstadoPedido` existen desde Change 03. El despliegue consiste en:
1. Agregar accessor `uow.pedidos` al `UnitOfWork` (el `PedidoRepository` consolida las operaciones de `Pedido`, `DetallePedido` e `HistorialEstadoPedido` — no se crean accessors separados por entidad).
2. Desplegar nuevos módulos backend (`pedidos_service.py`, `pedidos_router.py`, `pedido_repository.py`).
3. Registrar el router en `build_v1_router`.
4. Desplegar feature frontend `checkout`.

**Rollback**: Remover el registro del router (1 línea) y el deploy de los módulos. Sin impacto en BD.

## Open Questions

- **OQ-01**: ¿Se necesitan campos de snapshot de dirección en `Pedido` (linea1, ciudad, etc.)? Por ahora solo se guarda la FK. Change 20 puede necesitarlo. Decisión diferida.
- **OQ-02**: ¿El endpoint devuelve los `items` del pedido en el response 201, o solo el `PedidoRead` básico (sin items)? La propuesta es incluir `items` y el primer registro de `historial` en el 201 para que el frontend pueda mostrar confirmación sin un GET adicional.
