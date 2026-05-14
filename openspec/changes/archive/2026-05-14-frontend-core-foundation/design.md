## Context

The Food Store frontend currently has a working scaffold (FSD directory skeleton, Vite, TypeScript strict, Tailwind bare config, basic ESLint) delivered in Change 01 (`frontend-scaffold`). The backend delivers JWT auth endpoints (`POST /auth/login`, `POST /auth/refresh`, `GET /auth/me`) and domain schemas (LoginResponse, User) from Changes 02-04.

The frontend has zero infrastructure: no HTTP client, no stores, no router, no query layer. The next functional change (`auth-register-login`) and every downstream feature (catalog, cart, checkout) will need these layers to be in place and consistent. The risk of building them ad-hoc per feature is high: different interceptor strategies, incompatible persistence schemas, and router configuration conflicts.

This design establishes the single authoritative infrastructure layer for the entire frontend.

**Constraints:**
- Tailwind 3.4 (not v4) — already installed. All token config goes in `tailwind.config.js`, not CSS-first `@theme`.
- React 19 — no `forwardRef` wrappers needed; `ref` is a regular prop.
- FSD strict — imports must flow only downward. No circular dependencies.
- TypeScript strict with `noUncheckedIndexedAccess` and `exactOptionalPropertyTypes` — no `any`, no `@ts-ignore`.
- No implementation in this change — only OPSX artifacts.

---

## Goals / Non-Goals

**Goals:**
- Define the complete HTTP client architecture (Axios singleton, interceptors, token refresh queue, error normalizer).
- Define all four Zustand stores with their exact state shapes, persistence contracts, and FSD placement.
- Define the react-router-dom router structure (layouts, guards, lazy routes, placeholder pages).
- Define TanStack Query 5 configuration (QueryClient defaults, query keys factory, invalidation strategy).
- Define the Tailwind enterprise token system (two-level palette, typography, spacing, dark mode).
- Define FSD build-tooling extensions (layer aliases, ESLint boundary rules, strict TS flags).
- Establish all architectural decisions (D-1 to D-12) as written record for downstream changes.

**Non-Goals:**
- Implementing login/register UI or business logic (deferred to `auth-register-login`).
- Building any feature-specific components, pages with real content, or API calls.
- Implementing the toast notification UI (deferred to Change 27 — Design System).
- Adding MercadoPago SDK (deferred to the payment change).
- Implementing role-based content rendering (guards are structural stubs only).

---

## Decisions

### D-1: FSD Canonical Mapping (Flat-folder → FSD Slot)

**Problem**: The change request describes flat folders (`api/`, `stores/`, `router/`, `providers/`, `hooks/`, `lib/`, `components/`, `layouts/`, `pages/`). FSD requires these to land in specific layer slots.

**Decision**: Every block is mapped to its FSD canonical path. No exceptions.

| Requested block | FSD canonical path | Rationale |
|---|---|---|
| `api/` (Axios + interceptors) | `src/shared/api/` | Shared across all features — belongs in `shared` layer |
| `stores/` — auth state | `src/entities/auth/model/store.ts` | Auth is a domain entity |
| `stores/` — cart state | `src/entities/cart/model/store.ts` | Cart is a domain entity |
| `stores/` — payment (transient) | `src/shared/store/paymentStore.ts` | Cross-cutting, no owning entity yet |
| `stores/` — ui (theme, toasts) | `src/shared/store/uiStore.ts` | Cross-cutting UI state |
| `router/` | `src/app/router/` | App-level concern — only `app/` can wire routes |
| `providers/` | `src/app/providers/` | App-level wrappers |
| `hooks/` — transversal | `src/shared/hooks/` | Generic hooks with no feature owner |
| `hooks/` — feature-specific | `src/features/<name>/hooks/` | Feature-local by definition |
| `lib/` | `src/shared/lib/` | Utils, error normalizer, query keys |
| `components/` — atomic UI | `src/shared/ui/` | Placeholder `.gitkeep`; populated in Change 27 |
| `components/` — page-level blocks | `src/widgets/` | Placeholder `.gitkeep` |
| `layouts/` | `src/app/layouts/` | Layouts are app-level |
| `pages/` | `src/pages/` | FSD `pages` layer — placeholder TSX only |

