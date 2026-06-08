# backend-order-creation Specification

## Purpose
Transactional order creation endpoint introduced in Change 17 (`order-creation-with-snapshots`). Provides `POST /api/v1/pedidos` with atomic Unit of Work: pessimistic locking via `SELECT FOR UPDATE`, immutable snapshots per line item (`nombre_snapshot` + `precio_snapshot`), optional delivery address, retiro en local support, initial `HistorialEstadoPedido` entry with `estado_desde=NULL`, and payment method validation against the `FormaPago` catalog. This is the transactional counterpart to the advisory `POST /api/v1/pedidos/validar` (Change 16) — it re-runs all validations with full transactional guarantees and does NOT trust Change 16 results.

## ADDED Requirements

### Requirement: Endpoint POST /api/v1/pedidos — creación atómica de pedido

El sistema SHALL proveer el endpoint `POST /api/v1/pedidos` que crea un pedido de forma atómica dentro de un único `UnitOfWork`. El endpoint SHALL requerir autenticación Bearer con roles `CLIENT` o `ADMIN`. En éxito, devuelve HTTP 201 con `PedidoRead`. El `usuario_id` del pedido se extrae del JWT — el cliente no puede especificar otro usuario.

El schema de request SHALL ser:
```
PedidoCreate {
  items: list[ItemPedidoCreate]   -- mínimo 1 item
  forma_pago_codigo: str           -- código semántico del catálogo FormaPago
  direccion_id: UUID | None        -- None = retiro en local (válido)
  notas: str | None
}

ItemPedidoCreate {
  producto_id: UUID
  cantidad: int                   -- ≥ 1
  exclusiones: list[UUID]         -- UUIDs de ingredientes excluidos; [] si ninguno
}
```

#### Scenario: Creación exitosa con dirección de entrega devuelve 201
- **WHEN** se envía `POST /api/v1/pedidos` con Bearer token CLIENT, body válido con al menos un ítem, `forma_pago_codigo` habilitado y `direccion_id` perteneciente al usuario
- **THEN** el servidor devuelve HTTP 201
- **THEN** el body incluye `id` (UUID), `estado_codigo: "PENDIENTE"`, `items` con snapshots, `historial` con el primer registro
- **THEN** `Pedido.estado_codigo = "PENDIENTE"` en la BD

#### Scenario: Creación exitosa con retiro en local (direccion_id=null)
- **WHEN** se envía `POST /api/v1/pedidos` con `direccion_id: null`
- **THEN** el servidor devuelve HTTP 201
- **THEN** `Pedido.direccion_id IS NULL` en la BD
- **THEN** `Pedido.costo_envio = 0.00` en la BD

#### Scenario: Request sin autenticación es rechazado
- **WHEN** se envía `POST /api/v1/pedidos` sin header `Authorization`
- **THEN** el servidor devuelve HTTP 401

#### Scenario: Request con rol STOCK es rechazado
- **WHEN** se envía `POST /api/v1/pedidos` con Bearer token de rol `STOCK`
- **THEN** el servidor devuelve HTTP 403

#### Scenario: Request con rol PEDIDOS es rechazado
- **WHEN** se envía `POST /api/v1/pedidos` con Bearer token de rol `PEDIDOS`
- **THEN** el servidor devuelve HTTP 403

#### Scenario: Request con body mal formado devuelve 422
- **WHEN** se envía `POST /api/v1/pedidos` con tipos incorrectos o campos faltantes
- **THEN** el servidor devuelve HTTP 422 con estructura RFC 7807

---

### Requirement: Validación de carrito no vacío

El service SHALL rechazar requests donde `items` está vacío o ausente. Esta validación ocurre antes de abrir la transacción con locks.

#### Scenario: Carrito vacío rechazado con CART_EMPTY
- **WHEN** se envía `POST /api/v1/pedidos` con `items: []`
- **THEN** el servidor devuelve HTTP 400
- **THEN** el body contiene `{ "code": "CART_EMPTY" }`

---

