## Epic 1: Backend — Schemas Pydantic

- [x] 1.1 Crear `backend/app/schemas/pedidos.py` con `ItemPedidoCreate` (producto_id: UUID, cantidad: int ≥ 1, exclusiones: list[UUID] = [])
- [x] 1.2 Agregar `PedidoCreate` con `items: list[ItemPedidoCreate]` (min_length=1), `forma_pago_codigo: str`, `direccion_id: UUID | None`, `notas: str | None`
- [x] 1.3 Crear `DetallePedidoRead` con `id: UUID`, `producto_id: UUID`, `nombre_snapshot: str`, `precio_snapshot: str` (Decimal via @field_serializer), `cantidad: int`, `personalizacion: list[UUID]`
- [x] 1.4 Crear `HistorialEstadoPedidoRead` con `id: UUID`, `estado_desde: str | None`, `estado_hacia: str`, `motivo: str | None`, `created_at: datetime`
- [x] 1.5 Crear `PedidoRead` con `id: UUID`, `usuario_id: UUID`, `estado_codigo: str`, `forma_pago_codigo: str`, `direccion_id: UUID | None`, `subtotal: str`, `costo_envio: str`, `total: str`, `notas: str | None`, `items: list[DetallePedidoRead]`, `historial: list[HistorialEstadoPedidoRead]`, `created_at: datetime`
- [x] 1.6 Aplicar `@field_serializer` en `PedidoRead` para los campos Decimal (`subtotal`, `costo_envio`, `total`) → string con 2 decimales, siguiendo el patrón de Change 11

## Epic 2: Backend — Repository

- [x] 2.1 Crear `backend/app/repositories/pedido.py` con `PedidoRepository(BaseRepository[Pedido])`
- [x] 2.2 Implementar método `lock_productos_for_update(session: AsyncSession, ids: list[UUID]) -> list[Producto]` — `SELECT * FROM producto WHERE id IN (:ids) ORDER BY id FOR UPDATE`; el ORDER BY id previene deadlocks
- [x] 2.3 Implementar método `get_forma_pago(session: AsyncSession, codigo: str) -> FormaPago | None` — `SELECT * FROM forma_pago WHERE codigo = :codigo`
- [x] 2.4 Implementar método `create_pedido(session, pedido: Pedido) -> Pedido` — `session.add(pedido); await session.flush()` para obtener el ID antes del COMMIT
- [x] 2.5 Implementar método `create_detalle(session, detalle: DetallePedido) -> DetallePedido` — `session.add(detalle); await session.flush()`
- [x] 2.6 Implementar método `create_historial(session, historial: HistorialEstadoPedido) -> HistorialEstadoPedido` — `session.add(historial); await session.flush()`
- [x] 2.7 Implementar método `decrement_stock(session: AsyncSession, producto_id: UUID, cantidad: int)` — `UPDATE producto SET stock_cantidad = stock_cantidad - :cantidad WHERE id = :id`; atómico

## Epic 3: Backend — UnitOfWork (modificación)

- [x] 3.1 Agregar accessor `uow.pedidos` → `PedidoRepository(self._session)` con lazy property en `backend/app/core/uow.py`
- [x] 3.2 Verificar que el import usa `from app.repositories.pedido import PedidoRepository` (layer-first path)
- [x] 3.3 Verificar que el accessor sigue el patrón `@property` con cache `_pedidos` (consistente con accessors existentes)

## Epic 4: Backend — Service

