"""Interactive state diagram with draggable nodes."""
import math

from PySide6.QtWidgets import (
    QGraphicsRectItem, QGraphicsTextItem, QGraphicsItem, QGraphicsPathItem,
    QGraphicsView, QGraphicsScene, QGraphicsPolygonItem
)
from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import QBrush, QPen, QColor, QFont, QPainterPath, QPainter, QPolygonF

try:
    from .state_graph import STAGE_COLORS, NODES, EDGES
except ImportError:
    from state_graph import STAGE_COLORS, NODES, EDGES


class DraggableNode(QGraphicsRectItem):
    """A draggable rectangle representing a state node."""

    def __init__(self, node_id: str, label: str, stage: str, x: float, y: float, width: float = 120, height: float = 40):
        super().__init__(0, 0, width, height)
        self.node_id = node_id
        self.label = label
        self.stage = stage
        self.edges = []  # Connected edges to update on move

        # Position
        self.setPos(x, y)

        # Make draggable
        self.setFlag(QGraphicsItem.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges, True)

        # Styling
        color = QColor(STAGE_COLORS.get(stage, "#888888"))
        self.setBrush(QBrush(color))
        self.setPen(QPen(color.darker(120), 2))

        # Label text (centered)
        self._text = QGraphicsTextItem(label, self)
        self._text.setDefaultTextColor(Qt.white)
        font = QFont("Arial", 8)
        self._text.setFont(font)
        # Center text
        text_rect = self._text.boundingRect()
        self._text.setPos(
            (width - text_rect.width()) / 2,
            (height - text_rect.height()) / 2
        )

    def itemChange(self, change, value):
        """Update connected edges when node moves."""
        if change == QGraphicsItem.ItemPositionHasChanged:
            for edge in self.edges:
                edge.update_path()
        return super().itemChange(change, value)


class EdgePath(QGraphicsPathItem):
    """A path connecting two nodes that updates when nodes move."""

    def __init__(self, source: DraggableNode, target: DraggableNode, label: str = ""):
        super().__init__()
        self.source = source
        self.target = target
        self.label = label
        self._arrow = None

        # Register with nodes for position updates
        source.edges.append(self)
        target.edges.append(self)

        # Styling
        self.setPen(QPen(QColor("#666666"), 2))

        # Initial path
        self.update_path()

    def update_path(self):
        """Recalculate path from source edge to target edge with arrow."""
        path = QPainterPath()

        # Get bounding rectangles
        source_rect = self.source.sceneBoundingRect()
        target_rect = self.target.sceneBoundingRect()

        source_center = source_rect.center()
        target_center = target_rect.center()

        # Determine connection points on the edges of each node
        start = self._get_edge_point(source_rect, target_center)
        end = self._get_edge_point(target_rect, source_center)

        path.moveTo(start)
        path.lineTo(end)

        self.setPath(path)

        # Update arrow head
        self._update_arrow(start, end)

    def _get_edge_point(self, rect: QRectF, toward: QPointF) -> QPointF:
        """Get the midpoint of the rect side closest to the 'toward' point."""
        center = rect.center()
        dx = toward.x() - center.x()
        dy = toward.y() - center.y()

        # Determine which side is closest based on direction to target
        # Compare aspect-adjusted deltas to pick horizontal vs vertical side
        half_width = rect.width() / 2
        half_height = rect.height() / 2

        # Normalize by dimensions to handle non-square nodes
        if half_width > 0 and half_height > 0:
            norm_dx = abs(dx) / half_width
            norm_dy = abs(dy) / half_height
        else:
            norm_dx = abs(dx)
            norm_dy = abs(dy)

        if norm_dx > norm_dy:
            # Horizontal edge (left or right side)
            if dx > 0:
                # Target is to the right, use right side
                return QPointF(rect.right(), center.y())
            else:
                # Target is to the left, use left side
                return QPointF(rect.left(), center.y())
        else:
            # Vertical edge (top or bottom side)
            if dy > 0:
                # Target is below, use bottom side
                return QPointF(center.x(), rect.bottom())
            else:
                # Target is above, use top side
                return QPointF(center.x(), rect.top())

    def _update_arrow(self, start: QPointF, end: QPointF):
        """Draw arrow head at end point."""
        # Remove old arrow if it exists
        if self._arrow is not None:
            # Remove from scene if it has one
            if self._arrow.scene() is not None:
                self._arrow.scene().removeItem(self._arrow)
            self._arrow = None

        # Calculate arrow direction
        dx = end.x() - start.x()
        dy = end.y() - start.y()
        length = math.sqrt(dx * dx + dy * dy)
        if length == 0:
            return

        # Normalize direction vector
        dx /= length
        dy /= length

        # Arrow size
        arrow_size = 10

        # Arrow points: tip at end, two wings perpendicular to line
        p1 = end  # Arrow tip
        p2 = QPointF(
            end.x() - arrow_size * dx + arrow_size * 0.5 * dy,
            end.y() - arrow_size * dy - arrow_size * 0.5 * dx
        )
        p3 = QPointF(
            end.x() - arrow_size * dx - arrow_size * 0.5 * dy,
            end.y() - arrow_size * dy + arrow_size * 0.5 * dx
        )

        polygon = QPolygonF([p1, p2, p3])
        self._arrow = QGraphicsPolygonItem(polygon, self)  # self as parent
        self._arrow.setBrush(QBrush(QColor("#666666")))
        self._arrow.setPen(QPen(Qt.NoPen))


