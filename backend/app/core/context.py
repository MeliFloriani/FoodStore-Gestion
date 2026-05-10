"""
Single source of truth for the request_id ContextVar.

Design decision P-04 / D-16:
This is the ONLY module that owns the request_id ContextVar.
Both app/core/middleware.py (RequestIDMiddleware) and
app/core/logging.py (inject_request_id processor) import from here.
Do NOT create another ContextVar for request_id anywhere else.
"""

from __future__ import annotations

from contextvars import ContextVar, Token

# The single ContextVar for request_id — default=None means "no active request"
request_id_ctx: ContextVar[str | None] = ContextVar("request_id_ctx", default=None)


def get_request_id() -> str | None:
    """Return the current request_id from context, or None if not set."""
    return request_id_ctx.get()


def set_request_id(value: str) -> Token[str | None]:
    """Set the request_id in the current context and return the reset token.

    The caller is responsible for resetting the token (via request_id_ctx.reset(token))
    in a try/finally block to prevent ContextVar leaks between requests.
    """
    return request_id_ctx.set(value)
