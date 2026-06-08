## ADDED Requirements

### Requirement: GET /api/v1/pedidos — listado paginado con discriminación RBAC

El sistema SHALL proveer `GET /api/v1/pedidos` que devuelve un listado paginado de pedidos. El comportamiento SHALL discriminarse por rol del JWT:

- Rol **CLIENT**: devuelve únicamente los pedidos donde `pedido.usuario_id = current_user.id`. Los query params `?desde`, `?hasta` y `?cliente` son ignorados silenciosamente. El CLIENT **no puede** pasar `?usuario_id=` para ver pedidos de otro usuario.
- Roles **PEDIDOS** o **ADMIN**: devuelven **siempre todos los pedidos del sistema**, sin filtro por `usuario_id`. Aplican filtros opcionales (`estado`, `desde`, `hasta`, `cliente`) cuando están presentes. Sin filtros → listado completo paginado de todos los pedidos.

El endpoint requiere autenticación Bearer. El rol STOCK recibe HTTP 403.

**Response**: `200 Page[PedidoListItem]` siguiendo el contrato de `backend-pagination-schema`.

Schema `PedidoListItem`:
```
PedidoListItem {
  id: UUID
  estado_codigo: str
  total: str               -- decimal string serializado
  forma_pago_codigo: str
  items_count: int          -- cantidad de líneas en DetallePedido
  created_at: datetime (ISO 8601 UTC)
  usuario_nombre: str | None   -- null para respuestas CLIENT, poblado para PEDIDOS/ADMIN
  usuario_email: str | None    -- null para respuestas CLIENT, poblado para PEDIDOS/ADMIN
}
```

**Query params (CLIENT):** `?estado=&page=&size=`
**Query params (PEDIDOS/ADMIN):** `?estado=&desde=&hasta=&cliente=&page=&size=`

Defaults: `page=1`, `size=20`. Máximo `size=100`.

#### Scenario: CLIENT ve solo sus propios pedidos
- **WHEN** un token CLIENT envía `GET /api/v1/pedidos`
- **THEN** el servidor devuelve HTTP 200 con `Page[PedidoListItem]`
- **THEN** todos los items en `items[]` tienen el `usuario_id` igual al del JWT
- **THEN** los campos `usuario_nombre` y `usuario_email` son `null` en cada item

#### Scenario: CLIENT filtra sus pedidos por estado
- **WHEN** un token CLIENT envía `GET /api/v1/pedidos?estado=EN_CAMINO`
- **THEN** el servidor devuelve HTTP 200
- **THEN** todos los items tienen `estado_codigo = "EN_CAMINO"`

#### Scenario: CLIENT con parámetros admin ignorados
- **WHEN** un token CLIENT envía `GET /api/v1/pedidos?desde=2026-01-01&cliente=test`
- **THEN** el servidor devuelve HTTP 200 (sin error)
- **THEN** el filtro es idéntico a `GET /api/v1/pedidos` sin esos params (server-side isolation)
- **THEN** el CLIENT sigue viendo únicamente sus propios pedidos

#### Scenario: PEDIDOS ve todos los pedidos sin filtros
- **WHEN** un token PEDIDOS envía `GET /api/v1/pedidos`
- **THEN** el servidor devuelve HTTP 200 con pedidos de todos los usuarios
- **THEN** los campos `usuario_nombre` y `usuario_email` están poblados en cada item

#### Scenario: ADMIN filtra por estado
- **WHEN** un token ADMIN envía `GET /api/v1/pedidos?estado=CONFIRMADO`
- **THEN** el servidor devuelve HTTP 200
- **THEN** todos los items tienen `estado_codigo = "CONFIRMADO"`

#### Scenario: PEDIDOS filtra por rango de fechas
- **WHEN** un token PEDIDOS envía `GET /api/v1/pedidos?desde=2026-05-01&hasta=2026-05-31`
- **THEN** el servidor devuelve HTTP 200
- **THEN** todos los items tienen `created_at` dentro del rango [2026-05-01 00:00:00, 2026-05-31 23:59:59] UTC

#### Scenario: ADMIN busca pedidos por email de cliente
- **WHEN** un token ADMIN envía `GET /api/v1/pedidos?cliente=user@example.com`
- **THEN** el servidor devuelve HTTP 200
- **THEN** los items corresponden a usuarios cuyo email contiene "user@example.com" (ILIKE)