**Alternatives rejected**: Flat `src/infrastructure/` folder — breaks FSD; imports from feature into shared would be allowed, which is wrong direction.

---

### D-2: Axios Token Refresh Architecture (Concurrent Request Queue)

**Problem**: Multiple concurrent requests may receive 401 simultaneously when the access token expires. Naively calling `POST /auth/refresh` for each would violate the token rotation rule (RN-AU04/AU05) and likely cause a replay attack detection.

**Decision**: Implement a singleton `refreshPromise: Promise<string> | null` in the module scope of `http.ts`. The first request that detects 401 acquires the lock and creates the promise. All subsequent 401s enqueue on that same promise. When refresh completes (or fails), all queued requests resolve or reject together.

```
401 received → is refreshPromise null?
  YES → create refreshPromise = callRefresh()
         refresh succeeds → resolve with newToken → retry all queued
         refresh fails    → reject all queued → authStore.logout() → emit 'auth:expired' event
  NO  → await existing refreshPromise → retry with resolved token
```

**Loop prevention**: A `__isRetry: true` flag is set in the original request config. Requests with `__isRetry: true` do not enter the 401 handler again.

**Success path ordering**: On success, `refreshPromise` is resolved before being nulled — all queued requests dispatch with the new token before the lock releases. Specifically: (1) store is updated, (2) promise resolves, (3) all queued requests are dispatched, (4) `refreshPromise` is set to null. This ensures no concurrent 401 can trigger a second refresh during queue drain.

**Failure path ordering**: On failure, `refreshPromise` is nulled only after all queued rejections and the `auth:expired` event dispatch. Order: (1) `authStore.logout()`, (2) all queued requests rejected, (3) `CustomEvent('auth:expired')` dispatched, (4) `refreshPromise = null`.

**Endpoint exclusions**: `/auth/refresh` and `/auth/login` are excluded from the 401 handler to prevent recursive refresh.

**Decoupling router from store**: The interceptor emits a native DOM `CustomEvent('auth:expired')` instead of calling `router.navigate()`. The `RootLayout` (or an `AuthSync` component in `app/`) listens for this event and performs the redirect. This keeps `shared/api/` free of router dependencies.

---

### D-3: authStore Persistence Contract (Tokens Only)

**Problem**: Persisting the full user object to `localStorage` creates two risks: stale data after role changes, and PII in browser storage beyond what is operationally necessary.

**Decision**: `partialize` includes ONLY `accessToken` and `refreshToken`. The `user` object and `status` are excluded from persistence.

**Rehydration flow**: `onRehydrateStorage` callback fires after Zustand restores from `localStorage`. If `accessToken` is present, it sets `status: 'authenticating'` as a signal (does NOT call `http.ts` directly — see D-13). The `AuthSync` component in `app/providers/` detects this status and calls `GET /api/v1/auth/me`. On success → `setUser(user)` + `status: 'authenticated'`. On failure → `logout()` (tokens were invalid).

**Why not persist user**: The `/auth/me` call is cheap (one request at app boot), guarantees fresh data, and avoids the stale-role problem entirely.

**Public API surface**: The store exposes `login()`, `updateTokens()`, `isAuthenticated`, and `hasRole()` to match US-000e. These are additive; the internal `setTokens`/`setUser` primitives remain for use by the interceptor. The `isAuthenticated` derived value is NOT persisted.

---

### D-4: cartStore Exact Item Shape

**Problem**: The cart shape must match the backend's expected `DetallePedido` input exactly to avoid data transformation at checkout time. The domain spec (RN-CR05, RN-PE07) mandates `personalizacion` as an array of ingredient IDs.

**Decision**: `CartItem` type is fixed:

```ts
type CartItem = {
  producto_id: number;
  nombre: string;
  precio: number;       // unit price snapshot at add-to-cart time
  cantidad: number;
  imagen_url: string;
  personalizacion: number[];  // ingredient IDs to exclude
}
```

