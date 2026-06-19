# frontend-design-system-confirm-dialog Specification

## Purpose
Define the imperative confirm dialog primitive for the Food Store frontend: a `useConfirm()` hook returning `Promise<boolean>`, a portal-rendered modal, and a global provider. Replaces all `window.confirm` call sites across all feature pages. Introduced in Change 24 (ui-ux-design-system). Lives in `shared/ui/confirm-dialog/` per FSD.

---

## ADDED Requirements

### Requirement: `shared/ui/confirm-dialog/` SHALL provide an imperative `useConfirm` hook

The system SHALL provide a confirm dialog module at `frontend/src/shared/ui/confirm-dialog/` containing:
- `confirm-dialog.types.ts` — `ConfirmVariant` (`default | destructive`) and `ConfirmOptions` interface
- `ConfirmDialogProvider.tsx` — React context provider holding pending confirm state
- `ConfirmDialog.tsx` — modal UI rendered via `ReactDOM.createPortal`
- `useConfirm.ts` — hook returning `{ confirm: (options: ConfirmOptions) => Promise<boolean> }`
- `index.ts` — barrel exporting all public API

#### Scenario: `useConfirm` is callable inside `<ConfirmDialogProvider>`
- **WHEN** a component inside `<ConfirmDialogProvider>` calls `const { confirm } = useConfirm()`
- **THEN** the hook returns a stable `confirm` function without error

#### Scenario: `useConfirm` throws outside `<ConfirmDialogProvider>`
- **WHEN** a component outside `<ConfirmDialogProvider>` calls `useConfirm()`
- **THEN** the hook throws an error indicating missing provider context

---

### Requirement: `confirm()` SHALL return a `Promise<boolean>`

`useConfirm().confirm(options)` SHALL:
- Open the confirm dialog with the provided options.
- Return a `Promise<boolean>` that resolves `true` when the user clicks the confirm button.
- Resolve `false` when the user clicks the cancel button, presses `Escape`, or clicks the overlay.

#### Scenario: User confirms — Promise resolves true
- **GIVEN** `confirm({ title: '¿Eliminar?' })` is called and the dialog is open
- **WHEN** the user clicks the confirm button
- **THEN** the returned Promise resolves with `true` and the dialog closes

#### Scenario: User cancels — Promise resolves false
- **GIVEN** `confirm({ title: '¿Eliminar?' })` is called and the dialog is open
- **WHEN** the user clicks the cancel button
- **THEN** the returned Promise resolves with `false` and the dialog closes

#### Scenario: Escape key resolves false
- **GIVEN** the confirm dialog is open
- **WHEN** the user presses `Escape`
- **THEN** the Promise resolves `false` and the dialog closes

#### Scenario: Overlay click resolves false
- **GIVEN** the confirm dialog is open
- **WHEN** the user clicks outside the dialog modal (on the overlay)
- **THEN** the Promise resolves `false` and the dialog closes

---

### Requirement: `ConfirmDialog` SHALL be rendered via portal at `z-modal (40)`

`ConfirmDialog` SHALL be rendered using `ReactDOM.createPortal` into `document.body`. The dialog SHALL use z-index `40` (matching the `z-modal` scale token) and render above all page content and the sticky navigation.

#### Scenario: Dialog renders in document.body
- **WHEN** the confirm dialog is open
- **THEN** the dialog DOM element is a direct child of `document.body` (portal)

---

### Requirement: `ConfirmDialog` SHALL trap keyboard focus while open

While the dialog is open, keyboard focus SHALL be trapped within the dialog — Tab and Shift+Tab cycle only between focusable elements inside the dialog. Focus returns to the trigger element when the dialog closes.

#### Scenario: Focus is trapped inside dialog
- **GIVEN** the confirm dialog is open
- **WHEN** the user presses Tab repeatedly
- **THEN** focus cycles only between the dialog's focusable elements (cancel, confirm buttons)

---

### Requirement: `ConfirmDialog` SHALL use ARIA roles for accessibility

The dialog element SHALL have `role="alertdialog"`, `aria-modal="true"`, and `aria-labelledby` pointing to the title element's `id`.

#### Scenario: Dialog has correct ARIA attributes
- **WHEN** the confirm dialog is open
- **THEN** the dialog element has `role="alertdialog"`, `aria-modal="true"`, and `aria-labelledby` resolving to the visible title text

---

### Requirement: `destructive` variant SHALL style the confirm button as destructive

When `ConfirmOptions.variant === 'destructive'`, the confirm button SHALL use `bg-destructive text-destructive-foreground` semantic tokens. The cancel button SHALL remain unchanged.

#### Scenario: Destructive confirm button uses destructive colors
- **GIVEN** `confirm({ title: '¿Eliminar usuario?', variant: 'destructive' })` is called
- **WHEN** the dialog renders
- **THEN** the confirm button has class `bg-destructive text-destructive-foreground`

#### Scenario: Default variant uses primary colors
- **GIVEN** `confirm({ title: '¿Confirmar?' })` is called (no variant prop)
- **WHEN** the dialog renders
- **THEN** the confirm button uses `bg-primary text-primary-foreground`

---

### Requirement: `ConfirmDialogProvider` SHALL be mounted exactly once in `app/`

`<ConfirmDialogProvider>` SHALL be mounted at the root provider level in `frontend/src/app/providers.tsx` (or equivalent). It SHALL NOT be mounted inside individual feature or page components.

#### Scenario: Single provider at app root
- **WHEN** the application renders
- **THEN** exactly one `<ConfirmDialogProvider>` is present in the React tree

---

### Requirement: `window.confirm` SHALL NOT be used anywhere in the frontend

All call sites of `window.confirm` in `frontend/src/` SHALL be replaced with `useConfirm()` from `shared/ui/confirm-dialog/`. This is a normative convention enforced at code review.

#### Scenario: No window.confirm in codebase
- **WHEN** a grep for `window\.confirm` is run on `frontend/src/`
- **THEN** zero matches are found
