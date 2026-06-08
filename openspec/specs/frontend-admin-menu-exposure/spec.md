# frontend-admin-menu-exposure Specification

## Purpose
TBD - created by archiving change admin-catalog-orders-aggregated-permissions. Update Purpose after archive.
## Requirements
### Requirement: ADMIN menu exposes all management items

The path `/admin/metrics` SHALL be replaced with `/admin/metricas` throughout this requirement.

#### MODIFIED Scenario: filterNavItems with ADMIN role includes all management items
- **WHEN** `filterNavItems(NAVIGATION_ITEMS, ['ADMIN'])` is called
- **THEN** the result includes items with paths `/stock/products`, `/stock/categories`, `/stock/ingredients`, `/stock/inventory`, `/pedidos-panel`
- **THEN** the result includes ADMIN-only items with paths `/admin/users`, `/admin/metricas`
- **THEN** the result includes CLIENT-accessible items with paths `/catalog`, `/cart`, `/orders`, `/profile`, `/addresses`
- **THEN** no path appears more than once in the result (de-duplication invariant)

#### MODIFIED Scenario: Navigation component renders all management items for ADMIN user
- **WHEN** `<Navigation>` is rendered with `authStore.status = 'authenticated'` and `user.roles = ['ADMIN']`
- **THEN** the navigation renders links to `/stock/products`, `/stock/categories`, `/stock/ingredients`, `/stock/inventory`
- **THEN** the navigation renders a link to `/pedidos-panel`
- **THEN** the navigation renders links to `/admin/users` and `/admin/metricas`

---

### Requirement: Future management items MUST include ADMIN in allowedRoles
Any navigation item that grants access to a management capability (catalog, orders, users, metrics, or any future management domain) SHALL include `'ADMIN'` in its `allowedRoles` array. This is a forward-looking governance rule enforced at the spec level.

A "management item" is defined as any `NavigationItem` that:
1. Routes to a path under `/stock/*`, `/pedidos-panel`, `/admin/*`, or any future management namespace, OR
2. Performs write operations on catalog, order, user, or system data.

CLIENT-exclusive paths (`/cart`, `/checkout`, `/orders/confirm`) are exempt from this rule.

#### Scenario: New stock management item always includes ADMIN
- **WHEN** a new `NavigationItem` with path `/stock/promotions` (or any `/stock/*` path) is added to `NAVIGATION_ITEMS`
- **THEN** its `allowedRoles` array includes `'ADMIN'`
- **THEN** `filterNavItems(NAVIGATION_ITEMS, ['ADMIN'])` includes the new item

#### Scenario: New admin-domain item always includes ADMIN
- **WHEN** a new `NavigationItem` with path `/admin/config` (or any `/admin/*` path) is added to `NAVIGATION_ITEMS`
- **THEN** its `allowedRoles` array includes `'ADMIN'`

---

### Requirement: ADMIN management tests — navigation coverage

The expected path list SHALL reference `/admin/metricas` in place of `/admin/metrics`.

#### MODIFIED Scenario: navigation.admin.test.ts passes all assertions
- **WHEN** `filterNavItems(NAVIGATION_ITEMS, ['ADMIN'])` is executed in the test
- **THEN** the result has exactly 12 items (5 CLIENT-accessible + 4 STOCK + 1 PEDIDOS + 2 ADMIN-only)
- **THEN** each expected path appears exactly once
- **THEN** the ADMIN-only paths are `/admin/users` and `/admin/metricas` (not `/admin/metrics`)

