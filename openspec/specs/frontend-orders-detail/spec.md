# frontend-orders-detail Specification

## Purpose
Provides the `OrderDetailPage` at `/orders/:id` for CLIENT users to view the full detail of their own orders, including items with snapshots, order history timeline, payment status, and cancel action. Also provides the `useOrderDetail` hook. Introduced in Change 20 (orders-visualization).

## ADDED Requirements

### Requirement: Página de detalle de pedido del cliente (/orders/:id)

El sistema SHALL proveer la página `OrderDetailPage` en `src/pages/OrderDetailPage/` que muestra el detalle completo de un pedido propio del CLIENT.

La página SHALL:
- Estar accesible en `/orders/:id` con `RoleGuard roles={['CLIENT','ADMIN']}`.
- Consumir `GET /api/v1/pedidos/{id}` via el hook `useOrderDetail(pedidoId)`.
- Mostrar items con `nombre_snapshot`, `precio_snapshot`, `cantidad` y exclusiones.
- Mostrar `subtotal`, `costo_envio`, `total`.
- Mostrar el estado actual del pedido (badge coloreado por estado).
- Mostrar el componente `OrderHistoryTimeline` con el historial completo.
- Mostrar el estado del pago (campo `pago`): pending/approved/rejected con `mp_status`.
- Integrar `usePaymentStatus` condicionalmente: si `estado_codigo === "PENDIENTE"` y `paymentStore.status === "pending"`, montar el hook de polling de Change 19. Esto reutiliza el hook existente con el mismo query key `["pedido", pedidoId]`.
- Mostrar el componente `EstadoActionBar` de `frontend-pedido-state-actions` para que el CLIENT pueda cancelar el pedido si es posible.
- Mostrar un botón "Volver a mis pedidos" que navega a `/orders`.
- Mostrar skeleton loaders durante la carga.
- Redirigir a `/403` si la API devuelve 403 (acceso a pedido ajeno).
- Redirigir a `/404` si la API devuelve 404 (pedido no encontrado).

El hook `useOrderDetail` SHALL residir en `src/features/orders/hooks/useOrderDetail.ts`.

#### Scenario: Cliente ve el detalle de su propio pedido
- **WHEN** un CLIENT navega a `/orders/{id}` donde el pedido le pertenece
- **THEN** `GET /api/v1/pedidos/{id}` es llamado
- **THEN** la página muestra los items con snapshots
- **THEN** la página muestra el historial de estados via `OrderHistoryTimeline`
- **THEN** la página muestra el estado del pago

#### Scenario: Polling activo cuando el pedido está PENDIENTE
- **WHEN** la página carga un pedido con `estado_codigo === "PENDIENTE"` y `paymentStore.status === "pending"`
- **THEN** `usePaymentStatus` está montado con el `pedidoId` correcto
- **THEN** `GET /api/v1/pedidos/{pedidoId}` es refrescado automáticamente cada 30s
- **THEN** no se realizan llamadas duplicadas al backend (TanStack Query deduplication via mismo query key)

#### Scenario: Polling inactivo cuando el pedido no está PENDIENTE
- **WHEN** la página carga un pedido con `estado_codigo === "CONFIRMADO"` (u otro estado no-PENDIENTE)
- **THEN** `usePaymentStatus` está montado pero `enabled=false` (condición del hook de Change 19)
- **THEN** no se realizan polls adicionales

#### Scenario: Redirect a /403 cuando el backend devuelve 403
- **WHEN** el backend devuelve HTTP 403 (pedido ajeno)
- **THEN** la página redirige al usuario a `/403`

#### Scenario: Redirect a /404 cuando el backend devuelve 404
- **WHEN** el backend devuelve HTTP 404 (pedido inexistente)
- **THEN** la página redirige al usuario a `/404`

#### Scenario: EstadoActionBar visible para cancelación en PENDIENTE
- **WHEN** el pedido está en `estado_codigo = "PENDIENTE"` y el usuario es CLIENT
- **THEN** `EstadoActionBar` renderiza el botón "Cancelar pedido"
- **THEN** al confirmar, `useCancelarPedidoCliente` realiza `DELETE /api/v1/pedidos/{id}`

#### Scenario: Skeleton loaders durante la carga inicial
- **WHEN** la query está en `isLoading`
- **THEN** se muestran placeholders para items, timeline y pago

---

### Requirement: Hook useOrderDetail — TanStack Query para detalle de pedido

El sistema SHALL implementar `useOrderDetail(pedidoId: string)` en `src/features/orders/hooks/useOrderDetail.ts` como `useQuery`.

Query key: `pedidoEstadoKeys.detail(pedidoId)` = `['pedido', pedidoId]` (compatible con Change 18 y Change 19).

```typescript
// Tipo PedidoDetail (frontend)
interface PedidoDetail {
  id: string
  usuario_id: string
  usuario: UsuarioBasic | null
  estado_codigo: string
  forma_pago_codigo: string
  subtotal: string
  costo_envio: string
  total: string
  notas: string | null
  direccion_id: string | null
  direccion: DireccionBasic | null
  items: DetallePedidoRead[]
  historial: HistorialRead[]
  pago: PagoResponse | null
  created_at: string
}

interface UsuarioBasic {
  id: string
  nombre: string
  apellido: string
  email: string
}

interface DireccionBasic {
  alias: string | null
  linea1: string
}
```

`DetallePedidoRead` y `HistorialRead` se reusan de `frontend-checkout` y `frontend-pedido-state-actions` respectivamente.

#### Scenario: Hook usa el mismo query key que useHistorialPedido y usePaymentStatus
- **WHEN** `useOrderDetail("pedido-123")` y `usePaymentStatus("pedido-123")` están ambos montados
- **THEN** ambos usan `queryKey: ["pedido", "pedido-123"]`
- **THEN** TanStack Query los unifica en un solo fetch activo (no hay requests duplicados)

#### Scenario: Hook devuelve PedidoDetail en éxito
- **WHEN** la API responde con `200 PedidoDetail`
- **THEN** `data` contiene el objeto tipado
- **THEN** `isLoading` es `false`

#### Scenario: Hook propaga error 403
- **WHEN** la API responde con HTTP 403
- **THEN** `isError === true`
- **THEN** `error.response.status === 403`
- **THEN** la página puede usar este error para redirigir a `/403`
