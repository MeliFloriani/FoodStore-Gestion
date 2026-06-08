"""
Append-only repository for HistorialEstadoPedido.

RN-FS07 / RN-03: HistorialEstadoPedido is append-only.
NO update() or delete() methods. Does NOT inherit BaseRepository[T].
D-09 (Change 18): Introduced as uow.historial_pedido accessor.
"""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.order import HistorialEstadoPedido


class HistorialEstadoPedidoRepository:
    """Append-only repository — only INSERT (append) is permitted.

    Deliberately does NOT inherit BaseRepository[T] to prevent accidental
    exposure of update() and delete() methods (RN-03 / RN-FS07).

    The private _session attribute is intentional — services and routers must
    access data exclusively via uow.<repository_name>.<method>(), never via
    the raw session.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session  # PRIVATE — do not expose as public property

    async def append(
        self, historial: HistorialEstadoPedido
    ) -> HistorialEstadoPedido:
        """Persist a HistorialEstadoPedido row. Append-only (no update/delete).

        Calls session.flush() to populate server-side defaults (id, created_at)
        without committing. session.commit() is NEVER called here — UoW owns it.

        Args:
            historial: New HistorialEstadoPedido instance (not yet in session).

        Returns:
            The same HistorialEstadoPedido after flush (with id and created_at populated).
        """
        self._session.add(historial)
        await self._session.flush()
        await self._session.refresh(historial)
        return historial

    # RN-FS07: NO update() or delete() methods.
    # Any attempt to add them violates the append-only invariant.
