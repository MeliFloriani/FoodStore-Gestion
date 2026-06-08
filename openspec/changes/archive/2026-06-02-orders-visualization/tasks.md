## 1. Backend — Schemas Pydantic

- [x] 1.1 Agregar `PedidoListItem` a `backend/app/pedidos/schemas.py` con campos: `id`, `estado_codigo`, `total` (decimal string via `@field_serializer`), `forma_pago_codigo`, `items_count`, `created_at`, `usuario_nombre: str | None`, `usuario_email: str | None`. Usar `ConfigDict(from_attributes=True)`.
- [x] 1.2 Agregar `UsuarioBasic` en schemas de pedidos: `{ id, nombre, apellido, email }`.
- [x] 1.3 Agregar `DireccionBasic` en schemas de pedidos: `{ alias: str | None, linea1: str }`.
- [x] 1.4 Agregar `PedidoDetail` a `backend/app/pedidos/schemas.py` con campos: `id`, `usuario_id`, `usuario: UsuarioBasic | None`, `estado_codigo`, `forma_pago_codigo`, `subtotal` / `costo_envio` / `total` (decimal strings via `@field_serializer`), `notas: str | None`, `direccion_id: UUID | None`, `direccion: DireccionBasic | None`, `items: list[DetallePedidoRead]`, `historial: list[HistorialRead]`, `pago: PagoResponse | None`, `created_at`.
- [x] 1.5 Verificar que `DetallePedidoRead`, `HistorialRead` y `PagoResponse` se importan desde sus módulos originales (no se duplican).

## 2. Backend — Repository

- [x] 2.1 Agregar método `list_with_filters(usuario_id: UUID | None, estado: str | None, desde: date | None, hasta: date | None, cliente: str | None, page: int, size: int) -> tuple[list[Pedido], int]` en `PedidosRepository`. Si `usuario_id` es no-None, filtrar `WHERE pedido.usuario_id = :usuario_id`. Si `cliente` tiene al menos 3 chars, hacer JOIN a `usuario` y ILIKE sobre email y nombre+apellido.
- [x] 2.2 Agregar método `get_full_detail(pedido_id: UUID) -> Pedido | None` en `PedidosRepository` usando `selectinload` para `Pedido.detalles`, `Pedido.historial` y `Pedido.usuario` (NO usar lazy loading ni `joinedload`). La `DireccionEntrega` se carga si `direccion_id` no es NULL. El pago más reciente se obtiene vía llamada separada `uow.pagos.get_latest_by_pedido_id(pedido_id)` — no se carga como relación del `Pedido`.
- [x] 2.3 Confirmar que `UnitOfWork` expone `uow.pagos` (ya existente en Change 19) para el detail service.

## 3. Backend — Service

- [x] 3.1 Agregar función `list_pedidos(uow, current_user, params: ListPedidosParams) -> tuple[list[PedidoListItem], int]` en el pedidos service. Discrimina por rol: CLIENT → pasa `usuario_id=current_user.id`, ignora `desde/hasta/cliente`; PEDIDOS/ADMIN → pasa todos los filtros opcionales.
- [x] 3.2 Agregar función `get_pedido_detail(uow, pedido_id: UUID, current_user) -> PedidoDetail` en el pedidos service. Lógica: obtener pedido; si no existe → `HTTPException(404, "ORDER_NOT_FOUND")`; si rol CLIENT y `pedido.usuario_id != current_user.id` → `HTTPException(403, "ORDER_NOT_OWNED")`; si rol STOCK → `HTTPException(403, "FORBIDDEN")`; construir `PedidoDetail` con joins.
- [x] 3.3 Verificar que ningún service llama `session.commit()` directamente (UoW pattern).

## 4. Backend — Router

- [x] 4.1 Agregar `GET /` (listado) al `pedidos_router` en `backend/app/api/v1/pedidos.py`. Auth: `require_role(["CLIENT", "PEDIDOS", "ADMIN"])`. Response model: `Page[PedidoListItem]`. Query params: `estado: str | None`, `desde: date | None`, `hasta: date | None`, `cliente: str | None`, `page: int = 1`, `size: int = 20`. Delega a `list_pedidos(uow, current_user, params)`.
- [x] 4.2 Agregar `GET /{id}` (detalle) al `pedidos_router`. Auth: `get_current_user` (cualquier autenticado; el service valida RBAC). Response model: `PedidoDetail`. Delega a `get_pedido_detail(uow, id, current_user)`.
- [x] 4.3 Verificar el orden de declaración de rutas en `pedidos_router`: `POST /` → `GET /` → `PATCH /{id}/estado` → `GET /{id}/historial` → `GET /{id}` → `DELETE /{id}`. FastAPI evalúa en orden de declaración.
- [x] 4.4 Confirmar que ambas nuevas rutas tienen `response_model` explícito (criterio de rúbrica).

