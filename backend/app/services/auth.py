"""
AuthService — stateless authentication business logic.

Contains:
  - register_user: creates a new Usuario + assigns the CLIENT role.
  - login_user: validates credentials, issues JWT pair, persists refresh token hash.

Architectural rules:
  - session.commit() is NEVER called here — UnitOfWork owns the transaction.
  - All DB access goes through UnitOfWork typed repos (uow.usuarios, etc.).
  - Timing-attack prevention: verify_password is always called, even when the
    email is not found (using a pre-computed dummy hash).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import Request

from app.core.exceptions import ConflictError, UnauthorizedError
from app.core.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    verify_password,
)
from app.core.uow import UnitOfWork
from app.models.user import RefreshToken, Usuario, UsuarioRol
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse

# Pre-computed bcrypt hash used for timing-attack prevention on the
# "email not found" path — ensures bcrypt always runs, even for missing users.
# Generated with: hash_password("dummy-timing-prevention-password")
_DUMMY_HASH = "$2b$12$KIXAjkl7EYvs4j3JaWmg7OX7RFT1jCjN6jY6uaVl9b9gfXoKRpAoi"


class AuthService:
    """Stateless service for authentication operations.

    All methods are @staticmethod — no per-instance state.
    Receives UnitOfWork as a parameter for every operation.
    """

    @staticmethod
    async def register_user(uow: UnitOfWork, data: RegisterRequest) -> Usuario:
        """Register a new user and assign the CLIENT role.

        Steps:
          (a) Check email uniqueness — raises ConflictError(409) if taken.
          (b) Hash the plaintext password.
          (c) Create the Usuario record via uow.usuarios.create().
          (d) Look up the CLIENT role — raises RuntimeError if not seeded.
          (e) Create the UsuarioRol pivot record.
          (f) Return the Usuario instance (with usuario_roles loaded via selectin).

        Args:
            uow: The active UnitOfWork providing access to all repositories.
            data: Validated RegisterRequest with nombre, apellido, email, password.

        Returns:
            The newly created Usuario instance.

        Raises:
            ConflictError: If the email address is already registered.
            RuntimeError: If the CLIENT role has not been seeded.
        """
        # (a) Uniqueness check
        existing = await uow.usuarios.get_by_email(data.email)
        if existing is not None:
            raise ConflictError("Email already registered", code="email_conflict")

        # (b) Hash password
        hashed = hash_password(data.password)

        # (c) Create Usuario
        usuario = await uow.usuarios.create(
            Usuario(
                email=data.email,
                password_hash=hashed,
                nombre=data.nombre,
                apellido=data.apellido,
            )
        )

        # (d) Fetch CLIENT role — must exist (seeded in migrations)
        rol = await uow.roles.get_by_codigo("CLIENT")
        if rol is None:
            raise RuntimeError(
                "CLIENT role not seeded — run database migrations and seed data"
            )

        # (e) Create role assignment
        await uow.usuario_roles.create(
            UsuarioRol(
                usuario_id=usuario.id,
                rol_id=rol.id,
                asignado_por_id=None,
            )
        )

        return usuario

    @staticmethod
    async def login_user(
        uow: UnitOfWork,
        data: LoginRequest,
        request: Request,
    ) -> TokenResponse:
        """Validate credentials and issue a JWT access + refresh token pair.

        Timing-attack prevention:
          When the email is not found, verify_password is still called with a
          pre-computed dummy hash so the response time is indistinguishable from
          a wrong-password attempt.

        Steps:
          (a) Look up the user by email.
          (b) If not found, run dummy bcrypt verify + raise UnauthorizedError.
          (c) If found, verify the password — raise UnauthorizedError on mismatch.
          (d) Create access token (JWT, signed, 30 min).
          (e) Create refresh token (JWT, signed, 7 days) + SHA-256 digest.
          (f) Persist the RefreshToken row (hash only, never cleartext).
          (g) Return TokenResponse.

        Args:
            uow: The active UnitOfWork providing access to all repositories.
            data: Validated LoginRequest with email and password.
            request: The FastAPI Request object (available for future IP logging).

        Returns:
            A TokenResponse with access_token, refresh_token, token_type, expires_in.

        Raises:
            UnauthorizedError: For invalid credentials (wrong email or wrong password).
                               The error message is deliberately generic to prevent
                               email enumeration attacks.
        """
        from app.core.config import get_settings

        settings = get_settings()

        # (a) Look up by email
        usuario = await uow.usuarios.get_by_email(data.email)

        # (b) Email not found — run dummy verify to prevent timing attack
        if usuario is None:
            verify_password(data.password, _DUMMY_HASH)  # always runs bcrypt
            raise UnauthorizedError(
                "Invalid credentials",
                code="invalid_credentials",
            )

        # (c) Password mismatch
        if not verify_password(data.password, usuario.password_hash):
            raise UnauthorizedError(
                "Invalid credentials",
                code="invalid_credentials",
            )

        # (d) Issue access token
        access_token = create_access_token(str(usuario.id))

        # (e) Issue refresh token + digest
        cleartext_refresh, digest = create_refresh_token(str(usuario.id))

        # (f) Persist refresh token hash
        expires_at = datetime.now(timezone.utc) + timedelta(
            days=settings.REFRESH_TOKEN_EXPIRE_DAYS
        )
        await uow.refresh_tokens.insert(
            RefreshToken(
                token_hash=digest,
                usuario_id=usuario.id,
                expires_at=expires_at,
            )
        )

        # (g) Return token response
        return TokenResponse(
            access_token=access_token,
            refresh_token=cleartext_refresh,
        )
