# frontend-scaffold Specification

## Purpose
Defines the complete scaffold requirements for the Food Store frontend workspace: FSD directory structure, all runtime and dev dependencies (including React 19, react-router-dom, TanStack Query, Zustand, Axios, and tooling additions from the core-foundation change), TypeScript strict configuration with additional exactness flags (`noUncheckedIndexedAccess`, `exactOptionalPropertyTypes`), Vite setup with FSD-layer path aliases, TailwindCSS with enterprise token theme and `darkMode: 'class'`, ESLint/Prettier baseline with FSD boundary enforcement, and the operational scripts (dev, build, test, lint). This spec is the contract that all subsequent frontend changes depend on for a consistent, fully-typed, correctly-aliased development environment.

## Requirements

### Requirement: Estructura FSD frontend inicializada
El workspace `frontend/src/` SHALL contener las 6 capas de Feature-Sliced Design: `app/`, `pages/`, `widgets/`, `features/`, `entities/`, `shared/`. Las capas vacías (sin contenido en este change) SHALL tener un archivo `.gitkeep` para que sean rastreables en git.

#### Scenario: Estructura FSD presente
- **WHEN** se inspecciona `frontend/src/`
- **THEN** existen los directorios: `app/`, `pages/`, `widgets/`, `features/`, `entities/`, `shared/`
- **THEN** los directorios sin contenido funcional contienen `.gitkeep`

### Requirement: Dependencias frontend declaradas en package.json
El workspace frontend SHALL declarar todas las dependencias core en `package.json`. Las dependencias de runtime SHALL estar en `dependencies`; las de desarrollo en `devDependencies`.

**Full updated content (post frontend-core-foundation):**

Runtime `dependencies` SHALL include:
- `react@^19`, `react-dom@^19`
- `react-router-dom@^6`
- `@tanstack/react-query@^5`
- `@tanstack/react-form@^0`
- `zustand@^4`
- `axios@^1`

DevDependencies SHALL include (additions to existing set):
- `eslint-plugin-boundaries` — for FSD layer enforcement
- `@tanstack/react-query-devtools` — development inspection of query cache
- `tailwindcss-animate` — animation utilities, included in this foundation change (D-12); registered in `tailwind.config.js#plugins`

#### Scenario: package.json contiene dependencias core ampliadas
- **WHEN** se lee `frontend/package.json`
- **THEN** `dependencies` incluye: `react@^19`, `react-dom@^19`, `react-router-dom@^6`, `@tanstack/react-query@^5`, `@tanstack/react-form@^0`, `zustand@^4`, `axios@^1`
- **THEN** `devDependencies` incluye las dependencias del scaffold original más `eslint-plugin-boundaries`, `@tanstack/react-query-devtools`, `tailwindcss-animate`

### Requirement: TypeScript configurado en modo estricto
El archivo `frontend/tsconfig.app.json` SHALL habilitar `"strict": true`, `"noEmit": true`, `"noUncheckedIndexedAccess": true`, y `"exactOptionalPropertyTypes": true`. El target SHALL ser `ES2022` o superior.

**Full updated content:**

`compilerOptions` SHALL include:
- `"strict": true`
- `"noEmit": true`
- `"target": "ES2022"`
- `"noUncheckedIndexedAccess": true`
- `"exactOptionalPropertyTypes": true`
- `"paths"` matching all FSD layer aliases from vite.config.ts

#### Scenario: tsc compila sin errores en código infrastructure
- **WHEN** se ejecuta `npx tsc --noEmit` desde `frontend/`
- **THEN** el proceso termina con exit code 0 sobre todos los archivos de este change

### Requirement: Vite configurado con React y alias de rutas
El archivo `frontend/vite.config.ts` SHALL configurar el plugin React, un alias `@/` apuntando a `src/`, **más aliases por capa FSD**, y el servidor de desarrollo en puerto 5173.

**Full updated content:**

Aliases SHALL include:
- `@/` → `src/`
- `@/app` → `src/app/`
- `@/pages` → `src/pages/`
- `@/widgets` → `src/widgets/`
- `@/features` → `src/features/`
- `@/entities` → `src/entities/`
- `@/shared` → `src/shared/`

Same aliases SHALL be declared in `tsconfig.app.json` under `compilerOptions.paths`.

#### Scenario: Servidor de desarrollo arranca en puerto correcto
- **WHEN** se ejecuta `npm run dev` desde `frontend/`
- **THEN** Vite inicia en `http://localhost:5173`
- **THEN** la página index es accesible sin errores de compilación

#### Scenario: FSD layer aliases resolve at build time
- **WHEN** Vite processes an import using `@/entities/auth/model/store`
- **THEN** the module resolves to `src/entities/auth/model/store.ts` without error

### Requirement: TailwindCSS configurado con purge sobre src
El archivo `frontend/tailwind.config.js` SHALL apuntar el `content` a `./src/**/*.{ts,tsx}` y `./index.html`, establecer `darkMode: 'class'`, y extender el tema con **tokens enterprise** (ver capability `frontend-tailwind-tokens`). El archivo `postcss.config.js` SHALL incluir Tailwind y Autoprefixer como plugins.

**Full updated content:**

`tailwind.config.js` SHALL set:
- `content: ['./index.html', './src/**/*.{ts,tsx}']`
- `darkMode: 'class'`
- `theme.extend.colors`: full two-level palette (primitive + semantic via CSS variables)
- `theme.extend.fontFamily`, `theme.extend.fontSize`, `theme.extend.borderRadius`, `theme.extend.boxShadow`
- `theme.screens`: standard breakpoints

#### Scenario: Tailwind genera estilos semánticos en build
- **WHEN** se ejecuta `npm run build` desde `frontend/`
- **THEN** el bundle generado en `dist/` incluye clases como `bg-background`, `text-foreground`, `bg-primary`

### Requirement: Linting y formateo frontend configurado y operativo
El workspace frontend SHALL tener ESLint (v9 flat config) y Prettier configurados. El script `lint` SHALL ejecutar ESLint sobre `src/` sin errores en el código del bootstrap. ESLint SHALL enforce FSD layer boundary rules via `eslint-plugin-boundaries`.

#### Scenario: ESLint pasa sin errores en código bootstrap
- **WHEN** se ejecuta `npm run lint` desde `frontend/`
- **THEN** el proceso termina con exit code 0

### Requirement: Scripts frontend operativos
El workspace frontend SHALL exponer al menos los scripts en `package.json`: `dev` (Vite dev server), `build` (Vite build), `test` (Vitest), `lint` (ESLint).

#### Scenario: Script build genera artefacto sin errores
- **WHEN** se ejecuta `npm run build` desde `frontend/`
- **THEN** el proceso termina con exit code 0 y genera la carpeta `dist/`

#### Scenario: Script test ejecuta sin errores en base vacía
- **WHEN** se ejecuta `npm run test` desde `frontend/` sin tests de negocio
- **THEN** Vitest reporta 0 tests y termina con exit code 0

### Requirement: Página index como validador de bootstrap
El archivo `frontend/src/pages/home/ui/HomePage.tsx` SHALL exportar un componente React válido con contenido mínimo (ej. texto "Food Store — bootstrap OK") sin lógica de negocio. El componente SHALL ser montado en `src/app/App.tsx`.

#### Scenario: Página index visible en navegador
- **WHEN** se navega a `http://localhost:5173` con `npm run dev` activo
- **THEN** el navegador muestra la página sin errores de consola
