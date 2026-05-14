## 1. Dependencies and Package Installation

- [x] 1.1 Install runtime dependencies: `react-router-dom`, `@tanstack/react-query`, `@tanstack/react-form`, `zustand`, `axios`
- [x] 1.2 Install dev dependencies: `eslint-plugin-boundaries`, `@tanstack/react-query-devtools`, `tailwindcss-animate` (D-12)
- [x] 1.3 Verify `frontend/package.json` lists all new dependencies under correct sections (dependencies vs devDependencies)

## 2. TypeScript and Vite Configuration

- [x] 2.1 Add `noUncheckedIndexedAccess: true` and `exactOptionalPropertyTypes: true` to `frontend/tsconfig.app.json`
- [x] 2.2 Add FSD layer path aliases to `tsconfig.app.json` under `compilerOptions.paths`: `@/app`, `@/pages`, `@/widgets`, `@/features`, `@/entities`, `@/shared`
- [x] 2.3 Add matching FSD layer aliases to `frontend/vite.config.ts` `resolve.alias` (in addition to existing `@/`)
- [x] 2.4 Run `npx tsc --noEmit` from `frontend/` and confirm exit code 0

## 3. ESLint FSD Boundary Rules

- [x] 3.1 Add `eslint-plugin-boundaries` to `eslint.config.js` with zone definitions for all 6 FSD layers
- [x] 3.2 Configure boundary rules: `shared` cannot import from `entities/features/widgets/pages/app`; each layer can only import from layers below it
- [x] 3.3 Run `npm run lint` and confirm no boundary violations in existing scaffold files

## 4. Tailwind Token System

- [x] 4.1 Replace `frontend/tailwind.config.js` with token-enriched version: add `darkMode: 'class'`, primitive color palette (`brand`, `neutral`, `success`, `warning`, `danger`, `info` scales 50-900), semantic color tokens via CSS variable references
- [x] 4.2 Add `theme.extend.fontFamily` (sans, display), `theme.extend.fontSize`, `theme.extend.fontWeight`, `theme.extend.letterSpacing`, `theme.extend.lineHeight`
- [x] 4.3 Add `theme.extend.borderRadius` (`sm`, `md`, `lg`, `xl`, `2xl`, `full`), `theme.extend.boxShadow` (`sm`, `md`, `lg`, `xl`), `theme.screens` standard breakpoints
- [x] 4.4 Update `src/app/styles/index.css` (or create if not present): add `@tailwind base/components/utilities`, define CSS variables under `:root` for all semantic tokens (light mode values), define `.dark` overrides for all semantic tokens
- [x] 4.5 Register `tailwindcss-animate` in `tailwind.config.js` `plugins` array (D-12)

## 5. Shared Types and Utilities

- [x] 5.1 Create `src/entities/auth/types.ts` — export `User` type (`id`, `nombre`, `email`, `roles`) and `AuthStatus` union type
- [x] 5.2 Create `src/entities/cart/types.ts` — export `CartItem` type with exact fields: `producto_id`, `nombre`, `precio`, `cantidad`, `imagen_url`, `personalizacion`
- [x] 5.3 Create `src/shared/lib/env.ts` — single source of truth for all VITE_* env vars; exports typed accessors for `VITE_API_BASE_URL` and `VITE_MERCADOPAGO_PUBLIC_KEY` with runtime validation (throw on missing in production); do NOT create `src/shared/config/env.ts` (D-11)
- [x] 5.4 Create `src/shared/lib/errors.ts` — export `AppError` type and `normalizeError(error: unknown): AppError` function mapping 401/403/422/429/500 to typed error codes
- [x] 5.5 Create `src/shared/lib/queryKeys.ts` — export `queryKeys` factory object with namespaces for `auth`, `catalog`, `cart`, `orders`, `payment`; each namespace has `all()` key and common specific keys
- [x] 5.6 Create `src/shared/api/endpoints.ts` — export URL path constants: `AUTH_LOGIN`, `AUTH_REFRESH`, `AUTH_ME`, `AUTH_REGISTER`

## 6. Axios HTTP Client

