## ADDED Requirements

### Requirement: Hook useValidatePreCheckout implementado con TanStack Query useMutation

El sistema SHALL implementar `useValidatePreCheckout()` como un custom hook que usa TanStack Query `useMutation` para enviar la validación al endpoint `POST /api/v1/pedidos/validar`. El hook SHALL:
- Leer los ítems actuales del `cartStore` y derivar el payload `ValidarPreCheckoutRequest`.
- Convertir `item.precio` (number en cartStore) a string con `item.precio.toFixed(2)` antes de enviarlo.
- Enviar la request usando el Axios client configurado en `frontend-http-client` (con interceptor refresh).
- Exponer `mutateAsync`, `isPending`, `isError`, `isSuccess`, `data`, y `error` del mutation.

El hook SHALL residir en `src/features/pre-checkout-validation/` siguiendo la estructura FSD.

El tipo de retorno del mutation SHALL ser `ValidarPreCheckoutResponse`:
```typescript
interface ValidarPreCheckoutResponse {
  ok: boolean
  items: ItemValidadoRead[]
  cambios: CambioRead[]
}

interface ItemValidadoRead {
  producto_id: string
  cantidad_solicitada: number
  stock_disponible: number | null
  precio_actual: string | null
  precio_percibido: string
  vigente: boolean
  disponible: boolean | null
}

interface CambioRead {
  producto_id: string
  tipo: 'PRODUCTO_NO_VIGENTE' | 'PRODUCTO_NO_DISPONIBLE' | 'STOCK_INSUFICIENTE' | 'PRECIO_CAMBIADO' | 'PERSONALIZACION_INVALIDA'
  detalle: Record<string, unknown>
}
```

#### Scenario: Hook envía items del cartStore al endpoint
- **WHEN** se llama `mutateAsync()` o `mutateAsync(items)` con el carrito cargado
- **THEN** se realiza `POST /api/v1/pedidos/validar` con `{ items: [...] }` derivado del cartStore
- **THEN** cada item incluye `precio` como string con 2 decimales (ej: `"250.00"`)

#### Scenario: Hook expone estado isPending durante la request
- **WHEN** la mutación está en curso
- **THEN** `isPending` es `true` y el componente puede mostrar estado de carga

#### Scenario: Hook expone data con ValidarPreCheckoutResponse en éxito
- **WHEN** el servidor devuelve HTTP 200
- **THEN** `data` contiene el `ValidarPreCheckoutResponse` tipado
- **THEN** `isSuccess` es `true`

#### Scenario: Hook expone error en fallo de red o 4xx
- **WHEN** el servidor devuelve 401, 403 o hay error de red
- **THEN** `isError` es `true` y `error` contiene el AxiosError correspondiente

#### Scenario: Precio se convierte de number a string antes de enviar
- **WHEN** `cartStore` tiene un ítem con `precio: 250` (number)
- **THEN** el hook envía `precio: "250.00"` (string) en el body

---

### Requirement: Componente PreCheckoutReview muestra resultado de validación

El sistema SHALL implementar `<PreCheckoutReview />` como componente React que:
1. Al montarse, dispara automáticamente `useValidatePreCheckout().mutateAsync()` vía `useEffect` (on-mount). No hay botón de "Validar carrito" — la validación es parte del proceso de carga de la página de revisión.
2. Mientras `isPending` es true, muestra un estado de carga (spinner + texto "Verificando tu carrito...").
3. Si `isError`, muestra un mensaje de error con opción de reintentar.
4. Si `isSuccess`:
   - Lista los ítems del carrito con su estado de validación (vigente, disponible, stock, precio).
   - Muestra cambios detectados agrupados por ítem con descripción legible por tipo.
   - Si `ok === true` y `cambios` está vacío: habilita botón `"Continuar al pago"` (texto estándar) y botón `"Ajustar carrito"`.
   - Si `ok === false`: deshabilita `"Continuar al pago"` con tooltip explicativo; habilita `"Ajustar carrito"`.
   - Si `ok === true` y `cambios` contiene al menos un `PRECIO_CAMBIADO` (y ningún cambio bloqueante): habilita el botón con texto `"Continuar con nuevos precios"` (NO `"Continuar al pago"`) y muestra aviso visible con texto exacto `"Los precios de [N] producto(s) cambiaron. Al continuar, aceptás los nuevos precios."` donde `[N]` es el número de ítems con `PRECIO_CAMBIADO`.
   - El texto `"Continuar al pago"` solo se usa cuando `cambios` está completamente vacío.