#### Scenario: ADMIN busca pedidos por nombre de cliente (mínimo 3 caracteres)
- **WHEN** un token ADMIN envía `GET /api/v1/pedidos?cliente=jua`
- **THEN** el servidor devuelve HTTP 200
- **THEN** los items corresponden a usuarios cuyo nombre completo contiene "jua" (ILIKE, case-insensitive)

#### Scenario: Búsqueda de cliente con menos de 3 caracteres es ignorada
- **WHEN** un token ADMIN envía `GET /api/v1/pedidos?cliente=ab`
- **THEN** el servidor devuelve HTTP 200
- **THEN** el filtro `cliente` es ignorado (retorna todos los pedidos sin filtrar por cliente)

#### Scenario: Paginación funciona correctamente
- **WHEN** un token PEDIDOS envía `GET /api/v1/pedidos?page=2&size=5`
- **THEN** el servidor devuelve HTTP 200
- **THEN** el body contiene `{ items: [...], total: N, page: 2, size: 5, pages: ceil(N/5) }`
- **THEN** `items[]` contiene como máximo 5 elementos

#### Scenario: Pedidos ordenados por fecha descendente
- **WHEN** `GET /api/v1/pedidos` es llamado
- **THEN** los items están ordenados por `created_at DESC` (más recientes primero)

#### Scenario: STOCK rechazado con 403
- **WHEN** un token STOCK envía `GET /api/v1/pedidos`
- **THEN** el servidor devuelve HTTP 403

#### Scenario: Request sin autenticación rechazado con 401
- **WHEN** `GET /api/v1/pedidos` se envía sin header `Authorization`
- **THEN** el servidor devuelve HTTP 401

#### Scenario: Rango de fechas inválido (desde > hasta) devuelve 422
- **WHEN** un usuario ADMIN o PEDIDOS envía `?desde=2026-05-31&hasta=2026-05-01`
- **THEN** el servidor responde HTTP 422
- **THEN** el body contiene `{ "detail": "El parámetro 'desde' no puede ser posterior a 'hasta'.", "code": "INVALID_DATE_RANGE" }`

#### Scenario: Listado vacío devuelve Page válido
- **WHEN** un CLIENT que no tiene pedidos envía `GET /api/v1/pedidos`
- **THEN** el servidor devuelve HTTP 200
- **THEN** el body contiene `{ items: [], total: 0, page: 1, size: 20, pages: 0 }`

#### Scenario: PEDIDOS sin filtros ve TODOS los pedidos (no filtrado por usuario_id)
- **GIVEN** un usuario con rol PEDIDOS autenticado
- **WHEN** envía `GET /api/v1/pedidos` sin ningún filtro
- **THEN** el servidor devuelve HTTP 200 con pedidos de **todos los usuarios del sistema**
- **THEN** el listado **no** está filtrado por `usuario_id` del gestor que consulta
- **THEN** los campos `usuario_nombre` y `usuario_email` están poblados en cada item

#### Scenario: ADMIN sin filtros ve TODOS los pedidos (igual que PEDIDOS)
- **GIVEN** un usuario con rol ADMIN autenticado
- **WHEN** envía `GET /api/v1/pedidos` sin ningún filtro
- **THEN** el servidor devuelve HTTP 200 con pedidos de **todos los usuarios del sistema**
- **THEN** el listado **no** está filtrado por `usuario_id`
- **THEN** los campos `usuario_nombre` y `usuario_email` están poblados en cada item

---

### Requirement: PedidoListItem schema — campos compactos para listado

El sistema SHALL proveer el schema Pydantic `PedidoListItem` en `backend/app/pedidos/schemas.py`. Este schema SHALL usar `model_config = ConfigDict(from_attributes=True)`. El campo `total` SHALL serializar el `Decimal` a string via `@field_serializer`.

#### Scenario: PedidoListItem serializa total como string
- **WHEN** se serializa una instancia de `PedidoListItem` con `total = Decimal("1250.00")`
- **THEN** el JSON contiene `"total": "1250.00"` (string, no float)

#### Scenario: PedidoListItem tiene items_count
- **WHEN** un pedido tiene 3 `DetallePedido` rows
- **THEN** `PedidoListItem.items_count = 3`
