## Why

The Food Store frontend scaffold (Change 01) created the FSD directory skeleton and tooling baseline, but the application shell is empty: no HTTP client, no state management, no router, no query infrastructure, and no Tailwind token system. Without these shared infrastructure layers, every subsequent feature change (auth, catalog, cart, checkout) would have to implement its own networking, persistence, and layout conventions from scratch — creating inconsistency, duplication, and architectural drift. This change delivers the complete frontend core foundation so that all functional changes can build on a single coherent layer.

## What Changes

- **Axios HTTP client** (`src/shared/api/http.ts`): singleton with request interceptor (Bearer token injection) and response interceptor (401 → refresh + concurrent request queue + retry).
- **Error normalizer** (`src/shared/lib/errors.ts`): converts AxiosError to typed `AppError` with codes for 401, 403, 422, 429, 500 and structured `fieldErrors` for validation.
- **TanStack Query 5 setup** (`src/app/providers/QueryProvider.tsx`): `QueryClientProvider` with production-grade defaults (staleTime, gcTime, smart retry, refetchOnWindowFocus).
- **Query keys factory** (`src/shared/lib/queryKeys.ts`): centralized namespaced keys for `auth`, `catalog`, `cart`, `orders`, `payment`.
- **Environment accessor** (`src/shared/lib/env.ts`): single typed source of truth for all VITE_* env vars; no `shared/config/` directory (D-11).
- **Zustand stores** (four stores, FSD-correct paths):
  - `src/entities/auth/model/store.ts` — authStore with safe `localStorage` persistence (tokens only, never user object).
  - `src/entities/cart/model/store.ts` — cartStore with exact CartItem shape from domain spec.
  - `src/shared/store/paymentStore.ts` — paymentStore, no persistence.
  - `src/shared/store/uiStore.ts` — uiStore (theme, sidebar, toast queue); persists only `theme` via `partialize` (D-10); all other fields are ephemeral.
- **react-router-dom v6+ router** (`src/app/router/routes.tsx`): `createBrowserRouter` with lazy-loaded routes, `RootLayout`, `AuthLayout`, `AppLayout`, `<ProtectedRoute />`, `<RoleGuard />`, and placeholder pages for all top-level routes.
- **Global layouts** (`src/app/layouts/`): `RootLayout`, `AuthLayout`, `AppLayout` — structural shells only, no business UI.
- **App providers** (`src/app/providers/`): `QueryProvider`, `RouterProvider`, `ErrorBoundary`, `ThemeProvider` composed in `App.tsx`.
- **Tailwind token system** (`tailwind.config.js`): enterprise-ready semantic tokens (colors two-level palette, typography, spacing, borderRadius, boxShadow, screens), `darkMode: 'class'`, `tailwindcss-animate` registered in plugins (D-12).
- **FSD-layer Vite aliases** (`vite.config.ts`): `@/app`, `@/pages`, `@/widgets`, `@/features`, `@/entities`, `@/shared` in addition to existing `@/`.
- **ESLint FSD boundary enforcement**: `import/no-restricted-paths` (or `eslint-plugin-boundaries`) rules encoding the FSD import direction constraint.
- **Strict TS flags** (`tsconfig.app.json`): add `noUncheckedIndexedAccess: true` and `exactOptionalPropertyTypes: true` on top of existing `strict: true`.

## Capabilities

### New Capabilities

- `frontend-build-tooling`: FSD-layer aliases, ESLint boundary rules, additional strict TS flags.
- `frontend-tailwind-tokens`: enterprise Tailwind config with two-level color palette, typography scale, dark mode.
- `frontend-routing`: react-router-dom createBrowserRouter, layouts, ProtectedRoute, RoleGuard, placeholder pages.
- `frontend-query-client`: TanStack Query 5 provider + defaults + query keys factory.
- `frontend-http-client`: Axios singleton, request interceptor, 401-refresh-queue response interceptor, error normalizer.
- `frontend-auth-store`: authStore with safe persistence (tokens only), rehydration trigger for GET /auth/me.
- `frontend-cart-store`: cartStore with canonical CartItem shape, localStorage persistence.
- `frontend-ui-payment-stores`: uiStore (theme persists via `partialize`, D-10) and paymentStore (no persistence).
- `frontend-error-handling`: ErrorBoundary global provider, error normalizer, HTTP status → AppError mapping.

### Modified Capabilities

- `frontend-scaffold`: Vite alias config extended with FSD-layer aliases; tsconfig extended with additional strict flags; tailwind.config.js replaced with token-enriched version; package.json gains new runtime dependencies (react-router-dom, @tanstack/react-query, zustand, axios, etc.).

## Impact

- **Files created**: ~25 new files across `src/app/`, `src/entities/`, `src/shared/`, `src/pages/`.
- **Files modified**: `vite.config.ts`, `tsconfig.app.json`, `tailwind.config.js`, `frontend/package.json`, `src/app/App.tsx`, `src/app/styles/index.css`.
- **Dependencies added** (runtime): `react-router-dom`, `@tanstack/react-query`, `@tanstack/react-form`, `zustand`, `axios`.
- **Dependencies added** (dev): `eslint-plugin-boundaries`, `@tanstack/react-query-devtools`, `tailwindcss-animate` (D-12 — included now to prepare for Change 27 animations; zero runtime cost).
- **Backend coupling**: read-only. References `POST /api/v1/auth/refresh`, `GET /api/v1/auth/me` endpoint shapes from Changes 02-04. No backend changes required.
- **Downstream changes unlocked**: `auth-register-login`, all catalog/cart/checkout changes, Change 27 (Design System).

## Open Questions Resolved

- **OQ-1 — uiStore persistence** → RESOLVED (D-10): `theme` is the sole persisted field of `uiStore` via `partialize`. All other fields are ephemeral.
- **OQ-2 — env access consolidation** → RESOLVED (D-11): `src/shared/lib/env.ts` is the single env module. `src/shared/config/` is removed from the plan.
- **OQ-3 — tailwindcss-animate** → RESOLVED (D-12): included as `devDependency` and registered in `tailwind.config.js#plugins` in this foundation change.