- [x] 4.1 Crear `backend/app/services/pedidos_service.py` con función `crear_pedido(uow: UnitOfWork, user_id: UUID, request: PedidoCreate) -> PedidoRead`
- [x] 4.2 Implementar validación de carrito no vacío: `if not request.items: raise HTTPException(400, code="CART_EMPTY")`
- [x] 4.3 Implementar lock pesimista: `productos = await uow.pedidos.lock_productos_for_update(producto_ids_ordenados)` dentro del UoW
- [x] 4.4 Implementar validación por producto: `deleted_at IS NULL` → 400 `PRODUCT_NOT_FOUND`; `disponible=False` → 400 `PRODUCT_NOT_AVAILABLE`; `stock < cantidad` → 409 `INSUFFICIENT_STOCK` con detalle `{stock_disponible, cantidad_solicitada}`
- [x] 4.5 Implementar validación de personalización (batch): `SELECT * FROM producto_ingrediente WHERE producto_id IN (:ids)` una sola query; verificar en memoria `es_removible=True` y pertenencia → 400 `INVALID_CUSTOMIZATION` con detalle `{ingrediente_id, razon}`
- [x] 4.6 Implementar validación de forma de pago: `get_forma_pago(codigo)` → si None o `habilitado=False` → 400 `PAYMENT_METHOD_INVALID`
- [x] 4.7 Implementar validación de dirección: si `request.direccion_id is not None`, buscar en `uow.direcciones.get(id)` → si None → 400 `ADDRESS_NOT_FOUND`; si `direccion.usuario_id != user_id` → 403 `ADDRESS_NOT_OWNED`
- [x] 4.8 Implementar cálculo de totales server-side: `subtotal = Σ(Decimal(producto.precio_base) × item.cantidad)`, `costo_envio = Decimal("50.00") if request.direccion_id else Decimal("0.00")`, `total = subtotal + costo_envio`
- [x] 4.9 Crear `Pedido` con `usuario_id`, `estado_codigo="PENDIENTE"`, `forma_pago_codigo`, `direccion_id`, `subtotal`, `costo_envio`, `total`, `notas`; llamar `uow.pedidos.create_pedido(pedido)` para obtener ID con flush
- [x] 4.10 Crear `DetallePedido` por cada item con `pedido_id`, `producto_id`, `nombre_snapshot=producto.nombre`, `precio_snapshot=producto.precio_base`, `cantidad`, `personalizacion=item.exclusiones`; llamar `create_detalle` por cada uno
- [x] 4.11 Decrementar stock por cada item: `uow.pedidos.decrement_stock(producto_id, cantidad)`
- [x] 4.12 Crear primer `HistorialEstadoPedido` con `pedido_id`, `estado_desde=None`, `estado_hacia="PENDIENTE"`, `cambiado_por_id=None`; llamar `create_historial`
- [x] 4.13 Construir y retornar `PedidoRead` (el UoW hará COMMIT automático al salir del `async with`)
- [x] 4.14 Verificar que el service NO llama `session.commit()` directamente en ningún punto

## Epic 5: Backend — Router

- [x] 5.1 Crear `backend/app/api/v1/pedidos.py` con `APIRouter` (sin prefijo propio)
- [x] 5.2 Implementar `POST /` con `response_model=PedidoRead`, `status_code=201`, dependencia `require_role(["CLIENT","ADMIN"])` y `current_user = Depends(get_current_user)`
- [x] 5.3 Router extrae `user_id = current_user.id` y delega a `service.crear_pedido(uow, user_id, request)`
- [x] 5.4 Registrar `pedidos_router` en `build_v1_router` con `prefix="/pedidos"` y `tags=["pedidos"]` en `backend/app/api/v1/router.py`
- [x] 5.5 Verificar que el router de pedidos NO colisiona con el router `pedidos_validar` ya montado (el path `/validar` pertenece al otro router, el `POST /` al nuevo)

## Epic 6: Backend — Tests unitarios del Service

