# frontend-orders-history Specification

## Purpose
Provides the `OrdersPage` at `/orders` for CLIENT users to browse their paginated order history, with state filtering and pagination controls. Also provides the `useClientOrders` hook. Introduced in Change 20 (orders-visualization).

## ADDED Requirements

### Requirement: Página de listado de pedidos del cliente (/orders)

El sistema SHALL proveer la página `OrdersPage` en `src/pages/OrdersPage/` que muestra el listado paginado de los pedidos del CLIENT autenticado.

La página SHALL:
- Estar accesible en `/orders` con `RoleGuard roles={['CLIENT']}` (ya registrada en `frontend-routing` — se activa con la implementación real en este change). Roles PEDIDOS y ADMIN son rechazados a `/403` — deben usar `/pedidos-panel`.
- Consumir `GET /api/v1/pedidos` via el hook `useClientOrders(params)` (TanStack Query `useQuery`).
- Mostrar un filtro por estado con un `<select>` con las opciones: Todos, PENDIENTE, CONFIRMADO, EN_PREP, EN_CAMINO, ENTREGADO, CANCELADO.
- Mostrar paginación con botones "Anterior" / "Siguiente" y número de página actual.
- Mostrar skeleton loaders mientras carga.
- Mostrar estado vacío cuando `items` está vacío.
- Mostrar un error amigable cuando la query falla.
- Navegar a `/orders/:id` al hacer clic en un item del listado.

El hook `useClientOrders` SHALL residir en `src/features/orders/hooks/useClientOrders.ts` y usar query key `pedidoEstadoKeys.list()` de `frontend-pedido-state-actions` para compatibilidad de invalidación.

#### Scenario: Cliente ve su lista de pedidos al navegar a /orders
- **WHEN** un usuario CLIENT autenticado navega a `/orders`
- **THEN** `GET /api/v1/pedidos` es llamado con el Bearer token del CLIENT
- **THEN** se muestra la lista de pedidos del cliente (no pedidos de otros usuarios)
- **THEN** cada item muestra: número de pedido (id truncado), fecha, estado, total

#### Scenario: Filtro por estado actualiza el listado
- **WHEN** el usuario selecciona "EN_CAMINO" en el select de estado
- **THEN** `GET /api/v1/pedidos?estado=EN_CAMINO` es llamado
- **THEN** el listado muestra solo pedidos en estado EN_CAMINO

#### Scenario: Paginación navega entre páginas
- **WHEN** el usuario hace clic en "Siguiente" estando en la primera página
- **THEN** `GET /api/v1/pedidos?page=2` es llamado
- **THEN** el listado actualiza con los items de la segunda página

#### Scenario: Estado vacío cuando el cliente no tiene pedidos
- **WHEN** la respuesta de `GET /api/v1/pedidos` devuelve `items: []`
- **THEN** se muestra un mensaje de estado vacío (ej: "Todavía no realizaste ningún pedido.")
- **THEN** se muestra un link o botón "Ir al catálogo"

#### Scenario: Skeleton loaders visibles durante la carga
- **WHEN** la query está en estado `isLoading`
- **THEN** se renderizan skeleton placeholders en lugar de las filas del listado

#### Scenario: Solo CLIENT puede acceder a /orders
- **WHEN** un usuario con rol STOCK navega a `/orders`
- **THEN** el `RoleGuard` redirige a `/403`
- **WHEN** un usuario con rol PEDIDOS navega a `/orders`
- **THEN** el `RoleGuard` redirige a `/403` (debe usar `/pedidos-panel`)
- **WHEN** un usuario con rol ADMIN navega a `/orders`
- **THEN** el `RoleGuard` redirige a `/403` (debe usar `/pedidos-panel`)

---

### Requirement: Hook useClientOrders — TanStack Query para listado de pedidos

El sistema SHALL implementar `useClientOrders(params: ClientOrdersParams)` en `src/features/orders/hooks/useClientOrders.ts` como `useQuery`.

```typescript
interface ClientOrdersParams {
  estado?: string
  page?: number
  size?: number
}

interface PedidoListItem {
  id: string
  estado_codigo: string
  total: string           // decimal string
  forma_pago_codigo: string
  items_count: number
  created_at: string
  usuario_nombre: string | null
  usuario_email: string | null
}

interface PedidoPage {
  items: PedidoListItem[]
  total: number
  page: number
  size: number
  pages: number
}
```

Query key SHALL ser `[...pedidoEstadoKeys.list(), params]` para incluir los filtros en el cache.

#### Scenario: Hook llama a GET /api/v1/pedidos con los parámetros correctos
- **WHEN** `useClientOrders({ estado: "CONFIRMADO", page: 1, size: 10 })` es usado
- **THEN** la request es `GET /api/v1/pedidos?estado=CONFIRMADO&page=1&size=10`
- **THEN** `isLoading` es `true` hasta que la respuesta llega

#### Scenario: Hook devuelve PedidoPage en éxito
- **WHEN** la API responde con `200 Page[PedidoListItem]`
- **THEN** `data` contiene `{ items, total, page, size, pages }`
- **THEN** `isError` es `false`

#### Scenario: Hook maneja error de red
- **WHEN** la API responde con HTTP 5xx
- **THEN** `isError` es `true`
- **THEN** `error` contiene el error de Axios

#### Scenario: useClientOrders nunca envía filtros admin
- **WHEN** `useClientOrders(params)` construye la URL de request
- **THEN** los query params `?desde`, `?hasta` y `?cliente` **no se incluyen** en ninguna circunstancia
- **THEN** el endpoint recibe únicamente `?estado`, `?page` y `?size`
