## ADDED Requirements

### Requirement: /admin route subtree expanded with nested metrics and management routes
The router SHALL expand the existing `/admin/*` catch-all under `RoleGuard roles={['ADMIN']}` to define the following nested routes:

```
/admin                  → redirect to /admin/metricas
/admin/metricas         → AdminDashboardPage (MetricasTab) (lazy)
/admin/pedidos          → AdminDashboardPage (PedidosTab) (lazy) — embeds OrdersManagementPanel
/admin/usuarios         → AdminUsersPage (lazy) — existing, from Change 21
/admin/productos        → AdminDashboardPage (ProductosTab) (lazy)
/admin/stock            → AdminDashboardPage (StockTab) (lazy)
```

All routes inherit the `RoleGuard roles={['ADMIN']}` from the parent `/admin` route defined in Change 08. No additional guard is needed for sub-routes.

#### Scenario: /admin redirects to /admin/metricas
- **GIVEN** an authenticated ADMIN user navigates to `/admin`
- **WHEN** the route resolves
- **THEN** the user is redirected to `/admin/metricas`

#### Scenario: /admin/metricas renders AdminDashboardPage MetricasTab
- **GIVEN** an authenticated ADMIN user
- **WHEN** the user navigates to `/admin/metricas`
- **THEN** `AdminDashboardPage` is rendered with the Métricas tab active

#### Scenario: /admin/pedidos renders PedidosTab
- **GIVEN** an authenticated ADMIN user
- **WHEN** the user navigates to `/admin/pedidos`
- **THEN** `OrdersManagementPanel` is rendered within the admin layout

#### Scenario: Non-ADMIN user cannot access /admin/* routes
- **GIVEN** an authenticated CLIENT user
- **WHEN** the user navigates to `/admin/metricas`
- **THEN** the user is redirected to `/403`
