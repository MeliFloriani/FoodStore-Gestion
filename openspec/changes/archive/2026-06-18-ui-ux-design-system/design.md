# Design: ui-ux-design-system (Change 24)

## Architectural Goal

Introduce a coherent shared UI layer (`shared/ui/`) for the Food Store frontend that:
1. Builds on the Tailwind token foundation seeded in Change 05 (no re-invention of existing tokens).
2. Provides four new primitive components — Toast, Skeleton, ConfirmDialog, EmptyState — each living in `shared/ui/` per FSD.
3. Documents the typography scale and mobile-first layout policy as normative references for all feature pages.
4. Sequences the progressive rollout across all archived features (Changes 06–23) as Sprint 8 refinement tasks.

> **Historical note**: The existing `frontend-tailwind-tokens` spec references "Design System (Change 27)". That reference is stale from a prior 26-change roadmap. The current consolidated roadmap (`docs/CHANGES.md`) confirms 26 changes total and the design system is **Change 24**. This change fulfills the role previously attributed to "Change 27" in the seeded spec text. The spec text is not renamed or corrected — it is treated as historical context.

---

## Token Strategy

### What is reused from Change 05 (no changes)

The following are defined and complete in `openspec/specs/frontend-tailwind-tokens/spec.md`:
- Level 1 primitive palette: `brand`, `neutral`, `success`, `warning`, `danger`, `info` (50–900 scales).
- Level 2 semantic tokens via CSS variables: `background`, `foreground`, `muted`, `muted-foreground`, `accent`, `accent-foreground`, `destructive`, `destructive-foreground`, `border`, `input`, `ring`, `card`, `card-foreground`, `popover`, `popover-foreground`, `primary`, `primary-foreground`, `secondary`, `secondary-foreground`.
- `darkMode: 'class'` strategy — toggled via `dark` class on `<html>`.
- `tailwindcss-animate` plugin registered.
- `fontFamily.sans` and `fontFamily.display` stacks.
- `borderRadius`, `boxShadow`, `screens` scales.

### What Change 24 adds (additive only)

Only tokens not present in the current spec are added. Each addition is guarded by "if missing" — do not duplicate existing tokens.

| Token category | Proposed additions | Where |
|---|---|---|
| Focus-ring | `--color-ring-focus` CSS variable mapped to a brand-derived tint; `ring-focus` Tailwind token under `theme.extend.colors.ring` | `tailwind.config.js` + `:root` / `.dark` |
| Z-index scale | Named z-index tokens: `z-base (0)`, `z-dropdown (10)`, `z-sticky (20)`, `z-overlay (30)`, `z-modal (40)`, `z-toast (50)`, `z-tooltip (60)` | `tailwind.config.js` `theme.extend.zIndex` |
| Motion duration | `duration-instant (0ms)`, `duration-fast (150ms)`, `duration-base (250ms)`, `duration-slow (400ms)` | `tailwind.config.js` `theme.extend.transitionDuration` |

All additions land in `tailwind.config.js` and, for CSS variable tokens, in `src/app/styles/index.css` under `:root` and `.dark`.

### Palette accessibility contract

- All text-on-background combinations using semantic tokens MUST meet WCAG AA (4.5:1 normal text, 3:1 large text).
- Contrast is the responsibility of the CSS variable assignments in `:root` and `.dark` — the token definition phase establishes this contract; verification is in the audit checklist.

---

## Primitive Components Inventory

All primitives live in `shared/ui/` per FSD. They MUST NOT import from `features/`, `entities/`, or `pages/`.

### 1. Toast System

**FSD path**: `frontend/src/shared/ui/toast/`

**Architecture**: Provider + Consumer + Hook pattern.

```
shared/ui/toast/
├── index.ts                  ← Public API barrel
├── ToastProvider.tsx          ← Context + ARIA live region
├── Toast.tsx                  ← Individual toast UI
├── useToast.ts                ← Hook: enqueue, dismiss, clear
└── toast.types.ts             ← ToastVariant, ToastItem interfaces
```

**API contract**:
```typescript
type ToastVariant = 'success' | 'error' | 'warning' | 'info';

interface ToastItem {
  id: string;
  variant: ToastVariant;
  title: string;
  description?: string;
  duration?: number; // ms, default 4000; 0 = persist
}

// Hook (consumed anywhere inside <ToastProvider>)
function useToast(): {
  toast: (item: Omit<ToastItem, 'id'>) => string; // returns id
  dismiss: (id: string) => void;
  clear: () => void;
}
```

**Behavior**:
- `<ToastProvider>` renders an `aria-live="polite" aria-atomic="true"` region outside the main content flow (z-index: `z-toast`).
- Auto-dismiss uses `setTimeout` per toast; manual close button always present.
- Multiple toasts stack vertically (max 5 visible at once; older ones dismissed when limit exceeded).
- `<ToastProvider>` mounted once in `frontend/src/app/` (root provider).

**Usage pattern**:
```typescript
// In any feature component
const { toast } = useToast();
toast({ variant: 'success', title: 'Pedido creado', description: 'Tu pedido fue registrado.' });
```

---

### 2. Skeleton Loaders

