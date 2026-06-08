## ADDED Requirements

### Requirement: Panel de gestión de pedidos para PEDIDOS/ADMIN (/pedidos-panel)

El sistema SHALL proveer la página `PedidosPanelPage` en `src/pages/PedidosPanelPage/` que reemplaza el placeholder de `/pedidos-panel/*` del Change 08.

La página SHALL:
- Estar accesible en `/pedidos-panel` con el `RoleGuard roles={['PEDIDOS','ADMIN']}` ya existente.
- Consumir `GET /api/v1/pedidos` via el hook `useAdminOrders(params)`.
- Mostrar todos los pedidos del sistema en una tabla/lista paginada.
- Mostrar columnas: ID (truncado), cliente (nombre + email), estado (badge), total, fecha de creación.
- Mostrar un filtro por **estado** (select: Todos, PENDIENTE, CONFIRMADO, EN_PREP, EN_CAMINO, ENTREGADO, CANCELADO).
- Mostrar filtros de **rango de fechas**: dos inputs de tipo `date` para `desde` y `hasta`.
- Mostrar un input de **búsqueda de cliente** (texto libre, mínimo 3 caracteres) con debounce de 400ms.
- Mostrar paginación con `Page[T]` del backend.
- Mostrar skeleton loaders durante la carga.
- Navegar a `/pedidos-panel/:id` al hacer clic en un item.

Los filtros de fecha y búsqueda de cliente SHALL tener debounce de 400ms via `useDebounce` de `src/shared/hooks/`.

El filtro de estado (select) NO tiene debounce.

#### Scenario: Panel PEDIDOS muestra todos los pedidos del sistema
- **WHEN** un usuario PEDIDOS navega a `/pedidos-panel`
- **THEN** `GET /api/v1/pedidos` es llamado con el Bearer token PEDIDOS
- **THEN** la tabla muestra pedidos de todos los usuarios (no solo del usuario actual)
- **THEN** cada fila incluye nombre y email del cliente

#### Scenario: Filtro por estado actualiza la lista
- **WHEN** el usuario selecciona "CONFIRMADO" en el filtro de estado
- **THEN** `GET /api/v1/pedidos?estado=CONFIRMADO` es llamado
- **THEN** la tabla muestra solo pedidos CONFIRMADO

#### Scenario: Filtro de fechas con debounce
- **WHEN** el usuario ingresa `desde=2026-05-01` y `hasta=2026-05-31`
- **THEN** después de 400ms (debounce), `GET /api/v1/pedidos?desde=2026-05-01&hasta=2026-05-31` es llamado
- **THEN** la tabla muestra solo pedidos del rango de fechas indicado

#### Scenario: Búsqueda de cliente con debounce y mínimo 3 caracteres
- **WHEN** el usuario escribe "juan" en el campo de búsqueda
- **THEN** después de 400ms, `GET /api/v1/pedidos?cliente=juan` es llamado
- **WHEN** el usuario escribe solo "ju" (2 caracteres)
- **THEN** NO se realiza ninguna request (menos de 3 caracteres)

#### Scenario: Paginación en el panel
- **WHEN** hay más pedidos que `size=20`
- **THEN** se muestran controles de paginación
- **WHEN** el usuario navega a la página 2
- **THEN** `GET /api/v1/pedidos?page=2&size=20` es llamado

#### Scenario: Click en fila navega al detalle de gestión
- **WHEN** el usuario hace clic en una fila de la tabla
- **THEN** el navegador navega a `/pedidos-panel/{pedidoId}`

#### Scenario: STOCK no puede acceder al panel
- **WHEN** un usuario STOCK navega a `/pedidos-panel`
- **THEN** el `RoleGuard` redirige a `/403`

---

### Requirement: Página de detalle de gestión (/pedidos-panel/:id)

El sistema SHALL proveer la página `PedidosPanelDetailPage` en `src/pages/PedidosPanelDetailPage/` que muestra el detalle completo de un pedido para roles PEDIDOS/ADMIN.