El componente SHALL residir en `src/features/pre-checkout-validation/ui/PreCheckoutReview.tsx`.

#### Scenario: Componente muestra spinner durante validación
- **WHEN** `isPending` es true
- **THEN** se renderiza un indicador de carga visible
- **THEN** el botón "Continuar al pago" no es visible o está deshabilitado

#### Scenario: ok=true — botón continuar habilitado
- **WHEN** la validación retorna `ok: true` y `cambios: []`
- **THEN** el botón "Continuar al pago" está habilitado
- **THEN** no se muestran alertas de error

#### Scenario: ok=false con STOCK_INSUFICIENTE — botón continuar deshabilitado
- **WHEN** la validación retorna `ok: false` con al menos un cambio de tipo `STOCK_INSUFICIENTE`
- **THEN** el botón "Continuar al pago" está deshabilitado
- **THEN** se muestra un mensaje indicando el stock disponible para el producto afectado

#### Scenario: Solo PRECIO_CAMBIADO — botón "Continuar con nuevos precios" habilitado con aviso explícito
- **WHEN** la validación retorna `ok: true` y `cambios` contiene solo entradas de tipo `"PRECIO_CAMBIADO"`
- **THEN** el botón de continuar muestra el texto `"Continuar con nuevos precios"` (no `"Continuar al pago"`)
- **THEN** se muestra aviso visible con texto `"Los precios de [N] producto(s) cambiaron. Al continuar, aceptás los nuevos precios."` donde N es el count de cambios PRECIO_CAMBIADO
- **THEN** el usuario al hacer clic acepta implícitamente los nuevos precios (no se requiere confirmación adicional)

#### Scenario: PRODUCTO_NO_VIGENTE — botón continuar deshabilitado con sugerencia
- **WHEN** la validación retorna un cambio `tipo: "PRODUCTO_NO_VIGENTE"`
- **THEN** el botón "Continuar al pago" está deshabilitado
- **THEN** se muestra un mensaje sugiriendo eliminar el producto del carrito

#### Scenario: Botón "Ajustar carrito" navega de regreso al carrito
- **WHEN** el usuario hace clic en "Ajustar carrito"
- **THEN** el usuario es redirigido a `/cart` o se abre el cart drawer (según implementación)
- **THEN** el `cartStore` no es modificado por el componente

#### Scenario: Error de red muestra opción de reintentar
- **WHEN** `isError` es true (fallo de red o error HTTP)
- **THEN** se muestra mensaje de error genérico
- **THEN** se muestra botón "Reintentar" que vuelve a disparar la mutación

---

### Requirement: Ruta /checkout/review protegida con guard CLIENT

El sistema SHALL registrar la ruta `/checkout/review` en el router de React como ruta privada bajo `ProtectedRoute` con `RoleGuard roles={['CLIENT', 'ADMIN']}`. La ruta SHALL renderizar lazy `<PreCheckoutReviewPage />` que compone `<PreCheckoutReview />`.

La ruta SHALL ser un subnivel de `/checkout` para reutilizar el layout del flujo de checkout.

#### Scenario: Cliente autenticado accede a /checkout/review
- **WHEN** un usuario con rol `CLIENT` navega a `/checkout/review`
- **THEN** se renderiza `PreCheckoutReviewPage` sin redirección

#### Scenario: Usuario no autenticado es redirigido a /login
- **WHEN** un usuario no autenticado navega a `/checkout/review`
- **THEN** `ProtectedRoute` redirige a `/login` con `state.from` preservado

