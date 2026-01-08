# .storytree/gui/tests/test_interactive_diagram.py
"""Tests for the interactive state diagram with draggable nodes."""
import pytest
from PySide6.QtWidgets import QApplication, QGraphicsScene
from PySide6.QtCore import QPointF
from ..interactive_diagram import DraggableNode, EdgePath, InteractiveStateDiagram
from ..state_graph import STAGE_COLORS, NODES, EDGES


@pytest.fixture(scope="module")
def app():
    """Provide QApplication instance for Qt widget tests."""
    return QApplication.instance() or QApplication([])


def test_draggable_node_is_movable(app):
    """DraggableNode should be positioned correctly and have movable flag."""
    from PySide6.QtWidgets import QGraphicsItem
    scene = QGraphicsScene()
    node = DraggableNode("test_id", "Test Label", "concept", 100, 50, 120, 40)
    scene.addItem(node)

    assert node.pos().x() == 100
    assert node.pos().y() == 50
    assert node.flags() & QGraphicsItem.ItemIsMovable


def test_draggable_node_has_stage_color(app):
    """DraggableNode should use the correct stage color from STAGE_COLORS."""
    scene = QGraphicsScene()
    node = DraggableNode("test_id", "Test Label", "concept", 0, 0, 120, 40)
    scene.addItem(node)

    brush = node.brush()
    expected_color = STAGE_COLORS["concept"]
    assert brush.color().name() == expected_color.lower()


def test_edge_connects_two_nodes(app):
    """EdgePath should register with both source and target nodes."""
    scene = QGraphicsScene()
    source = DraggableNode("a", "A", "concept", 0, 0, 100, 40)
    target = DraggableNode("b", "B", "planning", 200, 100, 100, 40)
    scene.addItem(source)
    scene.addItem(target)

    edge = EdgePath(source, target, "transition")
    scene.addItem(edge)

    # Edge should be registered with both nodes
    assert edge in source.edges
    assert edge in target.edges


def test_edge_updates_when_node_moves(app):
    """EdgePath should update its path when a connected node moves."""
    scene = QGraphicsScene()
    source = DraggableNode("a", "A", "concept", 0, 0, 100, 40)
    target = DraggableNode("b", "B", "planning", 200, 100, 100, 40)
    scene.addItem(source)
    scene.addItem(target)

    edge = EdgePath(source, target, "transition")
    scene.addItem(edge)

    path_before = edge.path()

    # Move source node
    source.setPos(50, 50)

    # Path should have been updated
    path_after = edge.path()
    assert path_before != path_after


def test_interactive_diagram_creates_all_nodes(app):
    """InteractiveStateDiagram should create all 27 nodes from state_graph."""
    diagram = InteractiveStateDiagram()
    scene = diagram.scene()

    # Count DraggableNode items
    node_count = sum(1 for item in scene.items() if isinstance(item, DraggableNode))
    assert node_count == 27


def test_interactive_diagram_creates_all_edges(app):
    """InteractiveStateDiagram should create all edges from state_graph."""
    diagram = InteractiveStateDiagram()
    scene = diagram.scene()

    # Count EdgePath items
    edge_count = sum(1 for item in scene.items() if isinstance(item, EdgePath))
    assert edge_count == len(EDGES)


def test_state_diagram_dialog_uses_interactive_view(app):
    """StateDiagramDialog should use InteractiveStateDiagram instead of static SVG."""
    from ..xstory import StateDiagramDialog

    dialog = StateDiagramDialog()
    # Find InteractiveStateDiagram widget in dialog
    interactive = dialog.findChild(InteractiveStateDiagram)
    assert interactive is not None


def test_edge_has_arrow_head(app):
    """EdgePath should have a QGraphicsPolygonItem arrow head as child."""
    from PySide6.QtWidgets import QGraphicsPolygonItem

    scene = QGraphicsScene()
    source = DraggableNode("a", "A", "concept", 0, 0, 100, 40)
    target = DraggableNode("b", "B", "planning", 200, 100, 100, 40)
    scene.addItem(source)
    scene.addItem(target)

    edge = EdgePath(source, target, "transition")
    scene.addItem(edge)

    # Edge should have arrow polygon child item
    children = edge.childItems()
    assert len(children) > 0, "EdgePath should have at least one child item (arrow head)"

    # Verify the child is a QGraphicsPolygonItem
    arrow_heads = [c for c in children if isinstance(c, QGraphicsPolygonItem)]
    assert len(arrow_heads) == 1, "EdgePath should have exactly one QGraphicsPolygonItem arrow head"