class InteractiveStateDiagram(QGraphicsView):
    """QGraphicsView displaying the full interactive state diagram."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)

        # View settings
        self.setRenderHint(QPainter.Antialiasing)
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.setBackgroundBrush(QBrush(QColor("#ffffff")))

        # Build diagram
        self._nodes = {}
        self._build_nodes()
        self._build_edges()

    def _build_nodes(self):
        """Create DraggableNode for each state."""
        for node_id, node_data in NODES.items():
            node = DraggableNode(
                node_id=node_data.id,
                label=node_data.label,
                stage=node_data.stage,
                x=node_data.x,
                y=node_data.y,
                width=140,
                height=35
            )
            self._scene.addItem(node)
            self._nodes[node_id] = node

    def _build_edges(self):
        """Create EdgePath for each transition."""
        for source_id, target_id, label in EDGES:
            if source_id in self._nodes and target_id in self._nodes:
                edge = EdgePath(
                    self._nodes[source_id],
                    self._nodes[target_id],
                    label
                )
                self._scene.addItem(edge)

    def sugiyama_layout(self):
        """Apply Sugiyama algorithm to arrange nodes with minimal edge crossings.

        Extended to handle intra-layer edges (same-stage transitions).
        """
        import random

        stage_order = ["concept", "planning", "implementing", "testing", "releasing", "shipped"]
        stage_index = {stage: i for i, stage in enumerate(stage_order)}
        layers = [[] for _ in stage_order]

        # Phase 1: Layer assignment
        node_to_layer = {}
        for node_id, node in self._nodes.items():
            if node.stage in stage_index:
                layer_idx = stage_index[node.stage]
                layers[layer_idx].append(node)
                node_to_layer[node] = layer_idx

        # Collect ALL edges (including intra-layer)
        all_edges = []
        for item in self._scene.items():
            if isinstance(item, EdgePath):
                all_edges.append((item.source, item.target))

        # Separate intra-layer and inter-layer edges
        intra_layer_edges = {}  # layer_idx -> [(src, tgt)]
        inter_layer_edges = []

        for src, tgt in all_edges:
            src_l = node_to_layer.get(src)
            tgt_l = node_to_layer.get(tgt)
            if src_l is None or tgt_l is None:
                continue
            if src_l == tgt_l:
                # Intra-layer edge
                if src_l not in intra_layer_edges:
                    intra_layer_edges[src_l] = []
                intra_layer_edges[src_l].append((src, tgt))
            else:
                inter_layer_edges.append((src, tgt))

        # Phase 2: Insert dummy nodes for long inter-layer edges
        class DummyNode:
            def __init__(self, layer_idx, stage):
                self.layer_idx = layer_idx
                self.stage = stage
                self.is_dummy = True

        dummy_nodes = []
        expanded_edges = []

        for source, target in inter_layer_edges:
            src_layer = node_to_layer[source]
            tgt_layer = node_to_layer[target]

            if src_layer > tgt_layer:
                source, target = target, source
                src_layer, tgt_layer = tgt_layer, src_layer

            if tgt_layer - src_layer <= 1:
                expanded_edges.append((source, target))
            else:
                prev_node = source
                for layer_idx in range(src_layer + 1, tgt_layer):
                    dummy = DummyNode(layer_idx, stage_order[layer_idx])
                    dummy_nodes.append(dummy)
                    layers[layer_idx].append(dummy)
                    node_to_layer[dummy] = layer_idx
                    expanded_edges.append((prev_node, dummy))
                    prev_node = dummy
                expanded_edges.append((prev_node, target))

        # Build layer-pair edge lists for inter-layer crossing counting
        layer_pair_edges = {}
        for src, tgt in expanded_edges:
            src_l = node_to_layer[src]
            tgt_l = node_to_layer[tgt]
            if src_l > tgt_l:
                src, tgt = tgt, src
                src_l, tgt_l = tgt_l, src_l
            if tgt_l == src_l + 1:
                key = (src_l, tgt_l)
                if key not in layer_pair_edges:
                    layer_pair_edges[key] = []
                layer_pair_edges[key].append((src, tgt))

        def count_crossings(node_x_order):
            """Count total crossings: inter-layer + intra-layer."""
            total = 0

            # Inter-layer crossings
            for edge_list in layer_pair_edges.values():
                for i, (s1, t1) in enumerate(edge_list):
                    for s2, t2 in edge_list[i+1:]:
                        x_s1 = node_x_order.get(s1, 0)
                        x_s2 = node_x_order.get(s2, 0)
                        x_t1 = node_x_order.get(t1, 0)
                        x_t2 = node_x_order.get(t2, 0)
                        if (x_s1 < x_s2 and x_t1 > x_t2) or (x_s1 > x_s2 and x_t1 < x_t2):
                            total += 1

            # Intra-layer crossings (edges within same layer)
            for layer_idx, edge_list in intra_layer_edges.items():
                for i, (s1, t1) in enumerate(edge_list):
                    for s2, t2 in edge_list[i+1:]:
                        x_s1 = node_x_order.get(s1, 0)
                        x_s2 = node_x_order.get(s2, 0)
                        x_t1 = node_x_order.get(t1, 0)
                        x_t2 = node_x_order.get(t2, 0)
                        # Intra-layer crossing: edges cross if ranges overlap improperly
                        min1, max1 = min(x_s1, x_t1), max(x_s1, x_t1)
                        min2, max2 = min(x_s2, x_t2), max(x_s2, x_t2)
                        # They cross if one starts inside the other's range but ends outside
                        if min1 < min2 < max1 < max2 or min2 < min1 < max2 < max1:
                            total += 1

            return total

        # Build adjacency for barycenter
        all_nodes = list(self._nodes.values()) + dummy_nodes
        adjacency = {node: [] for node in all_nodes}
        for src, tgt in expanded_edges:
            adjacency[src].append(tgt)
            adjacency[tgt].append(src)
        # Include intra-layer edges in adjacency
        for edge_list in intra_layer_edges.values():
            for src, tgt in edge_list:
                adjacency[src].append(tgt)
                adjacency[tgt].append(src)

        # Phase 3: Multi-start optimization
        # First, capture the original order and its crossing count
        original_order = {}
        for layer_idx, layer in enumerate(layers):
            sorted_layer = sorted(layer, key=lambda n: n.pos().x() if hasattr(n, 'pos') else 0)
            for i, node in enumerate(sorted_layer):
                original_order[node] = i

        original_crossings = count_crossings(original_order)
        best_order = dict(original_order)
        best_crossings = original_crossings

        for trial in range(10):  # Try different initializations
            node_x_order = {}

            for layer_idx, layer in enumerate(layers):
                if trial == 0:
                    sorted_layer = sorted(layer, key=lambda n: n.pos().x() if hasattr(n, 'pos') else 0)
                else:
                    sorted_layer = layer[:]
                    random.shuffle(sorted_layer)
                for i, node in enumerate(sorted_layer):
                    node_x_order[node] = i

            # Barycenter iterations
            for iteration in range(20):
                for layer_idx in range(1, len(layers)):
                    self._barycenter_sort_layer(
                        layers[layer_idx], layers[layer_idx - 1], adjacency, node_x_order
                    )
                for layer_idx in range(len(layers) - 2, -1, -1):
                    self._barycenter_sort_layer(
                        layers[layer_idx], layers[layer_idx + 1], adjacency, node_x_order
                    )

            # Greedy swaps considering ALL crossings
            improved = True
            max_iterations = 100
            iteration = 0
            while improved and iteration < max_iterations:
                improved = False
                iteration += 1
                for layer in layers:
                    layer_sorted = sorted(layer, key=lambda n: node_x_order.get(n, 0))
                    for i in range(len(layer_sorted) - 1):
                        n1, n2 = layer_sorted[i], layer_sorted[i + 1]
                        old_crossings = count_crossings(node_x_order)
                        node_x_order[n1], node_x_order[n2] = node_x_order[n2], node_x_order[n1]
                        new_crossings = count_crossings(node_x_order)
                        if new_crossings < old_crossings:
                            improved = True
                            layer_sorted[i], layer_sorted[i + 1] = n2, n1
                        else:
                            node_x_order[n1], node_x_order[n2] = node_x_order[n2], node_x_order[n1]

            crossings = count_crossings(node_x_order)
            if crossings < best_crossings:
                best_crossings = crossings
                best_order = dict(node_x_order)

        # Phase 4: Coordinate assignment
        node_spacing = 160
        layer_y = 50
        layer_spacing = 120

        for layer_idx, layer in enumerate(layers):
            real_nodes = [n for n in layer if not getattr(n, 'is_dummy', False)]
            if not real_nodes:
                continue

            real_nodes_sorted = sorted(real_nodes, key=lambda n: best_order.get(n, 0))
            total_width = (len(real_nodes_sorted) - 1) * node_spacing
            start_x = 400 - total_width / 2

            for i, node in enumerate(real_nodes_sorted):
                node.setPos(start_x + i * node_spacing, layer_y)

            layer_y += layer_spacing

    def _barycenter_sort_layer(self, layer_nodes, adjacent_layer_nodes, adjacency, node_x_order):
        """Sort layer_nodes by barycenter of their neighbors in adjacent layer."""
        adjacent_set = set(adjacent_layer_nodes)

        def barycenter(node):
            neighbors_in_adjacent = [n for n in adjacency.get(node, []) if n in adjacent_set]
            if not neighbors_in_adjacent:
                return node_x_order.get(node, 0)
            return sum(node_x_order.get(n, 0) for n in neighbors_in_adjacent) / len(neighbors_in_adjacent)

        sorted_nodes = sorted(layer_nodes, key=barycenter)
        for i, node in enumerate(sorted_nodes):
            node_x_order[node] = i

    def force_directed_layout(self):
        """Apply force-directed (spring) layout to arrange nodes.

        Uses a hybrid approach: Y positions fixed by stage (layer), forces only affect X.
        Nodes repel each other, edges act as springs pulling connected nodes together.
        """
        # Constants (tuned for 27 nodes across 6 stages)
        repulsion = 50000.0  # Node-node repulsion strength (higher = more spacing)
        attraction = 0.005   # Edge spring constant (lower = less clustering)
        damping = 0.85       # Velocity damping per iteration
        iterations = 200     # Number of simulation steps
        min_distance = 1.0   # Prevent division by zero

        # Stage ordering for Y positions
        stage_order = ["concept", "planning", "implementing", "testing", "releasing", "shipped"]
        stage_y = {stage: 50 + i * 120 for i, stage in enumerate(stage_order)}

        # Get all nodes
        nodes = list(self._nodes.values())
        if not nodes:
            return

        # Build adjacency from edges
        adjacency = {node: [] for node in nodes}
        for item in self._scene.items():
            if isinstance(item, EdgePath):
                if item.source in adjacency and item.target in adjacency:
                    adjacency[item.source].append(item.target)
                    adjacency[item.target].append(item.source)

        # Initialize positions and velocities
        # Start with current X positions, fix Y by stage
        positions = {}
        velocities = {}
        for node in nodes:
            current_pos = node.pos()
            y = stage_y.get(node.stage, current_pos.y())
            positions[node] = [current_pos.x(), y]
            velocities[node] = [0.0, 0.0]

        # Simulation loop
        for _ in range(iterations):
            # Calculate forces
            forces = {node: [0.0, 0.0] for node in nodes}

            # Repulsion between all node pairs
            for i, node in enumerate(nodes):
                for other in nodes[i + 1:]:
                    dx = positions[node][0] - positions[other][0]
                    dy = positions[node][1] - positions[other][1]
                    dist_sq = dx * dx + dy * dy
                    dist = math.sqrt(dist_sq) if dist_sq > 0 else min_distance
                    dist = max(dist, min_distance)

                    # Coulomb-like repulsion: F = k / d^2
                    force_magnitude = repulsion / (dist * dist)
                    fx = (dx / dist) * force_magnitude
                    fy = (dy / dist) * force_magnitude

                    forces[node][0] += fx
                    forces[node][1] += fy
                    forces[other][0] -= fx
                    forces[other][1] -= fy

            # Attraction along edges (spring force)
            for node in nodes:
                for neighbor in adjacency[node]:
                    dx = positions[neighbor][0] - positions[node][0]
                    dy = positions[neighbor][1] - positions[node][1]
                    # Hooke's law: F = k * displacement
                    forces[node][0] += dx * attraction
                    forces[node][1] += dy * attraction

            # Apply forces to velocities, then velocities to positions
            for node in nodes:
                # Update velocity (only X dimension for hybrid approach)
                velocities[node][0] += forces[node][0]
                velocities[node][0] *= damping

                # Update X position only (Y fixed by stage)
                positions[node][0] += velocities[node][0]

        # Center the layout horizontally
        if nodes:
            min_x = min(positions[n][0] for n in nodes)
            max_x = max(positions[n][0] for n in nodes)
            center_offset = 400 - (min_x + max_x) / 2

            for node in nodes:
                positions[node][0] += center_offset

        # Apply final positions
        for node in nodes:
            node.setPos(positions[node][0], positions[node][1])
