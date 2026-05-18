# frontend-route-guards Specification

## Purpose
Define the complete route guard system for the Food Store frontend. This covers `ProtectedRoute` (existing behavior, referenced here for completeness), the real `RoleGuard` enforcement, the `useRequireRoles` hook as the single enforcement primitive, the `withAuth(Component, requiredRoles)` HOC, and the guard-before-Suspense invariant for lazy-loaded routes.

## Requirements

### Requirement: ProtectedRoute (reference — no changes)
`src/app/router/guards/ProtectedRoute.tsx` behavior is unchanged from Change 06. It reads `authStore.status` (never `accessToken`) and: renders a full-screen spinner on `'idle'`; renders `<Outlet />` on `'authenticated'`; redirects to `/login` with `replace` on `'unauthenticated'`. No changes to this component are required in this change. This requirement is documented here for completeness and to establish the contract that `RoleGuard` builds upon.

#### Scenario: ProtectedRoute passes authenticated user through
- **WHEN** `authStore.status` is `'authenticated'`
- **THEN** `<Outlet />` is rendered

#### Scenario: ProtectedRoute redirects unauthenticated user
- **WHEN** `authStore.status` is `'unauthenticated'`
- **THEN** user is redirected to `/login` with `replace`

#### Scenario: ProtectedRoute shows spinner on idle
- **WHEN** `authStore.status` is `'idle'`
- **THEN** a full-screen spinner is rendered (no redirect)

---

### Requirement: useRequireRoles hook
`src/app/router/guards/useRequireRoles.ts` SHALL export `useRequireRoles(requiredRoles: string[]): { allowed: boolean; reason: 'loading' | 'unauthenticated' | 'forbidden' | 'ok' }`. This hook is the SINGLE enforcement primitive for all role-based access in the application. Both `RoleGuard` and `withAuth` SHALL use this hook. The hook SHALL NOT be used directly by business components or features — it is internal to the `app/router/guards/` layer.

Logic (evaluated in order):
1. If `status === 'idle'` or `status === 'authenticating'` → return `{ allowed: false, reason: 'loading' }`.
2. If `status === 'unauthenticated'` → return `{ allowed: false, reason: 'unauthenticated' }`.
3. If `requiredRoles.length === 0` → return `{ allowed: true, reason: 'ok' }` (no role gate on this route).
4. If at least one entry in `requiredRoles` is present in `user.roles` → return `{ allowed: true, reason: 'ok' }`.
5. Otherwise → return `{ allowed: false, reason: 'forbidden' }`.

> **Reachability note**: In the private route tree where `ProtectedRoute` wraps `RoleGuard`, the `authenticating` status is intercepted by `ProtectedRoute` first (which renders a spinner), making the `authenticating` branch of `useRequireRoles` unreachable via layout guards. The branch IS reachable when `withAuth(Component, roles)` HOC is used directly on a public-branch component without a parent `ProtectedRoute`. The hook MUST handle both contexts — do not optimize away the `authenticating` branch based on private-tree assumptions.

The hook SHALL read `useAuthStore(s => s.status)` and `useAuthStore(s => s.user?.roles ?? [])`. It SHALL NOT call any write action on the store.

#### Scenario: Returns loading on idle status
- **WHEN** `authStore.status` is `'idle'`
- **THEN** hook returns `{ allowed: false, reason: 'loading' }`

#### Scenario: Returns unauthenticated when not logged in
- **WHEN** `authStore.status` is `'unauthenticated'`
- **THEN** hook returns `{ allowed: false, reason: 'unauthenticated' }`

#### Scenario: Returns ok when user has required role
- **WHEN** `authStore.status` is `'authenticated'` and `user.roles` includes a role from `requiredRoles`
- **THEN** hook returns `{ allowed: true, reason: 'ok' }`

#### Scenario: Returns forbidden when user lacks required role
- **WHEN** `authStore.status` is `'authenticated'` and `user.roles` does NOT include any role from `requiredRoles`
- **THEN** hook returns `{ allowed: false, reason: 'forbidden' }`

#### Scenario: Returns ok for empty requiredRoles (authenticated user on ungated private route)
- **WHEN** `authStore.status` is `'authenticated'` and `requiredRoles` is `[]`
- **THEN** hook returns `{ allowed: true, reason: 'ok' }`

---

### Requirement: RoleGuard real enforcement
`src/app/router/guards/RoleGuard.tsx` SHALL accept `roles: string[]` prop (API unchanged from stub). It SHALL call `useRequireRoles(roles)` and implement the following rendering decisions:
- `reason === 'loading'` → render `<FullScreenSpinner />`.
- `reason === 'unauthenticated'` → render `<Navigate to="/login" state={{ from: location }} replace />` where `location` is from `useLocation()`.
- `reason === 'forbidden'` → render `<Navigate to="/403" state={{ from: location }} replace />`.
- `reason === 'ok'` → render `<Outlet />`.

`RoleGuard` SHALL be placed in the route tree OUTSIDE (wrapping) any `React.Suspense` boundary that wraps a lazy-loaded page component. This is the guard-before-Suspense invariant (see below).

