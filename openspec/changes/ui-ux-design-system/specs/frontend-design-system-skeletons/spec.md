# frontend-design-system-skeletons Specification

## Purpose
Define the skeleton loader primitive library for the Food Store frontend: composable shape primitives and compound patterns that replace ad-hoc loading states across all feature pages. Introduced in Change 24 (ui-ux-design-system). Lives in `shared/ui/skeleton/` per FSD.

---

## ADDED Requirements

### Requirement: `shared/ui/skeleton/` SHALL provide composable shape primitives

The system SHALL provide the following components at `frontend/src/shared/ui/skeleton/`:
- `SkeletonLine.tsx` — single text-line placeholder
- `SkeletonCircle.tsx` — circular placeholder for avatars and icons
- `SkeletonRect.tsx` — rectangular block placeholder for images and cards
- `SkeletonCard.tsx` — compound pattern combining rect + multiple lines (product card)
- `SkeletonList.tsx` — compound pattern rendering N × `SkeletonCard`
- `index.ts` — barrel file exporting all public API

#### Scenario: All skeleton components import without error
- **WHEN** `import { SkeletonLine, SkeletonCircle, SkeletonRect, SkeletonCard, SkeletonList } from '@/shared/ui/skeleton'` is used
- **THEN** all imports resolve without TypeScript or bundler error

---

### Requirement: Skeleton primitives SHALL use `animate-pulse` and `bg-muted` token

All skeleton components SHALL apply `animate-pulse` (from `tailwindcss-animate`) and `bg-muted` (semantic Tailwind token) as their base visual treatment. They SHALL NOT use hard-coded hex colors.

#### Scenario: Skeleton uses semantic color token
- **WHEN** `<SkeletonLine />` renders in the DOM
- **THEN** the element has a class that maps to the `muted` semantic color token (light and dark mode compatible)

#### Scenario: Skeleton has pulse animation
- **WHEN** any skeleton component renders
- **THEN** the element includes `animate-pulse` class

---

### Requirement: `SkeletonLine` SHALL accept a `width` prop

`SkeletonLine` SHALL accept a `width` prop (Tailwind width class string, default `w-full`) and a `className` prop for additional customization. Height SHALL default to `h-4` (representing one line of text).

#### Scenario: Width prop controls line width
- **WHEN** `<SkeletonLine width="w-3/4" />` renders
- **THEN** the element has class `w-3/4`

#### Scenario: Default width is full
- **WHEN** `<SkeletonLine />` renders without props
- **THEN** the element has class `w-full`

---

### Requirement: `SkeletonCircle` SHALL accept a `size` prop

`SkeletonCircle` SHALL accept a `size` prop (Tailwind `h-X w-X` combined class string, default `h-10 w-10`) and `className`. Border-radius SHALL be `rounded-full`.

#### Scenario: Circle renders with correct size and shape
- **WHEN** `<SkeletonCircle size="h-12 w-12" />` renders
- **THEN** the element has classes `h-12 w-12 rounded-full`

---

### Requirement: `SkeletonRect` SHALL accept `width` and `height` props

`SkeletonRect` SHALL accept `width` (default `w-full`), `height` (default `h-24`), and `className`. Border-radius SHALL be `rounded-md`.

#### Scenario: Rect renders with correct dimensions
- **WHEN** `<SkeletonRect width="w-full" height="h-48" />` renders
- **THEN** the element has classes `w-full h-48 rounded-md`

---

### Requirement: `SkeletonCard` SHALL compose rect and lines to match product card layout

`SkeletonCard` SHALL render:
1. `<SkeletonRect height="h-48" />` — image area
2. `<SkeletonLine width="w-3/4" />` — title line
3. `<SkeletonLine width="w-1/2" />` — price line
4. `<SkeletonLine width="w-full" />` — description line

The layout SHALL match the visual footprint of the product card used in the public catalog.

#### Scenario: SkeletonCard renders four skeleton elements
- **WHEN** `<SkeletonCard />` renders
- **THEN** four child elements are rendered: one rect and three lines

---

### Requirement: `SkeletonList` SHALL render N `SkeletonCard` rows

`SkeletonList` SHALL accept a `rows` prop (number, default 4) and render that many `<SkeletonCard>` elements in a grid-compatible wrapper with `gap-4`. The wrapper class SHALL be compatible with the catalog grid (`grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3`).

#### Scenario: SkeletonList renders correct number of cards
- **WHEN** `<SkeletonList rows={6} />` renders
- **THEN** exactly 6 `SkeletonCard` elements are present in the DOM

#### Scenario: Default rows is 4
- **WHEN** `<SkeletonList />` renders without props
- **THEN** exactly 4 `SkeletonCard` elements are present

---

### Requirement: Skeleton usage convention for TanStack Query `isPending`

All feature components using TanStack Query hooks SHALL render the appropriate skeleton when the hook's `isPending` flag is `true` instead of returning `null`, `undefined`, or a spinner. This is a normative convention enforced at code review.

#### Scenario: Catalog renders skeleton while loading
- **WHEN** `useCatalog()` returns `isPending: true`
- **THEN** the page renders `<SkeletonList rows={8} />` instead of an empty state or null

#### Scenario: Detail page renders skeleton while loading
- **WHEN** a detail query returns `isPending: true`
- **THEN** the page renders an appropriate skeleton layout instead of a spinner
