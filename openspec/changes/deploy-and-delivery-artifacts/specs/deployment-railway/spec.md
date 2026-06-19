## ADDED Requirements

### Requirement: Backend service in Railway
The system SHALL deploy the backend as a Railway service with PostgreSQL managed database.

#### Scenario: Backend service starts from Dockerfile
- **WHEN** Railway builds and deploys the backend service
- **THEN** it uses the `Dockerfile` in the `backend/` directory
- **AND** the start command is the default CMD from the Dockerfile (uvicorn)
- **AND** the service is accessible at `https://<project>.railway.app`

#### Scenario: PostgreSQL plugin provides DATABASE_URL
- **WHEN** the Railway PostgreSQL plugin is provisioned
- **THEN** Railway injects `DATABASE_URL` as an environment variable automatically
- **AND** the backend connects to the managed PostgreSQL instance
- **AND** Alembic migrations are applied manually after deploy with `railway run alembic upgrade head`

#### Scenario: Production environment variables are configured
- **WHEN** the backend service deploys
- **THEN** the following env vars are set in Railway dashboard:
  - `ENVIRONMENT=production`
  - `BACKEND_CORS_ORIGINS=https://<frontend-domain>.railway.app`
  - `API_V1_PREFIX=/api/v1`
  - `SECRET_KEY` (random 64-char hex, production value)
  - `MP_ACCESS_TOKEN` (production access token)
  - `MP_WEBHOOK_SECRET` (webhook secret)
  - `MP_NOTIFICATION_URL=https://<backend-domain>.railway.app/api/v1/pagos/webhook`
  - `FRONTEND_BASE_URL=https://<frontend-domain>.railway.app`
  - `BCRYPT_COST=12`
  - `MP_PUBLIC_KEY` (sandbox or production public key from MercadoPago account)
- **AND** no sensitive values are hardcoded or versioned

### Requirement: Frontend service in Railway
The system SHALL deploy the frontend as a Railway service using its Dockerfile.

#### Scenario: Frontend service serves production build
- **WHEN** Railway builds and deploys the frontend service
- **THEN** it uses the `Dockerfile` in the `frontend/` directory
- **AND** the service is accessible at `https://<frontend-project>.railway.app`

#### Scenario: Frontend service connects to backend
- **WHEN** a user visits the frontend URL
- **THEN** all API requests are sent to the backend URL
- **AND** `VITE_API_BASE_URL` is set to `https://<backend-domain>.railway.app/api/v1`
- **AND** `VITE_API_BASE_URL` is configured as a **Build Variable** in Railway Dashboard (not just runtime env var) so it's available during `docker build` for Vite to embed statically

### Requirement: Seed data on first deploy
The system SHALL seed mandatory reference data (roles, order states, payment methods, admin user) after migrations on the production database.

#### Scenario: Seed runs after migration
- **WHEN** migrations complete on the Railway database
- **THEN** seed data is applied with `railway run python -m app.db.seed` (or equivalent seed command)
- **AND** the admin user `admin@foodstore.com` is available for login
- **AND** the six order states (PENDIENTE, CONFIRMADO, EN_PREP, EN_CAMINO, ENTREGADO, CANCELADO) exist
- **AND** payment methods (MERCADOPAGO, EFECTIVO, TRANSFERENCIA) are registered

### Requirement: Health check endpoint
The backend SHALL expose a health check endpoint for Railway's monitoring.

#### Scenario: Railway monitors health
- **WHEN** Railway sends a health check request
- **THEN** `GET /health` returns HTTP 200 with `{"status": "ok"}`
- **AND** Railway marks the service as healthy

### Requirement: Railway services configured via Dashboard
The system SHALL configure backend and frontend as separate services in Railway, each with its own Root Directory.

#### Scenario: Backend service configured with Root Directory
- **WHEN** the backend service is created in Railway Dashboard
- **THEN** its Root Directory is set to `backend/`
- **AND** Railway detects and uses the `Dockerfile` in that directory
- **AND** the service is accessible at `https://<backend-project>.railway.app`

#### Scenario: Frontend service configured with Root Directory
- **WHEN** the frontend service is created in Railway Dashboard
- **THEN** its Root Directory is set to `frontend/`
- **AND** Railway detects and uses the `Dockerfile` in that directory
- **AND** the service is accessible at `https://<frontend-project>.railway.app`
