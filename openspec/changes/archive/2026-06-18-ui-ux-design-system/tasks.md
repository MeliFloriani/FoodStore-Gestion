# Tasks: ui-ux-design-system (Change 24)

All tasks are unchecked. Do NOT mark any task as done during the propose phase.
This change is PROPOSE-ONLY. Implementation begins during Sprint 8 apply.

---

## 1. Token Extensions

> Only add tokens that are currently missing from `tailwind.config.js` and `src/app/styles/index.css`. Inspect before writing.

- [x] Inspect `frontend/tailwind.config.js` for existence of focus-ring token; if missing, add `ring.focus` under `theme.extend.colors` mapped to `var(--color-ring-focus)`
- [x] Inspect `frontend/src/app/styles/index.css` for `--color-ring-focus`; if missing, add to `:root` (brand-derived focus tint) and `.dark` (adjusted for dark backgrounds)
- [x] Inspect `tailwind.config.js` for z-index tokens; if missing, add `theme.extend.zIndex`: `base (0)`, `dropdown (10)`, `sticky (20)`, `overlay (30)`, `modal (40)`, `toast (50)`, `tooltip (60)`
- [x] Inspect `tailwind.config.js` for named motion duration tokens; if missing, add `theme.extend.transitionDuration`: `instant (0)`, `fast (150)`, `base (250)`, `slow (400)`
- [x] Verify `tailwindcss-animate` plugin is still registered (do not re-register if present)

---

## 2. Typography Utilities

- [x] Create `frontend/src/shared/ui/typography/` directory with `index.ts` barrel
- [x] Create `frontend/src/shared/ui/typography/typography.tokens.ts` — export heading and body class maps as typed constants (`HEADING_CLASSES`, `BODY_CLASSES`) for consumption in helper components
- [x] Create `frontend/src/shared/ui/typography/Heading.tsx` — renders `<h1>`–`<h6>` with canonical Tailwind classes per level (level prop: 1–6), forwards `className`
- [x] Create `frontend/src/shared/ui/typography/Text.tsx` — renders `<p>` or `<span>` with variant prop (`body | body-sm | caption | label | code`), forwards `className`
- [x] Export `Heading`, `Text`, `HEADING_CLASSES`, `BODY_CLASSES` from `index.ts`
- [x] Verify TypeScript strict — no errors (`tsc --noEmit`)

---

## 3. Toast System

- [x] Create `frontend/src/shared/ui/toast/toast.types.ts` — define `ToastVariant` union and `ToastItem` interface
- [x] Create `frontend/src/shared/ui/toast/ToastProvider.tsx` — React context holding toast list; renders `aria-live="polite" aria-atomic="true"` region outside main flow at z-index `z-toast (50)`; manages `add`, `dismiss`, `clear` reducers
- [x] Create `frontend/src/shared/ui/toast/Toast.tsx` — individual toast UI: icon by variant (success/error/warning/info), title, optional description, manual close button; uses `animate-in fade-in` from `tailwindcss-animate`; uses semantic color tokens (`bg-card`, `text-foreground`, border accent by variant)
- [x] Create `frontend/src/shared/ui/toast/useToast.ts` — hook consuming ToastContext; exposes `toast(item)`, `dismiss(id)`, `clear()`; auto-generates UUID `id` for each new item
- [x] Implement auto-dismiss: each toast with `duration > 0` uses `setTimeout`; cancels on manual dismiss
- [x] Implement toast queue cap: max 5 visible; enqueuing a 6th dismisses the oldest
- [x] Create `frontend/src/shared/ui/toast/index.ts` — barrel exporting `ToastProvider`, `Toast`, `useToast`, `ToastVariant`, `ToastItem`
- [x] Mount `<ToastProvider>` in `frontend/src/app/providers.tsx` (or equivalent root provider file); position: outermost wrapper after QueryClientProvider and BrowserRouter
- [x] Verify TypeScript strict — no errors

---

## 4. Skeleton Primitives

