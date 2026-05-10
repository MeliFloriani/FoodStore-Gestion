# monorepo-workspace Specification

## Purpose
TBD - created by archiving change bootstrap-monorepo-structure. Update Purpose after archive.
## Requirements
### Requirement: Monorepo raíz ejecutable
El repositorio SHALL contener una estructura raíz con dos workspaces independientes (`backend/` y `frontend/`) sin tooling de monorepo especial (no turborepo, no nx). La raíz SHALL incluir archivos de convención compartidos.

#### Scenario: Desarrollador clona y obtiene estructura completa
- **WHEN** un desarrollador clona el repositorio
- **THEN** existe la carpeta `backend/` con estructura de capas Python
- **THEN** existe la carpeta `frontend/` con estructura FSD
- **THEN** existe `README.md` raíz con instrucciones de bootstrap

#### Scenario: Archivos de convención presentes en raíz
- **WHEN** se inspecciona la raíz del repositorio
- **THEN** existe `.gitignore` que excluye `.env`, `__pycache__`, `node_modules`, `.venv`, `dist/`
- **THEN** existe `.editorconfig` con indent_style=space, indent_size=4 (backend) y 2 (frontend)
- **THEN** existe `.nvmrc` con valor `20`
- **THEN** existe `.python-version` con valor `3.11`

### Requirement: Variables de entorno gestionadas de forma segura
El repositorio SHALL contener `.env.example` en cada workspace con todas las variables requeridas y valores placeholder. El archivo `.env` SHALL estar incluido en `.gitignore` y nunca versionado.

#### Scenario: .env no llega al repositorio
- **WHEN** un desarrollador crea un archivo `.env` en `backend/` o `frontend/`
- **THEN** git no lo incluye en `git status` como untracked (está excluido)

#### Scenario: .env.example documenta variables requeridas
- **WHEN** un desarrollador revisa `backend/.env.example`
- **THEN** encuentra todas las variables de entorno que la aplicación necesita con valores placeholder
- **WHEN** un desarrollador revisa `frontend/.env.example`
- **THEN** encuentra todas las variables `VITE_*` requeridas con valores placeholder

### Requirement: Versiones de runtime pinneadas
El repositorio SHALL pinear la versión de Python (`.python-version`) y Node (`.nvmrc`) para garantizar reproducibilidad entre entornos.

#### Scenario: pyenv detecta la versión de Python
- **WHEN** pyenv está instalado y el desarrollador ejecuta `pyenv install` en la raíz
- **THEN** se instala Python 3.11.x según `.python-version`

#### Scenario: nvm detecta la versión de Node
- **WHEN** nvm está instalado y el desarrollador ejecuta `nvm use` en la raíz
- **THEN** se activa Node 20.x según `.nvmrc`

### Requirement: Conventional Commits documentado
El repositorio SHALL documentar la convención Conventional Commits en el `README.md` para que todos los commits del proyecto sigan el estándar desde el inicio (criterio CE-01).

#### Scenario: README contiene referencia a Conventional Commits
- **WHEN** se lee el `README.md` raíz
- **THEN** existe una sección que describe el formato de Conventional Commits con ejemplos (`feat:`, `fix:`, `chore:`, `docs:`)