### Requirement: Validación de producto — existencia, disponibilidad y soft delete

El service SHALL validar cada producto dentro de la transacción post-lock. Un producto falla si no existe, tiene `deleted_at IS NOT NULL`, o tiene `disponible=False`.

#### Scenario: Producto inexistente en BD rechazado con PRODUCT_NOT_FOUND
- **WHEN** `items[].producto_id` no existe en la tabla `producto`
- **THEN** el servidor devuelve HTTP 400
- **THEN** el body contiene `{ "code": "PRODUCT_NOT_FOUND", "field": "items[N].producto_id" }`
- **THEN** ningún pedido ni detalle es persistido (rollback total)

#### Scenario: Producto con soft delete rechazado con PRODUCT_NOT_AVAILABLE
- **WHEN** `producto.deleted_at IS NOT NULL` para algún item del carrito
- **THEN** el servidor devuelve HTTP 400
- **THEN** el body contiene `{ "code": "PRODUCT_NOT_AVAILABLE" }`
- **THEN** rollback total — ningún recurso persiste

#### Scenario: Producto no disponible rechazado con PRODUCT_NOT_AVAILABLE
- **WHEN** `producto.disponible = False` para algún item del carrito
- **THEN** el servidor devuelve HTTP 400
- **THEN** el body contiene `{ "code": "PRODUCT_NOT_AVAILABLE" }`
- **THEN** rollback total

---

### Requirement: Validación de stock con SELECT FOR UPDATE — prevención de overselling

El service SHALL ejecutar `SELECT * FROM producto WHERE id IN (:ids) ORDER BY id FOR UPDATE` dentro de la UoW ANTES de comparar stock. El ORDER BY id previene deadlocks entre transacciones concurrentes.

#### Scenario: Stock insuficiente post-lock rechazado con INSUFFICIENT_STOCK
- **WHEN** `producto.stock_cantidad < item.cantidad` para cualquier item (verificado POST-lock)
- **THEN** el servidor devuelve HTTP 409
- **THEN** el body contiene `{ "code": "INSUFFICIENT_STOCK", "detail": { "stock_disponible": int, "cantidad_solicitada": int } }`
- **THEN** rollback total — ningún pedido ni detalle es persistido

#### Scenario: SELECT FOR UPDATE previene overselling concurrente
> **TEST MARKER**: `@pytest.mark.integration` — requiere PostgreSQL real. No ejecutar con SQLite (SQLite no soporta `FOR UPDATE`). Usar `asyncio.gather(..., return_exceptions=True)` con fixture de BD real compartida entre corutinas.

- **GIVEN** un producto con `stock_cantidad = 1`
- **WHEN** dos requests concurrentes intentan crear un pedido para ese producto con `cantidad = 1`
- **THEN** exactamente una transacción tiene éxito con HTTP 201
- **THEN** la segunda transacción recibe HTTP 409 `INSUFFICIENT_STOCK`
- **THEN** `producto.stock_cantidad = 0` después de ambas transacciones (no negativo)

#### Scenario: Locks adquiridos en orden ascendente por ID (anti-deadlock)
- **WHEN** el service procesa un request con múltiples items con productos [P3, P1, P2]
- **THEN** el `SELECT FOR UPDATE` se ejecuta con `ORDER BY id` resultando en lock sobre [P1, P2, P3]
- **THEN** no hay riesgo de deadlock por orden inconsistente de locks

---

### Requirement: Validación de personalización (exclusiones)

El service SHALL validar que cada `ingrediente_id` en `exclusiones` (a) existe, (b) tiene `es_removible=True`, y (c) pertenece al producto asociado. La validación se realiza con una única query batch `SELECT * FROM producto_ingrediente WHERE producto_id IN (:ids)` seguida de verificación en memoria — sin N+1.

