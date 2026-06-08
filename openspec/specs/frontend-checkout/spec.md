# frontend-checkout Specification

## Purpose
Checkout submission feature introduced in Change 17 (`order-creation-with-snapshots`). Provides the `useCreateOrder()` hook (TanStack Query `useMutation`) and the `<CheckoutSubmit />` component that submits the cart to `POST /api/v1/pedidos`, handles transactional errors from the backend (re-validates against real catalog state), clears the cart on success, and navigates to the order confirmation. This is the transactional step after the advisory Change 16 pre-checkout review.

Change 16 (`frontend-pre-checkout-validation`) remains valid as a UX pre-validation step. This capability does NOT replace it — it is the confirmation step that follows after the user reviews and accepts the pre-checkout results.

## ADDED Requirements

### Requirement: Hook useCreateOrder implementado con TanStack Query useMutation

El sistema SHALL implementar `useCreateOrder()` como un custom hook que usa TanStack Query `useMutation` para enviar `POST /api/v1/pedidos`. El hook SHALL:
- Derivar el payload `CreateOrderRequest` a partir de `cartStore.items` (leer con selector, no full-store subscription).
- Pasar `CartItem.personalizacion: string[]` (UUIDs en cartStore) directamente como `exclusiones: string[]` (UUIDs de ingredientes excluidos) — sin conversión, los IDs son UUID en ambos lados.
- Aceptar como argumentos del `mutateAsync`: `{ forma_pago_codigo: string, direccion_id: string | null }`.
- Enviar la request usando el Axios client configurado en `frontend-http-client` (con interceptor de refresh automático).
- En `onSuccess`: llamar `cartStore.clearCart()` para vaciar el carrito.
- Exponer `mutateAsync`, `isPending`, `isError`, `isSuccess`, `data`, `error`.

El hook SHALL residir en `src/features/checkout/` siguiendo la estructura FSD.

El tipo de retorno del mutation SHALL ser `PedidoRead`:
```typescript
interface CreateOrderRequest {
  items: OrderItemRequest[]
  forma_pago_codigo: string
  direccion_id: string | null
  notas?: string
}

interface OrderItemRequest {
  producto_id: string
  cantidad: number
  exclusiones: string[]   // UUID[] — UUIDs de ingredientes excluidos
}

interface PedidoRead {
  id: string
  usuario_id: string
  estado_codigo: string        // "PENDIENTE" en creación
  forma_pago_codigo: string
  direccion_id: string | null
  subtotal: string             // decimal string
  costo_envio: string          // "50.00" o "0.00"
  total: string                // decimal string
  notas: string | null
  items: DetallePedidoRead[]
  historial: HistorialEstadoPedidoRead[]
  created_at: string
}

interface DetallePedidoRead {
  id: string
  producto_id: string
  nombre_snapshot: string
  precio_snapshot: string    // decimal string — inmutable al momento de creación
  cantidad: number
  personalizacion: string[]  // UUIDs de ingredientes excluidos
}

interface HistorialEstadoPedidoRead {
  id: string
  estado_desde: string | null   // null para el primer registro
  estado_hacia: string
  motivo: string | null
  created_at: string
}
```

#### Scenario: Hook envía items del cartStore al endpoint con exclusiones como number[]
- **WHEN** se llama `mutateAsync({ forma_pago_codigo: "EFECTIVO", direccion_id: null })`
- **THEN** se realiza `POST /api/v1/pedidos` con body derivado del cartStore
- **THEN** cada item incluye `exclusiones: string[]` (UUIDs — idéntico al `personalizacion` del cartStore)

#### Scenario: Hook limpia el carrito en éxito
- **WHEN** el servidor devuelve HTTP 201
- **THEN** `cartStore.clearCart()` es llamado
- **THEN** `cartStore.getState().items` queda vacío

#### Scenario: Hook NO limpia el carrito en error
- **WHEN** el servidor devuelve HTTP 409 INSUFFICIENT_STOCK
- **THEN** `cartStore.clearCart()` NO es llamado
- **THEN** el carrito conserva sus items para que el usuario pueda ajustarlo

#### Scenario: Hook expone isPending durante la request
- **WHEN** la mutación está en curso
- **THEN** `isPending` es `true`

#### Scenario: Hook expone data con PedidoRead en éxito
- **WHEN** el servidor devuelve HTTP 201
- **THEN** `data` contiene el `PedidoRead` tipado
- **THEN** `isSuccess` es `true`

#### Scenario: Hook expone error en fallo
- **WHEN** el servidor devuelve HTTP 409 o 400
- **THEN** `isError` es `true`
- **THEN** `error` contiene la respuesta de error con `code` semántico

---

### Requirement: Componente CheckoutSubmit — botón de confirmación con manejo de estados

