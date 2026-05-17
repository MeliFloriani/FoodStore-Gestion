"""
AuthService — stateless authentication business logic.

Contains:
  - register_user: creates a new Usuario + assigns the CLIENT role.
  - login_user: validates credentials, issues JWT pair, persists refresh token hash.
  - rotate_refresh: rotates a refresh token (Change 07 — auth-refresh-logout-rbac-me).
  - revoke_refresh: revokes a single refresh token for logout (Change 07).

Architectural rules:
  - session.commit() is NEVER called here — UnitOfWork owns the transaction.
  - All DB access goes through UnitOfWork typed repos (uow.usuarios, etc.).
  - Timing-attack prevention: verify_password is always called, even when the
    email is not found (using a pre-computed dummy hash).
  - rotate_refresh raises TokenReplayError (NOT UnauthorizedError) on replay —
    the router catches this and performs revoke_family in a second independent
    UoW (D-07-C Opción A). Do NOT call revoke_family inside this service.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import Request

from app.core.exceptions import ConflictError, TokenReplayError, UnauthorizedError
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
          (f) Re-query with explicit eager loading via get_with_roles() to avoid
              MissingGreenlet when the caller serializes the result with Pydantic.

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

        # (f) Re-query with explicit eager loading.
        #
        # WHY: The `usuario` object from uow.usuarios.create() is *persistent but
        # unloaded* — its `usuario_roles` collection was never fetched from the DB.
        # SQLAlchemy's lazy="selectin" fires during a SELECT-based load, not during
        # add+flush. Accessing `usuario.usuario_roles` synchronously (e.g. via
        # UserRead.model_validate) triggers a lazy-load in an async session context,
        # producing: MissingGreenlet: greenlet_spawn has not been called.
        #
        # Solution: re-query the just-created row with selectinload options that
        # populate both relationship levels in Python memory before returning.
        # get_with_roles() loads: Usuario → [UsuarioRol] → Rol (two chained selectins).
        loaded = await uow.usuarios.get_with_roles(usuario.id)
        assert loaded is not None, (
            f"Usuario {usuario.id} disappeared between flush and re-query — "
            "this should never happen within a single transaction"
        )
        return loaded

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

        # (f) Persist refresh token hash — family_id seeded fresh for each login
        family_id = uuid.uuid4()
        expires_at = datetime.now(timezone.utc) + timedelta(
            days=settings.REFRESH_TOKEN_EXPIRE_DAYS
        )
        await uow.refresh_tokens.insert(
            RefreshToken(
                token_hash=digest,
                usuario_id=usuario.id,
                family_id=family_id,
                expires_at=expires_at,
            )
        )

        # (g) Return token response
        return TokenResponse(
            access_token=access_token,
            refresh_token=cleartext_refresh,
        )

    @staticmethod
    async def rotate_refresh(
        uow: UnitOfWork,
        refresh_token_cleartext: str,
        ip: str,
        user_agent: str,
    ) -> TokenResponse:
        """Rotate a refresh token: revoke the old one and issue a new one.

        All steps execute within the provided UoW (single transaction).

        Steps:
          1. Hash the cleartext token.
          2. find_active_by_hash — if None, check replay vs expired vs unknown.
          3. If replay detected: raise TokenReplayError (NOT UnauthorizedError).
             CRITICAL: do NOT call revoke_family here — it would be rolled back
             on exception. The router catches TokenReplayError and opens a second
             independent UoW to call revoke_family (D-07-C Opción A).
          4. Revoke old token via revoke_by_hash.
          5. Issue new access token (in-memory, no DB write).
          6. Issue new refresh token + digest.
          7. Persist new RefreshToken with same family_id.
          8. Return TokenResponse.

        Args:
            uow: The active UnitOfWork for this transaction.
            refresh_token_cleartext: The raw refresh token string from the client.
            ip: Client IP address for audit logging.
            user_agent: Client user-agent for audit logging.

        Returns:
            A TokenResponse with new access_token and refresh_token.

        Raises:
            TokenReplayError: If the token is known but already revoked (replay).
            UnauthorizedError: If the token is expired (code="token_expired") or
                               unknown (code="invalid_token").
        """
        from app.core.config import get_settings

        settings = get_settings()

        # Step 1: Hash the cleartext token
        token_hash = hashlib.sha256(refresh_token_cleartext.encode()).hexdigest()

        # Step 2: Try to find an active (unrevoked, unexpired) token
        token = await uow.refresh_tokens.find_active_by_hash(token_hash)

        if token is None:
            # Token not active — determine why
            known = await uow.refresh_tokens.find_by_hash(token_hash)
            if known is None:
                # Token hash not in DB at all
                raise UnauthorizedError("Token inválido", code="invalid_token")

            if known.revoked_at is not None:
                # Token was revoked — this is a replay attack
                # CRITICAL: Do NOT call revoke_family here — it would be rolled
                # back when this exception causes the UoW to rollback.
                # The router catches TokenReplayError and handles revocation in
                # a second independent UoW (D-07-C Opción A).
                raise TokenReplayError(
                    family_id=known.family_id,
                    user_id=known.usuario_id,
                )

            # revoked_at IS NULL but expired (expires_at in the past)
            raise UnauthorizedError("Token expirado", code="token_expired")

        # Step 3: Revoke the current (active) token
        await uow.refresh_tokens.revoke_by_hash(token_hash)

        # Step 4: Issue new access token (in-memory, no DB write)
        new_access_token = create_access_token(str(token.usuario_id))

        # Step 5: Issue new refresh token cleartext + digest
        cleartext_new, digest_new = create_refresh_token(str(token.usuario_id))

        # Step 6: Persist new token with same family_id
        expires_at = datetime.now(timezone.utc) + timedelta(
            days=settings.REFRESH_TOKEN_EXPIRE_DAYS
        )
        await uow.refresh_tokens.create_with_family(
            RefreshToken(
                token_hash=digest_new,
                usuario_id=token.usuario_id,
                family_id=token.family_id,
                expires_at=expires_at,
            )
        )

        # Step 7: Return the new token pair
        return TokenResponse(
            access_token=new_access_token,
            refresh_token=cleartext_new,
        )

    @staticmethod
    async def revoke_refresh(
        uow: UnitOfWork,
        refresh_token_cleartext: str,
    ) -> None:
        """Revoke a single refresh token for logout.

        Idempotent: returns silently if the token is unknown or already revoked.
        Does NOT revoke the entire family — only the specific token.

        Args:
            uow: The active UnitOfWork for this transaction.
            refresh_token_cleartext: The raw refresh token string from the client.

        Returns:
            None (always — no error raised for unknown/revoked tokens).
        """
        token_hash = hashlib.sha256(refresh_token_cleartext.encode()).hexdigest()
        # revoke_by_hash returns False if not found — silently ignored (idempotent logout)
        await uow.refresh_tokens.revoke_by_hash(token_hash)
