"""
Unit/integration tests for CategoriaRepository.

TDD: tests written before implementation.
Uses the SAVEPOINT-based async_session fixture from conftest.py.
All DB mutations are rolled back after each test.
"""

from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from sqlalchemy.exc import IntegrityError

from app.models.catalog import Categoria
from app.repositories.categoria import CategoriaRepository


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_categoria(nombre: str, parent_id: uuid.UUID | None = None) -> Categoria:
    """Build an unsaved Categoria for testing."""
    return Categoria(nombre=nombre, parent_id=parent_id)


# ---------------------------------------------------------------------------
# Task 2.1 — get_tree returns flat rows with depth
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_tree_returns_flat_rows_with_depth(async_session) -> None:
    """get_tree() returns flat rows with virtual depth column (root = 1).

    Note: get_tree() returns ALL active categories in the DB, not just those
    created in this test. We verify the rows we created have correct depth
    values by looking them up by id rather than asserting total count.
    """
    repo = CategoriaRepository(async_session)

    root = await repo.create(_make_categoria(f"GetTreeRoot_{uuid.uuid4().hex[:8]}"))
    child1 = await repo.create(_make_categoria(f"GetTreeChild1_{uuid.uuid4().hex[:8]}", parent_id=root.id))
    child2 = await repo.create(_make_categoria(f"GetTreeChild2_{uuid.uuid4().hex[:8]}", parent_id=root.id))

    rows = await repo.get_tree()

    # Get our specific rows by ID (don't assume total count — table may have other rows)
    row_by_id = {r.id: r for r in rows}

    assert root.id in row_by_id, "Root category not found in get_tree() results"
    assert child1.id in row_by_id, "Child1 not found in get_tree() results"
    assert child2.id in row_by_id, "Child2 not found in get_tree() results"

    root_row = row_by_id[root.id]
    child1_row = row_by_id[child1.id]
    child2_row = row_by_id[child2.id]

    assert root_row.depth == 1
    assert child1_row.depth == 2
    assert child2_row.depth == 2


@pytest.mark.asyncio
async def test_get_tree_excludes_soft_deleted(async_session) -> None:
    """get_tree() excludes soft-deleted categories and their children."""
    repo = CategoriaRepository(async_session)

    root = await repo.create(_make_categoria(f"ActiveRoot_{uuid.uuid4().hex[:8]}"))
    ghost = await repo.create(_make_categoria(f"GhostParent_{uuid.uuid4().hex[:8]}"))
    # Child of ghost — should also be absent since CTE filters deleted_at
    _ghost_child = await repo.create(_make_categoria(f"GhostChild_{uuid.uuid4().hex[:8]}", parent_id=ghost.id))

    # Soft-delete ghost (its child has a ghost parent, won't appear in CTE)
    await repo.soft_delete(ghost.id)

    rows = await repo.get_tree()

    ids = {r.id for r in rows}
    assert root.id in ids
    assert ghost.id not in ids
    # ghost_child has parent that is deleted — CTE join on active parent excludes it
    assert _ghost_child.id not in ids


# ---------------------------------------------------------------------------
# Task 2.2 — would_create_cycle detects direct cycle
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_would_create_cycle_detects_direct_cycle(async_session) -> None:
    """would_create_cycle(A, B) returns True when B is a child of A."""
    repo = CategoriaRepository(async_session)

    a = await repo.create(_make_categoria("A"))
    b = await repo.create(_make_categoria("B", parent_id=a.id))

    # Making B the parent of A would create A→B→A
    result = await repo.would_create_cycle(a.id, b.id)
    assert result is True


# ---------------------------------------------------------------------------
# Task 2.3 — would_create_cycle returns False for valid reparent
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_would_create_cycle_returns_false_for_valid_reparent(async_session) -> None:
    """would_create_cycle returns False for unrelated categories."""
    repo = CategoriaRepository(async_session)

    a = await repo.create(_make_categoria("UnrelatedA"))
    b = await repo.create(_make_categoria("UnrelatedB"))

    result = await repo.would_create_cycle(a.id, b.id)
    assert result is False


