# Spec Delta — frontend-routing (Change 13: customer-profile-management)

## MODIFIED Requirements

### Private Routes — /profile
- **BEFORE** (Change 08): `/profile` rendered a placeholder component (`RoleGuard roles={['CLIENT','ADMIN']}` → ProfilePage stub — implemented in Change 13).
- **AFTER** (Change 13): `/profile` renders the real `ProfilePage` implementation.
  - Imported from `src/pages/ProfilePage/` (FSD layer: pages), which composes `EditProfileForm` and `ChangePasswordForm` from `src/features/profile/`.
  - Lazy-loaded (`React.lazy`) consistently with all other private routes.
  - `RoleGuard roles={['CLIENT','ADMIN']}` and `ProtectedRoute` wrapping are **unchanged** from Change 08.
  - Accesible for all authenticated users with CLIENT or ADMIN role (no additional role restriction).

All other routes in the router (public branch, auth branch, and all other private routes) are **unchanged** from the spec established in Change 08 (`frontend-navigation-route-guards`). This delta only modifies the `/profile` entry.

#### Scenario: CLIENT navigates to /profile and sees real ProfilePage
- **WHEN** an authenticated user with roles `['CLIENT']` navigates to `/profile`
- **THEN** the real `ProfilePage` component renders (not a placeholder)
- **THEN** the page shows the user's profile data and the two profile management forms (`EditProfileForm`, `ChangePasswordForm`)

#### Scenario: ADMIN navigates to /profile and sees real ProfilePage
- **WHEN** an authenticated user with roles `['ADMIN']` navigates to `/profile`
- **THEN** the real `ProfilePage` component renders
- **THEN** both profile management forms are visible

#### Scenario: Unauthenticated user is still blocked from /profile
- **WHEN** a user with `status: 'unauthenticated'` navigates to `/profile`
- **THEN** `ProtectedRoute` redirects to `/login` (behavior unchanged from Change 08)
