"""
CategoriaService — stateless business logic for the Categoria domain.

Architectural rules:
  - session.commit() is NEVER called here — UnitOfWork owns the transaction.
  - All DB access goes through UnitOfWork typed repo: uow.categorias.<method>().
  - Domain errors raised here are caught by global handlers in app/api/errors.py.
  - The router MUST pass the CategoriaUpdate Pydantic model instance directly —
    NOT model_dump() — to preserve model_fields_set for the parent_id sentinel.

Error codes raised:
  - CATEGORY_NOT_FOUND (404)
  - CATEGORY_NAME_DUPLICATE (409)
  - CATEGORY_HAS_ACTIVE_CHILDREN (409)
  - CATEGORY_HAS_ACTIVE_PRODUCTS (409)
  - CATEGORY_SELF_PARENT (422)
  - CATEGORY_CYCLE_DETECTED (422)
  - CATEGORY_MAX_DEPTH_EXCEEDED (422)
"""

from __future__ import annotations

import uuid

from sqlalchemy.exc import IntegrityError

from app.core.exceptions import AppValidationError, ConflictError, NotFoundError
from app.core.uow import UnitOfWork
from app.models.catalog import Categoria
from app.schemas.categoria import (
    CategoriaCreate,
    CategoriaRead,
    CategoriaTreeNode,
    CategoriaUpdate,
)

# Maximum allowed tree depth (root = 1, max leaf = 5)
_MAX_DEPTH = 5


