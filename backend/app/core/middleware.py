"""
HTTP middleware for the Food Store API.

Canonical location: app/core/middleware.py (not app/api/middleware.py).

Design decisions:
- D-16 / P-04: RequestIDMiddleware imports set_request_id and request_id_ctx from
  app.core.context — the single source of truth for the ContextVar.
  The structlog processor (app/core/logging.py) also imports from app.core.context.
  There is ONE ContextVar for request_id, defined once, imported everywhere.
- 11.3: The Token returned by set_request_id is reset in a try/finally block to
  prevent ContextVar leaks across requests when the event loop reuses a context.
"""

from __future__ import annotations

import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.context import request_id_ctx, set_request_id


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Middleware that assigns a unique request ID to every HTTP request.

    Behavior:
    1. Read X-Request-ID from incoming headers (propagate if client provides one).
    2. If absent, generate a new UUID v4.
    3. Write the request_id into the ContextVar (single source of truth, P-04).
    4. Process the request.
    5. Inject X-Request-ID into the response headers.
    6. Reset the ContextVar token in finally to prevent leaks between requests.
    """

    async def dispatch(self, request: Request, call_next: object) -> Response:
        # 1. Propagate or generate request_id
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())

        # 2. Write to ContextVar; keep token for reset (11.3)
        token = set_request_id(request_id)
        try:
            # 3. Process the request
            response: Response = await call_next(request)  # type: ignore[operator]
            # 4. Inject request_id into response header
            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            # 5. Reset ContextVar to prevent leaks if event loop reuses the context
            request_id_ctx.reset(token)
