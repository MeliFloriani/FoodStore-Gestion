# frontend-design-system-empty-state Specification

## Purpose
Define the empty-state UI primitive for the Food Store frontend: a single `<EmptyState>` component with a consistent layout for no-data, empty-cart, no-results, and similar states across all features. Introduced in Change 24 (ui-ux-design-system). Lives in `shared/ui/empty-state/` per FSD.

---

## ADDED Requirements

### Requirement: `shared/ui/empty-state/` SHALL provide an `<EmptyState>` component

The system SHALL provide an empty-state module at `frontend/src/shared/ui/empty-state/` containing:
- `EmptyState.tsx` — the component
- `index.ts` — barrel exporting `EmptyState`

#### Scenario: EmptyState imports without error
- **WHEN** `import { EmptyState } from '@/shared/ui/empty-state'` is used
- **THEN** the import resolves without TypeScript or bundler error

---

### Requirement: `EmptyState` SHALL accept `icon`, `title`, `description`, `action`, and `className` props

The `EmptyState` component SHALL define the following props interface:
```typescript
interface EmptyStateProps {
  icon?: ReactNode;       // SVG icon or emoji — optional
  title: string;          // Primary message — required
  description?: string;   // Secondary message — optional
  action?: ReactNode;     // CTA button or link — optional
  className?: string;     // Additional Tailwind classes for the wrapper
}
```

#### Scenario: Renders with only required prop
- **WHEN** `<EmptyState title="Sin resultados" />` renders
- **THEN** the component renders the title text without error; icon, description, and action are absent

#### Scenario: Renders with all props
- **WHEN** `<EmptyState icon={<SearchIcon />} title="Sin resultados" description="Intenta con otro término." action={<button>Limpiar</button>} />` renders
- **THEN** all four elements are visible in the DOM

---

### Requirement: `EmptyState` layout SHALL be a centered flex column

The outer wrapper SHALL use `flex flex-col items-center justify-center text-center gap-3` (or equivalent centered layout). Content SHALL be horizontally centered.

#### Scenario: Content is centered
- **WHEN** `<EmptyState title="Vacío" />` renders
- **THEN** the title is centered horizontally within its container

---

### Requirement: Icon SHALL render at 48×48 with `text-muted-foreground` color

When `icon` is provided, it SHALL be wrapped in a container of `h-12 w-12` (48px) and inherit `text-muted-foreground` color class. The icon itself should be an SVG that fills the container.

#### Scenario: Icon renders with muted color
- **WHEN** `<EmptyState icon={<CartIcon className="h-full w-full" />} title="Carrito vacío" />` renders
- **THEN** the icon wrapper has `text-muted-foreground` and dimensions `h-12 w-12`

---

### Requirement: Title SHALL use `text-lg font-semibold` typography

The `title` text SHALL be rendered as a `<p>` or `<h3>` element with `text-lg font-semibold text-foreground` classes.

#### Scenario: Title uses correct typography
- **WHEN** `<EmptyState title="Sin pedidos" />` renders
- **THEN** the title element has classes `text-lg font-semibold`

---

### Requirement: Description SHALL use `text-sm text-muted-foreground` typography

When `description` is provided, it SHALL be rendered with `text-sm text-muted-foreground` classes below the title.

#### Scenario: Description renders with muted style
- **WHEN** `<EmptyState title="Sin pedidos" description="No realizaste ningún pedido." />` renders
- **THEN** the description element has classes `text-sm text-muted-foreground`

---

### Requirement: `action` SHALL render below the description

When `action` is provided, it SHALL be rendered as a child below the description (or below the title if description is absent).

#### Scenario: Action appears below description
- **WHEN** `<EmptyState title="Carrito vacío" description="Agrega productos." action={<Link to="/catalog">Ver catálogo</Link>} />` renders
- **THEN** the action element appears in the DOM after the description

---

### Requirement: Empty-state usage convention for feature pages

All feature pages and widgets SHALL use `<EmptyState>` when their data list is empty (zero items from the API or zero items matching a filter). Ad-hoc empty-state copy (e.g., `<p>No hay resultados</p>`) SHALL be replaced with `<EmptyState>` during the progressive rollout in Sprint 8.

Standard empty-state messages SHALL be:

| Context | title | description |
|---|---|---|
| Empty cart | "Tu carrito está vacío" | "Agrega productos para continuar." |
| No orders (CLIENT) | "Sin pedidos" | "Aún no realizaste ningún pedido." |
| No addresses | "Sin direcciones guardadas" | "Agrega una dirección para el envío." |
| No search results | "Sin resultados" | `'No encontramos productos para "{query}".'` |
| No users (admin) | "Sin usuarios" | "No hay usuarios registrados." |
| No metrics data | "Sin datos para el período" | "Ajusta el rango de fechas para ver métricas." |

#### Scenario: Empty cart shows EmptyState
- **GIVEN** the cart store has zero items
- **WHEN** the cart page or panel renders
- **THEN** `<EmptyState title="Tu carrito está vacío" />` is visible
