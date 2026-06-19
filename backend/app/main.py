"""
Food Store API — application entry point.

Wires together all components:
- lifespan: startup (configure logging) + shutdown (dispose DB engine).
- CORS, RequestID, SlowAPI middlewares.
- RFC 7807 error handlers.
- API v1 router (factory pattern, prefix from settings).
- Liveness probe GET /health (no DB dependency, D-13).

Design decisions:
- D-05: settings = get_settings() called ONCE at module level to construct the app.
  Engine and session factory remain lazy (created on first request).
- D-13: GET /health (liveness) lives here in main.py, bypasses layered pattern.
  GET /api/v1/health (readiness) lives in the v1 router and uses Depends(get_session).
- D-14: app version comes from get_app_version() (importlib.metadata), not Settings.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi.middleware import SlowAPIMiddleware

from app.api.errors import register_error_handlers
from app.api.v1.router import build_v1_router
from app.core.config import get_app_version, get_settings
from app.core.logging import configure_logging
from app.core.middleware import RequestIDMiddleware
from app.core.rate_limit import get_limiter
from app.db.session import get_engine

# Obtain settings once — used both in lifespan and for middleware/router configuration.
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """FastAPI lifespan context manager.

    Startup:
    - Configure structlog with the settings from environment.

    Shutdown:
    - Dispose the async engine to cleanly close all DB connections.
      Without dispose(), workers may leave dangling connections on shutdown (D-05).
    """
    # Startup
    configure_logging(settings.LOG_LEVEL, settings.ENVIRONMENT)
    yield
    # Shutdown
    await get_engine().dispose()


# ---------------------------------------------------------------------------
# Application instance
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Food Store API",
    version=get_app_version(),
    lifespan=lifespan,
)

# --- Middlewares (registration order = execution order reversed) ---
# The LAST registered middleware is the OUTERMOST.
# CORSMiddleware must be outermost so ALL responses (including 429 from rate limiter)
# carry CORS headers. Otherwise the browser blocks error responses.

# 1. Rate limiting (innermost — runs last in the chain)
app.state.limiter = get_limiter()
app.add_middleware(SlowAPIMiddleware)

# 2. Request ID
app.add_middleware(RequestIDMiddleware)

# 3. CORS (outermost — runs first, wraps every response with CORS headers)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID"],
)

# --- Error handlers ---
register_error_handlers(app)

# --- Routers ---
app.include_router(build_v1_router(settings))


# ---------------------------------------------------------------------------
# Liveness probe — D-13 documented exception
# ---------------------------------------------------------------------------


@app.get("/health", tags=["health"], summary="Liveness probe")
def health_liveness() -> dict[str, str]:
    """Liveness probe — responds without any DB or auth dependency.

    Exception D-13: lives in main.py, bypasses layered pattern.
    This is a pure liveness check (is the process alive?), not domain logic.
    Readiness (is the DB reachable?) is at GET /api/v1/health.
    """
    return {"status": "ok"}
