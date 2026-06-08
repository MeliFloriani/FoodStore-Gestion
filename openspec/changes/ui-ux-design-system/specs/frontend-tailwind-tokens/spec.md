# frontend-tailwind-tokens Specification (delta — Change 24)

## Purpose (delta)
Extend the token system seeded in Change 05 (`frontend-core-foundation`) with three additive token categories: focus-ring CSS variable token, a named z-index scale, and a named motion duration scale. These extensions are consumed by the design system primitives introduced in Change 24 (toast z-index, confirm dialog z-index, skeleton animation duration). No existing requirements from Change 05 are modified.

---

## MODIFIED Requirements

> **Note**: The existing spec text references "Design System (Change 27)". That reference is stale from a prior 26-change roadmap. Change 24 (`ui-ux-design-system`) fulfills the role previously attributed to "Change 27". The spec text is not renamed — this note provides historical context.

### Requirement: `tailwind.config.js` SHALL extend the `ring` color token with a `focus` sub-token

`tailwind.config.js` SHALL add `ring.focus` under `theme.extend.colors` mapped to `var(--color-ring-focus)`. This token SHALL be used for focus-ring styling on interactive elements (buttons, inputs) to ensure keyboard navigation is visually distinct from the existing `ring` token.

#### Scenario: Focus-ring color utility class is generated
- **WHEN** `tailwindcss` processes `tailwind.config.js` after Change 24 additions
- **THEN** utility class `ring-focus` (or `outline-focus` equivalent) is available and resolves to the `--color-ring-focus` CSS variable

---

### Requirement: `src/app/styles/index.css` SHALL define `--color-ring-focus` CSS variable under `:root` and `.dark`

`src/app/styles/index.css` SHALL define `--color-ring-focus` under `:root` (brand-derived focus tint, e.g. brand primary at 400–500 level with sufficient contrast on white) and under `.dark` (adjusted brand tint at 300 level for dark background contrast). This variable SHALL be present alongside all existing `--color-*` semantic variables defined in Change 05.

#### Scenario: Focus-ring token resolves in light mode
- **WHEN** `<html>` does not have `dark` class
- **THEN** `--color-ring-focus` resolves from `:root` and is visually distinct against `--color-background`

#### Scenario: Focus-ring token resolves in dark mode
- **WHEN** `dark` class is on `<html>`
- **THEN** `--color-ring-focus` resolves from `.dark` and is visually distinct against the dark `--color-background`

---

## ADDED Requirements

### Requirement: `tailwind.config.js` SHALL define a named z-index scale under `theme.extend.zIndex`

`tailwind.config.js` SHALL extend `theme.zIndex` (via `theme.extend.zIndex`) with the following named levels:

| Token | Value | Intended use |
|---|---|---|
| `base` | `0` | Default stacking context |
| `dropdown` | `10` | Dropdown menus, popovers |
| `sticky` | `20` | Sticky headers, toolbars |
| `overlay` | `30` | Page overlays, drawer backdrops |
| `modal` | `40` | Modal dialogs (ConfirmDialog) |
| `toast` | `50` | Toast notifications |
| `tooltip` | `60` | Tooltips (always above everything) |

These values SHALL be available as Tailwind utility classes `z-base`, `z-dropdown`, `z-sticky`, `z-overlay`, `z-modal`, `z-toast`, `z-tooltip`.

#### Scenario: Named z-index utilities are generated
- **WHEN** `tailwindcss` generates utilities after Change 24 config additions
- **THEN** `z-modal`, `z-toast`, and `z-tooltip` classes are available in the output

#### Scenario: z-index stacking order is correct
- **WHEN** a toast renders simultaneously with a modal overlay
- **THEN** `z-toast (50) > z-modal (40) > z-overlay (30)` ensures toast is on top

---

### Requirement: `tailwind.config.js` SHALL define a named motion duration scale under `theme.extend.transitionDuration`

`tailwind.config.js` SHALL extend `theme.transitionDuration` (via `theme.extend.transitionDuration`) with:

| Token | Value | Intended use |
|---|---|---|
| `instant` | `0ms` | Immediate state changes (no animation) |
| `fast` | `150ms` | Micro-interactions (button hover, toggle) |
| `base` | `250ms` | Standard transitions (modal open, dropdown) |
| `slow` | `400ms` | Complex animations (skeleton fade, page transitions) |

These SHALL be available as Tailwind utility classes `duration-instant`, `duration-fast`, `duration-base`, `duration-slow`.

#### Scenario: Named duration utilities are generated
- **WHEN** `tailwindcss` generates utilities after Change 24 config additions
- **THEN** `duration-fast`, `duration-base`, `duration-slow` classes are available

#### Scenario: Motion tokens used in design system components
- **WHEN** `Toast.tsx` applies enter/exit animation
- **THEN** it uses `duration-base` (250ms) rather than a hard-coded duration value

---

### Requirement: New token additions SHALL NOT override or conflict with existing Change 05 tokens

The z-index scale, motion duration scale, and focus-ring token additions are purely additive. They SHALL be placed under `theme.extend.*` (not `theme.*`), ensuring they do not replace Tailwind's default z-index or duration values and do not conflict with any token defined in Change 05.

#### Scenario: Existing tokens remain unchanged after Change 24
- **WHEN** `tailwind.config.js` is inspected after Change 24 additions
- **THEN** all semantic color tokens (`primary`, `background`, `foreground`, `destructive`, etc.) from Change 05 are present and unchanged
- **THEN** all primitive palette tokens (`brand-500`, `neutral-700`, etc.) from Change 05 are present and unchanged