#### Scenario: Exclusión con ingrediente no removible rechazada con INVALID_CUSTOMIZATION
- **WHEN** `exclusiones` incluye un `ingrediente_id` cuyo `ProductoIngrediente.es_removible = False`
- **THEN** el servidor devuelve HTTP 400
- **THEN** el body contiene `{ "code": "INVALID_CUSTOMIZATION", "detail": { "ingrediente_id": str, "razon": "no_es_removible" } }`
- **THEN** rollback total

#### Scenario: Exclusión con ingrediente que no pertenece al producto rechazada
- **WHEN** `exclusiones` incluye un `ingrediente_id` que no está asociado al producto en `ProductoIngrediente`
- **THEN** el servidor devuelve HTTP 400
- **THEN** el body contiene `{ "code": "INVALID_CUSTOMIZATION", "detail": { "ingrediente_id": str, "razon": "no_pertenece_al_producto" } }`
- **THEN** rollback total

#### Scenario: Exclusiones vacías son válidas
- **WHEN** `item.exclusiones = []` para todos los items
- **THEN** no se ejecuta ninguna query a `producto_ingrediente`
- **THEN** la creación del pedido continúa normalmente

#### Scenario: Validación de personalización usa una sola query batch
- **GIVEN** un request con M items que tienen exclusiones no vacías
- **WHEN** el service valida las personalizaciones
- **THEN** se ejecuta exactamente 1 consulta a `producto_ingrediente` con cláusula `IN (:ids)`
- **THEN** no se ejecuta una consulta por cada item o por cada ingrediente

---

### Requirement: Validación de forma de pago contra catálogo FormaPago

El service SHALL validar que `forma_pago_codigo` existe en la tabla `FormaPago` y que `habilitado = True`.

#### Scenario: Forma de pago inexistente rechazada con PAYMENT_METHOD_INVALID
- **WHEN** `forma_pago_codigo` no existe en la tabla `forma_pago`
- **THEN** el servidor devuelve HTTP 400
- **THEN** el body contiene `{ "code": "PAYMENT_METHOD_INVALID" }`
- **THEN** rollback total

#### Scenario: Forma de pago con habilitado=False rechazada
- **WHEN** `forma_pago.habilitado = False` para el código enviado
- **THEN** el servidor devuelve HTTP 400
- **THEN** el body contiene `{ "code": "PAYMENT_METHOD_INVALID" }`
- **THEN** rollback total

#### Scenario: Forma de pago habilitada aceptada
- **WHEN** `forma_pago_codigo = "EFECTIVO"` y `habilitado = True` en el seed
- **THEN** la validación pasa y el pedido se crea normalmente

---

### Requirement: Validación de dirección — ownership y existencia

El service SHALL validar que `direccion_id`, si NO es NULL, pertenece al `usuario_id` del JWT.

#### Scenario: direccion_id nulo es válido (retiro en local)
- **WHEN** `direccion_id = null` en el request
- **THEN** la validación de dirección se omite completamente
- **THEN** el pedido se crea con `Pedido.direccion_id = NULL` y `costo_envio = 0.00`

#### Scenario: direccion_id que no pertenece al usuario rechazado con ADDRESS_NOT_OWNED
- **WHEN** `direccion_id` existe en BD pero `direccion.usuario_id != current_user.id`
- **THEN** el servidor devuelve HTTP 403
- **THEN** el body contiene `{ "code": "ADDRESS_NOT_OWNED" }`
- **THEN** rollback total

#### Scenario: direccion_id inexistente rechazado con ADDRESS_NOT_FOUND
- **WHEN** `direccion_id` no existe en la BD (ni activo ni soft-deleted)
- **THEN** el servidor devuelve HTTP 400
- **THEN** el body contiene `{ "code": "ADDRESS_NOT_FOUND" }`
- **THEN** rollback total

---

### Requirement: costo_envio calculado server-side — regla fija v1

El sistema SHALL calcular `costo_envio` server-side basándose únicamente en la presencia o ausencia de `direccion_id`. El frontend NO puede fijar este valor.

#### Scenario: costo_envio = 50.00 cuando hay dirección de entrega
- **WHEN** `direccion_id` es un UUID válido del usuario
- **THEN** `Pedido.costo_envio = 50.00` (exacto) en la BD

