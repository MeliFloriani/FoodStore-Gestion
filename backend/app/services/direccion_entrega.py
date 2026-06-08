"""
DireccionEntregaService — stateless business logic for delivery address management.

Change 14: delivery-addresses-management.

Architectural rules:
  - session.commit() is NEVER called here — UnitOfWork owns the transaction.
  - All DB access goes through UnitOfWork typed repo: uow.direcciones.<method>().
  - HTTPException is raised here for domain errors (404, 400). Never in repository.
  - All methods are @staticmethod — no per-instance state.

CRITICAL logic for crear_direccion (see spec backend-direcciones-management/spec.md):
  Si count == 0: forzar es_principal=True; ejecutar limpiar_principal (defensivo); insertar.
  Si count > 0:  es_principal=False; insertar DIRECTAMENTE — NO llamar limpiar_principal.
                 (llamarlo desactivaría la dirección principal existente sin promover ninguna nueva)
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import HTTPException, status

from app.core.uow import UnitOfWork
from app.models.address import DireccionEntrega
from app.schemas.direccion_entrega import (
    DireccionEntregaCreate,
    DireccionEntregaRead,
    DireccionEntregaUpdate,
)

_MAX_DIRECCIONES = 20


class DireccionEntregaService:
    """Stateless service for DireccionEntrega CRUD and business logic.

    All methods are @staticmethod — no per-instance state.
    Receives UnitOfWork as a parameter for every operation.
    """

    @staticmethod
    async def crear_direccion(
        uow: UnitOfWork,
        usuario_id: uuid.UUID,
        data: DireccionEntregaCreate,
    ) -> DireccionEntregaRead:
        """Create a new delivery address for the authenticated user.

        Business logic:
          1. Check that user has < 20 active addresses (limit enforced per spec).
          2. If count == 0 (first address):
               - Force es_principal = True
               - Call limpiar_principal() defensively (should be no-op but protects
                 against inconsistent prior state)
               - Insert the address
          3. If count > 0 (not first address):
               - es_principal stays False (default)
               - Insert DIRECTLY — do NOT call limpiar_principal() because that would
                 clear the existing principal without promoting a replacement.

        Args:
            uow: UnitOfWork providing uow.direcciones repository.
            usuario_id: UUID of the authenticated user (from JWT).
            data: DireccionEntregaCreate with validated input.

        Returns:
            DireccionEntregaRead for the newly created address.

        Raises:
            HTTPException(400): If user already has 20 active addresses.
        """
        count = await uow.direcciones.count_activos_por_usuario(usuario_id)

        if count >= _MAX_DIRECCIONES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Límite de {_MAX_DIRECCIONES} direcciones activas alcanzado.",
            )

        if count == 0:
            # Primera dirección — forzar es_principal=True
            es_principal = True
            # Medida defensiva contra estados inconsistentes previos
            await uow.direcciones.limpiar_principal(usuario_id)
        else:
            # Ya hay al menos una dirección activa — NO tocar es_principal de las existentes
            es_principal = False

        nueva = DireccionEntrega(
            usuario_id=usuario_id,
            alias=data.alias,
            linea1=data.linea1,
            linea2=data.linea2,
            ciudad=data.ciudad,
            provincia=data.provincia,
            codigo_postal=data.codigo_postal,
            referencia=data.referencia,
            es_principal=es_principal,
        )

        created = await uow.direcciones.create(nueva)
        return DireccionEntregaRead.model_validate(created)

    @staticmethod
    async def listar_direcciones(
        uow: UnitOfWork,
        usuario_id: uuid.UUID,
    ) -> list[DireccionEntregaRead]:
        """Return all active delivery addresses for the authenticated user.

        Args:
            uow: UnitOfWork providing uow.direcciones repository.
            usuario_id: UUID of the authenticated user (from JWT).

        Returns:
            List of DireccionEntregaRead for all active addresses.
        """
        addresses = await uow.direcciones.get_activos_por_usuario(usuario_id)
        return [DireccionEntregaRead.model_validate(a) for a in addresses]

    @staticmethod
    async def obtener_direccion(
        uow: UnitOfWork,
        usuario_id: uuid.UUID,
        direccion_id: uuid.UUID,
    ) -> DireccionEntregaRead:
        """Return a single address by id, enforcing ownership.

        Args:
            uow: UnitOfWork providing uow.direcciones repository.
            usuario_id: UUID of the authenticated user (from JWT).
            direccion_id: UUID of the address to retrieve.

        Returns:
            DireccionEntregaRead for the address.

        Raises:
            HTTPException(404): If not found, soft-deleted, or owned by another user.
                                 The 404 (not 403) ensures no information leakage.
        """
        addr = await uow.direcciones.get_by_id_and_usuario(direccion_id, usuario_id)
        if addr is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Dirección no encontrada.",
            )
        return DireccionEntregaRead.model_validate(addr)

    @staticmethod
    async def actualizar_direccion(
        uow: UnitOfWork,
        usuario_id: uuid.UUID,
        direccion_id: uuid.UUID,
        data: DireccionEntregaUpdate,
    ) -> DireccionEntregaRead:
        """Apply a partial update to an existing address.

        Only fields present in the request body (model_fields_set) are updated.
        es_principal cannot be changed via this method.

        Args:
            uow: UnitOfWork providing uow.direcciones repository.
            usuario_id: UUID of the authenticated user (from JWT).
            direccion_id: UUID of the address to update.
            data: DireccionEntregaUpdate with fields to change.

        Returns:
            DireccionEntregaRead for the updated address.

        Raises:
            HTTPException(404): If address not found or owned by another user.
        """
        addr = await uow.direcciones.get_by_id_and_usuario(direccion_id, usuario_id)
        if addr is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Dirección no encontrada.",
            )

        # Use exclude_unset=True to apply only explicitly sent fields
        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(addr, field, value)

        await uow.direcciones.session.flush()
        return DireccionEntregaRead.model_validate(addr)

    @staticmethod
    async def marcar_principal(
        uow: UnitOfWork,
        usuario_id: uuid.UUID,
        direccion_id: uuid.UUID,
    ) -> DireccionEntregaRead:
        """Mark an address as the user's principal address.

        Idempotent: if the address is already principal, returns it unchanged.

        Steps:
          1. Verify ownership (404 if not found).
          2. If already principal, return idempotently (no DB writes).
          3. limpiar_principal() — clear any existing principal for this user.
          4. set_principal(id) — mark this address as principal.

        Both steps 3 and 4 occur within the same UoW transaction.

        Args:
            uow: UnitOfWork providing uow.direcciones repository.
            usuario_id: UUID of the authenticated user (from JWT).
            direccion_id: UUID of the address to mark as principal.

        Returns:
            DireccionEntregaRead for the updated address.

        Raises:
            HTTPException(404): If address not found or owned by another user.
        """
        addr = await uow.direcciones.get_by_id_and_usuario(direccion_id, usuario_id)
        if addr is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Dirección no encontrada.",
            )

        # Idempotent: if already principal, return without modifying the DB
        if addr.es_principal:
            return DireccionEntregaRead.model_validate(addr)

        # Clear existing principal, then set new one (same UoW transaction)
        await uow.direcciones.limpiar_principal(usuario_id)
        await uow.direcciones.set_principal(direccion_id)

        # Refresh the address instance from session after updates
        await uow.direcciones.session.refresh(addr)
        return DireccionEntregaRead.model_validate(addr)

    @staticmethod
    async def eliminar_direccion(
        uow: UnitOfWork,
        usuario_id: uuid.UUID,
        direccion_id: uuid.UUID,
    ) -> None:
        """Soft-delete an address, auto-promoting a new principal if needed.

        Logic:
          1. Verify ownership (404 if not found).
          2. Capture era_principal BEFORE any modification.
          3. Soft-delete the address (sets deleted_at = now).
          4. If era_principal == True:
               - Get most recently created active address (deleted_at IS NULL).
               - If found, call set_principal(candidata.id) directly.
                 (do NOT use limpiar_principal — post-soft-delete it's a no-op
                 and calling it might have unintended side effects)
               - If not found, no promotion (valid — user has no more addresses).
          5. Return None (HTTP 204).

        All operations occur within the same UoW transaction.

        Args:
            uow: UnitOfWork providing uow.direcciones repository.
            usuario_id: UUID of the authenticated user (from JWT).
            direccion_id: UUID of the address to delete.

        Returns:
            None (HTTP 204 No Content).

        Raises:
            HTTPException(404): If address not found or owned by another user.
        """
        addr = await uow.direcciones.get_by_id_and_usuario(direccion_id, usuario_id)
        if addr is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Dirección no encontrada.",
            )

        # Capture before modifying — soft_delete() will change es_principal later
        era_principal = addr.es_principal

        # Soft-delete (sets deleted_at = now, flushes)
        addr.soft_delete()
        await uow.direcciones.session.flush()

        # Auto-promote if the deleted address was the principal and others exist
        if era_principal:
            candidata = await uow.direcciones.get_mas_reciente_activa(usuario_id)
            if candidata is not None:
                # Direct set_principal — limpiar_principal not needed post-soft-delete
                await uow.direcciones.set_principal(candidata.id)

        return None
