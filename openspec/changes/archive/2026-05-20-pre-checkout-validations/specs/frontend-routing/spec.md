## MODIFIED Requirements

### Requirement: Placeholder page routes defined for all top-level routes
The router SHALL define routes organized in three top-level branches under `RootLayout`:

**Public branch** (wrapped by `PublicLayout` — no auth required):
- `/` → redirect to `/catalog`
- `/catalog` → `CatalogPage` (lazy)
- `/401` → `UnauthorizedPage` (lazy)
- `/403` → `ForbiddenPage` (lazy)
- `/404` → `NotFoundPage` (lazy)
- `*` → redirect to `/404` (catch-all)

**Auth branch** (wrapped by `AuthLayout` — redirects authenticated users):
- `/login` → `LoginPage` (lazy)
- `/register` → `RegisterPage` (lazy)

**Private branch** (wrapped by `AppLayout → ProtectedRoute` — requires authentication):
- `/home` → `HomePage` (lazy)
- `/cart` → `RoleGuard roles={['CLIENT','ADMIN']}` → `CartPage` (lazy)
- `/checkout` → `RoleGuard roles={['CLIENT','ADMIN']}` → `CheckoutPage` (lazy)
- `/checkout/review` → `RoleGuard roles={['CLIENT','ADMIN']}` → `PreCheckoutReviewPage` (lazy, from `src/pages/PreCheckoutReviewPage/` — composes `PreCheckoutReview` from `src/features/pre-checkout-validation/`)
- `/orders` → `RoleGuard roles={['CLIENT','ADMIN']}` → `OrdersPage` (lazy)
- `/profile` → `RoleGuard roles={['CLIENT','ADMIN']}` → `ProfilePage` (lazy, from `src/pages/ProfilePage/` — composes `EditProfileForm` and `ChangePasswordForm` from `src/features/profile/`)
- `/addresses` → `RoleGuard roles={['CLIENT','ADMIN']}` → `AddressesPage` (lazy, implemented in Change 14 — real page, not placeholder)
- `/stock/*` → `RoleGuard roles={['STOCK','ADMIN']}` → stock subtree placeholder (lazy)
- `/pedidos-panel/*` → `RoleGuard roles={['PEDIDOS','ADMIN']}` → pedidos subtree placeholder (lazy)
- `/admin/*` → `RoleGuard roles={['ADMIN']}` → `AdminPage` (lazy)

`ProtectedRoute` behavior is unchanged: `status='idle'` → full-screen spinner; `status='authenticated'` → `<Outlet />`; `status='unauthenticated'` → `<Navigate to="/login" replace />`.

#### Scenario: Unauthenticated user accesses /catalog
- **WHEN** a user with `status: 'unauthenticated'` navigates to `/catalog`
- **THEN** the `CatalogPage` placeholder renders without redirect (public route)

#### Scenario: Unauthenticated user is blocked from /stock
- **WHEN** a user with `status: 'unauthenticated'` navigates to `/stock/products`
- **THEN** the user is redirected to `/login`

#### Scenario: CLIENT user is forbidden from /stock
- **WHEN** an authenticated user with roles `['CLIENT']` navigates to `/stock/products`
- **THEN** the user is redirected to `/403`

#### Scenario: Catch-all redirects to 404
- **WHEN** a user navigates to a path that matches no registered route
- **THEN** the user is redirected to `/404`

#### Scenario: All placeholder routes render without crashing
- **WHEN** any registered route is navigated to with appropriate auth/role state
- **THEN** the page renders without a runtime error or uncaught exception

#### Scenario: CLIENT navigates to /profile and sees real ProfilePage
- **WHEN** an authenticated user with roles `['CLIENT']` navigates to `/profile`
- **THEN** the real `ProfilePage` component renders (not a placeholder)
- **THEN** the page shows the user's profile data and the two profile management forms (`EditProfileForm`, `ChangePasswordForm`)

#### Scenario: ADMIN navigates to /profile and sees real ProfilePage
- **WHEN** an authenticated user with roles `['ADMIN']` navigates to `/profile`
- **THEN** the real `ProfilePage` component renders
- **THEN** both profile management forms are visible

#### Scenario: CLIENT navigates to /addresses and sees AddressesPage
- **WHEN** an authenticated user with roles `['CLIENT']` navigates to `/addresses`
- **THEN** the real `AddressesPage` component renders (not a placeholder)
- **THEN** the page displays the user's address list (or empty state if no addresses)

#### Scenario: Unauthenticated user is blocked from /addresses
- **WHEN** a user with `status: 'unauthenticated'` navigates to `/addresses`
- **THEN** the user is redirected to `/login`

#### Scenario: STOCK user is forbidden from /addresses
- **WHEN** an authenticated user with roles `['STOCK']` (without CLIENT or ADMIN) navigates to `/addresses`
- **THEN** the user is redirected to `/403`

#### Scenario: CLIENT navigates to /checkout/review and sees PreCheckoutReviewPage
- **WHEN** an authenticated user with roles `['CLIENT']` navigates to `/checkout/review`
- **THEN** the real `PreCheckoutReviewPage` component renders
- **THEN** the page triggers the pre-checkout validation and shows the review UI

#### Scenario: Unauthenticated user is blocked from /checkout/review
- **WHEN** a user with `status: 'unauthenticated'` navigates to `/checkout/review`
- **THEN** `ProtectedRoute` redirects to `/login` with `state.from` preserved

#### Scenario: STOCK user is forbidden from /checkout/review
- **WHEN** an authenticated user with roles `['STOCK']` (without CLIENT or ADMIN) navigates to `/checkout/review`
- **THEN** `RoleGuard` redirects to `/403`

#### Scenario: /checkout/review does not conflict with /checkout
- **WHEN** routes are resolved
- **THEN** `/checkout/review` routes to `PreCheckoutReviewPage` (not `CheckoutPage`)
- **THEN** `/checkout` still routes to `CheckoutPage`
