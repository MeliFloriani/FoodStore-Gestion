## ADDED Requirements

### Requirement: Frontend Docker image with multi-stage build
The system SHALL provide a Dockerfile for the frontend that builds static assets and serves them with Nginx.

#### Scenario: Build stage compiles frontend assets
- **WHEN** the Docker build executes the build stage
- **THEN** `npm ci` installs exact dependencies from `package-lock.json`
- **AND** `npm run build` produces optimized static assets in a `dist/` directory
- **AND** the build stage base image is `node:20-alpine`

#### Scenario: VITE_API_BASE_URL passed as Docker build argument
- **WHEN** the Docker build runs for production
- **THEN** `ARG VITE_API_BASE_URL` is declared before the build command
- **AND** `ENV VITE_API_BASE_URL=$VITE_API_BASE_URL` makes it available during `npm run build`
- **AND** Vite embeds the production API URL into the compiled assets

#### Scenario: Production stage uses Nginx Alpine
- **WHEN** the Docker build executes the production stage
- **THEN** the base image is `nginx:alpine`
- **AND** the `dist/` directory from the build stage is copied to `/usr/share/nginx/html`
- **AND** a custom `nginx.conf` is included in the image

### Requirement: Nginx configured for SPA and compression
The Nginx configuration SHALL support Single Page Application fallback routing and asset compression.

#### Scenario: SPA fallback routing works
- **WHEN** a request is made to a path that does not match a static file
- **THEN** Nginx serves `index.html` (SPA fallback) instead of returning 404

#### Scenario: Static assets are compressed
- **WHEN** a browser requests a JS, CSS, or SVG file
- **THEN** Nginx serves it with Brotli or gzip compression
- **AND** assets with content hashes in filename are cached with `max-age=31536000`

### Requirement: Frontend image exposes port 80
The Docker image SHALL listen on port 80 for HTTP traffic.

#### Scenario: Container listens on port 80
- **WHEN** the container runs
- **THEN** Nginx binds to port 80
- **AND** the container exposes port 80 via Dockerfile EXPOSE directive
