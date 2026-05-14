# frontend-build-tooling Specification

## Purpose
Define and enforce the build-system configuration for the Food Store frontend: FSD-layer path aliases in both Vite and TypeScript, additional strict TypeScript compiler flags (`noUncheckedIndexedAccess`, `exactOptionalPropertyTypes`), ESLint FSD boundary rules that prevent upward or cross-layer imports, and a centralized environment-variable accessor (`src/shared/lib/env.ts`). Together these constraints keep the codebase type-safe, alias-consistent, and architecturally honest at build time.

## Requirements

### Requirement: FSD layer path aliases in Vite and TypeScript
The build system SHALL expose named path aliases for every FSD layer so that imports are layer-semantic and not relative-path-fragile. Aliases SHALL resolve under both Vite (runtime) and TypeScript (type-checking).

Required aliases:
- `@/` → `src/`
- `@/app` → `src/app/`
- `@/pages` → `src/pages/`
- `@/widgets` → `src/widgets/`
- `@/features` → `src/features/`
- `@/entities` → `src/entities/`
- `@/shared` → `src/shared/`

#### Scenario: Import resolves via layer alias
- **WHEN** a file in `src/pages/` imports `@/shared/api/http`
- **THEN** TypeScript resolves the path without error and Vite bundles the module correctly

#### Scenario: TypeScript type-check passes with layer aliases
- **WHEN** `tsc --noEmit` is executed from `frontend/`
- **THEN** exit code is 0 and no alias-related errors are reported

---

### Requirement: Additional TypeScript strict flags
The `tsconfig.app.json` SHALL enable `noUncheckedIndexedAccess: true` and `exactOptionalPropertyTypes: true` in addition to the existing `strict: true`. All source files in `src/` SHALL compile without errors under these flags.

#### Scenario: Array index access requires null guard
- **WHEN** code accesses `array[0]` without a null/undefined guard
- **THEN** TypeScript reports a type error (value is `T | undefined`)

#### Scenario: Optional property exactness enforced
- **WHEN** code assigns `undefined` to a property declared as `x?: string` (which under exactOptionalPropertyTypes means the property may be absent, not explicitly `undefined`)
- **THEN** TypeScript reports a type error

#### Scenario: Full strict compilation passes
- **WHEN** `tsc --noEmit` is run against all files in `src/`
- **THEN** exit code is 0

---

### Requirement: ESLint FSD boundary rule enforcement
ESLint SHALL be configured to prohibit imports that violate FSD layer direction. The `shared` layer SHALL NOT import from `entities`, `features`, `widgets`, `pages`, or `app`. Each layer SHALL only import from layers below it.

Layer order (top = depends on bottom):
`app` → `pages` → `widgets` → `features` → `entities` → `shared`

#### Scenario: ESLint catches upward import from shared
- **WHEN** a file in `src/shared/` contains an import from `src/entities/`
- **THEN** ESLint reports a boundary violation error

#### Scenario: ESLint catches cross-layer import (features → pages)
- **WHEN** a file in `src/features/` contains an import from `src/pages/`
- **THEN** ESLint reports a boundary violation error

#### Scenario: ESLint allows downward import
- **WHEN** a file in `src/features/` imports from `src/entities/`
- **THEN** ESLint reports no boundary violations

#### Scenario: ESLint passes on all scaffold files
- **WHEN** `npm run lint` is executed
- **THEN** exit code is 0 on all infrastructure files created in this change

---

### Requirement: Environment access SHALL be centralized in src/shared/lib/env.ts
`src/shared/lib/env.ts` SHALL be the single typed source of truth for all VITE_* environment variable access. No other env module SHALL exist under `src/shared/`. The `src/shared/config/` directory SHALL NOT be created.

#### Scenario: All modules import env from shared/lib/env
- **WHEN** any module (e.g., `http.ts`, `QueryProvider`, router) needs an environment variable
- **THEN** it imports exclusively from `@/shared/lib/env` — no other module under `src/shared/` provides env access

#### Scenario: env.ts exports VITE_API_BASE_URL
- **WHEN** `env.ts` is imported
- **THEN** it exports `VITE_API_BASE_URL` (the canonical API base URL variable) and `VITE_MERCADOPAGO_PUBLIC_KEY` with runtime validation