#### Scenario: RoleGuard blocks wrong role
- **WHEN** `RoleGuard roles={['ADMIN']}` is rendered with `status: 'authenticated'` and `user.roles: ['CLIENT']`
- **THEN** user is redirected to `/403`
- **THEN** `state.from` is set to the original location

#### Scenario: RoleGuard allows correct role
- **WHEN** `RoleGuard roles={['ADMIN']}` is rendered with `status: 'authenticated'` and `user.roles: ['ADMIN']`
- **THEN** `<Outlet />` is rendered

#### Scenario: RoleGuard accepts multi-role (ADMIN+STOCK)
- **WHEN** `RoleGuard roles={['STOCK','ADMIN']}` is rendered with `user.roles: ['STOCK']`
- **THEN** `<Outlet />` is rendered

#### Scenario: RoleGuard redirects unauthenticated to login (not 403)
- **WHEN** `RoleGuard roles={['ADMIN']}` is rendered with `status: 'unauthenticated'`
- **THEN** user is redirected to `/login` (not `/403`)

---

### Requirement: withAuth HOC
`src/app/router/guards/withAuth.tsx` SHALL export `withAuth<P extends object>(Component: React.ComponentType<P>, requiredRoles: string[]): React.FC<P>`. The HOC SHALL call `useRequireRoles(requiredRoles)` internally and apply the same rendering decisions as `RoleGuard`. On `reason === 'ok'`, it SHALL render `<Component {...props} />` forwarding all props. The HOC provides an imperative wrapping alternative to the declarative `RoleGuard` for standalone page components that must self-declare access requirements.

`withAuth` SHALL NOT be used inside the main route tree where `RoleGuard` is available — the HOC is for exceptional cases only.

#### Scenario: HOC blocks wrong role
- **WHEN** `withAuth(AdminPage, ['ADMIN'])` is rendered with `user.roles: ['CLIENT']`
- **THEN** user is redirected to `/403`

#### Scenario: HOC allows correct role and forwards props
- **WHEN** `withAuth(ProfilePage, ['CLIENT'])` is rendered with `user.roles: ['CLIENT']` and `props: { id: 42 }`
- **THEN** `ProfilePage` is rendered with `id: 42`

---

### Requirement: Guard-before-Suspense invariant
In every route definition that uses both `RoleGuard` and `React.lazy`, `RoleGuard` SHALL be the outer element and `React.Suspense` SHALL be the inner element. Unauthorized users SHALL NOT trigger the `import()` call for a lazy module. This invariant ensures that forbidden JS chunks are never downloaded.

Route definition SHALL follow this pattern:
```
Route element={<RoleGuard roles={[...]} />}
  Route element={<Suspense fallback={<PageSpinner />}><LazyPage /></Suspense>}
```

The alternative (Suspense outer, RoleGuard inner) is explicitly FORBIDDEN.

### Anti-pattern: `withSuspense` helper
Do NOT use a `withSuspense(Page)` helper as the `element` of a child route inside a `RoleGuard`. The helper creates a Suspense boundary that fires before the guard's redirect evaluates, causing the forbidden chunk to be downloaded.

Use the two-node route pattern exclusively for all role-guarded routes:
- Outer node: `<Route element={<RoleGuard roles={[...]}/>}>`
- Inner node: `<Route path="..." element={<Suspense fallback={<RouteLoading/>}><LazyPage/></Suspense>}>`

#### Scenario: Unauthorized user does not download forbidden chunk
- **WHEN** a user with `roles: ['CLIENT']` navigates to `/admin`
- **THEN** `RoleGuard` evaluates `reason: 'forbidden'` and returns `<Navigate to="/403" />`
- **THEN** the lazy `AdminPage` module is NOT imported (no network request for the chunk)

#### Scenario: Authorized user triggers lazy import after guard passes
- **WHEN** a user with `roles: ['ADMIN']` navigates to `/admin`
- **THEN** `RoleGuard` returns `<Outlet />`
- **THEN** `Suspense` triggers the `React.lazy` import for `AdminPage`

## Acceptance

- `useRequireRoles(['ADMIN'])` with unauthenticated store SHALL return `{ allowed: false, reason: 'unauthenticated' }`.
- `useRequireRoles(['ADMIN'])` with CLIENT user SHALL return `{ allowed: false, reason: 'forbidden' }`.
- `useRequireRoles(['ADMIN'])` with ADMIN user SHALL return `{ allowed: true, reason: 'ok' }`.
- `useRequireRoles([])` with any authenticated user SHALL return `{ allowed: true, reason: 'ok' }`.
- `RoleGuard` with wrong role SHALL redirect to `/403` with `state.from`.
- `RoleGuard` with unauthenticated SHALL redirect to `/login` with `state.from`.
- `RoleGuard` with idle status SHALL render spinner (no redirect).
- `withAuth(Component, ['ADMIN'])` with CLIENT user SHALL redirect to `/403`.
- `withAuth(Component, ['CLIENT'])` with CLIENT user SHALL render the component with forwarded props.
- `RoleGuard` SHALL be placed outside `React.Suspense` in all route definitions.
