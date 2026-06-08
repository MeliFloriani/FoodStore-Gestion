---
spec: frontend-admin-menu-exposure
change: admin-metrics-dashboard
type: delta
---

# frontend-admin-menu-exposure — Delta Spec (Change 23)

## Purpose
Correct all occurrences of `/admin/metrics` (English placeholder) to `/admin/metricas` (Spanish route) introduced by this change.

---

## MODIFIED Requirements

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

### Requirement: ADMIN management tests — navigation coverage

The expected path list SHALL reference `/admin/metricas` in place of `/admin/metrics`.

#### MODIFIED Scenario: navigation.admin.test.ts passes all assertions
- **WHEN** `filterNavItems(NAVIGATION_ITEMS, ['ADMIN'])` is executed in the test
- **THEN** the result has exactly 12 items (5 CLIENT-accessible + 4 STOCK + 1 PEDIDOS + 2 ADMIN-only)
- **THEN** each expected path appears exactly once
- **THEN** the ADMIN-only paths are `/admin/users` and `/admin/metricas` (not `/admin/metrics`)