All totals and derived values are selectors (Zustand `useCartStore.use.total()`), never stored as state. Persistence uses `partialize` selecting `items` and `version` (for future migrations). Key: `food-store-cart`.

---

### D-5: Server State vs Client State Separation

**Decision**: TanStack Query is the exclusive owner of server state. Zustand stores must NOT cache server data, except:
- `authStore.user` — cached after `GET /auth/me` with no TanStack Query involvement (bootstrapping dependency: Query needs auth to work, so auth cannot depend on Query).
- `cartStore.items` — client-side only (RN-CR01 mandates no backend cart).

All other server data (products, orders, categories, addresses) lives exclusively in TanStack Query cache. Zustand stores that contain UI state derived from server data must use selectors against Query cache, not duplicate the data.

---

### D-6: TanStack Query Defaults and Retry Strategy

**Decision**:
```ts
defaultOptions: {
  queries: {
    staleTime: 60_000,          // 1 min — reduces redundant refetches
    gcTime: 5 * 60_000,         // 5 min garbage collection
    retry: (failureCount, error) => {
      // Never retry 4xx except 408 (timeout) and 429 (rate limit)
      if (isAxiosError(error) && error.response) {
        const status = error.response.status;
        if (status >= 400 && status < 500 && status !== 408 && status !== 429) return false;
      }
      return failureCount < 2;  // max 2 retries on 5xx / network errors
    },
    refetchOnWindowFocus: import.meta.env.DEV ? false : true,
  }
}
```

**Query keys factory** (`src/shared/lib/queryKeys.ts`): namespaced tuple factory. Example structure:
```ts
queryKeys = {
  auth: { me: () => ['auth', 'me'] },
  catalog: {
    all: () => ['catalog'],
    products: (filters) => ['catalog', 'products', filters],
    product: (id) => ['catalog', 'product', id],
  },
  cart: { ... },
  orders: { ... },
  payment: { ... },
}
```
Invalidation strategy: after mutations, call `queryClient.invalidateQueries({ queryKey: queryKeys.X.all() })`. This is documented here; implementation is per-feature change.

---

### D-7: Tailwind Token Architecture (v3.4, Two-Level Palette)

**Decision**: The `tailwind.config.js` uses `theme.extend` to add enterprise tokens without removing Tailwind defaults (avoids breaking the scaffold). Two levels:

1. **Primitive palette**: `brand-{50..900}`, `neutral-{50..900}`, `success-{50..900}`, `warning-{50..900}`, `danger-{50..900}`, `info-{50..900}`.
2. **Semantic tokens** (CSS variable references for dark mode switching):
   - `background`, `foreground`, `muted`, `muted-foreground`, `accent`, `accent-foreground`
   - `destructive`, `destructive-foreground`, `border`, `input`, `ring`
   - `card`, `card-foreground`, `popover`, `popover-foreground`
   - `primary`, `primary-foreground`, `secondary`, `secondary-foreground`

Dark mode uses `darkMode: 'class'` (toggle `dark` class on `<html>`). The CSS variable values are defined in `src/app/styles/index.css` under `:root` and `.dark`, with Tailwind reading them via `var(--color-*)` references in `tailwind.config.js`. This defers token color values to CSS variables, enabling runtime theming without a rebuild.

**Note**: The skill `tailwind-design-system` targets Tailwind v4 (CSS-first `@theme` blocks). Since this project uses Tailwind **v3.4**, the v4 `@theme` pattern is NOT used here. Tokens live in `tailwind.config.js` + CSS variables in `index.css`.

---

### D-8: ESLint FSD Boundary Enforcement

**Decision**: Add `eslint-plugin-boundaries` to enforce the FSD import direction rule. Configuration maps each FSD layer to a boundary zone and restricts upward imports:

```
shared   → cannot import from: entities, features, widgets, pages, app
entities → cannot import from: features, widgets, pages, app
features → cannot import from: widgets, pages, app
widgets  → cannot import from: pages, app
pages    → cannot import from: app
```

