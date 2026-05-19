"""
IngredienteService — stateless business logic for the Ingrediente domain.

Architectural rules:
  - session.commit() is NEVER called here — UnitOfWork owns the transaction.
  - All DB access goes through UnitOfWork typed repo: uow.ingredientes.<method>().
  - Domain errors raised here are caught by global handlers in app/api/errors.py.
  - The router MUST pass the IngredienteUpdate Pydantic model instance directly —
    NOT model_dump() — to preserve model_fields_set for the partial-update sentinel
    (D-05: model_fields_set preservation).

Error codes raised:
  - INGREDIENT_NOT_FOUND (404)
  - INGREDIENT_NAME_DUPLICATE (409)
"""

from __future__ import annotations

import uuid

from sqlalchemy.exc import IntegrityError

from app.core.exceptions import ConflictError, NotFoundError
from app.core.uow import UnitOfWork
from app.models.catalog import Ingrediente
from app.schemas.ingrediente import (
    IngredienteCreate,
    IngredienteRead,
    IngredienteUpdate,
)


class IngredienteService:
    """Stateless service for Ingrediente CRUD operations.

    All methods are @staticmethod — no per-instance state.
    Receives UnitOfWork as a parameter for every operation.
    Mirrors the CategoriaService pattern exactly.
    """

    @staticmethod
    async def list_ingredientes(
        es_alergeno: bool | None,
        uow: UnitOfWork,
    ) -> list[IngredienteRead]:
        """Return all active ingredients, optionally filtered by es_alergeno.

        Args:
            es_alergeno: If not None, filter to only allergen (True) or
                non-allergen (False) ingredients. If None, return all.
            uow: UnitOfWork providing uow.ingredientes.list_active().

        Returns:
            List of IngredienteRead for all matching active ingredients.
        """
        entities = await uow.ingredientes.list_active(es_alergeno)
        return [IngredienteRead.model_validate(e) for e in entities]

    @staticmethod
    async def get_ingrediente(
        ingrediente_id: uuid.UUID,
        uow: UnitOfWork,
    ) -> IngredienteRead:
        """Return an IngredienteRead for the given ingredient ID.

        Args:
            ingrediente_id: UUID of the ingredient to retrieve.
            uow: UnitOfWork providing uow.ingredientes.get_by_id().

        Returns:
            IngredienteRead for the found ingredient.

        Raises:
            NotFoundError(code="INGREDIENT_NOT_FOUND"): if not found or soft-deleted.
        """
        entity = await uow.ingredientes.get_by_id(ingrediente_id)
        if entity is None:
            raise NotFoundError(
                f"Ingrediente {ingrediente_id} no encontrado",
                code="INGREDIENT_NOT_FOUND",
            )
        return IngredienteRead.model_validate(entity)

    @staticmethod
    async def create_ingrediente(
        data: IngredienteCreate,
        uow: UnitOfWork,
    ) -> IngredienteRead:
        """Create a new ingredient.

        data (IngredienteCreate) MUST NOT be passed directly to create() —
        create() expects an Ingrediente ORM instance. We instantiate Ingrediente
        explicitly to preserve type safety and follow the CategoriaService pattern.

        Args:
            data: IngredienteCreate schema with nombre and es_alergeno.
            uow: UnitOfWork providing uow.ingredientes repository.

        Returns:
            IngredienteRead for the newly created ingredient.

        Raises:
            ConflictError(code="INGREDIENT_NAME_DUPLICATE"): if nombre already
                exists among active records (partial index violation from DB).
        """
        try:
            entity = await uow.ingredientes.create(
                Ingrediente(nombre=data.nombre, es_alergeno=data.es_alergeno)
            )
        except IntegrityError:
            raise ConflictError(
                "Nombre already exists",
                code="INGREDIENT_NAME_DUPLICATE",
            )
        return IngredienteRead.model_validate(entity)

    @staticmethod
    async def update_ingrediente(
        ingrediente_id: uuid.UUID,
        data: IngredienteUpdate,
        uow: UnitOfWork,
    ) -> IngredienteRead:
        """Update an existing ingredient.

        The router MUST pass the IngredienteUpdate Pydantic model instance directly —
        NOT data.model_dump() — to preserve model_fields_set for the partial-update
        sentinel (D-05).

        Only fields present in data.model_fields_set are applied to the ORM entity.
        Fields absent from the payload are left at their current DB values.

        Args:
            ingrediente_id: UUID of the ingredient to update.
            data: IngredienteUpdate with model_fields_set sentinel.
            uow: UnitOfWork providing uow.ingredientes repository.

        Returns:
            IngredienteRead for the updated ingredient.

        Raises:
            NotFoundError(code="INGREDIENT_NOT_FOUND"): if ingredient not found
                or soft-deleted.
            ConflictError(code="INGREDIENT_NAME_DUPLICATE"): on IntegrityError
                from duplicate nombre.
        """
        entity = await uow.ingredientes.get_by_id(ingrediente_id)
        if entity is None:
            raise NotFoundError(
                f"Ingrediente {ingrediente_id} no encontrado",
                code="INGREDIENT_NOT_FOUND",
            )

        # Build update dict from model_fields_set (only supplied fields)
        update_data: dict = {}
        if "nombre" in data.model_fields_set and data.nombre is not None:
            update_data["nombre"] = data.nombre
        if "es_alergeno" in data.model_fields_set and data.es_alergeno is not None:
            update_data["es_alergeno"] = data.es_alergeno

        try:
            updated = await uow.ingredientes.update(ingrediente_id, update_data)
        except IntegrityError:
            raise ConflictError(
                "Nombre ya existe",
                code="INGREDIENT_NAME_DUPLICATE",
            )

        # update() returns None only if entity not found — we already checked above
        if updated is None:
            raise NotFoundError(
                f"Ingrediente {ingrediente_id} no encontrado",
                code="INGREDIENT_NOT_FOUND",
            )

        return IngredienteRead.model_validate(updated)

    @staticmethod
    async def delete_ingrediente(
        ingrediente_id: uuid.UUID,
        uow: UnitOfWork,
    ) -> None:
        """Soft-delete an ingredient.

        MANDATORY: calls get_by_id FIRST to verify existence before soft_delete.
        Without this check, double-deletes would silently succeed instead of
        returning 404 (D-03 design decision).

        Args:
            ingrediente_id: UUID of the ingredient to soft-delete.
            uow: UnitOfWork providing uow.ingredientes repository.

        Raises:
            NotFoundError(code="INGREDIENT_NOT_FOUND"): if ingredient not found
                or already soft-deleted.
        """
        entity = await uow.ingredientes.get_by_id(ingrediente_id)
        if entity is None:
            raise NotFoundError(
                f"Ingrediente {ingrediente_id} no encontrado",
                code="INGREDIENT_NOT_FOUND",
            )
        await uow.ingredientes.soft_delete(ingrediente_id)