## 5. Backend — Tests

- [x] 5.1 Test `test_list_pedidos_client_isolation`: CLIENT A no puede ver pedidos del CLIENT B. Verificar que `GET /api/v1/pedidos` con token de CLIENT A no devuelve pedidos de CLIENT B.
- [x] 5.2 Test `test_list_pedidos_client_ignores_admin_params`: CLIENT que envía `?cliente=test&desde=2026-01-01` recibe 200 y ve solo sus propios pedidos (filtro server-side ignorado).
- [x] 5.3 Test `test_list_pedidos_pagination`: `GET /api/v1/pedidos?page=1&size=2` devuelve `Page[PedidoListItem]` con `pages` calculado correctamente.
- [x] 5.4 Test `test_list_pedidos_filter_estado`: `GET /api/v1/pedidos?estado=PENDIENTE` devuelve solo pedidos PENDIENTE.
- [x] 5.5 Test `test_list_pedidos_stock_forbidden`: token STOCK recibe HTTP 403.
- [x] 5.6 Test `test_get_pedido_detail_own_pedido`: CLIENT puede ver su propio pedido con snapshots correctos.
- [x] 5.7 Test `test_get_pedido_detail_cross_user_403`: CLIENT recibe HTTP 403 al intentar ver pedido ajeno (no 404).
- [x] 5.8 Test `test_get_pedido_detail_snapshots`: el detalle devuelve `nombre_snapshot` y `precio_snapshot` inmutables aunque el producto haya cambiado después.
- [x] 5.9 Test `test_get_pedido_detail_includes_historial`: detalle incluye `historial[]` ordenado por `created_at ASC`.
- [x] 5.10 Test `test_get_pedido_detail_pago_null`: detalle devuelve `pago: null` cuando no hay pago.
- [x] 5.11 Test `test_get_pedido_detail_pago_populated`: detalle devuelve el pago más reciente cuando existe.
- [x] 5.12 Test `test_get_pedido_detail_pedidos_role_can_see_any`: token PEDIDOS puede ver cualquier pedido.
- [x] 5.13 Test `test_admin_filter_by_fecha_rango`: ADMIN con `?desde=&hasta=` devuelve solo pedidos del rango.
- [x] 5.14 Test `test_admin_filter_cliente_min_3_chars`: `?cliente=ab` (2 chars) ignora el filtro; `?cliente=abc` lo aplica.
- [x] 5.15 Test: `GET /api/v1/pedidos?desde=2026-05-31&hasta=2026-05-01` → 422 con `code=INVALID_DATE_RANGE`.
- [x] 5.16 Test backend: `get_full_detail` con un pedido de 5 items y 4 historial entries ejecuta ≤ 5 queries (verificar con `sqlalchemy.event.listen('after_cursor_execute')`).

## 6. Frontend — Tipos e infraestructura compartida

- [x] 6.1 Crear/verificar `src/shared/hooks/useDebounce.ts` — hook genérico `useDebounce<T>(value: T, delay: number): T`.
- [x] 6.2 Definir tipos TypeScript de `PedidoListItem`, `PedidoPage`, `PedidoDetail`, `UsuarioBasic`, `DireccionBasic` en `src/entities/pedido/` (FSD entities layer).
- [x] 6.3 Crear función de API `pedidosApi.ts` en `src/shared/api/` o en `src/entities/pedido/api/`: `listPedidos(params)`, `getPedidoDetail(id)` usando el Axios client de `frontend-http-client`.

## 7. Frontend — Hooks de datos

- [x] 7.1 Crear `useClientOrders(params)` en `src/features/orders/hooks/useClientOrders.ts` — `useQuery` sobre `GET /api/v1/pedidos`. Query key: `[...pedidoEstadoKeys.list(), params]`.
- [x] 7.2 Crear `useOrderDetail(pedidoId)` en `src/features/orders/hooks/useOrderDetail.ts` — `useQuery` sobre `GET /api/v1/pedidos/{id}`. Query key: `pedidoEstadoKeys.detail(pedidoId)` = `['pedido', pedidoId]`.
- [x] 7.3 Crear `useAdminOrders(params)` en `src/features/orders-panel/hooks/useAdminOrders.ts` — `useQuery` sobre `GET /api/v1/pedidos` con filtros admin. Omitir `?cliente=` si tiene menos de 3 chars. Query key: `['pedidos', 'admin', params]`.
- [x] 7.4 Verificar que `useOrderDetail` usa el MISMO query key que `usePaymentStatus` de Change 19 (`['pedido', pedidoId]`) — no hay requests duplicados.

## 8. Frontend — Componente OrderHistoryTimeline