La página SHALL:
- Estar accesible en `/pedidos-panel/:id` con `RoleGuard roles={['PEDIDOS','ADMIN']}`.
- Consumir `GET /api/v1/pedidos/{id}` via `useOrderDetail(pedidoId)`.
- Mostrar toda la información de `PedidoDetail`: items con snapshots, dirección (best-effort), estado, totales.
- Mostrar los **datos del cliente**: nombre, apellido, email (del campo `usuario` de `PedidoDetail`).
- Mostrar el componente `OrderHistoryTimeline` con el historial completo.
- Mostrar el estado del pago (campo `pago`).
- Mostrar el componente `EstadoActionBar` de `frontend-pedido-state-actions` para que el staff pueda avanzar el estado.
- Mostrar un botón "Volver al panel" que navega a `/pedidos-panel`.

#### Scenario: Panel detail PEDIDOS muestra datos del cliente
- **WHEN** un PEDIDOS navega a `/pedidos-panel/{pedidoId}`
- **THEN** `GET /api/v1/pedidos/{pedidoId}` devuelve el `usuario` con nombre, apellido, email
- **THEN** la página muestra esos datos del cliente

#### Scenario: EstadoActionBar permite avanzar estado
- **WHEN** el pedido está en estado CONFIRMADO y el usuario es PEDIDOS
- **THEN** `EstadoActionBar` muestra el botón "Avanzar a EN_PREP"
- **THEN** al confirmar, `useTransitionEstado` realiza `PATCH /api/v1/pedidos/{id}/estado`
- **THEN** la página se refresca con el nuevo estado (via TanStack Query invalidation)

#### Scenario: Transición exitosa desde EstadoActionBar refresca el listado del panel
- **GIVEN** un usuario PEDIDOS en `/pedidos-panel/:id` con un pedido en CONFIRMADO
- **WHEN** acciona `EstadoActionBar` para avanzar a EN_PREP
- **THEN** `useTransitionEstado.onSuccess` invalida `pedidoEstadoKeys.list()` = `['pedidos']`
- **THEN** TanStack Query (prefix match) refetch `useAdminOrders` con query key `['pedidos','admin', params]`
- **THEN** al volver a `/pedidos-panel`, el listado muestra el pedido en estado EN_PREP sin acción manual del usuario

#### Scenario: Historial completo visible en el detalle de gestión
- **WHEN** el pedido tiene 4 transiciones en `HistorialEstadoPedido`
- **THEN** `OrderHistoryTimeline` renderiza 4 entradas cronológicas
- **THEN** cada entrada muestra: estado anterior → estado nuevo, fecha, actor

---

### Requirement: Hook useAdminOrders — TanStack Query para panel de gestión

El sistema SHALL implementar `useAdminOrders(params: AdminOrdersParams)` en `src/features/orders-panel/hooks/useAdminOrders.ts` como `useQuery`.

```typescript
interface AdminOrdersParams {
  estado?: string
  desde?: string        // ISO 8601 date string
  hasta?: string        // ISO 8601 date string
  cliente?: string      // mínimo 3 chars para activar el filtro
  page?: number
  size?: number
}
```

Query key: `['pedidos', 'admin', params]` (separado de `pedidoEstadoKeys.list()` para no contaminar el caché del CLIENT).

#### Scenario: Hook construye la URL con filtros opcionales
- **WHEN** `useAdminOrders({ estado: "CONFIRMADO", cliente: "juan", page: 1, size: 20 })` es usado
- **THEN** la request es `GET /api/v1/pedidos?estado=CONFIRMADO&cliente=juan&page=1&size=20`

#### Scenario: Hook omite params vacíos de la URL
- **WHEN** `useAdminOrders({ page: 1 })` es usado (sin otros filtros)
- **THEN** la request es `GET /api/v1/pedidos?page=1` (sin query params vacíos)

#### Scenario: Filtro cliente ignorado si tiene menos de 3 chars
- **WHEN** `useAdminOrders({ cliente: "ab" })` es usado
- **THEN** el query param `cliente` es omitido de la URL (no enviado)
