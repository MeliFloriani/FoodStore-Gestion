## 1. Backend — Schemas Pydantic

- [x] 1.1 Crear `backend/app/schemas/pedidos_validar.py` con `ItemAValidar` (producto_id: str, cantidad: int ≥ 1, personalizacion: list[str] = [], precio: str)
- [x] 1.2 Agregar validador Pydantic en `ItemAValidar` que verifica que `precio` sea un string decimal parseable a `Decimal`
- [x] 1.3 Crear `ValidarPreCheckoutRequest` con `items: list[ItemAValidar]` con `min_length=1`
- [x] 1.4 Crear `ItemValidadoRead` (producto_id, cantidad_solicitada, stock_disponible: int|None, precio_actual: str|None, precio_percibido: str, vigente: bool, disponible: bool|None)
- [x] 1.5 Crear `CambioRead` con `tipo: Literal["PRODUCTO_NO_VIGENTE","PRODUCTO_NO_DISPONIBLE","STOCK_INSUFICIENTE","PRECIO_CAMBIADO","PERSONALIZACION_INVALIDA"]` y `detalle: dict`
- [x] 1.6 Crear `ValidarPreCheckoutResponse` con `ok: bool`, `items: list[ItemValidadoRead]`, `cambios: list[CambioRead]`

## 2. Backend — Service

- [x] 2.1 Crear `backend/app/services/pedidos_validar_service.py` con función `validar_pre_checkout(uow: UnitOfWork, request: ValidarPreCheckoutRequest) -> ValidarPreCheckoutResponse`
- [x] 2.2 Implementar en el service la recopilación de todos los `producto_id` únicos del request
- [x] 2.3 Implementar la consulta única `productos_repository.get_by_ids(ids)` dentro del UoW (SELECT WHERE id IN — política anti-N+1). **Nota**: el método `get_by_ids` debe ser implementado como una adición al `ProductoRepository` existente de Change 11 (`backend/app/repositories/producto.py`). Ver la sección MODIFIED en `specs/backend-pre-checkout-validations/spec.md` para el contrato exacto del método.
- [x] 2.4 Implementar lógica de evaluación por ítem en orden: vigencia (`deleted_at is None and producto exists`) → disponibilidad (`disponible=True`) → stock (`stock_cantidad >= cantidad`) → precio (Decimal cuantizado 0.01) → personalización
- [x] 2.5 Implementar detección de `PRODUCTO_NO_VIGENTE` con razón "no_encontrado" o "eliminado" (deleted_at no nulo)
- [x] 2.6 Implementar detección de `PRODUCTO_NO_DISPONIBLE` (disponible=False)
- [x] 2.7 Implementar detección de `STOCK_INSUFICIENTE` con `detalle: {stock_disponible, cantidad_solicitada}`
- [x] 2.8 Implementar detección de `PRECIO_CAMBIADO` comparando `Decimal(item.precio).quantize(Decimal('0.01'))` vs `producto.precio_base` con tolerancia cero; incluir `detalle: {precio_anterior, precio_actual}`
- [x] 2.9 Implementar detección de `PERSONALIZACION_INVALIDA`: obtener todos los `ProductoIngrediente` con un solo `SELECT ... WHERE producto_id IN (:ids)` para los productos que tienen personalización no vacía. No consultar ingredientes producto por producto. Verificar `es_removible=True` y pertenencia al producto en memoria sobre el resultado batch. Ver la spec de carga batch en `specs/backend-pre-checkout-validations/spec.md`.
- [x] 2.10 Implementar cálculo de `ok = len([c for c in cambios if c.tipo != "PRECIO_CAMBIADO"]) == 0`
- [x] 2.11 Construir lista `items_validados: list[ItemValidadoRead]` con una entrada por ítem del request
- [x] 2.12 Verificar que el service no invoca ningún método de escritura del UoW ni hace commit de cambios

## 3. Backend — Router

- [x] 3.1 Crear `backend/app/api/v1/pedidos_validar.py` con `APIRouter` y path `/validar`
- [x] 3.2 Implementar `POST /validar` con `response_model=ValidarPreCheckoutResponse`, dependencia `require_role(["CLIENT","ADMIN"])` y delegación al service
- [x] 3.3 Registrar `pedidos_validar_router` en `build_v1_router` con `prefix="/pedidos"` y `tags=["pedidos-validacion"]`