Alternative considered: `eslint-plugin-import` with `no-restricted-paths` — less expressive, requires manual path patterns. `eslint-plugin-boundaries` provides declarative zone-to-zone rules with wildcard support.

---

### D-9: Additional TypeScript Strict Flags

**Decision**: Add to `tsconfig.app.json`:
- `"noUncheckedIndexedAccess": true` — array/object index access returns `T | undefined` forcing null checks.
- `"exactOptionalPropertyTypes": true` — `{ x?: string }` is different from `{ x?: string | undefined }`.

These flags break patterns common in scaffolded code (unguarded array[0] access). The change scope is infrastructure files only; all new files in this change must be written to pass these flags from day one.

---

### D-10: uiStore.theme is the Sole Persisted Field of uiStore

**Decision**: `uiStore` SHALL persist exclusively the `theme` field via Zustand `partialize`. No other field of `uiStore` (e.g., `sidebarOpen`, `toasts`) may be persisted. Storage: `localStorage`, key `food-store-ui-theme` (consistent with the `food-store-` prefix used by other persisted stores).

**Rationale**: Theme preference is a non-sensitive UX preference — not state, not identity, not server-derived data. Persisting it avoids Flash Of Unstyled Content (FOUC) when the user has previously selected dark mode. It is the one `uiStore` field whose loss on reload causes a visible regression with no security tradeoff.

**Implications**:
- `uiStore` uses the Zustand `persist` middleware with `partialize: (s) => ({ theme: s.theme })`.
- Rehydration is synchronous (localStorage read) and requires no side effects or fetches.
- `sidebarOpen` and `toasts` remain ephemeral and reset to defaults on reload.
- Storage key `food-store-ui-theme` maintains the naming convention established by `food-store-auth` and `food-store-cart`.

**Alternatives considered**: (a) Full persistence — rejected; leaks transient modal/sidebar state across sessions. (b) No persistence at all — rejected; theme flashes on reload for users who prefer dark mode.

---

### D-11: Environment Access Consolidated in `shared/lib/env.ts`

**Decision**: `src/shared/lib/env.ts` is the single module that parses, validates, and exports all typed VITE_* environment variables. The previously planned `src/shared/config/env.ts` is removed from the folder structure entirely.

**Rationale**: FSD `shared/lib/` is the canonical slot for pure utility modules (no framework, no side effects). Having `shared/config/env.ts` alongside `shared/lib/env.ts` would duplicate responsibility and create import ambiguity — different modules importing from different paths for the same values.

**Implications**:
- Any module that needs an env var (`http.ts`, `QueryProvider`, router, etc.) imports exclusively from `@/shared/lib/env`.
- The canonical API base URL variable is `VITE_API_BASE_URL` (not `VITE_API_URL`). All modules that reference the API base URL SHALL use `env.VITE_API_BASE_URL` from this module.
- The `src/shared/config/` directory does not appear in the project at all.
- Tests that need to mock env values mock this single module.

**Alternatives considered**: (a) Keep both files — rejected; duplication creates drift risk. (b) Move to `app/config/env.ts` — rejected; env is reusable infrastructure, not app-composition logic. `app/` layer cannot be imported by `shared/`.

---

### D-12: `tailwindcss-animate` Included in Foundation

**Decision**: `tailwindcss-animate` is installed as a `devDependency` in this foundation change and registered in `tailwind.config.js` under the `plugins` array.

**Rationale**: This plugin enables animation utility classes (e.g., `animate-in`, `animate-out`, `fade-in`, `slide-in-from-bottom`) used by future Design System primitives (dialogs, sheets, tooltips, comboboxes). Including it now has zero runtime cost when the utilities are unused (Tailwind purges them). Deferring it to Change 27 would force a `tailwind.config.js` edit and re-test cycle mid-Design-System work.

**Implications**:
- `devDependencies['tailwindcss-animate']` is pinned in `package.json`.
- `tailwind.config.js` `plugins` array includes `require('tailwindcss-animate')`.
- The `frontend-tailwind-tokens` spec is updated to reference plugin registration.
- No semantic token impact — the plugin adds animation utilities only.