#### Scenario: Usuario con rol STOCK es redirigido a /403
- **WHEN** un usuario con rol `STOCK` (sin CLIENT ni ADMIN) navega a `/checkout/review`
- **THEN** `RoleGuard` redirige a `/403`

---

### Requirement: Feature pre-checkout-validation sigue arquitectura FSD

El sistema SHALL organizar el feature `pre-checkout-validation` siguiendo FSD estricto bajo `src/features/pre-checkout-validation/`:

```
src/features/pre-checkout-validation/
├── api/
│   └── validatePreCheckout.ts     -- función de API (axios call)
├── model/
│   └── types.ts                   -- ValidarPreCheckoutRequest, Response, tipos
├── hooks/
│   └── useValidatePreCheckout.ts  -- custom hook (useMutation)
├── ui/
│   └── PreCheckoutReview.tsx      -- componente principal
└── index.ts                       -- barrel export
```

La feature SHALL importar únicamente hacia abajo en FSD:
- De `entities/` (tipos de producto, ingrediente si necesarios).
- De `shared/` (http client, ui components, utils).
- NO importar de otras features ni de `pages/`.
- NO modificar ni re-exportar lógica de `cartStore` (pertenece a `features/cart` o `shared/stores`).

#### Scenario: Feature no rompe el contrato del cartStore
- **WHEN** se importa `useValidatePreCheckout` en un componente
- **THEN** el hook lee de `cartStore` pero no llama a `addItem`, `removeItem`, `clearCart` ni ningún setter del cartStore
- **THEN** los selectores `subtotal()`, `costoEnvio()`, `total()` del cartStore siguen funcionando como antes

#### Scenario: Barrel export expone solo la API pública de la feature
- **WHEN** se importa desde `@/features/pre-checkout-validation`
- **THEN** están disponibles: `useValidatePreCheckout`, `PreCheckoutReview`, y los tipos `ValidarPreCheckoutResponse`, `CambioRead`, `ItemValidadoRead`
- **THEN** los internos de implementación (axios call directo, etc.) no son accesibles desde fuera de la feature

---

### Requirement: Tests del hook useValidatePreCheckout

El sistema SHALL incluir tests unitarios para `useValidatePreCheckout` que cubran:
- Envío correcto del payload derivado del cartStore (conversión precio number → string).
- Estado `isPending` mientras la mutación está en curso.
- `data` con `ValidarPreCheckoutResponse` en respuesta 200.
- `isError` en respuesta 401 / error de red.

Los tests SHALL usar `@testing-library/react-hooks` o `renderHook` de `@testing-library/react`, con `QueryClientWrapper` de TanStack Query y mocks de axios vía `vi.mock` (Vitest).

#### Scenario: Test cubre conversión de precio
- **WHEN** el mock de cartStore devuelve `precio: 250` (number) en un item
- **THEN** el test verifica que el payload enviado al mock de axios contiene `precio: "250.00"` (string)

#### Scenario: Test cubre respuesta ok=true
- **WHEN** el mock de axios devuelve `{ ok: true, items: [...], cambios: [] }`
- **THEN** `data.ok` es `true` y `data.cambios` es un array vacío

---

### Requirement: Tests del componente PreCheckoutReview

El sistema SHALL incluir tests de integración para `<PreCheckoutReview />` que cubran:
- Estado de carga (spinner visible cuando `isPending`).
- Botón "Continuar al pago" habilitado cuando `ok=true`.
- Botón "Continuar al pago" deshabilitado cuando `ok=false` por `STOCK_INSUFICIENTE`.
- Aviso de precio cambiado visible cuando el único cambio es `PRECIO_CAMBIADO`.
- Mensaje de error con botón "Reintentar" cuando `isError`.

Los tests SHALL usar `@testing-library/react` con mock de `useValidatePreCheckout`.

#### Scenario: Test ok=false deshabilita el botón de continuar
- **WHEN** el mock del hook devuelve `isSuccess=true, data={ ok: false, cambios: [{tipo: "STOCK_INSUFICIENTE", ...}] }`
- **THEN** el botón "Continuar al pago" tiene atributo `disabled`
