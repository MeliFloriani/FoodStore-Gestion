## ADDED Requirements

### Requirement: Endpoint POST /api/v1/pedidos/validar acepta request estructurado de ítems

El sistema SHALL proveer el endpoint `POST /api/v1/pedidos/validar` que recibe un body `ValidarPreCheckoutRequest` con la lista de ítems del carrito del cliente, incluyendo precios percibidos. El endpoint SHALL requerir autenticación Bearer (roles `CLIENT` o `ADMIN`). El endpoint SHALL ser stateless e idempotente: no crea pedidos, no modifica stock, no persiste ningún dato.

El schema de request SHALL ser:
```
ValidarPreCheckoutRequest {
  items: ItemAValidar[]   -- mínimo 1 ítem
}

ItemAValidar {
  producto_id: str        -- UUID string del producto
  cantidad: int           -- ≥ 1
  personalizacion: list[str]  -- lista de UUIDs de ingredientes (puede ser vacía [])
  precio: str             -- precio percibido por el cliente en formato decimal string (ej: "250.00")
}
```

#### Scenario: Request válido con ítems es aceptado
- **WHEN** se envía `POST /api/v1/pedidos/validar` con Bearer token CLIENT y body con al menos un ítem válido
- **THEN** el servidor devuelve HTTP 200

#### Scenario: Request sin autenticación es rechazado
- **WHEN** se envía `POST /api/v1/pedidos/validar` sin header `Authorization`
- **THEN** el servidor devuelve HTTP 401

#### Scenario: Request con token de rol incorrecto es rechazado
- **WHEN** se envía `POST /api/v1/pedidos/validar` con Bearer token de rol `STOCK` o `PEDIDOS`
- **THEN** el servidor devuelve HTTP 403

#### Scenario: Request con body mal formado devuelve 422
- **WHEN** se envía `POST /api/v1/pedidos/validar` con body que omite campos obligatorios o con tipos incorrectos
- **THEN** el servidor devuelve HTTP 422 con estructura RFC 7807

#### Scenario: Request con lista de ítems vacía es rechazado con 422
- **WHEN** se envía `POST /api/v1/pedidos/validar` con `items: []`
- **THEN** el servidor devuelve HTTP 422 (min_length 1 no satisfecho)

---

### Requirement: Response estructurado con ok flag, items validados y cambios detectados

El endpoint `POST /api/v1/pedidos/validar` SHALL devolver siempre HTTP 200 cuando el payload es válido, independientemente de los resultados de validación. La respuesta SHALL seguir el schema:

```
ValidarPreCheckoutResponse {
  ok: bool                    -- true si no hay cambios bloqueantes; false si hay al menos un cambio de tipo PRODUCTO_NO_VIGENTE, PRODUCTO_NO_DISPONIBLE, STOCK_INSUFICIENTE o PERSONALIZACION_INVALIDA
  items: ItemValidadoRead[]   -- un entry por ítem del request
  cambios: CambioRead[]       -- lista de cambios detectados (vacía si ok=true)
}

ItemValidadoRead {
  producto_id: str
  cantidad_solicitada: int
  stock_disponible: int | null  -- null si el producto no existe o fue eliminado
  precio_actual: str | null     -- precio_base actual como string decimal; null si no existe
  precio_percibido: str         -- precio enviado en el request
  vigente: bool                 -- true si el producto existe y deleted_at is null
  disponible: bool | null       -- null si no vigente
}

CambioRead {
  producto_id: str
  tipo: Literal["PRODUCTO_NO_VIGENTE", "PRODUCTO_NO_DISPONIBLE", "STOCK_INSUFICIENTE", "PRECIO_CAMBIADO", "PERSONALIZACION_INVALIDA"]
  detalle: dict                 -- datos de soporte según tipo (ver tipos de cambio)
}
```

Estructura del campo `detalle` por tipo de cambio:
- `PRODUCTO_NO_VIGENTE`: `{ "razon": "eliminado" | "no_encontrado" }`
- `PRODUCTO_NO_DISPONIBLE`: `{ "disponible": false }`
- `STOCK_INSUFICIENTE`: `{ "stock_disponible": int, "cantidad_solicitada": int }`
- `PRECIO_CAMBIADO`: `{ "precio_anterior": str, "precio_actual": str }`
- `PERSONALIZACION_INVALIDA`: `{ "ingrediente_id": str, "razon": "no_existe" | "no_es_removible" | "no_pertenece_al_producto" }`

