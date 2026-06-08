## Why

Al iniciar el checkout, el carrito del cliente refleja precios y disponibilidades capturados en el pasado (localStorage). Sin una validación server-side explícita antes de crear el pedido, el sistema puede intentar crear órdenes con productos eliminados, sin stock suficiente o con precios desactualizados, degradando la experiencia del usuario y generando pedidos inconsistentes. Este change introduce el paso de validación pre-checkout (US-069, US-070) como barrera UX explícita: antes de avanzar a la creación de pedido (Change 17), el cliente recibe una revisión detallada del estado actual de su carrito.

## What Changes

- **Nuevo endpoint backend** `POST /api/v1/pedidos/validar`: recibe los ítems del carrito (con precios percibidos por el cliente) y devuelve un reporte de validación sin crear pedido ni modificar stock. Es idempotente y stateless.
- **Nuevos schemas Pydantic** `ValidarPreCheckoutRequest` / `ValidarPreCheckoutResponse` con respuesta estructurada `200 OK` que incluye flag `ok` global, lista de ítems validados y lista de cambios detectados (tipos: `PRODUCTO_NO_VIGENTE`, `PRODUCTO_NO_DISPONIBLE`, `STOCK_INSUFICIENTE`, `PRECIO_CAMBIADO`, `PERSONALIZACION_INVALIDA`).
- **Nuevo service backend** `pedidos_validar_service.validar_pre_checkout(uow, request)` — stateless, solo-lectura, ejecutado dentro de UoW sin commit de escrituras. Consulta productos con un único `SELECT ... WHERE id IN (...)` (política anti-N+1).
- **RBAC**: endpoint protegido con `require_role(["CLIENT", "ADMIN"])`. No es público para evitar scraping de stock.
- **Nueva feature frontend** `pre-checkout-validation` en FSD: hook `useValidatePreCheckout()` (TanStack Query `useMutation`) y componente `<PreCheckoutReview />`.
- **Nueva ruta frontend** `/checkout/review` (protegida CLIENT y ADMIN — ADMIN permitido para testing/staging y soporte; el endpoint es stateless/read-only) que hospeda el componente de revisión pre-checkout.
- **Integración con cartStore** (Change 15): la validación lee items del store pero no los modifica. El contrato existente del cartStore no se rompe.
- Registro del nuevo router en `backend-api-v1-router` (tag `pedidos-validacion`).
- Registro de ruta `/checkout/review` en `frontend-routing`.

## Capabilities

### New Capabilities

- `backend-pre-checkout-validations`: Endpoint `POST /api/v1/pedidos/validar`, schemas de request/response, service stateless de validación, tipos de cambio detectado, política de comparación de precios y personalización.
- `frontend-pre-checkout-validation`: Hook `useValidatePreCheckout`, componente `<PreCheckoutReview />`, ruta `/checkout/review`, lógica de presentación de cambios detectados y flujo de aceptación/cancelación.

### Modified Capabilities

- `backend-api-v1-router`: Registrar el nuevo sub-router de pedidos-validación con prefijo `/pedidos/validar` y tag `pedidos-validacion`.
- `frontend-routing`: Agregar ruta privada `/checkout/review` con guard CLIENT y ADMIN.

## Impact

- **Backend**: Nuevo módulo `app/pedidos/` (router, service, schemas). Reutiliza `productos_repository` existente (solo lectura). Sin migraciones de BD — no hay cambios de modelo.
- **Frontend**: Nueva feature `pre-checkout-validation` en FSD. Reutiliza `cartStore` (Change 15 archivado) como fuente de datos de entrada. Reutiliza `frontend-http-client` (Axios + refresh queue). No modifica otras features.
- **Dependencias confirmadas**: Change 11 `catalog-products-management` (archivado) provee `Producto` con `precio_base`, `stock_cantidad`, `disponible`, `deleted_at`. Change 15 `shopping-cart-clientside` (archivado) provee `cartStore` con `CartItem { producto_id, nombre, precio, cantidad, imagen_url?, personalizacion }`.
- **No impacto**: No hay cambios en BD, no se toca la FSM de pedidos, no se integra con pagos ni con lógica de reserva de stock.
- **Contrato hacia Change 17**: Change 17 (creación de pedido) deberá re-ejecutar validaciones equivalentes dentro de su propia UoW transaccional con `SELECT FOR UPDATE` para evitar TOCTOU. La validación de este change es asesoría UX, no garantía transaccional.