- [x] Create `frontend/src/shared/ui/skeleton/SkeletonLine.tsx` — single text-line skeleton; props: `width` (Tailwind width class, default `w-full`), `className`; renders `animate-pulse bg-muted rounded`
- [x] Create `frontend/src/shared/ui/skeleton/SkeletonCircle.tsx` — circular skeleton; props: `size` (Tailwind `h-X w-X` classes, default `h-10 w-10`), `className`; renders `animate-pulse bg-muted rounded-full`
- [x] Create `frontend/src/shared/ui/skeleton/SkeletonRect.tsx` — rectangular block skeleton; props: `width` (default `w-full`), `height` (default `h-24`), `className`; renders `animate-pulse bg-muted rounded-md`
- [x] Create `frontend/src/shared/ui/skeleton/SkeletonCard.tsx` — compound pattern: `<SkeletonRect height="h-48" />` (image area) + `<SkeletonLine width="w-3/4" />` (title) + `<SkeletonLine width="w-1/2" />` (price) + `<SkeletonLine width="w-full" />` (description)
- [x] Create `frontend/src/shared/ui/skeleton/SkeletonList.tsx` — compound: renders `rows` (default 4) `<SkeletonCard>` elements in a grid-compatible wrapper; accepts `rows?: number` and `className`
- [x] Create `frontend/src/shared/ui/skeleton/index.ts` — barrel exporting all skeleton components
- [x] Verify TypeScript strict — no errors

---

## 5. Confirm-Dialog Primitive

- [x] Create `frontend/src/shared/ui/confirm-dialog/confirm-dialog.types.ts` — define `ConfirmVariant` and `ConfirmOptions` interfaces
- [x] Create `frontend/src/shared/ui/confirm-dialog/ConfirmDialogProvider.tsx` — context holding pending confirm state; renders `<ConfirmDialog>` modal only when a confirm is pending; exposes `openConfirm(options): Promise<boolean>` via context
- [x] Create `frontend/src/shared/ui/confirm-dialog/ConfirmDialog.tsx` — modal UI rendered via `ReactDOM.createPortal` into `document.body`; uses `z-modal (40)`; overlay with `bg-black/50`; keyboard: `Enter` → confirm, `Escape` → cancel; `destructive` variant: confirm button uses `bg-destructive text-destructive-foreground`; focus trap inside dialog while open; `role="alertdialog"` + `aria-modal="true"` + `aria-labelledby` on title
- [x] Create `frontend/src/shared/ui/confirm-dialog/useConfirm.ts` — hook consuming ConfirmDialogContext; exposes `confirm(options): Promise<boolean>`
- [x] Create `frontend/src/shared/ui/confirm-dialog/index.ts` — barrel exporting `ConfirmDialogProvider`, `ConfirmDialog`, `useConfirm`, `ConfirmVariant`, `ConfirmOptions`
- [x] Mount `<ConfirmDialogProvider>` in `frontend/src/app/providers.tsx` adjacent to `<ToastProvider>`
- [x] Verify TypeScript strict — no errors

---

## 6. Empty-State Primitive

- [x] Create `frontend/src/shared/ui/empty-state/EmptyState.tsx` — component with props: `icon?: ReactNode`, `title: string`, `description?: string`, `action?: ReactNode`, `className?`; renders centered flex column; icon at 48×48 `text-muted-foreground`; title `text-lg font-semibold`; description `text-sm text-muted-foreground`; action below description
- [x] Create `frontend/src/shared/ui/empty-state/index.ts` — barrel exporting `EmptyState`
- [x] Verify TypeScript strict — no errors

---

## 7. Mobile-First Layout Policy and Audit Checklist