El sistema SHALL implementar `<CheckoutSubmit />` como un componente React que usa `useCreateOrder()` para orquestar la confirmación del pedido.

El componente SHALL aceptar como props: `formaPagoCodigo: string`, `direccionId: string | null`, `onSuccess?: (pedido: PedidoRead) => void`.

#### Scenario: Estado de carga — botón deshabilitado durante la request
- **WHEN** `isPending = true` (request en curso)
- **THEN** el botón "Confirmar pedido" está deshabilitado
- **THEN** el botón muestra un indicador de carga (spinner o texto "Enviando...")
- **THEN** el usuario no puede hacer doble submit

#### Scenario: Flujo de éxito — navegación y limpieza de carrito
- **WHEN** la mutation retorna HTTP 201
- **THEN** el carrito es vaciado via `clearCart()`
- **THEN** si existe la ruta `/orders/{pedido.id}` (Change 20), navegar a ella
- **THEN** si la ruta no existe aún, mostrar mensaje "¡Pedido confirmado! #PENDIENTE" visible al usuario

#### Scenario: Error transaccional INSUFFICIENT_STOCK — mensaje legible
- **WHEN** el servidor devuelve HTTP 409 con `code: "INSUFFICIENT_STOCK"`
- **THEN** el componente muestra mensaje legible: "Uno o más productos no tienen stock suficiente. Por favor revisá tu carrito."
- **THEN** el botón vuelve a habilitarse para que el usuario pueda redirigirse a ajustar el carrito
- **THEN** el carrito NO es limpiado

#### Scenario: Error transaccional PAYMENT_METHOD_INVALID — mensaje legible
- **WHEN** el servidor devuelve HTTP 400 con `code: "PAYMENT_METHOD_INVALID"`
- **THEN** el componente muestra mensaje legible: "La forma de pago seleccionada no está disponible."

#### Scenario: Error transaccional PRODUCT_NOT_AVAILABLE — mensaje legible
- **WHEN** el servidor devuelve HTTP 400 con `code: "PRODUCT_NOT_AVAILABLE"`
- **THEN** el componente muestra mensaje indicando que uno o más productos no están disponibles

#### Scenario: Error transaccional ADDRESS_NOT_OWNED — mensaje legible
- **WHEN** el servidor devuelve HTTP 403 con `code: "ADDRESS_NOT_OWNED"`
- **THEN** el componente muestra mensaje legible sobre la dirección

#### Scenario: Botón "Confirmar pedido" activo cuando no hay request en curso
- **WHEN** `isPending = false` y `isError = false`
- **THEN** el botón está habilitado y muestra texto "Confirmar pedido"

---

### Requirement: Integración con cartStore — solo lectura hasta el éxito

El componente `<CheckoutSubmit />` y el hook `useCreateOrder()` SHALL interactuar con `cartStore` siguiendo las reglas de la spec `frontend-cart-store`:
- Leer items con selector (`useCartStore(state => state.items)`) — NO full-store subscription.
- `clearCart()` es llamado SOLO en `onSuccess` del mutation.
- El cart NO es modificado en ningún estado de error.
- El cart NO es modificado durante la request (`isPending`).

#### Scenario: cartStore usa slice subscription en el hook
- **WHEN** el hook `useCreateOrder` lee items del cartStore
- **THEN** usa `useCartStore(state => state.items)` — no `useCartStore()` sin selector
- **THEN** el hook no re-renderiza por cambios en otras partes del store

#### Scenario: clearCart solo en éxito
- **WHEN** la mutation completa con éxito (HTTP 201)
- **THEN** `clearCart()` es invocado exactamente una vez
- **WHEN** la mutation falla con cualquier error
- **THEN** `clearCart()` NO es invocado

---

### Requirement: Change 16 (pre-checkout-validation) NO es reemplazado

Este change NO modifica ni invalida la spec `frontend-pre-checkout-validation` (Change 16). Ambas coexisten:
- Change 16: validación UX advisory (`/checkout/review`) — informa al usuario sobre cambios en su carrito.
- Change 17: confirmación transaccional (`/checkout/confirm` o integrado en el flujo de checkout) — crea el pedido con garantías ACID.

#### Scenario: Flujo de checkout mantiene ambos pasos
- **WHEN** el usuario navega a `/checkout/review` (Change 16)
- **THEN** se ejecuta la validación pre-checkout (advisory)
- **WHEN** el usuario confirma y avanza
- **THEN** se ejecuta `useCreateOrder()` (transaccional)
- **THEN** los errores del backend (INSUFFICIENT_STOCK, etc.) son posibles aunque Change 16 haya devuelto ok=true
- **THEN** el componente maneja esos errores transaccionales sin expectativa de que Change 16 los haya prevenido

---