#### Scenario: costo_envio = 0.00 cuando es retiro en local
- **WHEN** `direccion_id = null`
- **THEN** `Pedido.costo_envio = 0.00` (exacto) en la BD

---

### Requirement: Snapshots inmutables — nombre_snapshot + precio_snapshot

El service SHALL copiar `producto.nombre` → `DetallePedido.nombre_snapshot` y `producto.precio_base` → `DetallePedido.precio_snapshot` al momento de crear cada `DetallePedido`. Estos valores SON write-once.

#### Scenario: nombre_snapshot congela el nombre del producto en el momento de creación
- **GIVEN** un producto con `nombre = "Pizza Margherita"` al momento de crear el pedido
- **WHEN** el pedido es creado exitosamente
- **THEN** `DetallePedido.nombre_snapshot = "Pizza Margherita"` en la BD
- **WHEN** el admin renombra el producto a "Pizza Clásica" posteriormente
- **THEN** `DetallePedido.nombre_snapshot` sigue siendo `"Pizza Margherita"` (inmutable)

#### Scenario: precio_snapshot congela el precio del producto en el momento de creación
- **GIVEN** un producto con `precio_base = Decimal("850.00")` al momento de crear el pedido
- **WHEN** el pedido es creado exitosamente
- **THEN** `DetallePedido.precio_snapshot = Decimal("850.00")` en la BD
- **WHEN** el admin cambia el precio a 950.00 posteriormente
- **THEN** `DetallePedido.precio_snapshot` sigue siendo `850.00` (inmutable)

#### Scenario: precio_snapshot se usa para calcular subtotal, no el precio del carrito
- **WHEN** el carrito del frontend tenía precio "800.00" pero el producto ahora vale 850.00
- **WHEN** el pedido es creado
- **THEN** `DetallePedido.precio_snapshot = 850.00` (precio actual, no el del carrito)
- **THEN** `Pedido.subtotal` se calcula con el precio_snapshot actual

---

### Requirement: Totales calculados server-side

El service SHALL calcular `subtotal`, `costo_envio`, y `total` server-side. El frontend NO envía estos campos. El cálculo usa los `precio_base` actuales de los productos (no los precios del carrito).

#### Scenario: subtotal es suma de precio_snapshot × cantidad
- **GIVEN** items `[{ precio_base=100.00, cantidad=2 }, { precio_base=50.00, cantidad=3 }]`
- **WHEN** el pedido es creado
- **THEN** `Pedido.subtotal = 350.00`

#### Scenario: total = subtotal + costo_envio
- **GIVEN** `subtotal = 350.00` y `costo_envio = 50.00` (con dirección)
- **WHEN** el pedido es creado
- **THEN** `Pedido.total = 400.00`

#### Scenario: totales del frontend ignorados
- **WHEN** un cliente envía un request manipulado con cualquier campo de total
- **THEN** el backend ignora esos campos y calcula sus propios totales
- **THEN** el total en el response difiere del valor manipulado si hay discrepancia

---

### Requirement: HistorialEstadoPedido inicial — primer asiento con estado_desde=NULL

El service SHALL crear exactamente un registro de `HistorialEstadoPedido` al crear el pedido con `estado_desde=NULL` y `estado_hacia="PENDIENTE"` (RN-02 del Integrador v5.0).

#### Scenario: Primer historial con estado_desde=NULL y estado_hacia=PENDIENTE
- **WHEN** el pedido es creado exitosamente
- **THEN** existe exactamente 1 registro en `HistorialEstadoPedido` para ese `pedido_id`
- **THEN** `estado_desde IS NULL` en ese registro
- **THEN** `estado_hacia = "PENDIENTE"` en ese registro

#### Scenario: HistorialEstadoPedido incluido en el response del 201
- **WHEN** el pedido es creado con HTTP 201
- **THEN** el body incluye `historial: [{ estado_desde: null, estado_hacia: "PENDIENTE", ... }]`

