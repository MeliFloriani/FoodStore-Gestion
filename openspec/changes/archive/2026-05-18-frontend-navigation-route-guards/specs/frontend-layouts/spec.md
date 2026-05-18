# frontend-layouts Specification

## Purpose
Define the layout tier responsibilities, contracts, and decoupling rules for the Food Store frontend. This covers all four layouts: `RootLayout` (unchanged), `PublicLayout` (new), `AuthLayout` (unchanged), and `AppLayout` (extended). Layouts are structural shells — they provide navigation chrome and `<Outlet />` slots; they do NOT contain business logic, feature imports, or access control decisions.

## Requirements

### Requirement: RootLayout (reference — no changes)
`src/app/layouts/RootLayout.tsx` is the outermost shell. It wraps all routes. It listens for the `auth:expired` custom DOM event on `window` and navigates to `/login` when triggered. It renders `<Outlet />`. No changes to this component are required.

#### Scenario: RootLayout handles auth:expired event
- **WHEN** the `auth:expired` CustomEvent is dispatched on `window`
- **THEN** the user is navigated to `/login`

#### Scenario: RootLayout renders outlet
- **WHEN** `RootLayout` mounts
- **THEN** `<Outlet />` is rendered without errors

---

### Requirement: PublicLayout (new)
`src/app/layouts/PublicLayout.tsx` SHALL be a new layout component that wraps all public routes (`/`, `/catalog`, `/401`, `/403`, `/404`). It SHALL:
1. Import and render `<Navigation>` from `widgets/navigation/Navigation` with `isPublic={true}`.
2. Render `<Outlet />` below the navigation.
3. NOT gate access — all routes under `PublicLayout` are accessible to any user.
4. NOT import any feature module.
5. NOT read `authStore` directly — the `<Navigation>` widget handles auth-state-dependent rendering internally.

An authenticated user visiting a public route (e.g., `/catalog`) SHALL see the full role-filtered navigation rendered by `<Navigation>`.
An unauthenticated user visiting a public route SHALL see the anonymous navigation rendered by `<Navigation>`.

#### Scenario: Unauthenticated user sees public layout with anonymous nav
- **WHEN** `PublicLayout` renders with `authStore.status: 'unauthenticated'`
- **THEN** the `<Navigation>` widget renders anonymous items (Catálogo, Login, Registrarse)
- **THEN** `<Outlet />` renders the child page

#### Scenario: Authenticated user visiting public route sees full nav
- **WHEN** `PublicLayout` renders with `authStore.status: 'authenticated'` and `user.roles: ['CLIENT']`
- **THEN** the `<Navigation>` widget renders CLIENT items
- **THEN** `<Outlet />` renders the child page without redirect

#### Scenario: PublicLayout does not block any user
- **WHEN** any user navigates to a route under `PublicLayout`
- **THEN** the route is accessible regardless of auth status

---

### Requirement: AuthLayout (reference — no changes in behavior; post-login redirect extended)
`src/app/layouts/AuthLayout.tsx` wraps `/login` and `/register`. Existing behavior: `status='idle'/'authenticating'` → full-screen spinner; `status='authenticated'` → redirect away; `status='unauthenticated'` → render `<Outlet />`.

**Extension in this change**: When `status` transitions to `'authenticated'`, `AuthLayout` SHALL redirect to `resolveDefaultRoute(user.roles)` (imported from `shared/lib/navigation`) unless `location.state?.from` is set, in which case it SHALL redirect to `location.state.from` (deep-link preservation). This replaces the previous hard-coded redirect to `/`.

#### Scenario: AuthLayout redirects to role-based home after login
- **WHEN** `authStore.status` transitions to `'authenticated'` with `user.roles: ['ADMIN']` and no `state.from`
- **THEN** user is redirected to `/admin`

#### Scenario: AuthLayout preserves deep-link after login
- **WHEN** `authStore.status` transitions to `'authenticated'` and `location.state.from` is `/stock/products`
- **THEN** user is redirected to `/stock/products`

#### Scenario: AuthLayout redirects CLIENT to /catalog after login
- **WHEN** `authStore.status` transitions to `'authenticated'` with `user.roles: ['CLIENT']` and no `state.from`
- **THEN** user is redirected to `/catalog`

#### Scenario: AuthLayout shows spinner on authenticating status
- **WHEN** `authStore.status` is `'authenticating'`
- **THEN** a full-screen spinner is shown (no redirect, no form re-render)

---

### Requirement: AppLayout (extended — add Navigation widget)
`src/app/layouts/AppLayout.tsx` wraps all private (authenticated) routes. It SHALL:
1. Import and render `<Navigation>` from `widgets/navigation/Navigation`.
2. Render `<Outlet />` in the main content area.
3. NOT import any feature module.
4. NOT read `authStore` directly — the `<Navigation>` widget handles auth state internally.
5. NOT contain any access control logic (guards are in `app/router/guards/`, not layouts).

The static "Food Store" text placeholder SHALL be replaced with the `<Navigation>` component.

#### Scenario: AppLayout renders Navigation widget
- **WHEN** `AppLayout` renders with an authenticated user
- **THEN** the `<Navigation>` widget is present in the DOM
- **THEN** `<Outlet />` renders the child page

#### Scenario: AppLayout does not perform access control
- **WHEN** `AppLayout` renders
- **THEN** no redirect or role check occurs within `AppLayout` itself

---

### Requirement: Layout decoupling rules
All layouts SHALL comply with the following decoupling rules:

1. **Layouts do not import feature modules.** No layout SHALL import from `features/`. If a layout needs UI from a feature, that UI must be promoted to `widgets/`.
2. **Layouts do not make access control decisions.** No layout SHALL call `useRequireRoles`, check `user.roles`, or render `<Navigate>` based on role state (except `AuthLayout`'s existing authenticated-user redirect and its extended `resolveDefaultRoute` call, which is routing, not business logic).
3. **Layouts do not know page internals.** A layout knows only that it renders `<Outlet />`. It does not import page components.
4. **Only `AppLayout` and `PublicLayout` import the `<Navigation>` widget.** Other layouts (`RootLayout`, `AuthLayout`) do not render navigation chrome.

#### Scenario: Layout import tree is FSD-compliant
- **WHEN** any layout file is statically analyzed
- **THEN** no import from `features/` or from a peer layout is present
- **THEN** widget imports flow from `app/layouts/` → `widgets/` (downward, valid)

## Acceptance

- `PublicLayout` SHALL render `<Navigation isPublic={true} />` + `<Outlet />`.
- `PublicLayout` SHALL NOT block any user.
- `AuthLayout` SHALL redirect authenticated users to `resolveDefaultRoute(user.roles)` when no `state.from` is present.
- `AuthLayout` SHALL redirect to `state.from` when present after login.
- `AppLayout` SHALL render `<Navigation>` widget instead of static text.
- No layout SHALL import from `features/`.
- No layout other than `AppLayout` and `PublicLayout` SHALL render the `<Navigation>` widget.
- `RootLayout` SHALL remain unchanged from Change 06.
