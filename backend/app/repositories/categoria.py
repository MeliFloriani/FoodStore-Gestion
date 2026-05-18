"""
CategoriaRepository — data-access layer for the Categoria entity.

Extends BaseRepository[Categoria] with category-specific methods:
  - get_tree(): recursive CTE returning flat rows with virtual depth column
  - would_create_cycle(): detect if reparenting would create a cycle
  - count_active_children(): count direct active subcategories
  - count_active_products(): count active products linked to this category
  - get_depth(): depth of a category (1 = root) via ancestor-traversal CTE
  - get_subtree_height(): max relative depth of subtree (0 = leaf)

All methods use session.execute() with text() for recursive CTEs.
Flush-only contract: inherited from BaseRepository.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.catalog import Categoria
from app.repositories.base import BaseRepository


@dataclass
class CategoriaTreeRow:
    """A flat row returned by get_tree() with a virtual depth column.

    All attributes mirror Categoria columns plus the computed depth.
    """

    id: uuid.UUID
    nombre: str
    descripcion: str | None
    parent_id: uuid.UUID | None
    depth: int


class CategoriaRepository(BaseRepository[Categoria]):
    """Repository for the Categoria entity with tree/CTE operations."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Categoria, session)

    # -------------------------------------------------------------------------
    # Tree retrieval
    # -------------------------------------------------------------------------

    async def get_tree(self) -> list[CategoriaTreeRow]:
        """Return all active categories as a flat list with virtual depth column.

        Uses a recursive CTE to traverse the tree breadth-first (ordered by
        depth then nombre). Only active (deleted_at IS NULL) rows appear in
        both the anchor and recursive steps.

        Root categories have depth = 1. Their direct children have depth = 2, etc.
        The safety guard depth < 10 prevents infinite loops on corrupted data.

        Returns:
            List of CategoriaTreeRow dataclass instances with id, nombre,
            descripcion, parent_id, and depth attributes.
        """
        sql = text("""
            WITH RECURSIVE tree AS (
                SELECT id, nombre, descripcion, parent_id, 1 AS depth
                FROM categoria
                WHERE parent_id IS NULL
                  AND deleted_at IS NULL

                UNION ALL

                SELECT c.id, c.nombre, c.descripcion, c.parent_id, t.depth + 1
                FROM categoria c
                JOIN tree t ON c.parent_id = t.id
                WHERE c.deleted_at IS NULL
                  AND t.depth < 10
            )
            SELECT id, nombre, descripcion, parent_id, depth
            FROM tree
            ORDER BY depth, nombre
        """)

        result = await self.session.execute(sql)
        rows = result.fetchall()

        return [
            CategoriaTreeRow(
                id=row.id,
                nombre=row.nombre,
                descripcion=row.descripcion,
                parent_id=row.parent_id,
                depth=row.depth,
            )
            for row in rows
        ]

    # -------------------------------------------------------------------------
    # Cycle detection
    # -------------------------------------------------------------------------

    async def would_create_cycle(
        self,
        category_id: uuid.UUID,
        new_parent_id: uuid.UUID,
    ) -> bool:
        """Return True if assigning new_parent_id as parent of category_id creates a cycle.

        Executes a recursive CTE starting from category_id and traversing all
        descendants. Filters deleted_at IS NULL in BOTH anchor and recursive step.
        The depth guard (depth < 10) ensures termination even on corrupted cyclic data.

        A cycle exists if new_parent_id appears in the descendant set of category_id.

        Args:
            category_id: The category being reparented.
            new_parent_id: The proposed new parent UUID.

        Returns:
            True if assigning new_parent_id would create a cycle, False otherwise.
        """
        # EXPLAIN ANALYZE: CTE is O(subtree_size). Max depth is 5, so at most
        # 5 recursive steps in production data. The depth < 10 guard adds safety
        # against corrupted data without impacting normal traversal.
        sql = text("""
            WITH RECURSIVE descendants AS (
                SELECT id, 1 AS depth
                FROM categoria
                WHERE id = :category_id
                  AND deleted_at IS NULL

                UNION ALL

                SELECT c.id, d.depth + 1
                FROM categoria c
                JOIN descendants d ON c.parent_id = d.id
                WHERE c.deleted_at IS NULL
                  AND d.depth < 10
            )
            SELECT EXISTS (
                SELECT 1 FROM descendants WHERE id = :new_parent_id
            ) AS would_cycle
        """)

        result = await self.session.execute(
            sql,
            {"category_id": category_id, "new_parent_id": new_parent_id},
        )
        return bool(result.scalar())

    # -------------------------------------------------------------------------
    # Count queries
    # -------------------------------------------------------------------------

    async def count_active_children(self, category_id: uuid.UUID) -> int:
        """Return the count of active direct subcategories.

        Args:
            category_id: The parent category UUID.

        Returns:
            Integer count of non-soft-deleted direct children.
        """
        sql = text("""
            SELECT COUNT(*)
            FROM categoria
            WHERE parent_id = :id
              AND deleted_at IS NULL
        """)
        result = await self.session.execute(sql, {"id": category_id})
        return int(result.scalar() or 0)

    async def count_active_products(self, category_id: uuid.UUID) -> int:
        """Return the count of active products linked to this category.

        Joins producto_categoria → producto and filters on producto.deleted_at IS NULL.

        # Guard active post Change 11: returns 0 until producto_categoria is
        # populated (Change 11 — catalog-products-management). The guard is
        # correct and will activate automatically once product data exists.

        Args:
            category_id: The category UUID to check for linked products.

        Returns:
            Integer count of active products (0 until Change 11 populates data).
        """
        sql = text("""
            SELECT COUNT(*)
            FROM producto_categoria pc
            JOIN producto p ON p.id = pc.producto_id
            WHERE pc.categoria_id = :id
              AND p.deleted_at IS NULL
        """)
        result = await self.session.execute(sql, {"id": category_id})
        return int(result.scalar() or 0)

    # -------------------------------------------------------------------------
    # Depth queries
    # -------------------------------------------------------------------------

    async def get_depth(self, category_id: uuid.UUID) -> int:
        """Return the depth of a category (1 = root, 2 = child of root, etc.).

        Uses an ancestor-traversal CTE that walks UP the tree from category_id.
        This is O(depth) — significantly cheaper than get_tree() which is O(n).
        The safety guard depth < 10 ensures termination on corrupted data.

        Args:
            category_id: The category UUID to measure depth for.

        Returns:
            Depth integer (1 for root categories). Returns 0 if not found.
        """
        sql = text("""
            WITH RECURSIVE ancestors AS (
                SELECT id, parent_id, 1 AS depth
                FROM categoria
                WHERE id = :category_id
                  AND deleted_at IS NULL

                UNION ALL

                SELECT c.id, c.parent_id, a.depth + 1
                FROM categoria c
                JOIN ancestors a ON c.id = a.parent_id
                WHERE c.deleted_at IS NULL
                  AND a.depth < 10
            )
            SELECT MAX(depth) FROM ancestors
        """)
        result = await self.session.execute(sql, {"category_id": category_id})
        return int(result.scalar() or 0)

    async def get_subtree_height(self, category_id: uuid.UUID) -> int:
        """Return the max relative depth of the subtree rooted at category_id.

        Leaf nodes return 0. A node with one level of children returns 1.
        A node with children and grandchildren returns 2. This is used to
        validate that reparenting a subtree won't exceed the max depth of 5.

        Uses a recursive CTE descending from category_id.
        The safety guard relative_depth < 10 prevents infinite loops on
        corrupted data.

        Args:
            category_id: The root of the subtree to measure.

        Returns:
            Maximum relative depth (0 for leaf nodes).
        """
        sql = text("""
            WITH RECURSIVE subtree AS (
                SELECT id, 0 AS relative_depth
                FROM categoria
                WHERE id = :category_id
                  AND deleted_at IS NULL

                UNION ALL

                SELECT c.id, s.relative_depth + 1
                FROM categoria c
                JOIN subtree s ON c.parent_id = s.id
                WHERE c.deleted_at IS NULL
                  AND s.relative_depth < 10
            )
            SELECT COALESCE(MAX(relative_depth), 0) FROM subtree
        """)
        result = await self.session.execute(sql, {"category_id": category_id})
        return int(result.scalar() or 0)