---

### Requirement: Atomicidad total — rollback en cualquier fallo

El service SHALL ejecutar todos los INSERTs y UPDATEs dentro de un único `UnitOfWork`. Si cualquier operación falla (validación, INSERT, UPDATE de stock), el UoW hace rollback y ningún dato se persiste.

#### Scenario: Rollback total si falla la creación de DetallePedido
- **GIVEN** un request válido con 3 items
- **WHEN** el INSERT del segundo DetallePedido falla (por cualquier razón)
- **THEN** ni el Pedido, ni el primer DetallePedido, ni el HistorialEstadoPedido son persistidos
- **THEN** el stock de los productos no fue decrementado

#### Scenario: Rollback total si falla la validación de stock después del lock
- **GIVEN** una transacción que ya adquirió los locks
- **WHEN** se detecta stock insuficiente durante la validación
- **THEN** los locks son liberados con el ROLLBACK
- **THEN** los productos no son modificados
- **THEN** ningún Pedido es creado

#### Scenario: El service no llama session.commit() directamente
- **WHEN** el código del service es inspeccionado estáticamente
- **THEN** no existe ninguna llamada a `session.commit()` en `pedidos_service.py`
- **THEN** el COMMIT es exclusivamente responsabilidad del UoW

---

### Requirement: Orden de operaciones dentro de la UoW (contrato)

El service SHALL ejecutar las operaciones en este orden exacto dentro del UoW:

1. `SELECT FOR UPDATE` sobre todos los productos del request (ordenados por ID).
2. Validar carrito no vacío.
3. Para cada producto: validar existencia, disponibilidad, stock suficiente.
4. Validar personalización (batch query `ProductoIngrediente`).
5. Validar forma de pago (`FormaPago` lookup).
6. Validar dirección si `direccion_id IS NOT NULL`.
7. Calcular totales server-side.
8. `CREATE Pedido` + `flush()`.
9. `CREATE DetallePedido` por cada item + `flush()`.
10. `DECREMENT stock_cantidad` por cada item.
11. `CREATE HistorialEstadoPedido` inicial + `flush()`.
12. UoW `COMMIT` automático.

#### Scenario: Validaciones ocurren antes de cualquier INSERT
- **WHEN** el request tiene un item con stock insuficiente
- **THEN** el servicio detecta el error en el paso 3 (pre-INSERT)
- **THEN** no se ejecuta ningún INSERT en `pedido`, `detalle_pedido`, ni `historial_estado_pedido`

#### Scenario: Stock decrementado después de crear los registros del pedido
- **WHEN** el pedido y sus detalles son creados (steps 8-9)
- **THEN** el decremento de stock ocurre en step 10, post-creación del pedido
- **THEN** si el decremento falla, el rollback revierte también el pedido y los detalles

---

### Requirement: Errores RFC 7807 con código semántico

Todos los errores devueltos por el endpoint SHALL seguir el formato `{ "detail": "<mensaje legible>", "code": "<CODIGO_SEMANTICO>", "field": "<campo opcional>" }`. Los códigos de error son: `CART_EMPTY`, `PRODUCT_NOT_FOUND`, `PRODUCT_NOT_AVAILABLE`, `INSUFFICIENT_STOCK`, `INVALID_CUSTOMIZATION`, `PAYMENT_METHOD_INVALID`, `ADDRESS_NOT_FOUND`, `ADDRESS_NOT_OWNED`.

#### Scenario: Error incluye code semántico en el body
- **WHEN** se envía un request que desencadena cualquier error de negocio
- **THEN** el body contiene `{ "code": "<CODIGO>", "detail": "..." }`
- **THEN** el `code` es uno de los códigos definidos en el catálogo

#### Scenario: Error 409 INSUFFICIENT_STOCK incluye detalle de stock
- **WHEN** el stock es insuficiente para un producto
- **THEN** el body contiene `{ "code": "INSUFFICIENT_STOCK", "detail": { "stock_disponible": int, "cantidad_solicitada": int } }`