class CategoriaService:
    """Stateless service for Categoria CRUD and tree operations.

    All methods are @staticmethod — no per-instance state.
    Receives UnitOfWork as a parameter for every operation.
    """

    @staticmethod
    async def get_tree(uow: UnitOfWork) -> list[CategoriaTreeNode]:
        """Return the category tree as a nested list of CategoriaTreeNode.

        Algorithm (O(n) two-pass dict assembly):
          Pass 1: build a dict of id → CategoriaTreeNode for every flat row.
          Pass 2: for each row with a parent_id, append the node to its parent's
                  subcategorias. Rows with parent_id=None are collected as roots.

        Note: The repository's get_tree() returns rows sorted by depth then nombre,
        guaranteeing that a parent always appears before its children — the dict
        lookup for parent_id is always valid.

        Args:
            uow: UnitOfWork providing uow.categorias.get_tree().

        Returns:
            List of root CategoriaTreeNode, each with nested subcategorias.
        """
        flat_rows = await uow.categorias.get_tree()

        # Pass 1: build lookup dict
        nodes: dict[uuid.UUID, CategoriaTreeNode] = {
            row.id: CategoriaTreeNode(
                id=row.id,
                nombre=row.nombre,
                descripcion=row.descripcion,
                subcategorias=[],
            )
            for row in flat_rows
        }

        # Pass 2: assemble hierarchy
        roots: list[CategoriaTreeNode] = []
        for row in flat_rows:
            if row.parent_id is None:
                roots.append(nodes[row.id])
            elif row.parent_id in nodes:
                nodes[row.parent_id].subcategorias.append(nodes[row.id])

        return roots

    @staticmethod
    async def get_by_id(
        category_id: uuid.UUID,
        uow: UnitOfWork,
    ) -> CategoriaRead:
        """Return a CategoriaRead for the given category ID.

        Args:
            category_id: UUID of the category to retrieve.
            uow: UnitOfWork providing uow.categorias.get_by_id().

        Returns:
            CategoriaRead for the found category.

        Raises:
            NotFoundError(code="CATEGORY_NOT_FOUND"): if not found or soft-deleted.
        """
        entity = await uow.categorias.get_by_id(category_id)
        if entity is None:
            raise NotFoundError(
                f"Categoría {category_id} no encontrada",
                code="CATEGORY_NOT_FOUND",
            )
        return CategoriaRead.model_validate(entity)

    @staticmethod
    async def create_categoria(
        data: CategoriaCreate,
        uow: UnitOfWork,
    ) -> CategoriaRead:
        """Create a new category.

        Validation steps:
          1. If parent_id provided, verify parent exists (NotFoundError if not).
          2. Validate depth: parent_depth + 1 ≤ 5 (AppValidationError if exceeded).
          3. Create entity; catch IntegrityError → ConflictError(CATEGORY_NAME_DUPLICATE).

        Args:
            data: CategoriaCreate schema with nombre, descripcion, parent_id.
            uow: UnitOfWork providing uow.categorias repository.

        Returns:
            CategoriaRead for the newly created category.

        Raises:
            NotFoundError(CATEGORY_NOT_FOUND): if parent_id doesn't exist.
            AppValidationError(CATEGORY_MAX_DEPTH_EXCEEDED): if depth would exceed 5.
            ConflictError(CATEGORY_NAME_DUPLICATE): if nombre already exists at same level.
        """
        if data.parent_id is not None:
            parent = await uow.categorias.get_by_id(data.parent_id)
            if parent is None:
                raise NotFoundError(
                    f"Categoría padre {data.parent_id} no encontrada",
                    code="CATEGORY_NOT_FOUND",
                )
            parent_depth = await uow.categorias.get_depth(data.parent_id)
            if parent_depth + 1 > _MAX_DEPTH:
                raise AppValidationError(
                    f"La profundidad máxima del árbol es {_MAX_DEPTH} niveles",
                    code="CATEGORY_MAX_DEPTH_EXCEEDED",
                )

        try:
            entity = await uow.categorias.create(
                Categoria(
                    nombre=data.nombre,
                    descripcion=data.descripcion,
                    parent_id=data.parent_id,
                )
            )
        except IntegrityError:
            raise ConflictError(
                f"Ya existe una categoría con el nombre '{data.nombre}' en este nivel",
                code="CATEGORY_NAME_DUPLICATE",
            )

        return CategoriaRead.model_validate(entity)

    @staticmethod
    async def update_categoria(
        category_id: uuid.UUID,
        data: CategoriaUpdate,
        uow: UnitOfWork,
    ) -> CategoriaRead:
        """Update an existing category.

        The router MUST pass the CategoriaUpdate Pydantic model instance directly —
        NOT data.model_dump() — to preserve model_fields_set for the parent_id sentinel.

        Validation steps (when parent_id in data.model_fields_set):
          1. Self-parent check: parent_id == category_id → AppValidationError.
          2. Cycle check: would_create_cycle() → AppValidationError.
          3. Depth validation:
             - new_parent_depth = get_depth(new_parent_id) if new_parent_id else 0
             - subtree_height = get_subtree_height(category_id)
             - validate: new_parent_depth + 1 + subtree_height ≤ 5
               (moving the subtree shifts ALL descendants by the same delta)

        Args:
            category_id: UUID of the category to update.
            data: CategoriaUpdate with model_fields_set sentinel for parent_id.
            uow: UnitOfWork providing uow.categorias repository.

        Returns:
            CategoriaRead for the updated category.

        Raises:
            NotFoundError(CATEGORY_NOT_FOUND): if category not found.
            AppValidationError(CATEGORY_SELF_PARENT): if parent_id == category_id.
            AppValidationError(CATEGORY_CYCLE_DETECTED): if cycle detected.
            AppValidationError(CATEGORY_MAX_DEPTH_EXCEEDED): if depth exceeded.
            ConflictError(CATEGORY_NAME_DUPLICATE): on IntegrityError.
        """
        entity = await uow.categorias.get_by_id(category_id)
        if entity is None:
            raise NotFoundError(
                f"Categoría {category_id} no encontrada",
                code="CATEGORY_NOT_FOUND",
            )

        # Build update dict from model_fields_set (respects sentinel for parent_id)
        update_data: dict = {}

        if "nombre" in data.model_fields_set and data.nombre is not None:
            update_data["nombre"] = data.nombre

        if "descripcion" in data.model_fields_set:
            update_data["descripcion"] = data.descripcion

        if "parent_id" in data.model_fields_set:
            new_parent_id = data.parent_id

            # 1. Self-parent check
            if new_parent_id is not None and new_parent_id == category_id:
                raise AppValidationError(
                    "Una categoría no puede ser su propio padre",
                    code="CATEGORY_SELF_PARENT",
                )

            if new_parent_id is not None:
                # 2. Cycle check — only when new_parent_id is not None
                if await uow.categorias.would_create_cycle(category_id, new_parent_id):
                    raise AppValidationError(
                        "La operación crearía un ciclo en el árbol de categorías",
                        code="CATEGORY_CYCLE_DETECTED",
                    )

                # 3. Depth validation
                # get_depth uses an ancestor-traversal CTE — O(depth), NOT get_tree() O(n)
                new_parent_depth = await uow.categorias.get_depth(new_parent_id)
                subtree_height = await uow.categorias.get_subtree_height(category_id)

                if new_parent_depth + 1 + subtree_height > _MAX_DEPTH:
                    raise AppValidationError(
                        (
                            f"La operación excedería la profundidad máxima de {_MAX_DEPTH} niveles "
                            f"(padre en profundidad {new_parent_depth}, "
                            f"subárbol de altura {subtree_height})"
                        ),
                        code="CATEGORY_MAX_DEPTH_EXCEEDED",
                    )
            else:
                # Moving to root — depth of root is 1, check subtree fits
                subtree_height = await uow.categorias.get_subtree_height(category_id)
                if 1 + subtree_height > _MAX_DEPTH:
                    raise AppValidationError(
                        f"La operación excedería la profundidad máxima de {_MAX_DEPTH} niveles",
                        code="CATEGORY_MAX_DEPTH_EXCEEDED",
                    )

            update_data["parent_id"] = new_parent_id

        try:
            updated = await uow.categorias.update(category_id, update_data)
        except IntegrityError:
            raise ConflictError(
                "Ya existe una categoría con ese nombre en este nivel",
                code="CATEGORY_NAME_DUPLICATE",
            )

        # update() returns None only if entity not found — we already checked above
        if updated is None:
            raise NotFoundError(
                f"Categoría {category_id} no encontrada",
                code="CATEGORY_NOT_FOUND",
            )

        return CategoriaRead.model_validate(updated)

    @staticmethod
    async def delete_categoria(
        category_id: uuid.UUID,
        uow: UnitOfWork,
    ) -> None:
        """Soft-delete a category, blocking if it has active children or products.

        Args:
            category_id: UUID of the category to soft-delete.
            uow: UnitOfWork providing uow.categorias repository.

        Raises:
            NotFoundError(CATEGORY_NOT_FOUND): if category not found.
            ConflictError(CATEGORY_HAS_ACTIVE_CHILDREN): if active subcategories exist.
            ConflictError(CATEGORY_HAS_ACTIVE_PRODUCTS): if active linked products exist.
        """
        entity = await uow.categorias.get_by_id(category_id)
        if entity is None:
            raise NotFoundError(
                f"Categoría {category_id} no encontrada",
                code="CATEGORY_NOT_FOUND",
            )

        active_children = await uow.categorias.count_active_children(category_id)
        if active_children > 0:
            raise ConflictError(
                f"La categoría tiene {active_children} subcategorías activas",
                code="CATEGORY_HAS_ACTIVE_CHILDREN",
            )

        # Guard active post Change 11: count_active_products returns 0 until
        # producto_categoria is populated (Change 11 — catalog-products-management).
        active_products = await uow.categorias.count_active_products(category_id)
        if active_products > 0:
            raise ConflictError(
                f"La categoría tiene {active_products} productos activos asociados",
                code="CATEGORY_HAS_ACTIVE_PRODUCTS",
            )

        await uow.categorias.soft_delete(category_id)
