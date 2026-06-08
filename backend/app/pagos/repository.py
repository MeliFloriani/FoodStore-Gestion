"""
PagoRepository — data-access layer for the Pago entity.

Change 19 — payments-mercadopago-integration.

Extends BaseRepository[Pago] with payment-specific query methods:
  - get_by_mp_payment_id(): find Pago by MercadoPago internal payment ID.
  - get_by_idempotency_key(): find Pago by idempotency key (dedup guard).
  - get_latest_by_pedido_id(): most recently created Pago for a given pedido.
  - list_by_pedido_id(): all Pago rows for a pedido (ordered by created_at DESC).

Flush-only contract: inherited from BaseRepository.
session.commit() is NEVER called here — UnitOfWork owns the transaction.

Design decisions:
  D-01: 1:N Pago per Pedido is supported (external_reference UQ was dropped in 0010).
  D-03: get_by_mp_payment_id is used by the webhook idempotency guard.
  D-09: This repository is instantiated by UoW via uow.pagos accessor.
"""

from __future__ import annotations

import uuid

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.order import Pago
from app.repositories.base import BaseRepository


class PagoRepository(BaseRepository[Pago]):
    """Repository for the Pago entity with payment-specific queries."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Pago, session)

    async def get_by_mp_payment_id(self, mp_payment_id: int) -> Pago | None:
        """Return the Pago row matching the given MercadoPago payment ID.

        Used by the webhook handler idempotency guard: if a Pago with this
        mp_payment_id already exists and is approved, skip processing.

        Args:
            mp_payment_id: The integer MP payment ID from the webhook data.id.

        Returns:
            Pago instance if found (active or not soft-deleted), else None.
        """
        stmt = select(Pago).where(
            Pago.mp_payment_id == mp_payment_id,  # type: ignore[union-attr]
            Pago.deleted_at.is_(None),  # type: ignore[union-attr]
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_by_idempotency_key(self, idempotency_key: str) -> Pago | None:
        """Return the Pago row matching the given idempotency key.

        Used to detect duplicate payment submissions from the frontend.

        Args:
            idempotency_key: UUID string generated when the payment was initiated.

        Returns:
            Pago instance if found, else None.
        """
        stmt = select(Pago).where(
            Pago.idempotency_key == idempotency_key,  # type: ignore[union-attr]
            Pago.deleted_at.is_(None),  # type: ignore[union-attr]
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_latest_by_pedido_id(self, pedido_id: uuid.UUID) -> Pago | None:
        """Return the most recently created Pago row for the given pedido.

        Ordered by created_at DESC, LIMIT 1. Used by GET /pagos/{pedido_id}/latest.

        Args:
            pedido_id: UUID of the order whose latest payment is requested.

        Returns:
            The Pago row with the latest created_at, or None if no payments exist.
        """
        stmt = (
            select(Pago)
            .where(
                Pago.pedido_id == pedido_id,  # type: ignore[union-attr]
                Pago.deleted_at.is_(None),  # type: ignore[union-attr]
            )
            .order_by(desc(Pago.created_at))  # type: ignore[union-attr]
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def list_by_pedido_id(self, pedido_id: uuid.UUID) -> list[Pago]:
        """Return all Pago rows for the given pedido, ordered by created_at DESC.

        Supports the 1:N Pago per Pedido relationship (retry support — D-01).

        Args:
            pedido_id: UUID of the order whose payment history is requested.

        Returns:
            List of Pago instances ordered by created_at DESC (newest first).
        """
        stmt = (
            select(Pago)
            .where(
                Pago.pedido_id == pedido_id,  # type: ignore[union-attr]
                Pago.deleted_at.is_(None),  # type: ignore[union-attr]
            )
            .order_by(desc(Pago.created_at))  # type: ignore[union-attr]
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