**FSD path**: `frontend/src/shared/ui/skeleton/`

```
shared/ui/skeleton/
├── index.ts                  ← Public API barrel
├── SkeletonLine.tsx           ← Single text line (width: prop, height: default 1rem)
├── SkeletonCircle.tsx         ← Avatar / icon placeholder (size: prop)
├── SkeletonRect.tsx           ← Block placeholder (width, height: props)
├── SkeletonCard.tsx           ← Compound: image rect + 3 lines (product card pattern)
└── SkeletonList.tsx           ← Compound: N × SkeletonCard (rows: prop, default 4)
```

**API contract**:
```typescript
// Primitives accept className for composition
<SkeletonLine width="w-3/4" />
<SkeletonCircle size="h-10 w-10" />
<SkeletonRect width="w-full" height="h-48" />

// Compounds
<SkeletonCard />                  // Single product card skeleton
<SkeletonList rows={6} />         // 6 stacked SkeletonCards
```

**Behavior**:
- All skeletons use `animate-pulse` from `tailwindcss-animate` and `bg-muted` token.
- Convention: whenever a TanStack Query hook returns `isPending: true`, render the appropriate skeleton instead of null or a spinner.

---

### 3. Confirm Dialog

**FSD path**: `frontend/src/shared/ui/confirm-dialog/`

```
shared/ui/confirm-dialog/
├── index.ts                     ← Public API barrel
├── ConfirmDialogProvider.tsx     ← Context + modal renderer
├── ConfirmDialog.tsx             ← Dialog UI (portal rendered)
└── useConfirm.ts                 ← Imperative hook → Promise<boolean>
```

**API contract**:
```typescript
type ConfirmVariant = 'default' | 'destructive';

interface ConfirmOptions {
  title: string;
  description?: string;
  confirmLabel?: string;   // default: 'Confirmar'
  cancelLabel?: string;    // default: 'Cancelar'
  variant?: ConfirmVariant; // default: 'default'
}

// Hook (consumed anywhere inside <ConfirmDialogProvider>)
function useConfirm(): {
  confirm: (options: ConfirmOptions) => Promise<boolean>;
}
```

**Behavior**:
- `useConfirm().confirm(opts)` opens the dialog and returns a Promise that resolves `true` (confirmed) or `false` (cancelled or dismissed via Escape / overlay click).
- Dialog is rendered into a portal (`document.body`) at z-index `z-modal`.
- `destructive` variant renders the confirm button in `bg-destructive text-destructive-foreground`.
- Keyboard: `Enter` confirms, `Escape` cancels.
- `<ConfirmDialogProvider>` mounted once in `frontend/src/app/` (root provider), adjacent to `<ToastProvider>`.

**Usage pattern**:
```typescript
const { confirm } = useConfirm();
const ok = await confirm({
  title: '¿Eliminar usuario?',
  description: 'Esta acción no se puede deshacer.',
  variant: 'destructive',
  confirmLabel: 'Eliminar',
});
if (ok) { /* proceed */ }
```

---

### 4. Empty State

**FSD path**: `frontend/src/shared/ui/empty-state/`

```
shared/ui/empty-state/
├── index.ts                ← Public API barrel
└── EmptyState.tsx           ← Single component
```

**API contract**:
```typescript
interface EmptyStateProps {
  icon?: ReactNode;            // SVG icon or emoji
  title: string;               // Primary message
  description?: string;        // Secondary message
  action?: ReactNode;          // CTA button (optional)
  className?: string;
}
```

**Behavior**:
- Renders a centered flex column.
- `icon` rendered at 48×48 with `text-muted-foreground`.
- `title` uses `text-lg font-semibold`.
- `description` uses `text-sm text-muted-foreground`.
- `action` renders below description.

**Usage conventions**:
| Context | title | description | action |
|---|---|---|---|
| Empty cart | "Tu carrito está vacío" | "Agrega productos para continuar." | Link to `/catalog` |
| No search results | "Sin resultados" | 'No encontramos productos para "{query}".' | Clear filter button |
| No orders | "Sin pedidos" | "Aún no realizaste ningún pedido." | Link to `/catalog` |
| No addresses | "Sin direcciones guardadas" | "Agrega una dirección para el envío." | Open add-address form |

---

## Typography Scale

### Font families

| Token | Stack | Usage |
|---|---|---|
| `font-sans` | Inter, system-ui, sans-serif | Body text, UI labels, form inputs |
| `font-display` | Poppins, Inter, system-ui, sans-serif | Page headings, hero text, brand elements |

> Both stacks already defined in Change 05 (`frontend-tailwind-tokens` spec). Change 24 enforces their usage — no new font families.

### Heading hierarchy (Tailwind utility patterns)

| Level | Classes | Use |
|---|---|---|
| h1 | `text-4xl font-display font-bold leading-tight` | Page titles |
| h2 | `text-2xl font-display font-semibold leading-snug` | Section headings |
| h3 | `text-xl font-display font-semibold leading-snug` | Card/widget headings |
| h4 | `text-lg font-sans font-semibold leading-normal` | Sub-sections |
| h5 | `text-base font-sans font-medium leading-normal` | Labels, sub-headings |
| h6 | `text-sm font-sans font-medium leading-normal` | Meta-labels |