def test_edge_arrow_head_updates_when_node_moves(app):
    """Arrow head should update position when connected node moves."""
    from PySide6.QtWidgets import QGraphicsPolygonItem

    scene = QGraphicsScene()
    source = DraggableNode("a", "A", "concept", 0, 0, 100, 40)
    target = DraggableNode("b", "B", "planning", 200, 100, 100, 40)
    scene.addItem(source)
    scene.addItem(target)

    edge = EdgePath(source, target, "transition")
    scene.addItem(edge)

    # Get initial arrow position
    arrow_before = [c for c in edge.childItems() if isinstance(c, QGraphicsPolygonItem)][0]
    polygon_before = arrow_before.polygon()

    # Move source node - this triggers update_path() via itemChange
    source.setPos(50, 50)

    # Arrow should have been updated (new arrow created)
    arrow_after = [c for c in edge.childItems() if isinstance(c, QGraphicsPolygonItem)][0]
    polygon_after = arrow_after.polygon()

    # The polygon points should be different due to the direction change
    assert polygon_before != polygon_after, "Arrow head should update when node moves"


def test_sugiyama_layout_method_exists(app):
    """InteractiveStateDiagram should have a sugiyama_layout method."""
    diagram = InteractiveStateDiagram()
    assert hasattr(diagram, 'sugiyama_layout')
    assert callable(diagram.sugiyama_layout)


def test_sugiyama_groups_nodes_by_stage(app):
    """sugiyama_layout should group nodes into layers by stage."""
    diagram = InteractiveStateDiagram()

    # Get initial Y positions - they vary within stages
    initial_ys = {nid: node.pos().y() for nid, node in diagram._nodes.items()}

    diagram.sugiyama_layout()

    # After layout, nodes in same stage should have same Y
    stage_ys = {}
    for node_id, node in diagram._nodes.items():
        stage = node.stage
        y = node.pos().y()
        if stage not in stage_ys:
            stage_ys[stage] = y
        else:
            assert abs(stage_ys[stage] - y) < 1, f"Nodes in stage {stage} should have same Y"


def test_sugiyama_orders_nodes_to_reduce_crossings(app):
    """sugiyama_layout should order nodes within layers to reduce edge crossings."""
    diagram = InteractiveStateDiagram()
    diagram.sugiyama_layout()

    # Nodes should be spread horizontally within their layer
    for stage in ["concept", "planning", "implementing", "testing", "releasing"]:
        nodes_in_stage = [n for n in diagram._nodes.values() if n.stage == stage]
        if len(nodes_in_stage) > 1:
            xs = sorted([n.pos().x() for n in nodes_in_stage])
            # Check nodes are spread out (not stacked)
            for i in range(1, len(xs)):
                assert xs[i] - xs[i-1] >= 100, f"Nodes in {stage} should be spread horizontally"


def test_state_diagram_dialog_has_sort_button(app):
    """StateDiagramDialog should have a Sort button in the header."""
    from PySide6.QtWidgets import QPushButton
    from ..xstory import StateDiagramDialog

    dialog = StateDiagramDialog()

    # Find Sort button
    sort_buttons = [w for w in dialog.findChildren(QPushButton) if w.text() == "Sort"]
    assert len(sort_buttons) == 1, "Should have exactly one Sort button"


def test_sort_button_triggers_sugiyama_layout(app):
    """Clicking Sort button should rearrange nodes."""
    from ..xstory import StateDiagramDialog
    from PySide6.QtWidgets import QPushButton

    dialog = StateDiagramDialog()
    diagram = dialog.diagram_view

    # Manually move a node to a weird position
    test_node = diagram._nodes.get("concept_nohold")
    if test_node:
        test_node.setPos(999, 999)

    # Click Sort button
    sort_btn = [w for w in dialog.findChildren(QPushButton) if w.text() == "Sort"][0]
    sort_btn.click()

    # Node should have been repositioned (not at 999, 999)
    if test_node:
        assert test_node.pos().x() != 999 or test_node.pos().y() != 999


def test_force_directed_layout_method_exists(app):
    """InteractiveStateDiagram should have a force_directed_layout method."""
    diagram = InteractiveStateDiagram()
    assert hasattr(diagram, 'force_directed_layout')
    assert callable(diagram.force_directed_layout)


def test_force_directed_layout_fixes_y_by_stage(app):
    """force_directed_layout should position nodes with Y fixed by stage layer."""
    diagram = InteractiveStateDiagram()

    diagram.force_directed_layout()

    # Check that nodes in same stage have same Y position
    stage_ys = {}
    for node_id, node in diagram._nodes.items():
        stage = node.stage
        y = node.pos().y()
        if stage not in stage_ys:
            stage_ys[stage] = y
        else:
            assert abs(stage_ys[stage] - y) < 1, f"Nodes in stage {stage} should have same Y"


def test_force_directed_layout_spreads_nodes_horizontally(app):
    """force_directed_layout should spread nodes horizontally within each layer."""
    diagram = InteractiveStateDiagram()
    diagram.force_directed_layout()

    # Nodes should be spread horizontally within their layer
    for stage in ["concept", "planning", "implementing", "testing", "releasing"]:
        nodes_in_stage = [n for n in diagram._nodes.values() if n.stage == stage]
        if len(nodes_in_stage) > 1:
            xs = sorted([n.pos().x() for n in nodes_in_stage])
            # Check nodes are spread out (minimum 50px apart for force-directed)
            for i in range(1, len(xs)):
                assert xs[i] - xs[i-1] >= 50, f"Nodes in {stage} should be spread horizontally"