- [x] 6.1 Create `src/shared/api/http.ts` — create Axios instance with `baseURL` set to `VITE_API_BASE_URL` sourced from `@/shared/lib/env` (D-11); do NOT access `import.meta.env` directly in http.ts
- [x] 6.2 Add request interceptor: reads `authStore.getState().accessToken` via `getState()` (not hook); attaches `Authorization: Bearer <token>` if non-null
- [x] 6.3 Add response interceptor: detect 401; skip if `__isRetry: true` or endpoint is `/auth/refresh` or `/auth/login`
- [x] 6.4 Implement `refreshPromise` singleton pattern: first 401 acquires lock and calls `POST /auth/refresh`; subsequent 401s await same promise
- [x] 6.5 On refresh success: update `authStore` via `updateTokens(newAccessToken, newRefreshToken)` (US-000e contract name); resolve all queued requests with new token; retry original requests with `__isRetry: true`; set `refreshPromise = null` only after all queued dispatches are initiated
- [x] 6.6 On refresh failure: call `authStore.getState().logout()`, dispatch `new CustomEvent('auth:expired')` on `window`, reject all queued requests, set `refreshPromise` to null
- [x] 6.7 Verify `http.ts` does not import `uiStore` or any store for write operations

## 7. Zustand Stores

- [x] 7.1 Create `src/entities/auth/model/store.ts` — authStore with state (`accessToken`, `refreshToken`, `user`, `status`), actions (`setTokens`, `setUser`, `logout`, `clear`), `persist` middleware with `partialize` selecting only `accessToken` and `refreshToken`, storage key `food-store-auth`
- [x] 7.2 Add `onRehydrateStorage` to authStore: if `accessToken` non-null after rehydration, set `status: 'authenticating'` (signal only — no direct network call in store; see MED-05); `AuthSync` in `app/providers/` will detect this and call `GET /auth/me`
- [x] 7.2a Implement `login(accessToken, refreshToken, user)` action — atomically sets tokens + user + `status: 'authenticated'` (canonical post-auth action per US-000e)
- [x] 7.2b Implement `updateTokens(accessToken, refreshToken)` alias action (exposes `setTokens` under US-000e contract name)
- [x] 7.2c Implement `isAuthenticated` computed/derived selector — returns `status === 'authenticated'`; NOT persisted
- [x] 7.2d Implement `hasRole(role: string): boolean` selector — returns `user?.roles?.includes(role) ?? false`
- [x] 7.2e Expose `triggerRehydrationFetch()` action — sets `status: 'authenticating'`; performs no network call in store (FSD decoupling per MED-05)
- [x] 7.3 Create `src/entities/cart/model/store.ts` — cartStore with state (`items`, `version`), actions (`addItem`, `removeItem`, `updateQuantity`, `clearCart`), selectors (`totalItems`, `totalPrice`), `persist` middleware with `partialize` selecting `items` and `version`, storage key `food-store-cart`
- [x] 7.4 Ensure `addItem` increments quantity instead of duplicating when `producto_id` already exists in items
- [x] 7.5 Create `src/shared/store/paymentStore.ts` — paymentStore with state (`preferenceId`, `status`, `lastErrorCode`), actions (`setPreferenceId`, `setStatus`, `setLastErrorCode`, `reset`); NO persist middleware
- [x] 7.5a Add `checkoutStep: 'idle' | 'order-summary' | 'payment' | 'confirmation'` state field to paymentStore (defaults to `'idle'`)
- [x] 7.5b Implement `startCheckout(pedidoId: number)` action — sets `checkoutStep` to `'order-summary'`; UI state stub only, no networking
- [x] 7.5c Implement `advanceStep(step: 'payment' | 'confirmation')` and `resetCheckout()` actions
- [x] 7.6 Create `src/shared/store/uiStore.ts` — uiStore with state (`theme`, `sidebarOpen`, `toasts`), actions (`setTheme`, `toggleTheme`, `setSidebarOpen`, `toggleSidebar`, `addToast`, `removeToast`); use `persist` middleware with `partialize` persisting ONLY `theme` field, storage key `food-store-ui-theme` (D-10)

## 8. TanStack Query Provider

- [x] 8.1 Create `src/app/providers/QueryProvider.tsx` — create `QueryClient` instance with defaults: `staleTime: 60_000`, `gcTime: 300_000`, smart retry function (no retry on 4xx except 408/429; max 2 on 5xx), `refetchOnWindowFocus: false` in DEV
- [x] 8.2 Export `QueryProvider` component wrapping children with `QueryClientProvider`
- [x] 8.3 Add `ReactQueryDevtools` (from `@tanstack/react-query-devtools`) inside `QueryProvider`, visible in DEV only

## 9. React Router and Layouts