## 4. Backend — Tests

- [x] 4.1 Crear `backend/tests/test_pedidos_validar_service.py` con fixture de UoW en modo test
- [x] 4.2 Escribir test: carrito válido → `ok=True`, `cambios=[]`
- [x] 4.3 Escribir test: producto con `deleted_at` no nulo → `PRODUCTO_NO_VIGENTE`, `ok=False`
- [x] 4.4 Escribir test: producto `disponible=False` → `PRODUCTO_NO_DISPONIBLE`, `ok=False`
- [x] 4.5 Escribir test: `stock_cantidad < cantidad` → `STOCK_INSUFICIENTE` con `stock_disponible` correcto en detalle, `ok=False`
- [x] 4.6 Escribir test: precio cambiado en 0.01 como **único** cambio → tipo `PRECIO_CAMBIADO` en `cambios`, `ok=True` (cambio no bloqueante)
- [x] 4.7 Escribir test: precio cambiado + stock insuficiente → `ok=False` (cambio bloqueante presente)
- [x] 4.8 Escribir test: ingrediente inválido en personalización → `PERSONALIZACION_INVALIDA`, `ok=False`
- [x] 4.9 Escribir test: producto_id inexistente → `PRODUCTO_NO_VIGENTE` con razón "no_encontrado", `ok=False`
- [x] 4.10 Escribir test: el service realiza exactamente 1 query a la tabla `productos` para N ítems distintos (verificar anti-N+1 con mock o spy del repository)
- [x] 4.11 Crear `backend/tests/test_pedidos_validar_router.py` con client de test FastAPI autenticado
- [x] 4.12 Escribir test router: `POST /api/v1/pedidos/validar` sin token → 401
- [x] 4.13 Escribir test router: `POST /api/v1/pedidos/validar` con rol `STOCK` → 403
- [x] 4.14 Escribir test router: `POST /api/v1/pedidos/validar` con body mal formado → 422
- [x] 4.15 Escribir test router: `POST /api/v1/pedidos/validar` con carrito válido y token CLIENT → 200, `ok=True`

## 5. Frontend — Tipos y API client

- [x] 5.1 Crear `src/features/pre-checkout-validation/model/types.ts` con interfaces `ValidarPreCheckoutRequest`, `ItemAValidar`, `ValidarPreCheckoutResponse`, `ItemValidadoRead`, `CambioRead`, y tipo union `TipoCambio`
- [x] 5.2 Crear `src/features/pre-checkout-validation/api/validatePreCheckout.ts` con función `validatePreCheckout(items: ItemAValidar[]): Promise<ValidarPreCheckoutResponse>` usando el Axios client configurado (`apiClient.post('/pedidos/validar', ...)`)

## 6. Frontend — Hook

- [x] 6.1 Crear `src/features/pre-checkout-validation/hooks/useValidatePreCheckout.ts` con `useMutation` de TanStack Query
- [x] 6.2 Implementar en el hook la derivación del payload desde `cartStore`: mapear `CartItem[]` a `ItemAValidar[]` convirtiendo `item.precio` con `item.precio.toFixed(2)` a string
- [x] 6.3 Verificar que el hook no llama setters del cartStore (solo lectura)
- [x] 6.4 Exponer `mutateAsync`, `isPending`, `isError`, `isSuccess`, `data`, `error` desde el hook

## 7. Frontend — Componente PreCheckoutReview

