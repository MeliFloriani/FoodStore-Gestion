# frontend-design-system-toasts Specification

## Purpose
Define the toast notification system for the Food Store frontend: a global provider, an imperative `useToast` hook, individual toast UI with ARIA-live accessibility, and the convention for connecting mutation feedback across all feature pages. Introduced in Change 24 (ui-ux-design-system). Lives in `shared/ui/toast/` per FSD.

---

## ADDED Requirements

### Requirement: `shared/ui/toast/` SHALL provide a global toast provider and hook

The system SHALL provide a toast module at `frontend/src/shared/ui/toast/` containing:
- `toast.types.ts` — `ToastVariant` (`success | error | warning | info`) and `ToastItem` interface
- `ToastProvider.tsx` — React context provider rendering an ARIA-live region
- `Toast.tsx` — individual toast UI component
- `useToast.ts` — imperative hook returning `{ toast, dismiss, clear }`
- `index.ts` — barrel exporting all public API

#### Scenario: `useToast` is callable inside `<ToastProvider>`
- **WHEN** a component inside `<ToastProvider>` calls `const { toast } = useToast()`
- **THEN** the hook returns a stable `toast` function without error

#### Scenario: `useToast` throws outside `<ToastProvider>`
- **WHEN** a component outside `<ToastProvider>` calls `useToast()`
- **THEN** the hook throws an error indicating missing provider context

---

### Requirement: `ToastProvider` SHALL render an ARIA-live region

`ToastProvider` SHALL render a container with `aria-live="polite"` and `aria-atomic="true"` for screen-reader accessibility. The container SHALL be positioned outside the main document flow using absolute/fixed positioning.

#### Scenario: ARIA-live region is present in the DOM
- **WHEN** `<ToastProvider>` is mounted
- **THEN** a DOM element with `aria-live="polite"` is present in the document

#### Scenario: Toasts are announced by screen readers
- **WHEN** `toast({ variant: 'success', title: 'Pedido creado' })` is called
- **THEN** the toast content appears inside the `aria-live` region and is announced by assistive technology

---

### Requirement: Toast variants SHALL use semantic color tokens

Each `ToastVariant` SHALL render with a distinct visual treatment using semantic Tailwind tokens:
- `success`: green accent border or icon using `text-success-600` (or nearest semantic token)
- `error`: destructive accent using `text-destructive`
- `warning`: warning accent using `text-warning-600` (or nearest semantic token)
- `info`: brand accent using `text-primary`

#### Scenario: Success toast renders with success color
- **WHEN** `toast({ variant: 'success', title: 'Hecho' })` is called
- **THEN** the rendered toast element includes a success-variant class or inline color indicator

#### Scenario: Error toast renders with destructive color
- **WHEN** `toast({ variant: 'error', title: 'Error' })` is called
- **THEN** the rendered toast element includes a destructive-variant class or color indicator

---

### Requirement: Toasts SHALL auto-dismiss after `duration` ms

Each `ToastItem` SHALL include a `duration` field (default 4000 ms). When `duration > 0`, the toast SHALL be automatically removed from the queue after that many milliseconds. When `duration === 0`, the toast persists until manually dismissed.

#### Scenario: Toast auto-dismisses after 4 seconds
- **GIVEN** a toast is enqueued with `duration: 4000`
- **WHEN** 4000 ms elapse
- **THEN** the toast is removed from the visible queue

#### Scenario: Toast with duration 0 does not auto-dismiss
- **GIVEN** a toast is enqueued with `duration: 0`
- **WHEN** 10000 ms elapse
- **THEN** the toast remains visible until `dismiss(id)` is explicitly called

---

### Requirement: Toast queue SHALL cap at 5 simultaneous toasts

When more than 5 toasts are enqueued simultaneously, the oldest toast SHALL be dismissed to maintain the cap.

#### Scenario: Sixth toast evicts oldest
- **GIVEN** 5 toasts are currently visible
- **WHEN** a sixth toast is enqueued
- **THEN** the oldest toast is dismissed and the new toast appears

---

### Requirement: `<ToastProvider>` SHALL be mounted exactly once in `app/`

`<ToastProvider>` SHALL be mounted at the root provider level in `frontend/src/app/providers.tsx` (or equivalent). It SHALL NOT be mounted inside individual feature or page components.

#### Scenario: Single provider at app root
- **WHEN** the application renders
- **THEN** exactly one `<ToastProvider>` is present in the React tree

---

### Requirement: Toast z-index SHALL use the `z-toast` scale token

The toast container SHALL use `z-index: 50` (matching the `z-toast` token from the design token extension) to render above modals and overlays during error states. Standard z-index stacking: `z-toast (50) > z-modal (40) > z-overlay (30)`.

#### Scenario: Toast renders above content
- **WHEN** a toast is triggered while a confirm dialog is open
- **THEN** the toast is visible above the dialog overlay
