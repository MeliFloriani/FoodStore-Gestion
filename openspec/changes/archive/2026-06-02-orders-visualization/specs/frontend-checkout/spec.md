## MODIFIED Requirements

### Requirement: `useCreateOrder.onSuccess` navega a `/order-confirmation/${pedido.id}`

El callback `onSuccess` del hook `useCreateOrder` SHALL navegar al usuario a la ruta `/order-confirmation/${pedido.id}` tras una creación exitosa del pedido. El comportamiento condicional previo (que mostraba mensaje si la ruta no existía) queda obsoleto al introducir este change la ruta `/order-confirmation/:id`.

Este cambio aplica al archivo `src/features/checkout/hooks/useCreateOrder.ts` (o donde resida el hook según Change 17). La modificación consiste únicamente en el callback `onSuccess` — no se altera la lógica de creación del pedido.

#### Scenario: navegación post-creación exitosa
- **GIVEN** un usuario CLIENT que confirma su carrito en `/checkout`
- **WHEN** `POST /api/v1/pedidos` responde 201 con el `PedidoRead`
- **THEN** `useCreateOrder.onSuccess` ejecuta `navigate('/order-confirmation/' + pedido.id)`
- **THEN** la página `OrderConfirmationPage` se monta con el pedido recién creado