- [x] 7.1 Crear `src/features/pre-checkout-validation/ui/PreCheckoutReview.tsx`
- [x] 7.2 Implementar estado de carga: spinner + texto "Verificando tu carrito..." cuando `isPending`
- [x] 7.3 Implementar estado de error: mensaje genérico + botón "Reintentar" cuando `isError`
- [x] 7.4 Implementar listado de ítems del carrito con indicadores de estado de validación (vigente, disponible, stock, precio)
- [x] 7.5 Implementar sección de cambios detectados: por cada `CambioRead` mostrar descripción legible según tipo
- [x] 7.6 Implementar lógica del botón de continuar: texto `"Continuar al pago"` si `cambios` vacío; texto `"Continuar con nuevos precios"` si `ok===true` y hay al menos un `PRECIO_CAMBIADO`; deshabilitado con tooltip si `ok===false` y hay cambios bloqueantes
- [x] 7.7 Implementar aviso visible de precios cambiados cuando `ok===true` y existen cambios de tipo `PRECIO_CAMBIADO`: mostrar texto exacto `"Los precios de [N] producto(s) cambiaron. Al continuar, aceptás los nuevos precios."` (N = cantidad de ítems con PRECIO_CAMBIADO) y cambiar etiqueta del botón a `"Continuar con nuevos precios"`
- [x] 7.8 Implementar botón "Ajustar carrito" que navega a `/cart`
- [x] 7.9 Disparar la mutación al montarse el componente `<PreCheckoutReview/>` invocando `mutateAsync()` automáticamente en `useEffect` (on-mount). No agregar un botón extra de "Verificar"; la validación es parte del proceso de carga de la página de revisión. El usuario ve inmediatamente el loading state y luego el resultado de la validación.

## 8. Frontend — Página y routing

- [x] 8.1 Crear `src/pages/PreCheckoutReviewPage/index.tsx` que compone `<PreCheckoutReview />`
- [x] 8.2 Registrar la ruta `/checkout/review` en el router de React bajo `ProtectedRoute` con `RoleGuard roles={['CLIENT','ADMIN']}` como subruta de `/checkout`
- [x] 8.3 Verificar que `/checkout` sigue funcionando como antes (sin conflicto con `/checkout/review`)
- [x] 8.4 Crear `src/features/pre-checkout-validation/index.ts` con barrel export de `useValidatePreCheckout`, `PreCheckoutReview`, y los tipos públicos

## 9. Frontend — Tests

- [x] 9.1 Crear `src/features/pre-checkout-validation/hooks/__tests__/useValidatePreCheckout.test.ts`
- [x] 9.2 Test hook: mock de cartStore con precio number → verifica payload enviado tiene precio como string "X.XX"
- [x] 9.3 Test hook: mock axios devuelve `{ ok: true, cambios: [] }` → `data.ok === true`
- [x] 9.4 Test hook: mock axios devuelve 401 → `isError === true`
- [x] 9.5 Test hook: `isPending` es true mientras la mutación está en curso (mock de axios con delay)
- [x] 9.6 Crear `src/features/pre-checkout-validation/ui/__tests__/PreCheckoutReview.test.tsx`
- [x] 9.7 Test componente: `isPending=true` → spinner visible, botón "Continuar al pago" no habilitado
- [x] 9.8 Test componente: `isSuccess=true, data.ok=true` → botón "Continuar al pago" habilitado, sin alertas de error
- [x] 9.9 Test componente: `isSuccess=true, data.ok=false` con `STOCK_INSUFICIENTE` → botón "Continuar al pago" tiene `disabled`, mensaje de stock visible
- [x] 9.10 Test componente: `isSuccess=true` con solo `PRECIO_CAMBIADO` → botón "Continuar al pago" habilitado, aviso de precios cambiados visible
- [x] 9.11 Test componente: `isError=true` → mensaje de error visible, botón "Reintentar" presente

## 10. Documentación

- [x] 10.1 Actualizar `docs/CHANGES.md`: mover Change 16 a estado "En progreso" con referencia a `openspec/changes/pre-checkout-validations/`
- [x] 10.2 Verificar que `openspec status --change pre-checkout-validations --json` confirma `isComplete: false` hasta que `tasks.md` sea generado (ya completado en propose) y `true` tras apply completo
- [x] 10.3 Al archivar este change, sincronizar también `openspec/specs/backend-api-v1-router/spec.md` con el nuevo endpoint registrado: agregar en la sección de rutas el registro de `pedidos_validar_router` con `prefix="/pedidos"` y `tags=["pedidos-validacion"]`, y el endpoint resultante `POST /api/v1/pedidos/validar`.
