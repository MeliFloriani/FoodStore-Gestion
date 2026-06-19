# frontend-tailwind-tokens Specification

## Purpose
Define the enterprise-grade Tailwind CSS token system for the Food Store frontend: a two-level color palette (primitive scales + semantic CSS-variable-backed tokens), dark-mode via `class` strategy, typography/spacing/shadow scales, and the `tailwindcss-animate` plugin registration. These tokens are the shared design contract consumed by all feature UIs and the Design System (Change 24 `ui-ux-design-system`), preventing ad-hoc color and spacing choices across the codebase.

## Requirements

### Requirement: Two-level color palette defined in tailwind.config.js
`tailwind.config.js` SHALL define a two-level color system under `theme.extend.colors`:

**Level 1 — Primitive palette**: `brand` (50-900), `neutral` (50-900), `success` (50-900), `warning` (50-900), `danger` (50-900), `info` (50-900). Each scale SHALL follow the standard Tailwind 11-step convention.

**Level 2 — Semantic tokens**: `background`, `foreground`, `muted`, `muted-foreground`, `accent`, `accent-foreground`, `destructive`, `destructive-foreground`, `border`, `input`, `ring`, `card`, `card-foreground`, `popover`, `popover-foreground`, `primary`, `primary-foreground`, `secondary`, `secondary-foreground`. Each semantic token SHALL reference a CSS variable (`var(--color-<token>)`) so that dark mode can override values without rebuilding.

#### Scenario: Semantic color utility classes are generated
- **WHEN** `tailwindcss` processes `tailwind.config.js`
- **THEN** utility classes like `bg-background`, `text-foreground`, `border-border`, `bg-primary`, `text-destructive` are available in the output

#### Scenario: Primitive color utility classes are generated
- **WHEN** `tailwindcss` processes `tailwind.config.js`
- **THEN** utility classes like `bg-brand-500`, `text-neutral-700`, `bg-danger-100` are available

---

### Requirement: CSS variable token values defined for light and dark modes
`src/app/styles/index.css` SHALL define CSS variables for all semantic tokens under `:root` (light mode) and `.dark` (dark mode override). All `var(--color-*)` references in `tailwind.config.js` SHALL resolve to defined CSS variables.

#### Scenario: Light mode tokens applied by default
- **WHEN** the `<html>` element does not have the `dark` class
- **THEN** CSS variables from `:root` are active and `bg-background` renders the light background color

#### Scenario: Dark mode tokens applied when class present
- **WHEN** the `dark` class is added to `<html>`
- **THEN** CSS variables from `.dark` override the defaults and `bg-background` renders the dark background color

---

### Requirement: Typography scale extended
`tailwind.config.js` SHALL extend `theme.fontFamily`, `theme.fontSize`, and `theme.fontWeight` with project-specific typography tokens. `fontFamily` SHALL define at least `sans` (body font stack) and `display` (heading font stack). `fontSize` SHALL include named sizes mapped to `[size, lineHeight]` tuples.

#### Scenario: Font family utilities are available
- **WHEN** Tailwind generates utilities
- **THEN** `font-sans` and `font-display` classes are available

---

### Requirement: Spacing, borderRadius, boxShadow, and screen scales defined
`tailwind.config.js` SHALL define:
- `theme.extend.borderRadius`: `sm`, `md`, `lg`, `xl`, `2xl`, `full`
- `theme.extend.boxShadow`: `sm`, `md`, `lg`, `xl`
- `theme.screens`: standard breakpoints `sm: 640px`, `md: 768px`, `lg: 1024px`, `xl: 1280px`, `2xl: 1536px`

#### Scenario: Custom border radius and shadow utilities exist
- **WHEN** Tailwind generates utilities
- **THEN** `rounded-md`, `rounded-xl`, `shadow-md`, `shadow-xl` resolve to project-defined values

---

### Requirement: darkMode set to 'class'
`tailwind.config.js` SHALL set `darkMode: 'class'`. Dark mode SHALL be toggled by adding or removing the `dark` class on the `<html>` element, NOT by `prefers-color-scheme` media query.

#### Scenario: Dark mode activates only via class
- **WHEN** the `dark` class is absent from `<html>` regardless of OS preference
- **THEN** light mode tokens are active

#### Scenario: Dark mode activates with class
- **WHEN** the `dark` class is added to `<html>`
- **THEN** dark mode tokens from `.dark` override `:root` variables

---

### Requirement: tailwind.config.js SHALL register the tailwindcss-animate plugin
`tailwind.config.js` SHALL include `require('tailwindcss-animate')` in its `plugins` array. This enables animation utility classes for use in Design System primitives (Change 27 and beyond).

#### Scenario: Animation utilities are available after build
- **WHEN** `npm run build` runs and Tailwind resolves `tailwind.config.js`
- **THEN** the resolved Tailwind configuration includes the `tailwindcss-animate` plugin and animation utilities such as `animate-in` and `fade-in` are available

---

### Requirement: package.json devDependencies SHALL declare tailwindcss-animate
`frontend/package.json` SHALL list `tailwindcss-animate` under `devDependencies`. It SHALL NOT be listed under runtime `dependencies`.

#### Scenario: tailwindcss-animate is a dev-only dependency
- **WHEN** `frontend/package.json` is read
- **THEN** `tailwindcss-animate` appears in `devDependencies` and NOT in `dependencies`

---

## MODIFIED Requirements (Change 24 — `ui-ux-design-system`)

### Requirement: `tailwind.config.js` SHALL extend the `ring` color token with a `focus` sub-token

`tailwind.config.js` SHALL add `ring.focus` under `theme.extend.colors` mapped to `var(--color-ring-focus)`. This token SHALL be used for focus-ring styling on interactive elements (buttons, inputs) to ensure keyboard navigation is visually distinct from the existing `ring` token.

#### Scenario: Focus-ring color utility class is generated
- **WHEN** `tailwindcss` processes `tailwind.config.js` after Change 24 additions
- **THEN** utility class `ring-focus` (or `outline-focus` equivalent) is available and resolves to the `--color-ring-focus` CSS variable

### Requirement: `src/app/styles/index.css` SHALL define `--color-ring-focus` CSS variable under `:root` and `.dark`

`src/app/styles/index.css` SHALL define `--color-ring-focus` under `:root` (brand-derived focus tint, e.g. brand primary at 400–500 level with sufficient contrast on white) and under `.dark` (adjusted brand tint at 300 level for dark background contrast). This variable SHALL be present alongside all existing `--color-*` semantic variables defined in Change 05.

#### Scenario: Focus-ring token resolves in light mode
- **WHEN** `<html>` does not have `dark` class
- **THEN** `--color-ring-focus` resolves from `:root` and is visually distinct against `--color-background`

#### Scenario: Focus-ring token resolves in dark mode
- **WHEN** `dark` class is on `<html>`
- **THEN** `--color-ring-focus` resolves from `.dark` and is visually distinct against the dark `--color-background`

---

## ADDED Requirements (Change 24 — `ui-ux-design-system`)

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
