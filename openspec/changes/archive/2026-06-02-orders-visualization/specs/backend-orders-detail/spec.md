## ADDED Requirements

### Requirement: GET /api/v1/pedidos/{id} — detalle completo del pedido

El sistema SHALL proveer `GET /api/v1/pedidos/{id}` que devuelve el detalle completo de un pedido incluyendo items con snapshots, historial de estados, datos del usuario y el pago asociado más reciente.

**RBAC y aislamiento:**
- Rol **CLIENT**: puede acceder solo si `pedido.usuario_id == current_user.id`. Si el pedido existe pero pertenece a otro usuario → **HTTP 403** (no 404). Si el pedido no existe → HTTP 404.
- Roles **PEDIDOS** o **ADMIN**: pueden acceder a cualquier pedido.
- Rol **STOCK**: HTTP 403 siempre.

**Response**: `200 PedidoDetail`.

Schema `PedidoDetail`:
```
PedidoDetail {
  id: UUID
  usuario_id: UUID
  usuario: UsuarioBasic | None       -- { id, nombre, apellido, email }
  estado_codigo: str
  forma_pago_codigo: str
  subtotal: str                       -- decimal string
  costo_envio: str                    -- decimal string ("50.00" o "0.00")
  total: str                          -- decimal string
  notas: str | None
  direccion_id: UUID | None
  direccion: DireccionBasic | None    -- { alias, linea1 } best-effort (deuda OQ-01)
  items: list[DetallePedidoRead]      -- schema de backend-order-creation
  historial: list[HistorialRead]      -- schema de backend-order-history, ORDER BY created_at ASC
  pago: PagoResponse | None           -- schema de backend-pagos-management; null si no existe pago
  created_at: datetime (ISO 8601 UTC)
}

UsuarioBasic {
  id: UUID
  nombre: str
  apellido: str
  email: str
}

DireccionBasic {
  alias: str | None
  linea1: str
}
```

`DetallePedidoRead`, `HistorialRead` y `PagoResponse` se importan de sus specs respectivas. No se redefinen.

#### Scenario: CLIENT obtiene detalle de su propio pedido
- **WHEN** un token CLIENT envía `GET /api/v1/pedidos/{id}` donde `pedido.usuario_id == current_user.id`
- **THEN** el servidor devuelve HTTP 200
- **THEN** el body incluye `items[]` con `nombre_snapshot` y `precio_snapshot` por ítem
- **THEN** el body incluye `historial[]` ordenado por `created_at ASC`
- **THEN** `items[].precio_snapshot` refleja el precio al momento de creación del pedido

#### Scenario: CLIENT recibe 403 al intentar ver pedido ajeno (RN-RB05)
- **WHEN** un token CLIENT envía `GET /api/v1/pedidos/{id}` donde `pedido.usuario_id != current_user.id`
- **THEN** el servidor devuelve **HTTP 403** (no 404)
- **THEN** el body contiene `{ "detail": "No tiene permiso para ver este pedido.", "code": "ORDER_NOT_OWNED" }`
- **THEN** ningún dato del pedido es expuesto

#### Scenario: PEDIDOS puede ver cualquier pedido
- **WHEN** un token PEDIDOS envía `GET /api/v1/pedidos/{id}` para cualquier pedido
- **THEN** el servidor devuelve HTTP 200 con el detalle completo

#### Scenario: ADMIN puede ver cualquier pedido con datos de usuario
- **WHEN** un token ADMIN envía `GET /api/v1/pedidos/{id}`
- **THEN** el servidor devuelve HTTP 200
- **THEN** el campo `usuario` contiene `{ id, nombre, apellido, email }` del propietario del pedido

#### Scenario: Pedido no existente devuelve 404
- **WHEN** el `{id}` no corresponde a ningún pedido en la BD
- **THEN** el servidor devuelve HTTP 404
- **THEN** el body contiene `{ "code": "ORDER_NOT_FOUND" }`

#### Scenario: STOCK rechazado con 403
- **WHEN** un token STOCK envía `GET /api/v1/pedidos/{id}`
- **THEN** el servidor devuelve HTTP 403

#### Scenario: Request sin autenticación rechazado con 401
- **WHEN** `GET /api/v1/pedidos/{id}` se envía sin `Authorization`
- **THEN** el servidor devuelve HTTP 401

#### Scenario: Detalle incluye pago null cuando no hay pago registrado
- **WHEN** un pedido en estado PENDIENTE no tiene ningún `Pago` registrado
- **THEN** el campo `pago` en la respuesta es `null`

#### Scenario: Detalle incluye el pago más reciente cuando existe
- **WHEN** un pedido tiene 1 o más rows en tabla `Pago`
- **THEN** el campo `pago` contiene la row con `created_at` más reciente (via `get_latest_by_pedido_id`)

#### Scenario: Snapshots inmutables reflejados en el detalle
- **GIVEN** un pedido creado cuando un producto tenía `precio_base = 850.00` y `nombre = "Pizza Margherita"`
- **WHEN** el admin cambió el nombre a "Pizza Clásica" y el precio a 950.00 después de la creación
- **WHEN** un CLIENT consulta `GET /api/v1/pedidos/{id}`
- **THEN** el item en `items[]` muestra `nombre_snapshot = "Pizza Margherita"` y `precio_snapshot = "850.00"`

#### Scenario: Dirección básica incluida cuando direccion_id no es null
- **WHEN** el pedido tiene `direccion_id` no nulo y la dirección aún existe en BD
- **THEN** el campo `direccion` contiene `{ alias, linea1 }` de la dirección actual

#### Scenario: Dirección null cuando fue eliminada (deuda OQ-01)
- **WHEN** el pedido tiene `direccion_id` no nulo pero la dirección fue eliminada (soft-delete)
- **THEN** el campo `direccion` es `null` (best-effort, no error)
- **THEN** `direccion_id` sigue presente con el UUID original

---

### Requirement: Estrategia de carga anti-N+1

El método `PedidoService.get_full_detail(pedido_id)` SHALL usar `selectinload` para cargar `Pedido.detalles`, `Pedido.historial` y `Pedido.usuario`. El pago asociado se obtiene mediante una consulta separada vía `uow.pagos.get_latest_by_pedido_id(pedido_id)` (definido en `backend-pagos-management`, Change 19). NO se permite lazy loading implícito ni `joinedload` para evitar row duplication.

#### Scenario: query count acotado en detalle con múltiples items e historial
- **GIVEN** un pedido con 5 `DetallePedido` y 4 entradas en `HistorialEstadoPedido`
- **WHEN** se invoca `get_full_detail(pedido_id)`
- **THEN** se ejecutan exactamente 4 queries: 1 pedido + selectinload detalles + selectinload historial + selectinload usuario + 1 query separada para Pago
- **THEN** no se ejecutan queries N+1 por item de detalle

---

### Requirement: PedidoDetail schema — campos completos para vista de detalle

El sistema SHALL proveer el schema `PedidoDetail` en `backend/app/pedidos/schemas.py` con `model_config = ConfigDict(from_attributes=True)`. Los campos `subtotal`, `costo_envio` y `total` SHALL serializarse como string via `@field_serializer`.

#### Scenario: PedidoDetail serializa campos Decimal como string
- **WHEN** se serializa `PedidoDetail` con `total = Decimal("1300.00")`
- **THEN** el JSON contiene `"total": "1300.00"` (string, no float o número)

#### Scenario: PedidoDetail incluye lista de items con snapshots
- **WHEN** se serializa `PedidoDetail` con 2 items
- **THEN** `items[0]` contiene `nombre_snapshot`, `precio_snapshot`, `cantidad`, `personalizacion`