### Body and caption variants

| Variant | Classes | Use |
|---|---|---|
| Body | `text-base font-sans leading-relaxed` | Paragraphs, list items |
| Body SM | `text-sm font-sans leading-relaxed` | Compact descriptions |
| Caption | `text-xs font-sans text-muted-foreground` | Timestamps, helper text |
| Label | `text-sm font-sans font-medium` | Form labels |
| Code | `font-mono text-sm` | Code snippets |

---

## Mobile-First Layout Policy

### Breakpoint contract

Inherited from Change 05 `tailwind.config.js` `theme.screens` (do not redefine):

| Breakpoint | Width | Typical target |
|---|---|---|
| (default) | < 640px | Mobile phones |
| `sm:` | ≥ 640px | Large phones / small tablets |
| `md:` | ≥ 768px | Tablets |
| `lg:` | ≥ 1024px | Laptops |
| `xl:` | ≥ 1280px | Desktops |
| `2xl:` | ≥ 1536px | Large desktops |

### Container widths

```
max-w-screen-sm (sm:) → max-w-screen-md (md:) → max-w-screen-lg (lg:) → max-w-screen-xl (xl:)
```
All page containers use `mx-auto px-4 sm:px-6 lg:px-8`.

### Grid utilities

- Single column by default; expand at `md:` to 2 columns, at `lg:` to 3–4 columns for grids.
- Catalog grid: `grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4`.
- Dashboard metrics grid: `grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4`.

### Touch target minimums

Per WCAG 2.5.5 (AAA) and Apple HIG: interactive elements MUST be at least **44×44 px** on mobile.
- Buttons: `min-h-[44px] min-w-[44px]` — use padding not fixed height.
- Icon buttons: `p-3` minimum (48px effective area).
- Form inputs: `h-11` (44px) as baseline.

### Per-page compliance checklist (normative)

Every page MUST satisfy these criteria before the change is archived:
- [ ] Renders correctly at 375px viewport width without horizontal scroll.
- [ ] All buttons and interactive elements meet 44×44px touch target.
- [ ] Text is readable without zoom at mobile viewport (no text smaller than 14px visible on mobile).
- [ ] Images and cards reflow correctly across all breakpoints.
- [ ] Tables / panels that don't fit on mobile have a horizontal scroll wrapper (`overflow-x-auto`).
- [ ] Loading states use skeleton primitives (not blank/null) on `isPending`.
- [ ] Empty states use `<EmptyState>` with a title and description.
- [ ] Destructive actions use `useConfirm` (not `window.confirm`).
- [ ] Success/error feedback on mutations uses `useToast` (not inline alert).

---

## Progressive Rollout Strategy (Sprint 8 Plan)

### Phasing

**Sprint 8 — Phase A (this change's apply scope)**:
1. Implement the 4 new shared primitives.
2. Apply minimal token extensions (focus-ring, z-index, motion durations).
3. Document typography utilities.
4. Write the mobile-first layout policy spec.
5. Mount `<ToastProvider>` and `<ConfirmDialogProvider>` in `app/`.

**Sprint 8 — Phase B (per-feature rollout — deferred tasks)**:
- Pick up tasks from `tasks.md §8` one feature at a time.
- Each feature's tasks are independent; no ordering requirement between features.
- Recommended order: high-visibility features first (catalog, checkout, orders).

### Rollout scope per archived change

The progressive rollout tasks are enumerated in `tasks.md` under section 8. They cover all archived changes 06–23 with specific file-level tasks per feature.

---

## Provider Mounting in `app/`

```
frontend/src/app/
├── providers.tsx    ← MODIFIED: add <ToastProvider>, <ConfirmDialogProvider>
└── App.tsx          ← Unchanged; composed via providers.tsx
```

Provider nesting order (outermost first):
1. `QueryClientProvider` (already present)
2. `BrowserRouter` (already present)
3. `ToastProvider` (NEW — Change 24)
4. `ConfirmDialogProvider` (NEW — Change 24)
5. Application routes

---

## Out of Scope

- Backend changes of any kind.
- New business features, API endpoints, or data models.
- Dark mode theming pass at component level (tokens already support it via CSS variables).
- Animation choreography beyond `animate-pulse` for skeletons.
- Custom icon library (use inline SVG or existing icon utilities from Tailwind).
- Storybook / component docs site.
- Automated accessibility testing (axe-core integration) — deferred to Change 25/26.

---

## Open Questions

| ID | Question | Default assumption |
|---|---|---|
| OQ-01 | Are focus-ring tokens truly missing from the current `tailwind.config.js`? | Assume missing; inspect during apply before adding. |
| OQ-02 | Should toast duration be configurable per toast or global? | Per-toast via `duration` prop; global default 4000ms. |
| OQ-03 | Should `SkeletonCard` layout match the exact current catalog card DOM? | Yes — match `frontend/src/features/catalog/` card structure during apply. |
| OQ-04 | Should `<EmptyState>` icon be required? | No — optional; render layout without icon slot if omitted. |