El flag `ok` SHALL ser `true` si y solo si `cambios` está vacío o solo contiene `PRECIO_CAMBIADO`. `PRECIO_CAMBIADO` es un cambio informativo que no bloquea el checkout; los demás tipos son bloqueantes.

#### Scenario: Carrito válido sin cambios devuelve ok=true y cambios vacíos
- **WHEN** todos los productos del carrito existen, están disponibles, tienen stock suficiente y los precios coinciden
- **THEN** la respuesta contiene `ok: true` y `cambios: []`

#### Scenario: Producto eliminado devuelve PRODUCTO_NO_VIGENTE y ok=false
- **WHEN** uno de los productos del carrito tiene `deleted_at` no nulo o no existe en BD
- **THEN** la respuesta contiene un `CambioRead` con `tipo: "PRODUCTO_NO_VIGENTE"` para ese producto
- **THEN** `ok` es `false`

#### Scenario: Producto no disponible devuelve PRODUCTO_NO_DISPONIBLE y ok=false
- **WHEN** uno de los productos existe y está vigente pero tiene `disponible=false`
- **THEN** la respuesta contiene `CambioRead` con `tipo: "PRODUCTO_NO_DISPONIBLE"`
- **THEN** `ok` es `false`

#### Scenario: Stock insuficiente devuelve STOCK_INSUFICIENTE y ok=false
- **WHEN** `producto.stock_cantidad < item.cantidad`
- **THEN** la respuesta contiene `CambioRead` con `tipo: "STOCK_INSUFICIENTE"` y `detalle.stock_disponible` con el valor real
- **THEN** `ok` es `false`

#### Scenario: Precio cambiado devuelve PRECIO_CAMBIADO pero ok puede ser true
- **WHEN** `Decimal(item.precio).quantize(0.01) != producto.precio_base.quantize(0.01)`
- **THEN** la respuesta contiene `CambioRead` con `tipo: "PRECIO_CAMBIADO"` y `detalle.precio_anterior` / `detalle.precio_actual`
- **THEN** si `PRECIO_CAMBIADO` es el único tipo de cambio presente, `ok` es `true`

#### Scenario: PRECIO_CAMBIADO con otro cambio bloqueante resulta en ok=false
- **WHEN** hay un `PRECIO_CAMBIADO` y además un `STOCK_INSUFICIENTE` para el mismo u otro producto
- **THEN** `ok` es `false`

#### Scenario: Personalización inválida devuelve PERSONALIZACION_INVALIDA y ok=false
- **WHEN** un ítem incluye un `ingrediente_id` en `personalizacion` que no existe, no es `es_removible=true`, o no pertenece al producto
- **THEN** la respuesta contiene `CambioRead` con `tipo: "PERSONALIZACION_INVALIDA"` con el primer ingrediente inválido encontrado
- **THEN** `ok` es `false`

---

### Requirement: Service pedidos_validar_service.validar_pre_checkout stateless y solo-lectura

El sistema SHALL implementar `pedidos_validar_service.validar_pre_checkout(uow: UnitOfWork, request: ValidarPreCheckoutRequest) -> ValidarPreCheckoutResponse` como función stateless que:
1. Recopila todos los `producto_id` del request.
2. Ejecuta un único `SELECT * FROM productos WHERE id IN (...)` (política anti-N+1, D-07).
3. Para cada ítem del request, evalúa en orden: vigencia → disponibilidad → stock → precio → personalización.
4. Acumula cambios detectados.
5. Calcula `ok = len([c for c in cambios if c.tipo != "PRECIO_CAMBIADO"]) == 0`.
6. Retorna `ValidarPreCheckoutResponse`.

El service SHALL ejecutarse dentro de un `UnitOfWork` abierto en modo consulta. No SHALL llamar a métodos de escritura ni hacer commit de cambios. El UoW SHALL cerrarse normalmente al finalizar (el commit es no-op).

#### Scenario: Service consulta todos los productos en una sola query
- **WHEN** el request contiene N ítems con distintos producto_id
- **THEN** el service ejecuta exactamente 1 consulta a la tabla `productos` (con IN clause)
- **THEN** no ejecuta una consulta separada por cada ítem

#### Scenario: Service no produce efectos secundarios
- **WHEN** se invoca `validar_pre_checkout` múltiples veces con los mismos datos
- **THEN** el estado de la BD no cambia entre llamadas
- **THEN** cada llamada devuelve la foto actual del estado de la BD en ese momento