**Alternatives considered**: (a) Defer to Change 27 — rejected; forces config change and re-test cycle later. (b) Use Framer Motion instead — rejected; runtime bundle cost and out of scope for foundation layer.

---

### D-13: Rehydration Decoupling via `triggerRehydrationFetch()` (MED-05)

**Problem**: `onRehydrateStorage` in `authStore` needs to call `GET /auth/me` via `http.ts`, but the spec prohibits `authStore` from importing `http.ts` (FSD: `entities` can import from `shared`, but `http.ts` reads from `authStore` → circular dependency).

**Decision**: `onRehydrateStorage` sets `status: 'authenticating'` as a signal only — no network call. A dedicated `AuthSync` component in `src/app/providers/` subscribes to `authStore.status` and performs the actual `GET /api/v1/auth/me` call when it detects `'authenticating'`.

**Import direction preserved**: `shared/api/http.ts` → reads `entities/auth/store` (permitted). `entities/auth/store` → does NOT import `shared/api/http.ts` (preserved). `app/providers/AuthSync` → imports both `shared/api/http.ts` and `entities/auth/store` (permitted; `app/` is the topmost layer).

**Rehydration decoupling**: `onRehydrateStorage` sets `status: 'authenticating'` as signal. `AuthSync` in `app/providers/` performs the actual fetch. This preserves the FSD constraint that `entities/auth/store` does not import `shared/api/http.ts`.

---

## Final Folder Structure (FSD-Compliant, Post-Change State)

```
frontend/src/
├── app/
│   ├── providers/
│   │   ├── QueryProvider.tsx      ← TanStack Query v5 client + provider
│   │   ├── RouterProvider.tsx     ← react-router-dom RouterProvider
│   │   ├── ErrorBoundary.tsx      ← Global React error boundary
│   │   ├── ThemeProvider.tsx      ← Dark/light class toggle on <html>
│   │   └── AuthSync.tsx           ← Watches status='authenticating', calls GET /auth/me (D-13)
│   ├── router/
│   │   ├── routes.tsx             ← createBrowserRouter + all routes
│   │   └── guards/
│   │       ├── ProtectedRoute.tsx ← Reads authStore.accessToken
│   │       └── RoleGuard.tsx      ← roles prop, stub enforcement
│   ├── layouts/
│   │   ├── RootLayout.tsx         ← Root outlet + auth:expired listener
│   │   ├── AuthLayout.tsx         ← Public pages (login, register)
│   │   └── AppLayout.tsx          ← Protected pages (navbar placeholder)
│   ├── styles/
│   │   └── index.css              ← @tailwind directives + CSS variables
│   └── App.tsx                    ← Composes all providers
├── pages/
│   ├── login/ui/LoginPage.tsx         ← <div>Placeholder: Login</div>
│   ├── register/ui/RegisterPage.tsx   ← <div>Placeholder: Register</div>
│   ├── home/ui/HomePage.tsx           ← <div>Placeholder: Home</div>
│   ├── catalog/ui/CatalogPage.tsx     ← <div>Placeholder: Catalog</div>
│   ├── cart/ui/CartPage.tsx           ← <div>Placeholder: Cart</div>
│   ├── checkout/ui/CheckoutPage.tsx   ← <div>Placeholder: Checkout</div>
│   ├── orders/ui/OrdersPage.tsx       ← <div>Placeholder: Orders</div>
│   └── admin/ui/AdminPage.tsx         ← <div>Placeholder: Admin</div>
├── widgets/
│   └── .gitkeep
├── features/
│   └── .gitkeep
├── entities/
│   ├── auth/
│   │   ├── model/
│   │   │   └── store.ts           ← authStore (Zustand + persist)
│   │   └── types.ts               ← User, AuthStatus types
│   └── cart/
│       ├── model/
│       │   └── store.ts           ← cartStore (Zustand + persist)
│       └── types.ts               ← CartItem type
└── shared/
    ├── api/
    │   ├── http.ts                ← Axios singleton + interceptors
    │   └── endpoints.ts           ← URL constants (no base URL)
    ├── store/
    │   ├── uiStore.ts             ← Theme, sidebar, toast queue
    │   └── paymentStore.ts        ← Payment flow state (no persist)
    ├── lib/
    │   ├── queryKeys.ts           ← Namespaced query keys factory
    │   ├── errors.ts              ← AppError type + normalizer
    │   └── env.ts                 ← Typed VITE_* env accessor
    ├── hooks/
    │   └── .gitkeep
    └── ui/
        └── .gitkeep
```