- [x] 8.1 Crear `src/features/orders/ui/OrderHistoryTimeline.tsx` que acepta `pedidoId: string` y consume `useHistorialPedido(pedidoId)` importado de `@/features/pedido-state-actions`.
- [x] 8.2 Renderizar la lista cronológica: `estado_desde → estado_hacia`, fecha formateada (`dd/MM/yyyy HH:mm`), actor (`null` → "Sistema"), motivo si existe.
- [x] 8.3 Mostrar skeleton loaders durante `isLoading` y error amigable en `isError`.
- [x] 8.4 Verificar que el primer entry (con `estado_desde: null`) renderiza sin crash (mostrar "Pedido creado — PENDIENTE").

## 9. Frontend — Página OrdersPage (listado CLIENT)

- [x] 9.1 Crear `src/pages/OrdersPage/index.tsx` que reemplaza el placeholder de `/orders`.
- [x] 9.2 Implementar filtro por estado (select) y paginación (anterior/siguiente).
- [x] 9.3 Mostrar skeleton loaders y estado vacío.
- [x] 9.4 Navegar a `/orders/:id` al hacer clic en un item.

## 10. Frontend — Página OrderDetailPage (detalle CLIENT)

- [x] 10.1 Crear `src/pages/OrderDetailPage/index.tsx` que consume `useOrderDetail(pedidoId)`.
- [x] 10.2 Mostrar items con snapshots, totales, estado y dirección (best-effort).
- [x] 10.3 Montar `usePaymentStatus(pedidoId)` condicionalmente cuando `estado_codigo === "PENDIENTE"` (reutiliza hook de Change 19 — mismo query key, no hay request duplicado).
- [x] 10.4 Incluir `<OrderHistoryTimeline pedidoId={pedidoId} />`.
- [x] 10.5 Incluir `<EstadoActionBar>` de `frontend-pedido-state-actions` para acciones del CLIENT.
- [x] 10.6 Redirigir a `/403` si el error es 403; a `/404` si el error es 404.
- [x] 10.7 Mostrar skeleton loaders durante la carga.

## 11. Frontend — Página OrderConfirmationPage

- [x] 11.1 Crear `src/pages/OrderConfirmationPage/index.tsx` que lee `:id` de URL params.
- [x] 11.2 Mostrar resumen del pedido con items, totales y estado "PENDIENTE - Esperando pago".
- [x] 11.3 Incluir `<PayWithMercadoPagoButton pedidoId={pedidoId} />` de `frontend-checkout-payment` (Change 19, sin duplicar lógica).
- [x] 11.4 Incluir botón "Ver detalle del pedido" → navega a `/orders/:id`.
- [x] 11.5 Redirigir a `/404` si la API devuelve 404.
- [x] 11.6 Actualizar el callback `onSuccess` de `useCreateOrder` (Change 17) en `CheckoutPage` para navegar a `/order-confirmation/${pedido.id}` en lugar del comportamiento actual (si era `/orders` o placeholder).

## 12. Frontend — Panel PedidosPanelPage (gestión PEDIDOS/ADMIN)

- [x] 12.1 Crear `src/pages/PedidosPanelPage/index.tsx` que reemplaza el placeholder de `/pedidos-panel`.
- [x] 12.2 Implementar tabla con columnas: ID (truncado), cliente (nombre + email), estado (badge), total, fecha.
- [x] 12.3 Implementar filtros: estado (select, sin debounce), fechas `desde`/`hasta` (inputs date, debounce 400ms via `useDebounce`), búsqueda cliente (input text, debounce 400ms, mínimo 3 chars vía `useAdminOrders`).
- [x] 12.4 Implementar paginación.
- [x] 12.5 Navegar a `/pedidos-panel/:id` al hacer clic en una fila.

## 13. Frontend — Página PedidosPanelDetailPage (detalle gestión)

- [x] 13.1 Crear `src/pages/PedidosPanelDetailPage/index.tsx` que consume `useOrderDetail(pedidoId)`.
- [x] 13.2 Mostrar datos del cliente (`usuario.nombre`, `usuario.apellido`, `usuario.email`).
- [x] 13.3 Mostrar items con snapshots, totales, dirección (best-effort).
- [x] 13.4 Incluir `<OrderHistoryTimeline pedidoId={pedidoId} />`.
- [x] 13.5 Incluir `<EstadoActionBar>` para que el staff pueda avanzar el estado del pedido.
- [x] 13.6 Mostrar estado del pago (`pago.mp_status`).
- [x] 13.7 Botón "Volver al panel" → `/pedidos-panel`.

## 14. Frontend — Routing

