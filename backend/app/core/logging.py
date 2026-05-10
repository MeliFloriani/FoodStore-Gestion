"""
Structured logging configuration using structlog.

Provides:
- configure_logging(log_level, environment): call once at startup (in lifespan).
- inject_request_id processor: adds request_id to every log entry from ContextVar.
- get_logger(name): returns a structlog logger bound to the given name.

Design decisions:
- D-16 / P-04: inject_request_id imports get_request_id from app.core.context
  (single ContextVar source — not duplicated here).
- In "development" mode, logs are human-readable via ConsoleRenderer.
- In other environments (staging, production), logs are emitted as JSON.
"""

from __future__ import annotations

from typing import Any

import structlog

from app.core.context import get_request_id


def inject_request_id(
    logger: Any,
    method_name: str,
    event_dict: dict[str, Any],
) -> dict[str, Any]:
    """Structlog processor: inject request_id into the log event dict.

    Imports get_request_id from app.core.context — the single source of truth
    for the ContextVar (P-04). Only adds the key when a request_id is active.
    """
    request_id = get_request_id()
    if request_id is not None:
        event_dict["request_id"] = request_id
    return event_dict


def configure_logging(log_level: str, environment: str) -> None:
    """Configure structlog for the application.

    Call once during application startup (in the lifespan context manager).

    Args:
        log_level: Log level string (e.g. "INFO", "DEBUG"). Passed to stdlib logging.
        environment: Current environment (e.g. "development", "production").
                     Selects ConsoleRenderer for development, JSONRenderer otherwise.
    """
    import logging

    # Configure stdlib logging to capture log records at the desired level
    logging.basicConfig(
        format="%(message)s",
        level=getattr(logging, log_level.upper(), logging.INFO),
    )

    # Choose renderer based on environment
    if environment == "development":
        renderer: Any = structlog.dev.ConsoleRenderer()
    else:
        renderer = structlog.processors.JSONRenderer()

    shared_processors: list[Any] = [
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        inject_request_id,
    ]

    structlog.configure(
        processors=shared_processors + [renderer],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, log_level.upper(), logging.INFO)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> Any:
    """Return a structlog logger bound to the given name.

    Usage:
        logger = get_logger(__name__)
        logger.info("event", key="value")
    """
    return structlog.get_logger(name)
