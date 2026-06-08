## Why

Los endpoints `GET /api/v1/pedidos` y `GET /api/v1/pedidos/{id}` no existen todavía: el CLIENT no puede listar ni ver el detalle de sus pedidos, y los roles PEDIDOS/ADMIN carecen de panel de gestión con filtros. Sin esta capacidad, el ciclo completo compra → pago → seguimiento queda incompleto y el criterio de rúbrica "Frontend — Panel Admin (15 pts)" y "Frontend — Funcionalidades Cliente (15 pts)" no son evaluables. Este change abre el Sprint 7 entregando la visualización end-to-end de pedidos.

## What Changes

- **Nuevo endpoint** `GET /api/v1/pedidos`: listado paginado discriminado por RBAC — CLIENT ve solo sus pedidos (server-side filter), PEDIDOS/ADMIN ven todos con filtros adicionales (estado, rango de fechas, búsqueda de cliente). Un único endpoint con discriminación RBAC según el contrato de Integrador §5.3, que especifica exactamente este esquema.
- **Nuevo endpoint** `GET /api/v1/pedidos/{id}`: detalle completo del pedido. CLIENT obtiene 403 si intenta ver un pedido ajeno (RN-RB05). Incluye items con snapshots, historial completo (reutiliza data de `backend-order-history`), dirección FK y pagos asociados.
- **Nuevos schemas Pydantic**: `PedidoListItem` (listado compacto) y `PedidoDetail` (detalle completo con joins).
- **Nuevas páginas frontend**: listado CLIENT (`/orders`), detalle CLIENT (`/orders/:id`), página `OrderConfirmation` (`/order-confirmation/:id`), panel de gestión PEDIDOS/ADMIN (`/pedidos-panel`) y detalle de gestión (`/pedidos-panel/:id`).
- **Nuevo componente** `OrderHistoryTimeline`: timeline visual del historial alimentado por `GET /api/v1/pedidos/{id}/historial` (ya existente en `backend-order-history`). Reutiliza `useHistorialPedido` de `frontend-pedido-state-actions`.
- **Polling de PaymentStatus** en el detalle del pedido cuando `estado_codigo === "PENDIENTE"`: reutiliza `usePaymentStatus` de `frontend-payment-polling`. No se duplica lógica.
- **Filtros con debounce** en el panel de gestión: estado (select), rango de fechas (`desde`/`hasta`), búsqueda de cliente (email/nombre con debounce 400ms).
- **Delta en `backend-api-v1-router`**: registrar los dos nuevos endpoints GET de pedidos en `build_v1_router`.
- **Delta en `frontend-routing`**: agregar rutas `/orders`, `/orders/:id`, `/order-confirmation/:id`, y activar el subtree `/pedidos-panel/*`.

## Capabilities

### New Capabilities

- `backend-orders-listing`: `GET /api/v1/pedidos` — listado paginado con discriminación RBAC y filtros.
- `backend-orders-detail`: `GET /api/v1/pedidos/{id}` — detalle completo con items, historial, dirección y pago.
- `frontend-orders-history`: página de listado de pedidos para el CLIENT con filtro por estado y paginación.
- `frontend-orders-detail`: página de detalle de pedido propio para el CLIENT con timeline y polling de pago.
- `frontend-order-confirmation`: página `OrderConfirmation` post-creación con botón "Pagar con MercadoPago" y "Ver detalle".
- `frontend-orders-management-panel`: panel de gestión para PEDIDOS/ADMIN con filtros, búsqueda con debounce y paginación.
- `frontend-order-history-timeline`: componente reusable `OrderHistoryTimeline` que renderiza el historial de estados.

### Modified Capabilities

- `backend-api-v1-router`: registrar `GET /api/v1/pedidos` y `GET /api/v1/pedidos/{id}` en `build_v1_router`.
- `frontend-routing`: agregar rutas `/orders`, `/orders/:id`, `/order-confirmation/:id`; conectar `/pedidos-panel/*` con el panel real.

## Impact

- **Backend**: nuevo service `pedidos_service.py` extendido con métodos `list_pedidos()` y `get_pedido_detail()`. Nuevo repositorio `PedidosRepository` extendido con `list_by_usuario()`, `list_all_filtered()` y `get_full_detail()`. Schemas nuevos en `pedidos/schemas.py`: `PedidoListItem` y `PedidoDetail`.
- **Frontend**: nuevas páginas en `src/pages/`, nuevas features en `src/features/orders/` y `src/features/orders-panel/`. Reutiliza `useHistorialPedido` y `pedidoEstadoKeys` de `frontend-pedido-state-actions` (Change 18), y `usePaymentStatus` de `frontend-payment-polling` (Change 19).
- **RBAC**: endpoint `GET /api/v1/pedidos` requiere autenticación; CLIENT ve solo sus datos (server-side isolation). Endpoint `GET /api/v1/pedidos/{id}` aplica 403 explícito para acceso cruzado de CLIENT (no 404).
- **Dependencias de specs vivas**: `backend-order-history`, `backend-order-creation`, `backend-pagos-management`, `backend-pagination-schema`, `frontend-pedido-state-actions`, `frontend-payment-polling`, `frontend-routing`.
- **Sin cambios** en: flujo de pago (Change 19), FSM/transiciones (Change 18), creación de pedido (Change 17). Deuda OQ-01 (snapshot de dirección) documentada pero no cerrada en este change.
