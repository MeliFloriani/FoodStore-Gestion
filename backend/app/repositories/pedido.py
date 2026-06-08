"""
PedidoRepository — data-access layer for the order domain.

Change 17: order-creation-with-snapshots.

Consolidates operations for Pedido, DetallePedido, and HistorialEstadoPedido.
No separate repositories are created for DetallePedido or HistorialEstadoPedido
(uow.detalles_pedido and uow.historial_pedido do NOT exist — per spec constraint).

Methods:
  - lock_productos_for_update(): SELECT ... FOR UPDATE to prevent overselling.
  - get_forma_pago(): Lookup FormaPago by codigo.
  - get_direccion_usuario(): Ownership-scoped lookup for DireccionEntrega.
  - create_pedido(): Persist a Pedido via session.add + flush.
  - create_detalle(): Persist a DetallePedido via session.add + flush.
  - create_historial(): Persist a HistorialEstadoPedido via session.add + flush.
  - decrement_stock(): Atomic UPDATE to decrement stock_cantidad.
  - get_ingredientes_batch(): Batch fetch ProductoIngrediente for all given producto_ids.

Flush-only contract: inherited from BaseRepository.
session.commit() is NEVER called here — UnitOfWork owns the transaction.

Design decisions:
- D-02: lock_productos_for_update uses ORDER BY id to prevent deadlocks between
  concurrent transactions locking multiple products in different orders.
- D-07: All write methods call session.flush() to stage changes without committing.
  The UoW does the final COMMIT in __aexit__ on clean exit.
- Anti-N+1: get_ingredientes_batch fetches all ProductoIngrediente for all
  products in a single query (IN clause), not one query per product.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

from sqlalchemy import func, or_, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.address import DireccionEntrega
from app.models.catalog import FormaPago, Producto, ProductoIngrediente
from app.models.order import DetallePedido, HistorialEstadoPedido, Pedido
from app.models.user import Usuario
from app.repositories.base import BaseRepository


class PedidoRepository(BaseRepository[Pedido]):
    """Repository for the Pedido entity and related order operations."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Pedido, session)

    async def lock_productos_for_update(
        self, ids: list[uuid.UUID]
    ) -> list[Producto]:
        """Acquire pessimistic row-level locks on the given products.

        Executes SELECT * FROM producto WHERE id IN (:ids) ORDER BY id FOR UPDATE.

        The ORDER BY id is critical: it guarantees that all concurrent transactions
        acquire locks in the same ascending order, preventing deadlocks (D-02).

        The FOR UPDATE lock is held until the UoW commits or rolls back.

        Args:
            ids: List of product UUIDs to lock. May be empty (returns []).

        Returns:
            List of Producto instances with locks held, ordered by id.
            Products that do not exist are silently excluded — caller checks.
        """
        if not ids:
            return []
        # Use text() to emit FOR UPDATE — SQLAlchemy ORM select().with_for_update()
        # also works but we want explicit ORDER BY id for deadlock prevention.
        stmt = (
            select(Producto)
            .where(Producto.id.in_(ids))  # type: ignore[union-attr]
            .order_by(Producto.id)  # type: ignore[union-attr]
            .with_for_update()
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_forma_pago(self, codigo: str) -> FormaPago | None:
        """Fetch a FormaPago by its semantic code.

        Args:
            codigo: Semantic code (e.g. "MERCADOPAGO", "EFECTIVO", "TRANSFERENCIA").

        Returns:
            FormaPago instance if found, None if the code does not exist.
        """
        stmt = select(FormaPago).where(FormaPago.codigo == codigo)  # type: ignore[union-attr]
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_direccion_usuario(
        self, direccion_id: uuid.UUID, usuario_id: uuid.UUID
    ) -> DireccionEntrega | None:
        """Fetch a delivery address by ID, scoped to the given user.

        This is the ownership check: returns None if the address belongs to a
        different user or if the address does not exist (active or soft-deleted).
        Only active (non-soft-deleted) addresses are returned.

        Args:
            direccion_id: UUID of the address to fetch.
            usuario_id: UUID of the user who must own the address.

        Returns:
            DireccionEntrega if found and owned by the user, None otherwise.
        """
        stmt = select(DireccionEntrega).where(
            DireccionEntrega.id == direccion_id,  # type: ignore[union-attr]
            DireccionEntrega.usuario_id == usuario_id,  # type: ignore[union-attr]
            DireccionEntrega.deleted_at.is_(None),  # type: ignore[union-attr]
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_direccion_by_id(
        self, direccion_id: uuid.UUID
    ) -> DireccionEntrega | None:
        """Fetch a delivery address by ID (any user, active only).

        Used to distinguish ADDRESS_NOT_FOUND from ADDRESS_NOT_OWNED.

        Args:
            direccion_id: UUID of the address to fetch.

        Returns:
            DireccionEntrega if found (regardless of owner), None if not found.
        """
        stmt = select(DireccionEntrega).where(
            DireccionEntrega.id == direccion_id,  # type: ignore[union-attr]
            DireccionEntrega.deleted_at.is_(None),  # type: ignore[union-attr]
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def create_pedido(self, pedido: Pedido) -> Pedido:
        """Persist a new Pedido, flushing to obtain the server-side UUID.

        session.flush() is called so that pedido.id is populated before
        DetallePedido and HistorialEstadoPedido records are created (they need
        pedido_id as FK). session.commit() is NOT called — UoW owns it.

        Args:
            pedido: New Pedido instance (not yet in the session).

        Returns:
            The same Pedido after flush (with id and created_at populated).
        """
        self.session.add(pedido)
        await self.session.flush()
        return pedido

    async def create_detalle(self, detalle: DetallePedido) -> DetallePedido:
        """Persist a DetallePedido record within the current transaction.

        Args:
            detalle: New DetallePedido instance (not yet in the session).

        Returns:
            The same DetallePedido after flush.
        """
        self.session.add(detalle)
        await self.session.flush()
        return detalle

    async def create_historial(
        self, historial: HistorialEstadoPedido
    ) -> HistorialEstadoPedido:
        """Persist a HistorialEstadoPedido record (append-only — RN-03).

        Args:
            historial: New HistorialEstadoPedido instance.

        Returns:
            The same HistorialEstadoPedido after flush.
        """
        self.session.add(historial)
        await self.session.flush()
        return historial

    async def decrement_stock(
        self, producto_id: uuid.UUID, cantidad: int
    ) -> None:
        """Atomically decrement stock_cantidad for a product.

        Uses UPDATE SET stock_cantidad = stock_cantidad - :cantidad without a
        WHERE stock_cantidad >= :cantidad guard — that guard was already enforced
        by the SELECT FOR UPDATE validation step. The FOR UPDATE lock ensures no
        other transaction can change stock between the validation and this UPDATE.

        Args:
            producto_id: UUID of the product to decrement.
            cantidad: Amount to decrement (must be >= 1, validated by service).
        """
        stmt = (
            update(Producto)
            .where(Producto.id == producto_id)  # type: ignore[union-attr]
            .values(stock_cantidad=Producto.stock_cantidad - cantidad)  # type: ignore[union-attr]
        )
        await self.session.execute(stmt)

    async def get_for_update(self, pedido_id: uuid.UUID) -> "Pedido | None":
        """SELECT pedido FOR UPDATE — pessimistic lock before state transition.

        Change 18: prevents concurrent FSM transitions on the same order.
        Task 4.6 — created unconditionally (did not exist in Change 17).

        Args:
            pedido_id: UUID of the pedido to lock.

        Returns:
            Pedido instance with a row-level lock held, or None if not found.
            Note: does NOT filter by deleted_at (orders are not soft-deleted).
        """
        stmt = (
            select(Pedido)
            .where(Pedido.id == pedido_id)
            .with_for_update()
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def update_estado(self, pedido_id: uuid.UUID, nuevo_estado: str) -> "Pedido":
        """Update pedido.estado_codigo. Returns updated Pedido after flush.

        Change 18: Created unconditionally (method did not exist in Change 17).
        Uses UPDATE ... RETURNING for atomic fetch of the updated row.

        Args:
            pedido_id: UUID of the pedido to update.
            nuevo_estado: New estado_codigo value (e.g. "EN_PREP", "CANCELADO").

        Returns:
            Updated Pedido instance after flush + refresh.

        Raises:
            sqlalchemy.exc.NoResultFound: If pedido_id does not exist (should not
            happen if get_for_update was called first).
        """
        from sqlalchemy import update as sa_update

        stmt = (
            sa_update(Pedido)
            .where(Pedido.id == pedido_id)
            .values(estado_codigo=nuevo_estado)
            .returning(Pedido)
        )
        result = await self.session.execute(stmt)
        await self.session.flush()
        updated = result.scalar_one()
        await self.session.refresh(updated)
        return updated

    async def list_by_usuario(
        self, usuario_id: uuid.UUID, limit: int = 50, offset: int = 0
    ) -> list[Pedido]:
        """Fetch paginated orders for a given user, ordered by creation date DESC.

        Filters out soft-deleted rows (deleted_at IS NULL) in compliance with
        BaseRepository flush-only contract and Base.soft_delete() pattern.

        Pedido.detalles uses lazy="selectin" — automatically loaded by SQLAlchemy.
        Pedido.historial uses lazy="noload" — NOT loaded here; the caller
        (_load_pedido_for_response) fetches historial via a separate query per
        pedido. For list endpoints with many rows this is acceptable (N+1 bounded
        by limit=50 max), and avoids a complex JOIN that would duplicate rows.

        Args:
            usuario_id: UUID of the user whose orders to list.
            limit: Maximum number of orders to return (default 50, hard cap by API).
            offset: Number of records to skip (pagination offset).

        Returns:
            List of Pedido instances with detalles loaded (selectin), ordered by
            created_at DESC.
        """
        stmt = (
            select(Pedido)
            .where(
                Pedido.usuario_id == usuario_id,
                Pedido.deleted_at.is_(None),  # type: ignore[union-attr]
            )
            .order_by(Pedido.created_at.desc())  # type: ignore[union-attr]
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_ingredientes_batch(
        self, producto_ids: list[uuid.UUID]
    ) -> dict[uuid.UUID, list[ProductoIngrediente]]:
        """Fetch all ProductoIngrediente records for the given products in one query.

        Anti-N+1: executes a single SELECT WHERE producto_id IN (:ids) instead of
        one query per product (D-07 compliance from service spec).

        Args:
            producto_ids: List of product UUIDs to fetch ingredients for.

        Returns:
            Dict mapping producto_id → list[ProductoIngrediente].
            Products with no ingredients map to [].
        """
        if not producto_ids:
            return {}
        stmt = select(ProductoIngrediente).where(
            ProductoIngrediente.producto_id.in_(producto_ids)  # type: ignore[union-attr]
        )
        result = await self.session.execute(stmt)
        rows = result.scalars().all()

        mapping: dict[uuid.UUID, list[ProductoIngrediente]] = {}
        for pi in rows:
            key = pi.producto_id  # type: ignore[union-attr]
            mapping.setdefault(key, []).append(pi)
        return mapping

    async def list_with_filters(
        self,
        usuario_id: uuid.UUID | None,
        estado: str | None,
        desde: date | None,
        hasta: date | None,
        cliente: str | None,
        page: int,
        size: int,
    ) -> tuple[list[Pedido], int]:
        """List Pedidos with optional filters and pagination.

        Change 20 (task 2.1): used by the listing service with RBAC discrimination.

        - If usuario_id is not None → filter WHERE pedido.usuario_id = :usuario_id.
        - If cliente has >= 3 chars → JOIN Usuario and ILIKE on email or nombre+apellido.
        - Returns (items, total_count) tuple for Page[PedidoListItem] construction.

        Args:
            usuario_id: If set, restrict to this user's orders (CLIENT mode).
            estado: Optional estado_codigo filter.
            desde: Optional lower bound on created_at (inclusive, at midnight UTC).
            hasta: Optional upper bound on created_at (inclusive, at end-of-day UTC).
            cliente: Optional ILIKE search on usuario.email / nombre+apellido (≥3 chars).
            page: 1-based page number.
            size: Page size (max enforced by caller).

        Returns:
            Tuple of (list of Pedido instances, total count matching filters).
            Items are ordered by created_at DESC.
            Pedido.detalles is loaded via selectin (lazy="selectin" on the model).
        """
        # Build base WHERE conditions
        conditions = [
            Pedido.deleted_at.is_(None),  # type: ignore[union-attr]
        ]

        if usuario_id is not None:
            conditions.append(Pedido.usuario_id == usuario_id)  # type: ignore[union-attr]

        if estado is not None:
            conditions.append(Pedido.estado_codigo == estado)  # type: ignore[union-attr]

        if desde is not None:
            desde_dt = datetime(desde.year, desde.month, desde.day, 0, 0, 0, tzinfo=timezone.utc)
            conditions.append(Pedido.created_at >= desde_dt)  # type: ignore[union-attr]

        if hasta is not None:
            hasta_dt = datetime(hasta.year, hasta.month, hasta.day, 23, 59, 59, tzinfo=timezone.utc)
            conditions.append(Pedido.created_at <= hasta_dt)  # type: ignore[union-attr]

        # Cliente search: JOIN to Usuario only when at least 3 chars (D-10)
        needs_usuario_join = cliente is not None and len(cliente) >= 3

        # Count query
        if needs_usuario_join:
            count_stmt = (
                select(func.count(Pedido.id))  # type: ignore[union-attr]
                .join(Usuario, Pedido.usuario_id == Usuario.id)  # type: ignore[union-attr]
                .where(*conditions)
                .where(
                    or_(
                        Usuario.email.ilike(f"%{cliente}%"),  # type: ignore[union-attr]
                        func.concat(Usuario.nombre, " ", Usuario.apellido).ilike(f"%{cliente}%"),  # type: ignore[union-attr]
                    )
                )
            )
        else:
            count_stmt = select(func.count(Pedido.id)).where(*conditions)  # type: ignore[union-attr]

        count_result = await self.session.execute(count_stmt)
        total = count_result.scalar_one()

        # Data query with pagination
        offset = (page - 1) * size
        if needs_usuario_join:
            data_stmt = (
                select(Pedido)
                .join(Usuario, Pedido.usuario_id == Usuario.id)  # type: ignore[union-attr]
                .where(*conditions)
                .where(
                    or_(
                        Usuario.email.ilike(f"%{cliente}%"),  # type: ignore[union-attr]
                        func.concat(Usuario.nombre, " ", Usuario.apellido).ilike(f"%{cliente}%"),  # type: ignore[union-attr]
                    )
                )
                .order_by(Pedido.created_at.desc())  # type: ignore[union-attr]
                .offset(offset)
                .limit(size)
            )
        else:
            data_stmt = (
                select(Pedido)
                .where(*conditions)
                .order_by(Pedido.created_at.desc())  # type: ignore[union-attr]
                .offset(offset)
                .limit(size)
            )

        data_result = await self.session.execute(data_stmt)
        items = list(data_result.scalars().all())
        return items, total

    async def get_full_detail(self, pedido_id: uuid.UUID) -> Pedido | None:
        """Fetch a Pedido with all relations needed for PedidoDetail response.

        Change 20 (task 2.2): Anti-N+1 strategy via selectinload.
        Loads Pedido.detalles, Pedido.historial (ordered by created_at ASC)
        using selectinload. The usuario and pago are loaded separately by the
        service (uow.usuarios.get_by_id and uow.pagos.get_latest_by_pedido_id).

        Args:
            pedido_id: UUID of the pedido to fetch.

        Returns:
            Pedido instance with detalles and historial eagerly loaded,
            or None if not found.
        """
        stmt = (
            select(Pedido)
            .where(Pedido.id == pedido_id)  # type: ignore[union-attr]
            .options(
                selectinload(Pedido.detalles),  # type: ignore[union-attr]
                selectinload(Pedido.historial),  # type: ignore[union-attr]
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
