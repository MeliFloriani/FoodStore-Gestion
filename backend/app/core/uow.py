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
from typing import TYPE_CHECKING

from app.core.logging import get_logger

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.repositories.admin_usuarios import AdminUsuariosRepository  # Change 21
    from app.repositories.categoria import CategoriaRepository
    from app.repositories.direccion_entrega import DireccionEntregaRepository  # Change 14
    from app.repositories.historial_estado import HistorialEstadoPedidoRepository  # Change 18
    from app.repositories.ingrediente import IngredienteRepository  # 6.1a — Change 10
    from app.repositories.pedido import PedidoRepository  # Change 17
    from app.repositories.producto import ProductoRepository  # Change 11
    from app.repositories.user import (
        RefreshTokenRepository,
        RolRepository,
        UsuarioRepository,
        UsuarioRolRepository,
    )
    from app.pagos.repository import PagoRepository  # Change 19

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
        self._categorias: CategoriaRepository | None = None
        self._ingredientes: IngredienteRepository | None = None  # 6.1b — Change 10
        self._productos: ProductoRepository | None = None  # Change 11
        self._direcciones_entrega: DireccionEntregaRepository | None = None  # Change 14
        self._pedidos: PedidoRepository | None = None  # Change 17
        self._historial_pedido: HistorialEstadoPedidoRepository | None = None  # Change 18
        self._pagos: PagoRepository | None = None  # Change 19
        self._admin_usuarios: AdminUsuariosRepository | None = None  # Change 21

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
        self._categorias = None
        self._ingredientes = None  # 6.1c — Change 10
        self._productos = None  # Change 11
        self._direcciones_entrega = None  # Change 14
        self._pedidos = None  # Change 17
        self._historial_pedido = None  # Change 18
        self._pagos = None  # Change 19
        self._admin_usuarios = None  # Change 21
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
    def productos(self) -> "ProductoRepository":
        """Lazy accessor for ProductoRepository, bound to the current session.

        Implemented in Change 11 (catalog-products-management).
        Follows the same lazy @property pattern as uow.categorias and uow.ingredientes.
        """
        if self._session is None:
            raise RuntimeError(
                "UnitOfWork.productos accessed outside of async context manager."
            )
        if self._productos is None:
            from app.repositories.producto import ProductoRepository

            self._productos = ProductoRepository(self._session)
        return self._productos

    @property
    def categorias(self) -> "CategoriaRepository":
        """Lazy accessor for CategoriaRepository, bound to the current session.

        Implemented in Change 09 (catalog-categories-management).
        Follows the same lazy @property pattern as uow.usuarios, uow.roles, etc.
        """
        if self._session is None:
            raise RuntimeError(
                "UnitOfWork.categorias accessed outside of async context manager."
            )
        if self._categorias is None:
            from app.repositories.categoria import CategoriaRepository

            self._categorias = CategoriaRepository(self._session)
        return self._categorias

    @property
    def ingredientes(self) -> "IngredienteRepository":
        """Lazy accessor for IngredienteRepository, bound to the current session.

        Implemented in Change 10 (catalog-ingredients-management).
        Follows the same lazy @property pattern as uow.categorias.
        """
        if self._session is None:
            raise RuntimeError(
                "UnitOfWork.ingredientes accessed outside of async context manager."
            )
        if self._ingredientes is None:
            from app.repositories.ingrediente import IngredienteRepository

            self._ingredientes = IngredienteRepository(self._session)
        return self._ingredientes

    @property
    def pedidos(self) -> "PedidoRepository":
        """Lazy accessor for PedidoRepository, bound to the current session.

        Implemented in Change 17 (order-creation-with-snapshots).
        Follows the same lazy @property pattern as uow.productos, uow.categorias.

        PedidoRepository consolidates operations for Pedido, DetallePedido, and
        HistorialEstadoPedido creation. Change 18 introduces uow.historial_pedido
        — see D-09. uow.detalles_pedido does NOT exist.
        """
        if self._session is None:
            raise RuntimeError(
                "UnitOfWork.pedidos accessed outside of async context manager."
            )
        if self._pedidos is None:
            from app.repositories.pedido import PedidoRepository

            self._pedidos = PedidoRepository(self._session)
        return self._pedidos

    @property
    def historial_pedido(self) -> "HistorialEstadoPedidoRepository":
        """Lazy accessor for HistorialEstadoPedidoRepository, bound to the current session.

        Change 18 (D-09): Supersedes Change 17 restriction that stated
        uow.historial_pedido did NOT exist.
        Append-only — HistorialEstadoPedidoRepository has no update/delete.
        """
        if self._session is None:
            raise RuntimeError(
                "UnitOfWork.historial_pedido accessed outside of async context manager."
            )
        if self._historial_pedido is None:
            from app.repositories.historial_estado import HistorialEstadoPedidoRepository

            self._historial_pedido = HistorialEstadoPedidoRepository(self._session)
        return self._historial_pedido

    @property
    def pagos(self) -> "PagoRepository":
        """Lazy accessor for PagoRepository, bound to the current session.

        Implemented in Change 19 (payments-mercadopago-integration).
        Provides access to payment CRUD and query methods for the pagos service.
        """
        if self._session is None:
            raise RuntimeError(
                "UnitOfWork.pagos accessed outside of async context manager."
            )
        if self._pagos is None:
            from app.pagos.repository import PagoRepository

            self._pagos = PagoRepository(self._session)
        return self._pagos

    @property
    def admin_usuarios(self) -> "AdminUsuariosRepository":
        """Lazy accessor for AdminUsuariosRepository, bound to the current session.

        Implemented in Change 21 (admin-users-management).
        Provides paginated listing and last-admin guard count methods.
        """
        if self._session is None:
            raise RuntimeError(
                "UnitOfWork.admin_usuarios accessed outside of async context manager."
            )
        if self._admin_usuarios is None:
            from app.repositories.admin_usuarios import AdminUsuariosRepository

            self._admin_usuarios = AdminUsuariosRepository(self._session)
        return self._admin_usuarios

    @property
    def direcciones(self) -> "DireccionEntregaRepository":
        """Lazy accessor for DireccionEntregaRepository, bound to the current session.

        Implemented in Change 14 (delivery-addresses-management).
        Follows the same lazy @property pattern as uow.categorias and uow.productos.
        """
        if self._session is None:
            raise RuntimeError(
                "UnitOfWork.direcciones accessed outside of async context manager."
            )
        if self._direcciones_entrega is None:
            from app.repositories.direccion_entrega import DireccionEntregaRepository

            self._direcciones_entrega = DireccionEntregaRepository(self._session)
        return self._direcciones_entrega


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