# ---------------------------------------------------------------------------
# Task 2.3b — would_create_cycle ignores soft-deleted intermediate nodes
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_would_create_cycle_ignores_soft_deleted_intermediate_nodes(async_session) -> None:
    """CTE must filter deleted_at IS NULL on intermediate hops.

    Chain: A → B(soft-deleted) → C
    Reparenting C under A: should NOT create a cycle since B is deleted.
    But A → B → C (all active) SHOULD be a cycle.
    """
    repo = CategoriaRepository(async_session)

    # Case 1: A → B(deleted) → C — reparent C under A should NOT be cycle
    a1 = await repo.create(_make_categoria("CycleA1"))
    b1 = await repo.create(_make_categoria("CycleB1", parent_id=a1.id))
    c1 = await repo.create(_make_categoria("CycleC1", parent_id=b1.id))
    await repo.soft_delete(b1.id)

    # C1 has parent B1 (deleted), which has parent A1 — but B1 is deleted
    # so the CTE won't traverse from A1 to B1 to C1
    result_no_cycle = await repo.would_create_cycle(a1.id, c1.id)
    assert result_no_cycle is False, "Should not detect cycle through deleted intermediate"

    # Case 2: A → B → C (all active) — reparent A under C would create cycle
    a2 = await repo.create(_make_categoria("CycleA2"))
    b2 = await repo.create(_make_categoria("CycleB2", parent_id=a2.id))
    c2 = await repo.create(_make_categoria("CycleC2", parent_id=b2.id))

    result_cycle = await repo.would_create_cycle(a2.id, c2.id)
    assert result_cycle is True, "Should detect real cycle through active chain"


# ---------------------------------------------------------------------------
# Task 2.4 — get_depth returns 1 for root
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_depth_returns_1_for_root(async_session) -> None:
    """get_depth returns 1 for a root category (parent_id IS NULL)."""
    repo = CategoriaRepository(async_session)
    root = await repo.create(_make_categoria("DepthRoot"))

    depth = await repo.get_depth(root.id)
    assert depth == 1


# ---------------------------------------------------------------------------
# Task 2.5 — get_depth returns correct depth for nested
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_depth_returns_correct_depth_for_nested(async_session) -> None:
    """get_depth returns 3 for a grandchild category."""
    repo = CategoriaRepository(async_session)

    root = await repo.create(_make_categoria("DepthRootL1"))
    child = await repo.create(_make_categoria("DepthChildL2", parent_id=root.id))
    grandchild = await repo.create(_make_categoria("DepthGrandL3", parent_id=child.id))

    assert await repo.get_depth(root.id) == 1
    assert await repo.get_depth(child.id) == 2
    assert await repo.get_depth(grandchild.id) == 3


# ---------------------------------------------------------------------------
# Task 2.6 — count_active_children counts only active
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_count_active_children_counts_only_active(async_session) -> None:
    """count_active_children only counts non-soft-deleted direct children."""
    repo = CategoriaRepository(async_session)

    parent = await repo.create(_make_categoria("CountParent"))
    _active1 = await repo.create(_make_categoria("ActiveChild1", parent_id=parent.id))
    _active2 = await repo.create(_make_categoria("ActiveChild2", parent_id=parent.id))
    deleted_child = await repo.create(_make_categoria("DeletedChild", parent_id=parent.id))
    await repo.soft_delete(deleted_child.id)

    count = await repo.count_active_children(parent.id)
    assert count == 2


# ---------------------------------------------------------------------------
# Task 2.7 — partial unique index via repository
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_partial_unique_index_via_repository(async_session) -> None:
    """Two categories with same nombre under same parent raise IntegrityError."""
    repo = CategoriaRepository(async_session)

    parent = await repo.create(_make_categoria("UniqueParent"))
    await repo.create(_make_categoria("DupName", parent_id=parent.id))

    with pytest.raises(IntegrityError):
        await repo.create(_make_categoria("DupName", parent_id=parent.id))


# ---------------------------------------------------------------------------
# Task 2.14 — get_subtree_height returns 0 for leaf (TDD)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_subtree_height_returns_0_for_leaf(async_session) -> None:
    """get_subtree_height returns 0 for a leaf node (no children)."""
    repo = CategoriaRepository(async_session)

    leaf = await repo.create(_make_categoria("LeafNode"))
    height = await repo.get_subtree_height(leaf.id)
    assert height == 0


# ---------------------------------------------------------------------------
# Task 2.15 — get_subtree_height returns 2 for node with grandchildren (TDD)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_subtree_height_returns_2_for_node_with_grandchildren(async_session) -> None:
    """get_subtree_height returns 2 for node with children and grandchildren."""
    repo = CategoriaRepository(async_session)

    root = await repo.create(_make_categoria("HeightRoot"))
    child = await repo.create(_make_categoria("HeightChild", parent_id=root.id))
    _grandchild = await repo.create(_make_categoria("HeightGrand", parent_id=child.id))

    # root subtree has height 2 (root→child→grandchild = 2 relative levels)
    assert await repo.get_subtree_height(root.id) == 2
    # child subtree has height 1
    assert await repo.get_subtree_height(child.id) == 1
    # grandchild subtree (leaf) has height 0
    assert await repo.get_subtree_height(_grandchild.id) == 0