- [x] 9.1 Create `src/app/layouts/RootLayout.tsx` — renders `<Outlet />`; adds `useEffect` event listener for `auth:expired` CustomEvent that calls `navigate('/login')`
- [x] 9.2 Create `src/app/layouts/AuthLayout.tsx` — reads `authStore.status` (not `accessToken`); if `'idle'` render full-screen loading spinner; if `'authenticated'` redirect to `/`; if `'unauthenticated'` render `<Outlet />`
- [x] 9.3 Create `src/app/layouts/AppLayout.tsx` — renders structural shell with placeholder nav + `<Outlet />`; no business logic
- [x] 9.4 Create `src/app/router/guards/ProtectedRoute.tsx` — reads `authStore.status` (not `accessToken`); handle `'idle'` state with full-screen loading spinner (no redirect); `'authenticated'` renders `<Outlet />`; `'unauthenticated'` renders `<Navigate to="/login" replace />`
- [x] 9.5 Create `src/app/router/guards/RoleGuard.tsx` — accepts `roles: string[]` prop; renders `<Outlet />` unconditionally (stub, no enforcement yet); interface ready for future role checking
- [x] 9.6 Create placeholder page components (one per route): `LoginPage`, `RegisterPage`, `HomePage`, `CatalogPage`, `CartPage`, `CheckoutPage`, `OrdersPage`, `AdminPage` — each renders a single `<div>Placeholder: <PageName></div>` with no logic
- [x] 9.7 Create `src/app/router/routes.tsx` — configure `createBrowserRouter` with route tree: public routes under `AuthLayout`, protected routes under `AppLayout + ProtectedRoute`, admin under `RoleGuard roles={['ADMIN']}`, all page components wrapped in `lazy()`

## 10. App Providers and Entry Point

- [x] 10.0 Implement `AuthSync` component in `src/app/providers/AuthSync.tsx` — uses `useEffect` to watch `authStore.status === 'authenticating'`; calls `GET /api/v1/auth/me` via `http.ts`; on success calls `authStore.setUser(user)` and sets status to `'authenticated'`; on failure calls `authStore.logout()` (MED-05 decoupling)
- [x] 10.1 Create `src/app/providers/ThemeProvider.tsx` — reads `uiStore.theme`; syncs `dark` class to `document.documentElement` on theme change
- [x] 10.2 Create `src/app/providers/ErrorBoundary.tsx` — global React error boundary with accessible fallback UI (error message + reset button)
- [x] 10.3 Create `src/app/providers/RouterProvider.tsx` — wraps the router from `routes.tsx` in react-router-dom's `RouterProvider`
- [x] 10.4 Update `src/app/App.tsx` — compose all providers in correct order: `ErrorBoundary` → `ThemeProvider` → `QueryProvider` → `RouterProvider`
- [x] 10.5 Ensure `src/main.tsx` mounts `<App />` into `#root` (update if bootstrap code differs)

## 11. Placeholder and Gitkeep Files

- [x] 11.1 Add `.gitkeep` to `src/widgets/` if no other file exists
- [x] 11.2 Add `.gitkeep` to `src/features/` if no other file exists
- [x] 11.3 Add `.gitkeep` to `src/shared/hooks/` if no other file exists
- [x] 11.4 Add `.gitkeep` to `src/shared/ui/` if no other file exists

## 12. Environment Configuration

- [x] 12.1 Update `frontend/.env.example` to include: `VITE_API_BASE_URL=http://localhost:8000/api/v1` and `VITE_MERCADOPAGO_PUBLIC_KEY=TEST-xxx`

## 13. Verification

- [x] 13.1 Run `npx tsc --noEmit` from `frontend/` — exit code 0, no type errors
- [x] 13.2 Run `npm run lint` from `frontend/` — exit code 0, no ESLint errors including boundary violations
- [x] 13.3 Run `npm run dev` from `frontend/` — server starts on port 5173 without errors
- [x] 13.4 Navigate to `http://localhost:5173/login` — renders `Placeholder: Login` without console errors
- [x] 13.5 Navigate to `http://localhost:5173/` — ProtectedRoute redirects to `/login` (no authToken in fresh session)
- [x] 13.6 Confirm `localStorage` has no `food-store-auth` or `food-store-cart` entries on first load (clean state)
- [x] 13.7 Confirm `src/shared/api/http.ts` does not import from `src/shared/store/` or `src/entities/auth/model/store.ts` directly (only `getState()` access via imported store reference)
- [x] 13.8 Run `npm run test` from `frontend/` — Vitest passes (0 tests is acceptable; no test failures)