- [x] 6.1 Crear `backend/tests/test_pedidos_service.py` con fixtures de UoW en modo test
- [x] 6.2 Test: carrito vacío → HTTPException 400 `CART_EMPTY`
- [x] 6.3 Test: producto inexistente (no retornado por lock_for_update) → HTTPException 400 `PRODUCT_NOT_FOUND`
- [x] 6.4 Test: producto con `deleted_at` no nulo → HTTPException 400 `PRODUCT_NOT_AVAILABLE`
- [x] 6.5 Test: producto con `disponible=False` → HTTPException 400 `PRODUCT_NOT_AVAILABLE`
- [x] 6.6 Test: stock insuficiente post-lock → HTTPException 409 `INSUFFICIENT_STOCK` con detalle correcto
- [x] 6.7 Test: ingrediente inválido en exclusiones (no es_removible) → HTTPException 400 `INVALID_CUSTOMIZATION`
- [x] 6.8 Test: forma de pago inexistente → HTTPException 400 `PAYMENT_METHOD_INVALID`
- [x] 6.9 Test: forma de pago con `habilitado=False` → HTTPException 400 `PAYMENT_METHOD_INVALID`
- [x] 6.10 Test: `direccion_id` no pertenece al usuario → HTTPException 403 `ADDRESS_NOT_OWNED`
- [x] 6.11 Test: `direccion_id=None` → pedido creado con `costo_envio=Decimal("0.00")`, estado `PENDIENTE`
- [x] 6.12 Test: `direccion_id` válida → pedido creado con `costo_envio=Decimal("50.00")`, estado `PENDIENTE`
- [x] 6.13 Test: totales calculados server-side → `total = subtotal + costo_envio` (ignorar totales del carrito)
- [x] 6.14 Test: `DetallePedido.nombre_snapshot` = nombre del producto al momento de creación (no nombre del request)
- [x] 6.15 Test: `DetallePedido.precio_snapshot` = precio del producto al momento de creación (no precio del carrito)
- [x] 6.16 Test: `HistorialEstadoPedido` creado con `estado_desde=None`, `estado_hacia="PENDIENTE"`
- [x] 6.17 Test: rollback — si falla el INSERT de DetallePedido, no se persiste el Pedido (atomicidad)
- [x] 6.18 Test: lock order — los productos se lockan en orden ascendente por ID (prevención de deadlock)

## Epic 7: Backend — Tests de concurrencia (SELECT FOR UPDATE)

- [x] 7.1 Crear `backend/tests/test_pedidos_concurrency.py` requiriendo BD real (PostgreSQL, NO SQLite) — agregar `pytestmark = [pytest.mark.asyncio, pytest.mark.integration]` a nivel de módulo
- [x] 7.2 Test: dos coroutines concurrentes crean pedido para el mismo producto con stock=1 → exactamente una tiene éxito, la otra recibe 409 `INSUFFICIENT_STOCK`; usar `asyncio.gather(..., return_exceptions=True)`
- [x] 7.3 Test: post-concurrencia, `producto.stock_cantidad == 0` (no negativo, no 1 — no doble decremento)
- [x] 7.4 Marcar estos tests con `@pytest.mark.asyncio` y `@pytest.mark.integration` (requieren BD real PostgreSQL); en `conftest.py` o `pytest.ini`: `integration` debe saltarse si `DATABASE_URL` apunta a SQLite o si no está configurado; los tests unitarios de Epic 6 NO deben usar este marker

## Epic 8: Backend — Tests del Router

- [x] 8.1 Crear `backend/tests/test_pedidos_router.py` con client de test FastAPI autenticado
- [x] 8.2 Test: `POST /api/v1/pedidos` sin token → 401
- [x] 8.3 Test: `POST /api/v1/pedidos` con rol `STOCK` → 403
- [x] 8.4 Test: `POST /api/v1/pedidos` con rol `PEDIDOS` → 403
- [x] 8.5 Test: `POST /api/v1/pedidos` con body mal formado → 422
- [x] 8.6 Test: `POST /api/v1/pedidos` con carrito válido y token CLIENT → 201, body contiene `estado_codigo="PENDIENTE"`, `items`, `historial[0].estado_desde=null`
- [x] 8.7 Test: response body incluye `id` del pedido (UUID), `total` como string decimal

## Epic 9: Frontend — Tipos y API client

- [x] 9.1 Crear `src/features/checkout/model/types.ts` con interfaces: `CreateOrderRequest`, `OrderItemRequest`, `PedidoRead`, `DetallePedidoRead`, `HistorialEstadoPedidoRead`
- [x] 9.2 Crear `src/features/checkout/api/createOrder.ts` con función `createOrder(request: CreateOrderRequest): Promise<PedidoRead>` usando el Axios client (`apiClient.post('/pedidos', request)`)

## Epic 10: Frontend — Hook useCreateOrder

