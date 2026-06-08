## ADDED Requirements

### Requirement: filterNavItems renders all management items for ADMIN role
The `filterNavItems` function SHALL, when called with `userRoles = ['ADMIN']`, return all items from `NAVIGATION_ITEMS` because every item in the registry has at least one `allowedRoles` entry that includes `'ADMIN'`. Specifically:
- CLIENT-accessible items (`catalog`, `cart`, `orders`, `profile`, `addresses`) have `allowedRoles: ['CLIENT', 'ADMIN']` → included for ADMIN.
- STOCK items (`stock-products`, `stock-categories`, `stock-ingredients`, `stock-inventory`) have `allowedRoles: ['STOCK', 'ADMIN']` → included for ADMIN.
- PEDIDOS item (`pedidos-panel`) has `allowedRoles: ['PEDIDOS', 'ADMIN']` → included for ADMIN.
- ADMIN-only items (`admin-users`, `admin-metrics`) have `allowedRoles: ['ADMIN']` → included for ADMIN.

This is the navigation invariant for US-064 and US-065: ADMIN sees the union of all management items without any special casing.

#### Scenario: filterNavItems with ADMIN role returns all 12 NAVIGATION_ITEMS
- **WHEN** `filterNavItems(NAVIGATION_ITEMS, ['ADMIN'])` is called
- **THEN** the result has exactly 12 items
- **THEN** the result includes paths `/stock/products`, `/stock/categories`, `/stock/ingredients`, `/stock/inventory`
- **THEN** the result includes path `/pedidos-panel`
- **THEN** the result includes paths `/admin/users`, `/admin/metrics`
- **THEN** the result includes CLIENT paths `/catalog`, `/cart`, `/orders`, `/profile`, `/addresses`

#### Scenario: Navigation widget renders management items for ADMIN user
- **WHEN** `<Navigation>` is rendered with `authStore.status = 'authenticated'` and `user.roles = ['ADMIN']`
- **THEN** the navigation renders a link to path `/stock/products` with label "Productos"
- **THEN** the navigation renders a link to path `/pedidos-panel` with label "Panel de Pedidos"
- **THEN** the navigation renders a link to path `/admin/users` with label "Usuarios"
