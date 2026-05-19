"""
Reusable Pydantic field validators for the application.

Extracted from inline schema validators to enable reuse across multiple schemas
without duplicating validation rules (D-07: single source of truth for password
validation logic — Change 13).
"""

from __future__ import annotations


def validate_password(value: str) -> str:
    """Validate that a password meets minimum length requirements.

    Rule: minimum 8 characters (matches RegisterRequest.password in auth schemas).

    This function is the single source of truth for password minimum-length validation.
    Use it as the body of a @field_validator in any schema that needs password validation.

    Args:
        value: The plaintext password string to validate.

    Returns:
        The unchanged password string if valid.

    Raises:
        ValueError: If the password is shorter than 8 characters.
    """
    if len(value) < 8:
        raise ValueError("La contraseña debe tener al menos 8 caracteres")
    return value
