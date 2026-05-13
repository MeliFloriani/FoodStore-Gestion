"""
Unit of Work — async context manager that owns all transaction lifecycle.

Commit / rollback ownership invariant:
  session.commit() is called ONLY in UnitOfWork.__aexit__ on clean exit.
  session.rollback() is called ONLY in UnitOfWork.__aexit__ on exception.
  NO Service, Router, or Repository may call session.commit() directly.
  This invariant is enforced via the verification grep gate in tasks.md §8.3.

get_session() vs get_uow():
  get_session() from app.db.session continues to exist for test fixtures that
  need direct session access (see backend/tests/conftest.py and tests/fixtures/uow.py).
  In production code (routers, services, repositories), get_session MUST NOT be
  injected via Depends. Production code MUST inject get_uow instead.
  Verification: tasks.md §8.9 and §8.11 grep gates.

Session visibility note:
  uow.session is an internal implementation detail of UnitOfWork.
  Services and Routers MUST access data exclusively via
  uow.<repository_name>.<method>().
  Only UnitOfWork internal code and test fixtures may access session directly.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING, NoReturn

from app.core.logging import get_logger

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.repositories.user import (
        RefreshTokenRepository,
        RolRepository,
        UsuarioRepository,
        UsuarioRolRepository,
    )

logger = get_logger(__name__)


class UnitOfWork:
    """Async context manager that wraps a single database transaction.

    Usage (in a Service):
        async with UnitOfWork() as uow:
            user = await uow.usuarios.get_by_id(user_id)
            user = await uow.usuarios.update(user_id, {"nombre": "Nuevo"})
        # commit happens automatically on exit

    Usage (in a FastAPI route via dependency injection):
        @router.get("/users/{id}")
        async def get_user(id: UUID, uow: UnitOfWork = Depends(get_uow)):
            user = await uow.usuarios.get_by_id(id)
            ...

    WARNING: Do NOT access uow.session directly in Services or Routers.
    Only UnitOfWork internals and test fixtures may use the raw session.
    """

    def __init__(self) -> None:
        # _session is initialised in __aenter__ — not here.
        # This prevents accidental usage before entering the context manager.
        self._session: AsyncSession | None = None

        # Lazy repository instances — initialised on first access via properties.
        self._usuarios: UsuarioRepository | None = None
        self._roles: RolRepository | None = None
        self._usuario_roles: UsuarioRolRepository | None = None
        self._refresh_tokens: RefreshTokenRepository | None = None

    async def __aenter__(self) -> UnitOfWork:
        """Open a new AsyncSession via get_session_factory() and return self.

        Repository stub attributes are reset to None so they are lazily
        re-initialised using the new session.
        """
        from app.db.session import get_session_factory

        self._session = get_session_factory()()
        # Reset lazy repo instances to ensure they bind to this session.
        self._usuarios = None
        self._roles = None
        self._usuario_roles = None
        self._refresh_tokens = None
        logger.debug("uow.begin", session_id=id(self._session))
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        """Commit on clean exit; rollback and re-raise on any exception.

        The session is always closed in the finally block, regardless of whether
        commit or rollback succeeded (R-03 mitigation).

        Exception chaining: the original exception is preserved via 'raise ... from ...'
        semantics (the exception is re-raised by returning None from __aexit__).
        """
        assert self._session is not None, (
            "UnitOfWork.__aexit__ called before __aenter__"
        )
        try:
            if exc_type is None:
                await self._session.commit()
                logger.debug("uow.commit", session_id=id(self._session))
            else:
                await self._session.rollback()
                logger.debug(
                    "uow.rollback",
                    session_id=id(self._session),
                    exc_type=exc_type.__name__ if exc_type else None,
                )
        finally:
            await self._session.close()
        # Return None (not True) so exceptions are re-raised by Python.

    # -------------------------------------------------------------------------
    # Internal session accessor (test fixtures only)
    # -------------------------------------------------------------------------

    @property
    def session(self) -> AsyncSession:
        """Raw session — for test fixtures ONLY.

        WARNING: Services and Routers MUST NOT access this property.
        Use uow.<repository_name>.<method>() instead.
        This property exists exclusively to support test fixture patterns
        (see backend/tests/fixtures/uow.py and D-03 session injection).
        """
        if self._session is None:
            raise RuntimeError(
                "UnitOfWork.session accessed outside of async context manager. "
                "Use 'async with UnitOfWork() as uow:' before accessing repositories."
            )
        return self._session

    # -------------------------------------------------------------------------
    # Typed repository accessors — auth path (Change 04)
    # -------------------------------------------------------------------------

    @property
    def usuarios(self) -> UsuarioRepository:
        """Lazy accessor for UsuarioRepository, bound to the current session."""
        if self._session is None:
            raise RuntimeError(
                "UnitOfWork.usuarios accessed outside of async context manager."
            )
        if self._usuarios is None:
            from app.repositories.user import UsuarioRepository

            self._usuarios = UsuarioRepository(self._session)
        return self._usuarios

    @property
    def roles(self) -> RolRepository:
        """Lazy accessor for RolRepository, bound to the current session."""
        if self._session is None:
            raise RuntimeError(
                "UnitOfWork.roles accessed outside of async context manager."
            )
        if self._roles is None:
            from app.repositories.user import RolRepository

            self._roles = RolRepository(self._session)
        return self._roles

    @property
    def usuario_roles(self) -> UsuarioRolRepository:
        """Lazy accessor for UsuarioRolRepository, bound to the current session."""
        if self._session is None:
            raise RuntimeError(
                "UnitOfWork.usuario_roles accessed outside of async context manager."
            )
        if self._usuario_roles is None:
            from app.repositories.user import UsuarioRolRepository

            self._usuario_roles = UsuarioRolRepository(self._session)
        return self._usuario_roles

    @property
    def refresh_tokens(self) -> RefreshTokenRepository:
        """Lazy accessor for RefreshTokenRepository, bound to the current session.

        No methods are called on this repository in Change 04.
        Token issuance and verification logic is deferred to Change 06.
        """
        if self._session is None:
            raise RuntimeError(
                "UnitOfWork.refresh_tokens accessed outside of async context manager."
            )
        if self._refresh_tokens is None:
            from app.repositories.user import RefreshTokenRepository

            self._refresh_tokens = RefreshTokenRepository(self._session)
        return self._refresh_tokens

    # -------------------------------------------------------------------------
    # Stub accessors — future repositories (Change N)
    # -------------------------------------------------------------------------

    @property
    def productos(self) -> NoReturn:
        """Stub: ProductoRepository not yet implemented.

        # TODO(change-09): implement ProductoRepository and wire here.
        """
        raise NotImplementedError(
            "uow.productos not implemented"
            " — see Change 09 (catalog-categories-management)"
        )

    @property
    def categorias(self) -> NoReturn:
        """Stub: CategoriaRepository not yet implemented.

        # TODO(change-09): implement CategoriaRepository and wire here.
        """
        raise NotImplementedError(
            "uow.categorias not implemented"
            " — see Change 09 (catalog-categories-management)"
        )

    @property
    def ingredientes(self) -> NoReturn:
        """Stub: IngredienteRepository not yet implemented.

        # TODO(change-10): implement IngredienteRepository and wire here.
        """
        raise NotImplementedError(
            "uow.ingredientes not implemented"
            " — see Change 10 (catalog-ingredients-management)"
        )

    @property
    def pedidos(self) -> NoReturn:
        """Stub: PedidoRepository not yet implemented.

        # TODO(change-11): implement PedidoRepository and wire here.
        """
        raise NotImplementedError(
            "uow.pedidos not implemented — see Change 11 (orders)"
        )

    @property
    def direcciones(self) -> NoReturn:
        """Stub: DireccionRepository not yet implemented.

        # TODO(change-11): implement DireccionRepository and wire here.
        """
        raise NotImplementedError(
            "uow.direcciones not implemented — see Change 11 (orders)"
        )


async def get_uow() -> AsyncGenerator[UnitOfWork, None]:
    """FastAPI async generator dependency that yields a UnitOfWork for the request.

    Usage in a route handler:
        @router.get("/users")
        async def list_users(uow: UnitOfWork = Depends(get_uow)):
            users = await uow.usuarios.list_all()
            return users

    IMPORTANT — do NOT wrap or alias this function:
        # WRONG: get_uow_v2 = get_uow        ← breaks FastAPI Depends deduplication
        # WRONG: partial(get_uow, ...)        ← breaks FastAPI Depends deduplication
        # CORRECT: Depends(get_uow)           ← always use the original callable

    FastAPI deduplicates Depends() by callable identity. If get_uow is wrapped,
    two separate UnitOfWork instances (and two AsyncSessions) are created per request,
    breaking transactional atomicity (D-06).
    """
    async with UnitOfWork() as uow:
        yield uow