---

## Risks / Trade-offs

| Risk | Mitigation |
|---|---|
| `noUncheckedIndexedAccess` breaks existing scaffold code | Fix on write — all new files and any modified existing files must pass. Run `tsc --noEmit` as part of task verification. |
| Refresh queue: unresolved race if `refreshToken` is simultaneously used by two browser tabs | Tab isolation is acceptable for v1. Full cross-tab sync via `BroadcastChannel` deferred to a future hardening change. |
| `exactOptionalPropertyTypes` may conflict with some third-party type definitions | `skipLibCheck: true` is already set, which covers third-party `.d.ts` files. |
| Tailwind v3.4 CSS variable approach requires manual dark mode token wiring in `index.css` | Documented clearly; Change 27 (Design System) will fully own the token values. |
| `eslint-plugin-boundaries` adds a new dev dependency; configuration is verbose | The plugin is well-maintained and widely used for FSD projects. The config is added once and requires no per-file effort. |

---

## Migration Plan

1. Install new dependencies (`npm install --save react-router-dom @tanstack/react-query zustand axios`; `npm install --save-dev eslint-plugin-boundaries @tanstack/react-query-devtools tailwindcss-animate`).
2. Extend `tsconfig.app.json` with two additional strict flags.
3. Extend `vite.config.ts` with FSD layer aliases.
4. Replace `tailwind.config.js` with token-enriched version; update `index.css` with CSS variable definitions.
5. Configure `eslint.config.js` with `eslint-plugin-boundaries` zones.
6. Create all new files per D-1 folder structure.
7. Update `src/app/App.tsx` to compose all providers.
8. Run `tsc --noEmit` and `npm run lint` — both must pass.

No backend migration required. No data migration required. No breaking changes to existing scaffold.

**Rollback**: Revert all file changes. No persistent storage schema has changed yet (stores are new files; no pre-existing data to migrate).

---

## Downstream Changes (Integration Contracts)

These downstream changes depend on artifacts defined here:

| Downstream Change | What it consumes from this change |
|---|---|
| `auth-register-login` | `authStore` (setTokens, setUser, logout), `http.ts` (POST /auth/login, /auth/register), `LoginPage`, `RegisterPage` (replace placeholder) |
| catalog / products | `queryKeys.catalog.*`, `http.ts`, `AppLayout` (add nav items), `CatalogPage` (replace placeholder) |
| cart feature | `cartStore` (addItem, removeItem, updateQuantity), `CartPage` (replace placeholder) |
| checkout / payment | `paymentStore`, `cartStore`, `queryKeys.orders`, `CheckoutPage` (replace placeholder) |
| Change 27 (Design System) | `tailwind.config.js` tokens, `shared/ui/` (populate with components), `ThemeProvider` |
| Admin features | `RoleGuard`, `AdminPage` (replace placeholder) |

---

## Open Questions

1. **`uiStore` persistence** — **RESOLVED → D-10**: `uiStore` persists ONLY the `theme` field via `partialize`. All other fields remain ephemeral. Storage key: `food-store-ui-theme`.

2. **`env.ts` duplication** — **RESOLVED → D-11**: `src/shared/lib/env.ts` is the single source of truth. `src/shared/config/env.ts` is removed from the plan entirely. The `shared/config/` directory does not exist.

3. **`tailwindcss-animate` inclusion** — **RESOLVED → D-12**: `tailwindcss-animate` is included in this foundation change as a `devDependency` and registered in `tailwind.config.js#plugins`.
