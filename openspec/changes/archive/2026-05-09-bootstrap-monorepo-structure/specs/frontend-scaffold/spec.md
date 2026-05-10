## ADDED Requirements

### Requirement: Estructura FSD frontend inicializada
El workspace `frontend/src/` SHALL contener las 6 capas de Feature-Sliced Design: `app/`, `pages/`, `widgets/`, `features/`, `entities/`, `shared/`. Las capas vacías (sin contenido en este change) SHALL tener un archivo `.gitkeep` para que sean rastreables en git.

#### Scenario: Estructura FSD presente
- **WHEN** se inspecciona `frontend/src/`
- **THEN** existen los directorios: `app/`, `pages/`, `widgets/`, `features/`, `entities/`, `shared/`
- **THEN** los directorios sin contenido funcional contienen `.gitkeep`

### Requirement: Dependencias frontend declaradas en package.json
El workspace frontend SHALL declarar todas las dependencias core en `package.json`. Las dependencias de runtime SHALL estar en `dependencies`; las de desarrollo en `devDependencies`.

#### Scenario: package.json contiene dependencias core
- **WHEN** se lee `frontend/package.json`
- **THEN** `dependencies` incluye: `react@^18`, `react-dom@^18`, `axios@^1`, `@tanstack/react-query@^5`, `@tanstack/react-form@^0`, `zustand@^4`
- **THEN** `devDependencies` incluye: `typescript@^5`, `vite@^5`, `@vitejs/plugin-react`, `tailwindcss@^3`, `postcss`, `autoprefixer`, `eslint`, `prettier`, `eslint-config-prettier`, `vitest`, `@testing-library/react`, `@testing-library/jest-dom`

### Requirement: TypeScript configurado en modo estricto
El archivo `frontend/tsconfig.json` SHALL habilitar `"strict": true` y `"noEmit": true`. El target SHALL ser `ES2022` o superior.

#### Scenario: tsc compila sin errores en código bootstrap
- **WHEN** se ejecuta `npx tsc --noEmit` desde `frontend/`
- **THEN** el proceso termina con exit code 0 sobre el código del bootstrap

### Requirement: Vite configurado con React y alias de rutas
El archivo `frontend/vite.config.ts` SHALL configurar el plugin React, un alias `@/` apuntando a `src/` y el servidor de desarrollo en puerto 5173.

#### Scenario: Servidor de desarrollo arranca en puerto correcto
- **WHEN** se ejecuta `npm run dev` desde `frontend/`
- **THEN** Vite inicia en `http://localhost:5173`
- **THEN** la página index es accesible sin errores de compilación

### Requirement: TailwindCSS configurado con purge sobre src
El archivo `frontend/tailwind.config.js` SHALL apuntar el `content` a `./src/**/*.{ts,tsx}` y `./index.html`. El archivo `postcss.config.js` SHALL incluir Tailwind y Autoprefixer como plugins.

#### Scenario: Tailwind genera estilos en build
- **WHEN** se ejecuta `npm run build` desde `frontend/`
- **THEN** el bundle generado en `dist/` incluye estilos de Tailwind aplicados a los componentes

### Requirement: Linting y formateo frontend configurado y operativo
El workspace frontend SHALL tener ESLint (v9 flat config) y Prettier configurados. El script `lint` SHALL ejecutar ESLint sobre `src/` sin errores en el código del bootstrap.

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
