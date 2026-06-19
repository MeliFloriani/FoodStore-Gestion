# frontend-design-system-mobile-first-layout Specification

## Purpose
Define the normative mobile-first layout policy for the Food Store frontend: breakpoint contract, container width conventions, grid utilities, touch target minimums, and the per-page compliance checklist that every page MUST satisfy before archiving any change. Introduced in Change 24 (ui-ux-design-system). Does not refactor existing pages — establishes policy only.

---

## ADDED Requirements

### Requirement: All pages SHALL be authored mobile-first

All new and existing frontend pages SHALL use Tailwind's mobile-first (no prefix = mobile) approach: default styles target the smallest viewport (375px); responsive prefixes (`sm:`, `md:`, `lg:`, `xl:`, `2xl:`) progressively enhance at larger breakpoints.

#### Scenario: New page starts with mobile styles
- **WHEN** a new page component is created
- **THEN** its Tailwind classes apply sensible layout at 375px without any responsive prefix, and larger viewports are handled via `sm:` and above

#### Scenario: No horizontal overflow on 375px
- **WHEN** any page is rendered at a 375px viewport width
- **THEN** there is no horizontal scrollbar (no element overflows beyond viewport width)

---

### Requirement: The breakpoint scale SHALL follow the Change 05 `theme.screens` definition without additional custom breakpoints

The breakpoint scale SHALL use the values defined in Change 05 `tailwind.config.js` and SHALL NOT be extended with custom breakpoints without updating this spec:
- Default (no prefix): < 640px — mobile phones
- `sm:` ≥ 640px — large phones / small tablets
- `md:` ≥ 768px — tablets
- `lg:` ≥ 1024px — laptops
- `xl:` ≥ 1280px — desktops
- `2xl:` ≥ 1536px — large desktops

#### Scenario: Breakpoints match config
- **WHEN** `tailwind.config.js` is inspected
- **THEN** `theme.screens` defines exactly `sm: 640px`, `md: 768px`, `lg: 1024px`, `xl: 1280px`, `2xl: 1536px`

---

### Requirement: `PageContainer` SHALL provide the standard page-width wrapper

The system SHALL provide `frontend/src/shared/ui/layout/PageContainer.tsx` rendering:
```
<div className="mx-auto w-full max-w-screen-xl px-4 sm:px-6 lg:px-8">
  {children}
</div>
```
All main content pages SHALL use `PageContainer` (or apply equivalent classes directly) as their outermost content wrapper.

#### Scenario: PageContainer constrains content width
- **WHEN** `<PageContainer>` renders on a 1440px viewport
- **THEN** the content is constrained to `max-w-screen-xl` (1280px) and centered with `mx-auto`

#### Scenario: PageContainer applies horizontal padding on mobile
- **WHEN** `<PageContainer>` renders at 375px viewport
- **THEN** the content has `px-4` horizontal padding (no edge-to-edge content)

---

### Requirement: Catalog and list grids SHALL use the standard responsive grid

All multi-item grid layouts (product catalog, user list, metrics KPI grid) SHALL use a responsive grid:
- Single column by default (mobile)
- 2 columns at `sm:`
- 3–4 columns at `lg:` and `xl:` respectively

Standard catalog grid class pattern: `grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4`

#### Scenario: Catalog grid renders single column at 375px
- **WHEN** the catalog page renders at 375px viewport
- **THEN** product cards stack in a single column

#### Scenario: Catalog grid renders 3 columns at 1024px
- **WHEN** the catalog page renders at 1024px viewport
- **THEN** product cards display in 3 columns

---

### Requirement: All interactive elements SHALL meet the 44×44px touch target minimum

Per WCAG 2.5.5 and Apple HIG, every button, link, and interactive control SHALL have an effective tap area of at least 44×44px when rendered on mobile. This is achieved via minimum padding, not fixed dimensions.

Specific conventions:
- Text buttons: `min-h-[44px]` with sufficient horizontal padding (`px-4` minimum)
- Icon-only buttons: `p-3` minimum (creates ~48px effective area including border)
- Form inputs: `h-11` (44px) minimum height
- List item rows that are clickable: `min-h-[44px] flex items-center`

#### Scenario: Primary CTA button meets touch target
- **WHEN** any primary action button renders on a 375px viewport
- **THEN** its computed height is ≥ 44px

#### Scenario: Form inputs meet touch target
- **WHEN** any form text input renders
- **THEN** its height class resolves to ≥ 44px (e.g., `h-11`)

---

### Requirement: Non-responsive tables SHALL use horizontal scroll wrappers on mobile

Any table or wide panel that cannot reflow to a single column at mobile viewports SHALL be wrapped in `<div className="overflow-x-auto">` to enable horizontal scrolling without page overflow.

#### Scenario: Wide table is scrollable on mobile
- **WHEN** an admin orders table renders at 375px viewport
- **THEN** the table is horizontally scrollable within a container, and the page itself has no horizontal scroll

---

### Requirement: Every page SHALL pass the mobile-first compliance checklist before its change is archived

The following checklist items are normative for every page. Compliance MUST be verified before a change is archived:

1. Renders without horizontal overflow at 375px viewport width
2. All interactive elements meet 44×44px touch target
3. Text is legible at mobile viewport without zoom (minimum 14px, `text-sm`)
4. Images and cards reflow correctly across all breakpoints
5. Non-responsive tables/panels use `overflow-x-auto` wrapper
6. Loading states use skeleton primitives (`<SkeletonList>`, `<SkeletonRect>`, etc.) — not null or blank
7. Empty states use `<EmptyState>` with title and description
8. Destructive actions use `useConfirm` — not `window.confirm`
9. Success/error mutation feedback uses `useToast` — not inline alert divs

#### Scenario: New page passes all checklist items
- **GIVEN** a new page is implemented and about to be archived
- **WHEN** the mobile-first checklist is applied at 375px viewport
- **THEN** all 9 checklist items pass