- [x] 10.1 Crear `src/features/checkout/hooks/useCreateOrder.ts` con `useMutation` de TanStack Query
- [x] 10.2 Implementar en el hook la derivación del payload `CreateOrderRequest` a partir de `cartStore.items` (mapear `CartItem[]` a `OrderItemRequest[]`)
- [x] 10.3 Pasar `personalizacion: string[]` del cartStore directamente como `exclusiones: string[]` (UUIDs) — sin conversión; `Ingrediente.id` es UUID en ambos lados
- [x] 10.4 Aceptar parámetros `forma_pago_codigo: string` y `direccion_id: string | null` como argumentos del `mutateAsync`
- [x] 10.5 En `onSuccess`: llamar `cartStore.clearCart()` para vaciar el carrito
- [x] 10.6 Exponer `mutateAsync`, `isPending`, `isError`, `isSuccess`, `data`, `error` desde el hook

## Epic 11: Frontend — Componente CheckoutSubmit

- [x] 11.1 Crear `src/features/checkout/ui/CheckoutSubmit.tsx`
- [x] 11.2 Implementar estado de carga: botón deshabilitado con spinner cuando `isPending`
- [x] 11.3 Implementar estado de error: mostrar mensaje de error mapeado al código del backend (`CART_EMPTY`, `INSUFFICIENT_STOCK`, `PAYMENT_METHOD_INVALID`, etc.)
- [x] 11.4 Implementar flujo de éxito: navegar a `/orders/{pedido.id}` si la ruta existe (Change 20); si no existe, mostrar mensaje "¡Pedido confirmado!" y limpiar carrito
- [x] 11.5 Implementar botón "Confirmar pedido" que llama `mutateAsync({ forma_pago_codigo, direccion_id })`
- [x] 11.6 Verificar que errores transaccionales del backend (409 `INSUFFICIENT_STOCK`) muestran mensaje legible al usuario (no mensaje técnico)
- [x] 11.7 Verificar que el carrito se limpia (`clearCart()`) solo en `onSuccess`, nunca en caso de error

## Epic 12: Frontend — Integración y routing

- [x] 12.1 Crear `src/pages/CheckoutConfirmPage/index.tsx` (o integrar en la página existente de checkout) que compone `<CheckoutSubmit />`
- [x] 12.2 Si se agrega ruta `/checkout/confirm`: registrarla en el router bajo `ProtectedRoute` con `RoleGuard roles={['CLIENT','ADMIN']}`
- [x] 12.3 Crear `src/features/checkout/index.ts` con barrel export de `useCreateOrder`, `CheckoutSubmit` y tipos públicos

## Epic 13: Frontend — Tests

- [x] 13.1 Crear `src/features/checkout/hooks/__tests__/useCreateOrder.test.ts`
- [x] 13.2 Test hook: mock de cartStore con items → verifica que el payload enviado incluye `exclusiones: string[]` (UUIDs — idéntico al `personalizacion` del cartStore, sin parseInt)
- [x] 13.3 Test hook: mock axios devuelve 201 con `PedidoRead` → `isSuccess=true`, `cartStore.clearCart()` fue llamado
- [x] 13.4 Test hook: mock axios devuelve 409 `INSUFFICIENT_STOCK` → `isError=true`, carrito NO se limpió
- [x] 13.5 Crear `src/features/checkout/ui/__tests__/CheckoutSubmit.test.tsx`
- [x] 13.6 Test componente: `isPending=true` → botón deshabilitado, spinner visible
- [x] 13.7 Test componente: `isSuccess=true` → mensaje de confirmación o navegación disparada
- [x] 13.8 Test componente: `isError=true` con código `INSUFFICIENT_STOCK` → mensaje de error legible visible
- [x] 13.9 Test componente: `isError=true` con código `PAYMENT_METHOD_INVALID` → mensaje de error legible visible

## Epic 14: Documentación y sync

- [x] 14.1 Verificar que `openspec status --change order-creation-with-snapshots --json` refleja artifacts generados
- [x] 14.2 Al archivar el change, actualizar `docs/CHANGES.md`: mover Change 17 a "Ya realizado", agregar fecha, evidencia y specs sincronizadas
- [x] 14.3 Al archivar, sincronizar `openspec/specs/backend-api-v1-router/spec.md` con el nuevo router de pedidos
- [x] 14.4 Al archivar, sincronizar `openspec/specs/backend-unit-of-work/spec.md` con los nuevos accessors `uow.pedidos`