- [x] 14.1 Agregar ruta `/orders` → `OrdersPage` (lazy) con `RoleGuard roles={['CLIENT']}` (reemplaza placeholder; nota: spec D-15 requiere CLIENT-ONLY, tasks.md original decía CLIENT+ADMIN — se siguió la spec).
- [x] 14.2 Agregar ruta `/orders/:id` → `OrderDetailPage` (lazy) con `RoleGuard roles={['CLIENT']}`.
- [x] 14.3 Agregar ruta `/order-confirmation/:id` → `OrderConfirmationPage` (lazy) con `RoleGuard roles={['CLIENT']}`.
- [x] 14.4 Reemplazar placeholder de `/pedidos-panel` con `PedidosPanelPage` (lazy), manteniendo `RoleGuard roles={['PEDIDOS','ADMIN']}`.
- [x] 14.5 Agregar ruta `/pedidos-panel/:id` → `PedidosPanelDetailPage` (lazy) con `RoleGuard roles={['PEDIDOS','ADMIN']}`.
- [x] 14.6 Verificar que `/checkout/return` (Change 19) no es afectada.

## 15. Frontend — Tests

- [x] 15.1 Test `OrderHistoryTimeline`: renderiza 3 entradas en orden cronológico dado un historial de 3 transiciones.
- [x] 15.2 Test `OrderHistoryTimeline`: la primera entrada con `estado_desde: null` renderiza sin crash ("Pedido creado — PENDIENTE").
- [x] 15.3 Test `OrderHistoryTimeline`: entrada con `actor_user_id: null` muestra "Sistema".
- [x] 15.4 Test `OrderHistoryTimeline`: muestra skeleton durante `isLoading`.
- [x] 15.5 Test `useOrderDetail`: usa query key `['pedido', pedidoId]` — mismo que `usePaymentStatus` (no requests duplicados con TanStack Query).
- [x] 15.6 Test `useAdminOrders`: omite `?cliente=` cuando tiene menos de 3 caracteres.
- [x] 15.7 Test `useAdminOrders`: incluye `?cliente=` cuando tiene 3+ caracteres.
- [x] 15.8 Test `OrderDetailPage`: redirige a `/403` cuando la API devuelve HTTP 403.
- [x] 15.9 Test `PedidosPanelPage`: `RoleGuard` bloquea a usuario STOCK (redirect `/403`).
- [x] 15.10 Test `OrdersPage`: filtro por estado llama a la API con `?estado=<valor>`.
- [x] 15.11 Test `useDebounce`: verifica que el valor debounced se actualiza después del delay configurado.
- [x] 15.12 Test integración polling: `useOrderDetail` y `usePaymentStatus` montados simultáneamente con mismo pedidoId realizan solo 1 request activo (TanStack Query deduplication).
- [x] 15.13 Test: `OrderConfirmationPage` con `useOrderDetail` mock devolviendo 403 → router navega a `/403`.

## 16. Verificación final

- [x] 16.1 Ejecutar `openspec validate --strict orders-visualization` — debe pasar sin errores.
- [x] 16.2 Verificar `openspec status --change orders-visualization --json` — todos los artifacts en estado `complete` e `isComplete: true`.
- [x] 16.3 Smoke test backend: `GET /api/v1/pedidos` con token CLIENT devuelve 200 con `Page[PedidoListItem]`.
- [x] 16.4 Smoke test backend: `GET /api/v1/pedidos/{id}` con token CLIENT ajeno devuelve 403.
- [x] 16.5 Smoke test frontend: navegar a `/orders` como CLIENT → lista visible con paginación.
- [x] 16.6 Smoke test frontend: navegar a `/order-confirmation/{id}` → resumen + botón MP visible.
- [x] 16.7 Smoke test frontend: navegar a `/pedidos-panel` como PEDIDOS → tabla con filtros.
- [x] 16.8 Verificar `tsc --noEmit` en el frontend: 0 errores TypeScript.
- [x] 16.9 Verificar que `usePaymentStatus` (Change 19, `frontend-payment-polling`) consume `GET /api/v1/pedidos/{pedidoId}` (definido por este change en `backend-orders-detail`) y usa query key `['pedido', pedidoId]` consistente con `useOrderDetail` y `usePaymentStatus`. Confirmar dedupe automática TanStack Query.
- [x] 16.10 Reconciliación manual: leer `frontend-payment-polling` spec vivo y confirmar que `usePaymentStatus` en código consume el endpoint correcto (`GET /api/v1/pedidos/{pedidoId}`) y no `/latest`. Si hay discrepancia en código, abrir micro-change.
- [x] 16.11 Verificar que los tipos en `src/entities/pedido/model/types.ts` coinciden 1:1 con los definidos en `specs/frontend-orders-history`, `specs/frontend-orders-detail` y `specs/frontend-order-confirmation` (mismos nombres, tipos, opcionalidad). El spec es la fuente de verdad.
