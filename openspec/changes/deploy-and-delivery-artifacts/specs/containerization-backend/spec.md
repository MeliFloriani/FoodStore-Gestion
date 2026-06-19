## ADDED Requirements

### Requirement: Backend Docker image
The system SHALL provide a Dockerfile for the backend that produces a production-ready image using multi-stage build.

#### Scenario: Multi-stage build produces slim image
- **WHEN** the Docker build runs
- **THEN** the final image uses `python:3.11-slim` as base
- **AND** build artifacts (pip cache, build dependencies) are excluded from the final stage
- **AND** the image size SHALL be under 500MB

#### Scenario: Dependencies installed from requirements.txt
- **WHEN** the Docker build executes the install stage
- **THEN** `pip install --no-cache-dir -r requirements.txt` is executed
- **AND** only runtime dependencies are installed (no dev/test dependencies)

### Requirement: Backend entrypoint and health check
The Docker image SHALL expose the FastAPI application via Uvicorn with a health check endpoint.

#### Scenario: Container starts uvicorn
- **WHEN** the container runs
- **THEN** `uvicorn app.main:app --host 0.0.0.0 --port 8000` is executed
- **AND** the container listens on port 8000

#### Scenario: Health check is configured
- **WHEN** the container is running
- **THEN** `GET /health` returns HTTP 200
- **AND** Docker HEALTHCHECK uses `python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"` with 30s interval and 3 retries
- **AND** no external dependency (curl/wget) is required for the health check

### Requirement: Environment variables passed at runtime
The Docker image SHALL accept configuration via environment variables at container runtime.

#### Scenario: Production env vars override defaults
- **WHEN** the container runs with `ENVIRONMENT=production` and a `DATABASE_URL` variable
- **THEN** the backend connects to the database specified in `DATABASE_URL`
- **AND** CORS origins are set from `BACKEND_CORS_ORIGINS`
- **AND** JWT secrets and MP credentials are read from env vars