## ADDED Requirements (Change 19: payments-mercadopago-integration)

### Requirement: Checkout final step shows PayWithMercadoPagoButton after order creation
The checkout flow SHALL be extended so that after a successful `POST /api/v1/pedidos` (order creation — Change 17), the user is presented with the `<PayWithMercadoPagoButton>` component from `frontend-checkout-payment` to complete payment via MercadoPago Checkout Pro.

The flow SHALL be:
1. User completes order review (Change 16 pre-checkout).
2. `<CheckoutSubmit>` fires `useCreateOrder.mutateAsync(...)` → order created → `PedidoRead` returned.
3. `paymentStore.startCheckout(pedidoId)` is called (sets `checkoutStep` to `'order-summary'`).
4. UI transitions to payment step: `<PayWithMercadoPagoButton pedidoId={pedido.id} className="w-full" />` is rendered.
5. On click: the button generates `idempotency_key = crypto.randomUUID()`, calls `POST /api/v1/pagos`, and redirects the browser to `sandbox_init_point` (dev) or `init_point` (prod).
6. MP redirects back to `/checkout/return?status=<status>&pedido_id=<uuid>` after the user pays.

The `<CheckoutSubmit>` component (Change 17) SHALL NOT be modified to include payment logic — the payment step is a separate UI transition triggered by `onSuccess` of the order creation mutation.

The checkout page (`/checkout`) SHALL be updated to conditionally render either `<CheckoutSubmit>` (step 1) or `<PayWithMercadoPagoButton>` (step 2) based on `paymentStore.checkoutStep`.

**Note**: `<CardPaymentWidget>` and `<MercadoPagoProvider>` are REMOVED. The embedded card payment widget has been replaced by the Checkout Pro redirect flow.

#### Scenario: PayWithMercadoPagoButton rendered after successful order creation
- **WHEN** `useCreateOrder.onSuccess` fires with a new `PedidoRead`
- **THEN** `paymentStore.startCheckout(pedidoId)` is called
- **THEN** the checkout UI transitions to show `<PayWithMercadoPagoButton>`
- **THEN** `<CheckoutSubmit>` is no longer visible

#### Scenario: Payment step is only shown for MERCADOPAGO payment method
- **WHEN** the order was created with `forma_pago_codigo = "MERCADOPAGO"`
- **THEN** `<PayWithMercadoPagoButton>` is rendered in the payment step
- **NOTE**: Cash and transfer flows are out of scope for this change; only MERCADOPAGO triggers the redirect button

#### Scenario: Navigating away from checkout step resets paymentStore
- **WHEN** the user navigates away from the checkout page during the payment step
- **THEN** `paymentStore.resetCheckout()` is called (via `useEffect` cleanup)
- **THEN** `paymentStore.checkoutStep` returns to `"idle"`
- **THEN** if the user returns, they see the initial checkout form (not the payment button mid-flow)

#### Scenario: Existing CheckoutSubmit behavior is preserved
- **WHEN** `<CheckoutSubmit>` is in step 1 (before order creation)
- **THEN** all behaviors from the `frontend-checkout` spec (Change 17) remain valid
- **THEN** the addition of the payment step does NOT alter `useCreateOrder` behavior, cart clearing logic, or error handling of the order creation step

#### Scenario: PaymentStatusScreen is NOT mounted on CheckoutPage
- **WHEN** the user clicks "Pagar con MercadoPago" and is redirected to MP
- **THEN** `<PaymentStatusScreen>` is NOT shown on CheckoutPage
- **THEN** `<PaymentStatusScreen>` IS shown on `/checkout/return` (CheckoutReturnPage) after MP redirects back

## MODIFIED Requirements (Change 20: orders-visualization)

### Requirement: `useCreateOrder.onSuccess` navega a `/order-confirmation/${pedido.id}`

El callback `onSuccess` del hook `useCreateOrder` SHALL navegar al usuario a la ruta `/order-confirmation/${pedido.id}` tras una creación exitosa del pedido. El comportamiento condicional previo (que mostraba mensaje si la ruta no existía) queda obsoleto al introducir este change la ruta `/order-confirmation/:id`.

Este cambio aplica al archivo `src/features/checkout/hooks/useCreateOrder.ts` (o donde resida el hook según Change 17). La modificación consiste únicamente en el callback `onSuccess` — no se altera la lógica de creación del pedido.

#### Scenario: navegación post-creación exitosa
- **GIVEN** un usuario CLIENT que confirma su carrito en `/checkout`
- **WHEN** `POST /api/v1/pedidos` responde 201 con el `PedidoRead`
- **THEN** `useCreateOrder.onSuccess` ejecuta `navigate('/order-confirmation/' + pedido.id)`
- **THEN** la página `OrderConfirmationPage` se monta con el pedido recién creado
