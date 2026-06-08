## ADDED Requirements

### Requirement: Rutas de visualización de pedidos en la rama privada

El router de la aplicación SHALL agregar las siguientes rutas dentro de la rama privada (bajo `AppLayout → ProtectedRoute`):

```
/orders          → RoleGuard roles={['CLIENT']} → OrdersPage (lazy)
/orders/:id      → RoleGuard roles={['CLIENT']} → OrderDetailPage (lazy)
/order-confirmation/:id → RoleGuard roles={['CLIENT']} → OrderConfirmationPage (lazy)
```

Estas rutas coexisten con `/orders` ya registrado como placeholder en Changes 08/13 (mismo path, se reemplaza el componente placeholder con la implementación real).

> IMPORTANTE: `/orders/:id` debe declararse DESPUÉS de `/orders` para evitar conflictos. React Router 6+ resuelve correctamente rutas estáticas antes de dinámicas dentro del mismo padre.

#### Scenario: CLIENT navega a /orders y ve su lista de pedidos
- **WHEN** un usuario CLIENT navega a `/orders`
- **THEN** `OrdersPage` real renderiza (no el placeholder)
- **THEN** `GET /api/v1/pedidos` es llamado con el token del CLIENT

#### Scenario: CLIENT navega a /orders/:id y ve el detalle
- **WHEN** un usuario CLIENT navega a `/orders/some-uuid`
- **THEN** `OrderDetailPage` renderiza con `pedidoId = "some-uuid"`
- **THEN** `GET /api/v1/pedidos/some-uuid` es llamado

#### Scenario: /orders/:id no colisiona con /orders
- **WHEN** se resuelven las rutas
- **THEN** `/orders` route to `OrdersPage`
- **THEN** `/orders/some-uuid` routes to `OrderDetailPage`
- **THEN** no hay ambigüedad

#### Scenario: /order-confirmation/:id es accesible post-creación de pedido
- **WHEN** `useCreateOrder` navega a `/order-confirmation/{pedidoId}` tras HTTP 201
- **THEN** `OrderConfirmationPage` renderiza
- **THEN** el `:id` está disponible via `useParams`

#### Scenario: Roles no-CLIENT rechazados en /orders
- **WHEN** un usuario con rol STOCK navega a `/orders`
- **THEN** `RoleGuard` redirige a `/403`
- **WHEN** un usuario con rol PEDIDOS navega a `/orders`
- **THEN** `RoleGuard` redirige a `/403`
- **WHEN** un usuario con rol ADMIN (sin rol CLIENT) navega a `/orders`
- **THEN** `RoleGuard` redirige a `/403`

---

## MODIFIED Requirements

### Requirement: Placeholder page routes defined for all top-level routes

El router SHALL actualizar la configuración de la rama privada para conectar `/pedidos-panel/*` con el panel real. El árbol de rutas privadas es ahora:

**Private branch** (wrapped by `AppLayout → ProtectedRoute` — requires authentication):
- `/home` → `HomePage` (lazy)
- `/cart` → `RoleGuard roles={['CLIENT','ADMIN']}` → `CartPage` (lazy)
- `/checkout` → `RoleGuard roles={['CLIENT','ADMIN']}` → `CheckoutPage` (lazy)
- `/checkout/review` → `RoleGuard roles={['CLIENT','ADMIN']}` → `PreCheckoutReviewPage` (lazy)
- `/checkout/return` → `CheckoutReturnPage` (lazy — Change 19, sin RoleGuard adicional, auth via ProtectedRoute)
- `/orders` → `RoleGuard roles={['CLIENT']}` → `OrdersPage` (lazy — **implementación real, Change 20**)
- `/orders/:id` → `RoleGuard roles={['CLIENT']}` → `OrderDetailPage` (lazy — **Change 20**)
- `/order-confirmation/:id` → `RoleGuard roles={['CLIENT']}` → `OrderConfirmationPage` (lazy — **Change 20**)
- `/profile` → `RoleGuard roles={['CLIENT','ADMIN']}` → `ProfilePage` (lazy)
- `/addresses` → `RoleGuard roles={['CLIENT','ADMIN']}` → `AddressesPage` (lazy)
- `/stock/*` → `RoleGuard roles={['STOCK','ADMIN']}` → stock subtree placeholder (lazy)
- `/pedidos-panel` → `RoleGuard roles={['PEDIDOS','ADMIN']}` → `PedidosPanelPage` (lazy — **implementación real, Change 20**)
- `/pedidos-panel/:id` → `RoleGuard roles={['PEDIDOS','ADMIN']}` → `PedidosPanelDetailPage` (lazy — **Change 20**)
- `/admin/*` → `RoleGuard roles={['ADMIN']}` → `AdminPage` (lazy)

#### Scenario: PEDIDOS navega a /pedidos-panel y ve el panel real
- **WHEN** un usuario PEDIDOS navega a `/pedidos-panel`
- **THEN** `PedidosPanelPage` real renderiza (no el placeholder)
- **THEN** `GET /api/v1/pedidos` es llamado con el token del PEDIDOS

#### Scenario: PEDIDOS navega a /pedidos-panel/:id y ve el detalle de gestión
- **WHEN** un usuario PEDIDOS navega a `/pedidos-panel/some-uuid`
- **THEN** `PedidosPanelDetailPage` renderiza con el `pedidoId` correcto

#### Scenario: /pedidos-panel/:id no colisiona con /pedidos-panel
- **WHEN** se resuelven las rutas
- **THEN** `/pedidos-panel` routes to `PedidosPanelPage`
- **THEN** `/pedidos-panel/some-uuid` routes to `PedidosPanelDetailPage`

#### Scenario: Rutas previas no afectadas
- **WHEN** se agregan las nuevas rutas
- **THEN** `/checkout/return` (Change 19) sigue operativo
- **THEN** `/checkout/review` (Change 16) sigue operativo
- **THEN** `/addresses` (Change 14) sigue operativo
- **THEN** todas las rutas auth y públicas permanecen sin cambios