- [x] Read the current `frontend/src/app/` layout files and verify container class usage (`mx-auto px-4 sm:px-6 lg:px-8`)
- [x] Verify `frontend/src/shared/ui/` or `frontend/src/widgets/` contains a `PageContainer` or equivalent wrapper; if not, create `frontend/src/shared/ui/layout/PageContainer.tsx` — renders `<div className="mx-auto w-full max-w-screen-xl px-4 sm:px-6 lg:px-8">`
- [x] Create `frontend/src/shared/ui/layout/index.ts` — barrel exporting `PageContainer`
- [x] Read `openspec/specs/frontend-layouts/spec.md` and `openspec/specs/frontend-scaffold/spec.md` to verify no conflicts with new container utility
- [x] Document the mobile-first layout policy in `openspec/changes/ui-ux-design-system/specs/frontend-design-system-mobile-first-layout/spec.md` (already written in this change's specs)
- [x] Perform a quick audit of all page files in `frontend/src/pages/` — note which pages lack mobile-first responsive classes and add those pages to the per-feature rollout tasks in section 8 as needed

---

## 8. Progressive Feature Rollout (Sprint 8 Refinement)

> Each subsection corresponds to one archived change. Tasks within each subsection are independent.
> Do NOT implement any of these tasks during this change's apply phase — they are Sprint 8 refinement work.
> Each task targets a specific file or component. No structural refactoring allowed.

---

### Change 06 — `auth-register-login`

- [x] Replace any inline loading spinner in `features/auth/` registration/login forms with skeleton pattern or loading state using `isPending` from TanStack Form mutation
- [x] Connect `useToast` to registration success/error feedback (replace any inline alert/div error messaging at form level)
- [x] Connect `useToast` to login error feedback
- [x] Audit `pages/auth/` at 375px — verify inputs meet 44px height (`h-11`) and submit button meets 44px touch target

---

### Change 07 — `auth-refresh-logout-rbac-me`

- [x] Replace any `window.confirm` in logout flow (if present) with `useConfirm`
- [x] Connect `useToast` to logout success notification
- [x] Audit `pages/auth/` and any session-expired redirect — verify user receives toast feedback on forced logout

---

### Change 08 — `frontend-navigation-route-guards`

- [x] Audit `AppLayout`, `PublicLayout`, `AuthLayout` for mobile-first container classes; apply `PageContainer` or equivalent if missing
- [x] Verify mobile navigation (hamburger menu / sidebar) meets 44px touch targets on menu items
- [x] Verify `Navigation` component renders correctly at 375px — no horizontal overflow
- [x] Replace any `window.confirm` in navigation-level actions (if any) with `useConfirm`

---

### Change 09 — `catalog-categories-management` (admin side)

- [x] Replace inline skeleton/loading state in categories list view with `<SkeletonList rows={4} />`
- [x] Replace `window.confirm` in category delete action with `useConfirm({ variant: 'destructive', title: '¿Eliminar categoría?' })`
- [x] Add `<EmptyState title="Sin categorías" description="Aún no hay categorías creadas." />` when category list is empty
- [x] Connect `useToast` to create/update/delete success and error feedback

---

### Change 10 — `catalog-ingredients-management` (admin side)

- [x] Replace inline skeleton/loading state in ingredients list view with `<SkeletonList rows={4} />`
- [x] Replace `window.confirm` in ingredient delete action with `useConfirm({ variant: 'destructive', title: '¿Eliminar ingrediente?' })`
- [x] Add `<EmptyState title="Sin ingredientes" description="Aún no hay ingredientes registrados." />` when list is empty
- [x] Connect `useToast` to create/update/delete success and error feedback

---

### Change 11 — `catalog-products-management` (admin/stock side)

- [x] Replace inline skeleton in product list (stock/admin view) with `<SkeletonList rows={6} />`
- [x] Replace `window.confirm` in product delete action with `useConfirm({ variant: 'destructive', title: '¿Eliminar producto?' })`
- [x] Add `<EmptyState title="Sin productos" description="Aún no hay productos en el catálogo." />` when product list is empty
- [x] Connect `useToast` to product create/update/delete/availability-toggle feedback
- [x] Audit `pages/stock/` and `pages/admin/productos/` at 375px — verify table or card list reflows without horizontal overflow

---

### Change 12 — `catalog-public-browsing`

- [x] Replace inline skeleton implementation in `features/catalog/` with `<SkeletonList rows={8} />` for catalog grid `isPending` state
- [x] Replace any inline empty-state copy (no products found) with `<EmptyState title="Sin resultados" description='No encontramos productos para "{query}".' action={<ClearFilterButton />} />`
- [x] Audit `pages/catalog/` at 375px — verify product grid uses `grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4`
- [x] Verify product images use `aspect-square` or fixed height to prevent layout shift on load

---

### Change 13 — `customer-profile-management`

- [x] Replace inline skeleton/loading in `pages/profile/` with `<SkeletonRect height="h-64" />` or structured skeleton during data fetch
- [x] Connect `useToast` to profile update success/error feedback
- [x] Connect `useToast` to password change success/error feedback
- [x] Replace `window.confirm` on password change form (if present) with `useConfirm`
- [x] Audit `pages/profile/` at 375px — verify form inputs meet 44px touch target

---

### Change 14 — `delivery-addresses-management`

- [x] Replace inline skeleton in addresses list with `<SkeletonList rows={3} />`
- [x] Add `<EmptyState title="Sin direcciones guardadas" description="Agrega una dirección para el envío." action={<AddAddressButton />} />` when list is empty
- [x] Replace `window.confirm` in address delete action with `useConfirm({ variant: 'destructive', title: '¿Eliminar dirección?' })`
- [x] Connect `useToast` to address create/update/delete/set-principal feedback
- [x] Audit `pages/addresses/` at 375px — verify address cards stack correctly

---

### Change 15 — `shopping-cart-clientside`

- [x] Add `<EmptyState title="Tu carrito está vacío" description="Agrega productos para continuar." action={<Link to="/catalog">Ver catálogo</Link>} />` when cart has zero items
- [x] Replace `window.confirm` in cart item remove / clear-cart actions with `useConfirm` (if applicable)
- [x] Connect `useToast` to "Producto agregado al carrito" on add-to-cart action
- [x] Audit cart panel/drawer at 375px — verify item list scrolls correctly and checkout button meets 44px touch target

---

### Change 16 — `pre-checkout-validations`

- [x] Connect `useToast` to validation warning feedback (price changed, stock insufficient)
- [x] ~~Replace any inline alert/warning div with toast `warning` variant~~ — DECISION: kept inline alerts (UX-critical persistent feedback) + supplemented with toasts
- [x] Audit `pages/checkout/` validation step at 375px — action buttons at 44px (py-3)

---

### Change 17 — `order-creation-with-snapshots`

- [x] Replace inline loading/spinner during order submission with a skeleton overlay (SkeletonLine + SkeletonRect)
- [x] Connect `useToast` to order creation error feedback (network error, validation failure)
- [x] Audit `pages/checkout/` at 375px — verify address selection and summary reflow correctly

---

### Change 18 — `order-state-machine-transitions`

- [x] Replace `window.confirm` in all state-transition actions (advance state, cancel order) with `useConfirm`; use `variant: 'destructive'` for cancel with motivo
- [x] Connect `useToast` to state transition success (e.g. "Pedido marcado como EN PREPARACIÓN") and error feedback
- [x] Audit `pages/pedidos-panel/` at 375px — verify order list and action buttons reflow correctly and meet 44px touch target

---

### Change 19 — `payments-mercadopago-integration`

- [x] Connect `useToast` to payment initiation feedback (success redirect, error on preference creation)
- [x] Connect `useToast` to `/checkout/return` page feedback (payment approved, rejected, pending)
- [x] Audit `pages/checkout/return/` at 375px — verify status cards and CTA buttons meet touch targets

---

### Change 20 — `orders-visualization`

- [x] Replace inline skeleton in orders history list (`pages/orders/`) with `<SkeletonList rows={5} />`
- [x] Replace inline skeleton in order detail page with structured skeleton (header rect + timeline lines)
- [x] Add `<EmptyState title="Sin pedidos" description="Aún no realizaste ningún pedido." action={<Link to="/catalog">Ver catálogo</Link>} />` when CLIENT order list is empty
- [x] Replace inline skeleton in `widgets/orders-management-panel/` with `<SkeletonList rows={8} />`
- [x] Add `<EmptyState title="Sin pedidos" description="No hay pedidos que coincidan con los filtros." />` in management panel when filtered list is empty
- [x] Audit `pages/orders/` and `pages/orders/[id]/` at 375px — verify timeline and snapshot details scroll correctly

---

### Change 21 — `admin-users-management`

- [x] Replace inline skeleton in admin users list with `<SkeletonList rows={6} />`
- [x] Add `<EmptyState title="Sin usuarios" description="No hay usuarios registrados." />` when list is empty
- [x] Replace `window.confirm` in user deactivation action with `useConfirm({ variant: 'destructive', title: '¿Desactivar usuario?' })`
- [x] Connect `useToast` to user edit/deactivate success and error feedback
- [x] Audit `pages/admin/usuarios/` at 375px — verify table/card list reflows without horizontal overflow

---

### Change 22 — `admin-catalog-orders-aggregated-permissions`

- [x] Audit all admin-embedded views (products, stock, orders from admin tabs) — verify they inherit skeleton/empty-state primitives from Changes 09–20 rollout tasks
- [x] Verify ADMIN navigation items meet 44px touch targets in mobile view
- [x] Connect `useToast` to any ADMIN-level action feedback not already covered in per-feature rollout tasks

---

### Change 23 — `admin-metrics-dashboard`

- [x] Replace inline skeleton/spinner in KPI cards during `useMetricasResumen` `isPending` with `<SkeletonRect height="h-20" />` per card
- [x] Replace inline skeleton/spinner in chart components during `isPending` with `<SkeletonRect height="h-64" />`
- [x] Add `<EmptyState title="Sin datos para el período" description="Ajusta el rango de fechas para ver métricas." />` when metrics return empty arrays
- [x] Connect `useToast` to date range filter validation errors (invalid date range)
- [x] Audit `pages/admin/metricas/` at 375px — verify charts use horizontal scroll wrapper on mobile; verify KPI grid stacks to single column

---

## 9. Specs Validation

- [x] Run `openspec validate ui-ux-design-system --strict` and confirm PASS
- [x] Run `openspec status --change "ui-ux-design-system" --json` and confirm `isComplete: true`