#### Scenario: Service maneja productos no encontrados sin excepción
- **WHEN** un `producto_id` del request no existe en la BD
- **THEN** el service agrega `CambioRead(tipo="PRODUCTO_NO_VIGENTE", detalle={"razon": "no_encontrado"})` para ese ítem
- **THEN** el service no lanza `HTTPException` ni otra excepción

---

### Requirement: Comparación de precios con Decimal cuantizado a 2 decimales

El sistema SHALL comparar precios convirtiendo `item.precio` (string) a `Decimal` y cuantizando a `Decimal('0.01')` antes de comparar con `producto.precio_base` (almacenado como `DECIMAL(10,2)`). La tolerancia SHALL ser exactamente cero: cualquier diferencia después de cuantizar dispara `PRECIO_CAMBIADO`.

El campo `precio` en el wire format (request y response) SHALL ser siempre un string decimal con 2 decimales (ej: `"250.00"`), no un número JSON float.

#### Scenario: Precio idéntico no genera cambio
- **WHEN** `Decimal(item.precio).quantize(Decimal('0.01')) == producto.precio_base`
- **THEN** no se genera `CambioRead` de tipo `PRECIO_CAMBIADO`

#### Scenario: Precio diferente en 0.01 genera cambio
- **WHEN** `item.precio = "250.00"` y `producto.precio_base = Decimal("250.01")`
- **THEN** se genera `CambioRead(tipo="PRECIO_CAMBIADO", detalle={"precio_anterior": "250.00", "precio_actual": "250.01"})`

#### Scenario: Precio string con más de 2 decimales se cuantiza antes de comparar
- **WHEN** `item.precio = "250.009"` y `producto.precio_base = Decimal("250.01")`
- **THEN** el service cuantiza `250.009` → `250.01` antes de comparar (result: sin cambio detectado)

---

### Requirement: Carga batch de ProductoIngrediente — política anti-N+1

El service SHALL cargar todos los `ProductoIngrediente` relevantes para la validación de personalización con una única query batch, nunca consulta por producto.

```
Carga batch de ProductoIngrediente:
- Recopilar los producto_id de todos los ítems que tienen personalizacion no vacía.
- Obtener todos los ProductoIngrediente relevantes con un único:
  SELECT * FROM producto_ingrediente WHERE producto_id IN (:ids_de_productos_con_personalizacion)
- NO consultar ingredientes producto por producto (evitar N+1).
- La verificación de es_removible=True y pertenencia al producto se realiza en memoria
  sobre el resultado de esta query batch.
- Si personalizacion está vacía para todos los ítems, no se realiza ninguna consulta a
  producto_ingrediente.
```

#### Scenario: Validación de personalización ejecuta exactamente 1 query a producto_ingrediente
- **GIVEN** un request con M ítems que tienen personalización no vacía (M distintos producto_id)
- **WHEN** el service valida las personalizaciones
- **THEN** se ejecuta exactamente 1 consulta a `producto_ingrediente` con cláusula `IN (:ids)`
- **THEN** no se ejecuta una consulta por cada ítem o por cada producto

#### Scenario: Verificación de es_removible y pertenencia se hace en memoria
- **GIVEN** la carga batch retornó los ProductoIngrediente de todos los productos afectados
- **WHEN** se verifica que ingrediente_id pertenece al producto y es_removible=True
- **THEN** la verificación se realiza sobre el conjunto en memoria (sin consultas adicionales)

---

### Requirement: RBAC — require_role CLIENT y ADMIN

El endpoint `POST /api/v1/pedidos/validar` SHALL aplicar `require_role(["CLIENT", "ADMIN"])` como dependencia de FastAPI. Tokens sin rol válido SHALL recibir HTTP 403. Requests sin token SHALL recibir HTTP 401.

#### Scenario: CLIENT autenticado accede correctamente
- **WHEN** se envía la request con un token JWT válido de rol `CLIENT`
- **THEN** el endpoint procesa la request y devuelve HTTP 200

#### Scenario: ADMIN autenticado accede correctamente
- **WHEN** se envía la request con un token JWT válido de rol `ADMIN`
- **THEN** el endpoint procesa la request y devuelve HTTP 200

#### Scenario: Token de rol STOCK es rechazado
- **WHEN** se envía la request con un token JWT válido de rol `STOCK`
- **THEN** el servidor devuelve HTTP 403

#### Scenario: Request sin token devuelve 401
- **WHEN** se envía la request sin header `Authorization`
- **THEN** el servidor devuelve HTTP 401

---

### Requirement: Errores RFC 7807 solo para fallos de protocolo

