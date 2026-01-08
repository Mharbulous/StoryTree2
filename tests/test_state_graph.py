# .storytree/gui/tests/test_state_graph.py
import pytest
from ..state_graph import StateNode, NODES, EDGES, STAGE_COLORS


def test_node_has_required_fields():
    node = StateNode(id="concept_nohold", label="concept:no_hold", stage="concept", x=100, y=50)
    assert node.id == "concept_nohold"
    assert node.label == "concept:no_hold"
    assert node.stage == "concept"
    assert node.x == 100
    assert node.y == 50


def test_nodes_dict_contains_all_27_states():
    assert len(NODES) == 27
    assert "concept_nohold" in NODES
    assert "shipped" in NODES


def test_edges_reference_valid_nodes():
    """All edges should reference nodes that exist in NODES."""
    for source_id, target_id, label in EDGES:
        assert source_id in NODES, f"Edge source '{source_id}' not found in NODES"
        assert target_id in NODES, f"Edge target '{target_id}' not found in NODES"


def test_stage_colors_exist_for_all_stages():
    """All stages used in nodes should have colors defined."""
    stages_used = {node.stage for node in NODES.values()}
    for stage in stages_used:
        assert stage in STAGE_COLORS, f"Stage '{stage}' missing from STAGE_COLORS"


def test_nodes_grouped_by_stage_correctly():
    """Verify node counts per stage match expected values."""
    stage_counts = {}
    for node in NODES.values():
        stage_counts[node.stage] = stage_counts.get(node.stage, 0) + 1

    # From state-transitions-flat-L.md summary table
    assert stage_counts["concept"] == 7
    assert stage_counts["planning"] == 5
    assert stage_counts["implementing"] == 5
    assert stage_counts["testing"] == 4
    assert stage_counts["releasing"] == 5
    assert stage_counts["shipped"] == 1
