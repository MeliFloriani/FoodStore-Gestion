# frontend-order-confirmation Specification

## Purpose
Provides the `OrderConfirmationPage` at `/order-confirmation/:id`, shown immediately after successful order creation. Displays order summary, integrates the MercadoPago payment button, and provides a link to the full order detail. Introduced in Change 20 (orders-visualization).

## ADDED Requirements

### Requirement: Página OrderConfirmation (/order-confirmation/:id)

El sistema SHALL proveer la página `OrderConfirmationPage` en `src/pages/OrderConfirmationPage/` que se muestra inmediatamente después de la creación exitosa de un pedido.

La página SHALL:
- Estar accesible en `/order-confirmation/:id` con `RoleGuard roles={['CLIENT']}`. Roles PEDIDOS y ADMIN son rechazados a `/403` — el flujo de confirmación post-creación es exclusivo de compradores CLIENT.
- Leer el `pedidoId` del URL param `:id`.
- Consumir `GET /api/v1/pedidos/{id}` via `useOrderDetail(pedidoId)` para obtener el resumen del pedido.
- Mostrar: número de pedido (id truncado o completo), estado ("PENDIENTE - Esperando pago"), items con `nombre_snapshot` y `precio_snapshot`, subtotal, costo de envío, total.
- Mostrar un botón **"Pagar con MercadoPago"** que inicia el flujo de pago del Change 19. El botón SHALL delegar al componente `PayWithMercadoPagoButton` de `src/features/checkout-payment/` (ya existente en Change 19). Al hacer clic, invoca `POST /api/v1/pagos` y redirige al `init_point` de MercadoPago.
- Mostrar un botón **"Ver detalle del pedido"** que navega a `/orders/:id`.
- NO montar `usePaymentStatus` — el polling es responsabilidad de `CheckoutReturnPage` (`/checkout/return`) del Change 19.
- Mostrar skeleton loaders si la query de detalle está cargando.

La navegación a esta página SHALL ocurrir automáticamente desde el hook `useCreateOrder` (Change 17) en su callback `onSuccess`: `navigate('/order-confirmation/${pedido.id}')`.

#### Scenario: OrderConfirmationPage se muestra post-creación exitosa
- **WHEN** `useCreateOrder` resuelve con HTTP 201 y navega a `/order-confirmation/{pedidoId}`
- **THEN** la página renderiza con el `pedidoId` del URL
- **THEN** `GET /api/v1/pedidos/{pedidoId}` es llamado para obtener el resumen
- **THEN** se muestran los items del pedido con snapshots

#### Scenario: Botón "Pagar con MercadoPago" inicia el flujo de pago
- **WHEN** el usuario hace clic en "Pagar con MercadoPago"
- **THEN** `POST /api/v1/pagos` es llamado con `pedido_id` y `idempotency_key` generado
- **THEN** si la respuesta es exitosa, el browser redirige a `init_point` (MercadoPago)
- **THEN** si la respuesta es un error, se muestra un toast con el mensaje de error

#### Scenario: Botón "Ver detalle del pedido" navega al detalle
- **WHEN** el usuario hace clic en "Ver detalle del pedido"
- **THEN** el navegador navega a `/orders/{pedidoId}`

#### Scenario: Estado del pedido muestra "PENDIENTE - Esperando pago"
- **WHEN** el pedido recién creado tiene `estado_codigo = "PENDIENTE"`
- **THEN** el badge/label muestra "PENDIENTE - Esperando pago"

#### Scenario: Skeleton visible mientras carga el detalle
- **WHEN** `useOrderDetail` está en estado `isLoading`
- **THEN** se muestran skeleton placeholders para los items y los totales

#### Scenario: Pedido no existente redirige a /404
- **WHEN** la API devuelve 404 para el `pedidoId` del URL
- **THEN** la página redirige a `/404`

#### Scenario: 403 cuando CLIENT navega a /order-confirmation/<uuid-ajeno>
- **GIVEN** un usuario CLIENT autenticado
- **WHEN** navega manualmente a `/order-confirmation/<uuid-de-otro-cliente>` (URL guessable)
- **WHEN** `useOrderDetail` recibe HTTP 403 de `GET /api/v1/pedidos/<uuid-ajeno>`
- **THEN** la página redirige a `/403` (ForbiddenPage)
- **THEN** el comportamiento es consistente con `OrderDetailPage` para errores 403

---

### Requirement: Integración con PayWithMercadoPagoButton (Change 19)

La página `OrderConfirmationPage` SHALL importar y usar `PayWithMercadoPagoButton` de `src/features/checkout-payment/` (ya existente). No SHALL reimplementar la lógica de creación de preferencias MP.

El botón recibe `pedidoId: string` como prop y gestiona internamente el `idempotency_key` y la llamada a `POST /api/v1/pagos`.

#### Scenario: PayWithMercadoPagoButton reutilizado sin duplicar lógica
- **WHEN** `OrderConfirmationPage` renderiza el botón de pago
- **THEN** el componente usado es el mismo `PayWithMercadoPagoButton` del Change 19
- **THEN** no existe un segundo componente de pago en el codebase con la misma responsabilidad
