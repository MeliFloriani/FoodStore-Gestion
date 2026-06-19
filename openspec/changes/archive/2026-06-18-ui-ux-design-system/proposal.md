# Proposal: ui-ux-design-system (Change 24)

## Sprint
8

## User Stories Covered
- **Rubric criterion**: "UI/UX y Diseño" (10 pts) — no specific user story; transversal quality criterion.

---

## Why

The Food Store frontend has accumulated 18 feature changes (06–23) each building their own inline UI patterns: ad-hoc skeleton divs, `window.confirm` dialogs, inline empty-state copy, and non-unified loading states. Change 05 seeded a two-level Tailwind token system to avoid later retooling, but the semantic layer above those tokens — shared primitives for feedback, confirmation, and graceful degradation — was deferred. With all business features now implemented, the system is evaluable on visual coherence under rubric criterion "UI/UX y Diseño" (10 pts). This change consolidates the design system, introduces the missing shared primitives, establishes the mobile-first layout policy, and sequences the progressive rollout of those primitives across all existing features.

This change does **NOT** add business functionality and does **NOT** modify the behavior of any existing feature. It is a purely visual/UX consolidation pass.

---

## What Changes

### New shared UI primitives (FSD `shared/ui/`)

- **Toast system** — `shared/ui/toast/`: provider + `useToast` hook; variants `success | error | warning | info`; ARIA-live region; auto-dismiss + manual close. Global provider mounted once in `app/`.
- **Skeleton loaders** — `shared/ui/skeleton/`: composable shape primitives (`SkeletonLine`, `SkeletonCircle`, `SkeletonRect`) + compound patterns (`SkeletonList`, `SkeletonCard`). Usage convention for TanStack Query `isPending` states.
- **Confirm dialog** — `shared/ui/confirm-dialog/`: imperative `useConfirm()` hook returning `Promise<boolean>`; variants `default | destructive`. Replaces all `window.confirm` call sites across features.
- **Empty state** — `shared/ui/empty-state/`: `<EmptyState>` component with `icon`, `title`, `description`, optional `action` props. Convention for "no data", "empty cart", "no results in filter".

### Design token extensions (tailwind.config.js + CSS variables)

- Extend Change 05 token base with: focus-ring tokens (if missing), z-index scale, motion duration scale.
- No re-definition of existing primitive or semantic tokens — only additive.

### Typography utilities

- Document and enforce consistent heading hierarchy (h1–h6 Tailwind utility patterns), body/caption variants, and `font-sans` / `font-display` usage.

### Mobile-first layout policy

- Written policy (design.md + spec) covering breakpoints, container widths, grid utilities, 44×44 px touch targets, and per-page compliance checklist.
- No page refactoring — policy only.

### Progressive rollout plan (tasks.md)

- `tasks.md` enumerates, per archived feature (Changes 06–23), concrete visual-refinement tasks (replace inline skeleton → `<SkeletonList>`, replace `window.confirm` → `useConfirm`, replace ad-hoc empty UI → `<EmptyState>`, audit mobile breakpoints, connect toast on mutations). Tasks are all unchecked; implementation is Sprint 8 refinement work.

---

## Capabilities

### New Capabilities

- `frontend-design-system-toasts`: Toast primitive provider + `useToast` hook with ARIA-live support and auto-dismiss behavior.
- `frontend-design-system-skeletons`: Composable skeleton shape primitives and compound patterns for loading states.
- `frontend-design-system-confirm-dialog`: Imperative `useConfirm()` hook + modal primitive returning `Promise<boolean>`.
- `frontend-design-system-empty-state`: `<EmptyState>` component contract for no-data, empty-cart, and no-results states.
- `frontend-design-system-typography`: Typography scale, heading hierarchy utilities, and font-family usage policy.
- `frontend-design-system-mobile-first-layout`: Mobile-first layout policy, breakpoint contract, touch target minimums, and per-page compliance checklist.

### Modified Capabilities

- `frontend-tailwind-tokens`: Extend the seeded token system (Change 05) with focus-ring CSS variables, a z-index scale, and motion duration tokens — only if those are missing from the current spec. Existing primitive and semantic token requirements are not changed.

---

## Non-Goals

- **No business logic changes** — no new API endpoints, no new data models, no behavioral changes to existing features.
- **No visual refactoring during this change's apply** — `tasks.md` sequences it, but implementation of the per-feature rollout is Sprint 8 refinement work run separately.
- **No new user stories** — this change has no associated US. The driver is solely the rubric criterion.
- **No duplication of Change 05 token work** — the existing primitive and semantic tokens are consumed as-is; this change only adds the missing semantic layer above them.
- **No dark mode theming pass** — light/dark parity is assured at token level (CSS variables already support it from Change 05); component-level dark mode utilities are inherited from Tailwind tokens.
- **No backend changes** — purely frontend.

---

## Dependencies

| Change | Name | What It Provides |
|---|---|---|
| Change 05 | `frontend-core-foundation` | Two-level Tailwind token system (primitive + semantic), `tailwindcss-animate` plugin, `darkMode: 'class'` strategy — all consumed as foundation |

---

## Impact

- **Files created (apply phase)**: `frontend/src/shared/ui/toast/`, `frontend/src/shared/ui/skeleton/`, `frontend/src/shared/ui/confirm-dialog/`, `frontend/src/shared/ui/empty-state/`; minor additions to `tailwind.config.js` and `src/app/styles/index.css`.
- **Files modified (apply phase)**: `frontend/src/app/` (mount toast provider); per-feature rollout files enumerated in `tasks.md`.
- **No backend impact**.
- **No API contract changes**.
- **No breaking changes** — new primitives are additive; rollout is opt-in per task.

---

## Risks

- **R-01 — Rollout scope creep**: Per-feature rollout tasks (Changes 06–23) touch many files. Risk: apply phase spirals into untracked refactoring. Mitigation: each rollout task in `tasks.md` is scoped to a single file/component; no structural refactoring allowed.
- **R-02 — `useConfirm` async pattern unfamiliarity**: Imperative Promise-based confirm differs from React's typical declarative patterns and may be implemented incorrectly. Mitigation: design.md specifies the exact hook API contract; spec includes WHEN/THEN scenarios.
- **R-03 — Mobile-first policy non-compliance in existing pages**: Some archived features may use non-responsive layouts. Risk: audit discovers widespread violations requiring more effort than anticipated. Mitigation: policy is a checklist, not a blocker; items are deferred tasks, not apply-phase gates.
