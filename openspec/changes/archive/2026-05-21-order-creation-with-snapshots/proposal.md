## Why

Con Change 16 (`pre-checkout-validations`, archivado 2026-05-20), el cliente puede verificar el estado actual de su carrito antes de confirmar. Sin embargo, esa validación es consultiva y stateless: no crea ni reserva ningún recurso, y la ventana TOCTOU entre esa verificación y la creación del pedido es intencional. Este change cierra esa ventana: implementa `POST /api/v1/pedidos` con creación atómica vía Unit of Work, re-validando stock con `SELECT FOR UPDATE` dentro de la transacción para eliminar la posibilidad de overselling concurrente.

El sistema necesita un mecanismo confiable para persistir órdenes con inmutabilidad histórica garantizada: si el precio de un producto cambia mañana, los pedidos de hoy deben conservar el precio al momento de la compra (RN-04 v5). Los snapshots de `nombre_snapshot` + `precio_snapshot` en `DetallePedido` son el mecanismo principal de inmutabilidad. Para la dirección, Change 17 persiste únicamente la FK nullable `direccion_id` — el snapshot completo de campos de dirección (linea1, ciudad, etc.) es deuda técnica OQ-01 diferida a Change 20.

## What Changes

- **Nuevo endpoint backend** `POST /api/v1/pedidos`: creación atómica de pedido. Requiere rol `CLIENT` o `ADMIN`. Devuelve `PedidoRead` con HTTP 201 en éxito.
- **Nuevos schemas Pydantic**: `PedidoCreate`, `ItemPedidoCreate`, `PedidoRead`, `DetallePedidoRead`, `HistorialEstadoPedidoRead`.
- **Nuevo service backend** `pedidos_service.crear_pedido(uow, user_id, request)`: orquesta la transacción completa dentro de un único `UnitOfWork`.
- **Nuevo repository backend** `PedidoRepository` (hereda `BaseRepository[Pedido]`) con método `create_with_details`.
- **Modificación a UoW**: agregar accessor `uow.pedidos` apuntando a `PedidoRepository`. Los métodos para `DetallePedido` e `HistorialEstadoPedido` residen en ese mismo repositorio — no se crean accessors separados.
- **Nuevo hook frontend** `useCreateOrder()` (`useMutation` de TanStack Query 5) en la feature `checkout`.
- **Nuevo componente frontend** `<CheckoutSubmit />`: botón de confirmación, manejo de estado de carga/error, limpieza del carrito post-éxito.
- **Ruta frontend** `/checkout/confirm` (si no existe) o integración en `/checkout/review` existente como paso de confirmación.
- Registro del nuevo sub-router de pedidos en `backend-api-v1-router` (prefijo `/pedidos`, tag `pedidos`).

## Capabilities

### New Capabilities

- `backend-order-creation`: Endpoint `POST /api/v1/pedidos`, schemas de request/response, service transaccional de creación de pedido con SELECT FOR UPDATE, snapshots, HistorialEstadoPedido inicial, validaciones de carrito no vacío, producto, stock, personalización, forma de pago y dirección.
- `frontend-checkout`: Hook `useCreateOrder()`, componente `<CheckoutSubmit />`, flujo de éxito con limpieza del carrito y navegación, manejo de errores transaccionales del backend.

### Modified Capabilities

- `backend-api-v1-router`: Registrar el nuevo sub-router de pedidos con prefijo `/pedidos` y tag `pedidos`. Coexiste con el sub-router `pedidos-validacion` ya montado (Change 16).
- `backend-unit-of-work`: Agregar accessor `uow.pedidos` (expone `PedidoRepository` con métodos para `Pedido`, `DetallePedido` e `HistorialEstadoPedido`).

### Capabilities opcionales (solo si aplica)

- `frontend-cart-store`: Si `clearCart()` no está cubierta en Change 15 spec (ya existe según spec archivada — NO modificar).
- `frontend-routing`: Solo si se agrega ruta nueva `/checkout/confirm`.

## Impact

- **Backend**: Nuevo módulo `app/pedidos/` (o extensión del módulo pedidos existente): `pedidos_service.py`, `pedidos_router.py`, `pedidos_repository.py`, `schemas/pedidos.py`. Sin nuevas migraciones de BD — los modelos `Pedido`, `DetallePedido`, `HistorialEstadoPedido` ya existen desde Change 03. Se modifica `core/uow.py` para agregar los nuevos accessors.
- **Frontend**: Nueva feature `checkout` en FSD (o extensión de `pre-checkout-validation` si ya tiene la feature creada). Reutiliza `cartStore` (Change 15) para leer items y `clearCart()` post-éxito. Reutiliza `frontend-http-client`. No modifica otras features.
- **Dependencias confirmadas**: Change 14 provee `DireccionEntrega` con `usuario_id` (ownership). Change 15 provee `cartStore` con `CartItem`. Change 16 provee validación UX previa (consultiva). Change 04 provee `BaseRepository`, `UnitOfWork`, `require_role`.
- **No impacto**: No hay cambios de BD (sin migraciones). No se toca la FSM posterior a PENDIENTE (Change 18). No se integran pagos reales (Change 19). No hay panel de pedidos (Change 20).

## Out of Scope (explícito)

Los siguientes ítems están intencionalmente excluidos de este change:

| Item excluido | Change responsable |
|---|---|
| Pagos online reales (MercadoPago, webhooks, IPN) | Change 19 |
| Transiciones FSM posteriores a PENDIENTE (CONFIRMADO, EN_PREP, EN_CAMINO, ENTREGADO) | Change 18 |
| Cancelación de pedidos con restauración de stock | Change 18 |
| Panel de visualización de pedidos (listado, detalle completo) | Change 20 |
| Confirmación por email al cliente | Fuera del TPI |
| Paginación de pedidos | Change 20 |
| Cálculo dinámico de costo de envío | Fuera del TPI |
| Descuentos o cupones | Fuera del TPI |
