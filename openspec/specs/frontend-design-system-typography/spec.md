# frontend-design-system-typography Specification

## Purpose
Define the typography utility policy and helper components for the Food Store frontend: heading hierarchy (h1–h6), body/caption variants, font-family usage rules, and the `Heading` / `Text` helper components in `shared/ui/typography/`. Introduced in Change 24 (ui-ux-design-system). Builds on the font-family tokens seeded in Change 05 (`frontend-tailwind-tokens`).

---

## ADDED Requirements

### Requirement: `shared/ui/typography/` SHALL provide `Heading` and `Text` helper components

The system SHALL provide a typography module at `frontend/src/shared/ui/typography/` containing:
- `typography.tokens.ts` — exported typed constants `HEADING_CLASSES` and `BODY_CLASSES`
- `Heading.tsx` — renders semantic heading elements (`h1`–`h6`) with canonical Tailwind classes
- `Text.tsx` — renders `<p>` or `<span>` with variant-specific Tailwind classes
- `index.ts` — barrel exporting all public API

#### Scenario: Typography components import without error
- **WHEN** `import { Heading, Text, HEADING_CLASSES, BODY_CLASSES } from '@/shared/ui/typography'` is used
- **THEN** all imports resolve without TypeScript or bundler error

---

### Requirement: `Heading` SHALL render the correct semantic element and classes per level

`Heading` SHALL accept a `level` prop (`1 | 2 | 3 | 4 | 5 | 6`) and render the corresponding HTML element (`h1`–`h6`) with the canonical typography classes as defined in `HEADING_CLASSES`.

| Level | Canonical classes |
|---|---|
| 1 | `text-4xl font-display font-bold leading-tight` |
| 2 | `text-2xl font-display font-semibold leading-snug` |
| 3 | `text-xl font-display font-semibold leading-snug` |
| 4 | `text-lg font-sans font-semibold leading-normal` |
| 5 | `text-base font-sans font-medium leading-normal` |
| 6 | `text-sm font-sans font-medium leading-normal` |

`Heading` SHALL also accept `className` (merged into canonical classes) and forward other HTML heading props.

#### Scenario: `<Heading level={1}>` renders as h1 with correct classes
- **WHEN** `<Heading level={1}>Catálogo</Heading>` renders
- **THEN** the DOM element is `<h1>` with class including `text-4xl font-display font-bold leading-tight`

#### Scenario: `<Heading level={3}>` renders as h3 with correct classes
- **WHEN** `<Heading level={3}>Sección</Heading>` renders
- **THEN** the DOM element is `<h3>` with class including `text-xl font-display font-semibold leading-snug`

---

### Requirement: `Text` SHALL render correct classes per variant

`Text` SHALL accept a `variant` prop (`'body' | 'body-sm' | 'caption' | 'label' | 'code'`) and render the corresponding element with canonical classes.

| Variant | Element | Canonical classes |
|---|---|---|
| `body` | `<p>` | `text-base font-sans leading-relaxed` |
| `body-sm` | `<p>` | `text-sm font-sans leading-relaxed` |
| `caption` | `<span>` | `text-xs font-sans text-muted-foreground` |
| `label` | `<span>` | `text-sm font-sans font-medium` |
| `code` | `<code>` | `font-mono text-sm` |

`Text` SHALL also accept `as` prop to override the element type, `className`, and forward other HTML props.

#### Scenario: `<Text variant="caption">` renders as span with muted color
- **WHEN** `<Text variant="caption">2026-06-03</Text>` renders
- **THEN** the element has class `text-xs font-sans text-muted-foreground`

#### Scenario: `<Text variant="label">` renders as span with medium weight
- **WHEN** `<Text variant="label">Precio</Text>` renders
- **THEN** the element has class `text-sm font-sans font-medium`

---

### Requirement: `font-display` SHALL be used exclusively for headings h1–h3

The `font-display` Tailwind class (defined in Change 05 as a display font stack) SHALL be applied only to heading levels 1, 2, and 3. Levels 4–6 and all body text SHALL use `font-sans`. This is a normative coding convention.

#### Scenario: Page titles use font-display
- **WHEN** a page title is rendered using `<Heading level={1}>`
- **THEN** the heading has `font-display` applied

#### Scenario: Body text does not use font-display
- **WHEN** any body paragraph or label is rendered
- **THEN** `font-display` is absent from the element's classes

---

### Requirement: Minimum font size on mobile SHALL be 14px (text-sm)

No text visible on a 375px mobile viewport SHALL be smaller than `text-sm` (14px). The `caption` variant (`text-xs`, 12px) MAY be used for supplementary metadata not critical to usability.

#### Scenario: Body text meets minimum size
- **WHEN** body text renders on a 375px viewport
- **THEN** the computed font size is at least 14px

---

### Requirement: WCAG AA contrast SHALL be met for all text-on-background combinations

All text rendered using semantic tokens (`text-foreground`, `text-muted-foreground`, `text-primary-foreground`, `text-destructive-foreground`) on their respective background tokens SHALL meet WCAG AA contrast ratio (4.5:1 for normal text, 3:1 for large text ≥ 18px bold / 24px regular).

#### Scenario: foreground text on background meets WCAG AA
- **WHEN** `text-foreground` is used on `bg-background` in light mode
- **THEN** the contrast ratio between the resolved CSS variable values is ≥ 4.5:1

#### Scenario: muted-foreground text meets WCAG AA for large text
- **WHEN** `text-muted-foreground` is used for body-sm or caption text
- **THEN** the contrast ratio is ≥ 4.5:1 (normal text threshold applies since text-xs/text-sm are below large text threshold)
