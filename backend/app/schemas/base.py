"""
Shared Pydantic schemas for pagination and RFC 7807 error responses.

Design decisions:
- D-08: ProblemDetail uses extra="allow" ConfigDict to support RFC 7807 extensions.
  The errors extension (for validation failures) is a list of dicts, NOT one response
  per field error. One response with all errors (P-03).
- Page is generic over T to work with any response model.
"""

from __future__ import annotations

import math
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict

T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    """Generic paginated response envelope."""

    items: list[T]
    total: int
    page: int
    size: int
    pages: int


def create_pagination_meta(total: int, page: int, size: int) -> dict[str, int]:
    """Calculate pagination metadata.

    Args:
        total: Total number of items across all pages.
        page: Current page number (1-based).
        size: Number of items per page.

    Returns:
        Dict with keys: total, page, size, pages.
        pages=0 when size=0 (explicit edge case handling).
    """
    pages = math.ceil(total / size) if size > 0 else 0
    return {"total": total, "page": page, "size": size, "pages": pages}


class ProblemDetail(BaseModel):
    """RFC 7807 Problem Details for HTTP APIs.

    Fields:
    - type: URI reference identifying the problem type. Use "about:blank" as default.
    - title: Short, human-readable summary of the problem type.
    - status: HTTP status code.
    - detail: Human-readable explanation specific to this occurrence.
    - instance: URI reference identifying the specific occurrence (e.g. request path).
    - code: Optional machine-readable error code for programmatic handling.
    - errors: Extension for validation errors (D-08). A list of field error dicts,
              NOT one ProblemDetail per error — the entire validation failure is
              a single response with an errors=[...] extension array.

    extra="allow" permits arbitrary RFC 7807 extensions beyond the standard fields.
    """

    model_config = ConfigDict(extra="allow")

    type: str
    title: str
    status: int
    detail: str
    instance: str
    code: str | None = None
    errors: list[dict] | None = None