El endpoint SHALL adherirse al estándar RFC 7807 (`ProblemDetail`) únicamente para respuestas de error HTTP (4xx, 5xx). Los cambios de negocio detectados (stock insuficiente, precio cambiado, etc.) NO SHALL modelarse como errores HTTP — se representan dentro del body `200 OK` como parte de `cambios[]`.

#### Scenario: Payload inválido devuelve RFC 7807
- **WHEN** el body del request tiene un tipo de dato incorrecto (ej: `cantidad: "abc"`)
- **THEN** la respuesta es HTTP 422 con estructura `{ "type": ..., "title": ..., "status": 422, "detail": ... }`

#### Scenario: Stock insuficiente NO genera error HTTP
- **WHEN** un producto tiene stock insuficiente para la cantidad solicitada
- **THEN** la respuesta es HTTP 200 con `ok: false` y el cambio en `cambios[]`
- **THEN** no se devuelve HTTP 422 ni 409

#### Scenario: Producto no vigente NO genera error HTTP
- **WHEN** un producto del carrito fue eliminado o desactivado
- **THEN** la respuesta es HTTP 200 con `ok: false`
- **THEN** no se devuelve HTTP 404 ni 422

---

## MODIFIED Requirements

### MODIFIED: backend-products-management — ProductoRepository.get_by_ids (requerido por Change 16)

El sistema SHALL implementar el método `get_by_ids` en el `ProductoRepository` existente de Change 11 (`backend/app/repositories/producto.py`). Este método es necesario para la política anti-N+1 de Change 16 y NO existía en la spec de Change 11.

```
ProductoRepository — nuevo método requerido por Change 16:

get_by_ids(ids: list[UUID]) -> list[Producto]
  - Ejecuta SELECT * FROM producto WHERE id IN (:ids) AND deleted_at IS NULL
  - Devuelve la lista de productos encontrados (puede ser menor que len(ids) si algunos
    son soft-deleted o no existen)
  - No lanza excepción si algún ID no se encuentra
  - Evita N+1: una sola query para todos los IDs
  - El implementador debe agregar este método al ProductoRepository existente de Change 11
  - Nota: los productos con deleted_at IS NOT NULL NO se retornan; el service de Change 16
    interpreta su ausencia como PRODUCTO_NO_VIGENTE con razon="eliminado" o "no_encontrado"
```

#### Scenario: get_by_ids retorna lista completa cuando todos los IDs existen y están activos
- **GIVEN** productos con ids [A, B, C] existen y tienen `deleted_at IS NULL`
- **WHEN** se llama `get_by_ids([A, B, C])`
- **THEN** retorna lista de 3 productos, uno por cada ID

#### Scenario: get_by_ids retorna lista parcial cuando algunos IDs no existen o están eliminados
- **GIVEN** producto A existe activo, producto B tiene `deleted_at` no nulo, producto C no existe
- **WHEN** se llama `get_by_ids([A, B, C])`
- **THEN** retorna lista de 1 producto (solo A)
- **THEN** no lanza excepción por B ni C ausentes

#### Scenario: get_by_ids ejecuta exactamente una query para N IDs
- **WHEN** se llama `get_by_ids` con una lista de N IDs distintos
- **THEN** se ejecuta exactamente 1 consulta SQL con cláusula `IN (:ids)`
- **THEN** no se ejecuta una consulta separada por cada ID (sin N+1)

---

### Requirement: Manejo de producto_id duplicado en el request

El service SHALL manejar correctamente el caso donde dos o más ítems del request tienen el mismo `producto_id` pero diferente `personalizacion`.

```
Deduplicación para la consulta batch:
- Al recopilar IDs para get_by_ids, el service deduplica los producto_id (list → set → list).
- Un mismo producto se consulta UNA SOLA VEZ en la BD (sin N+1 por duplicados).
- Al construir la respuesta, cada ítem del request recibe su propio ItemValidadoRead
  (sin deduplicar ítems — el response tiene el mismo número de items que el request).
```

#### Scenario: Dos ítems del mismo producto con diferente personalización
- **GIVEN** un request con dos items con el mismo `producto_id` pero diferente `personalizacion`
- **WHEN** el service valida el request
- **THEN** se consulta el producto UNA SOLA VEZ (no hay N+1 por productos duplicados)
- **AND** ambos ítems son validados correctamente contra el mismo registro de producto
- **AND** el response incluye un `ItemValidadoRead` por cada ítem del request (no deduplica ítems)
