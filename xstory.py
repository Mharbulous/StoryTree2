#!/usr/bin/env python3
"""
Xstory v1.5 - Consolidated Source of Truth
A desktop app to explore story-tree databases.
Uses PySide6 (Qt for Python) under the LGPL v3 license.

PySide6 License: LGPL v3 (https://www.gnu.org/licenses/lgpl-3.0.html)
Qt for Python: https://www.qt.io/qt-for-python
"""

import os
import sys
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

try:
    from PySide6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QTreeWidget, QTreeWidgetItem, QSplitter, QGroupBox, QCheckBox,
        QPushButton, QLabel, QTextEdit, QDialog, QDialogButtonBox,
        QFileDialog, QMessageBox, QScrollArea, QFrame, QStatusBar,
        QMenu, QLineEdit, QStyledItemDelegate, QStyleOptionViewItem, QStyle,
        QGridLayout, QListWidget, QListWidgetItem
    )
    from PySide6.QtCore import Qt, Signal, QSize, QRect, QPoint
    from PySide6.QtGui import (
        QBrush, QColor, QFont, QAction, QPixmap, QPainter, QPen, QIcon,
        QLinearGradient, QFontMetrics
    )
except ImportError:
    print("Error: PySide6 is required. Install with: pip install PySide6")
    sys.exit(1)

# Status colors (22-status rainbow system - optimized for visibility)
STATUS_COLORS = {
    # Epic stage (container-only - purple)
    'epic': '#9966CC',         # Medium Purple - container nodes, no workflow
    # Terminal states (consistent red - harshest to mildest)
    'infeasible': '#CC0000',   # Red (harshest - fundamentally impossible)
    'rejected': '#CC0000',     # Red (explicitly declined)
    'duplicative': '#CC0000',  # Red (redundant with another story)
    'deprecated': '#CC0000',   # Red (being phased out)
    'legacy': '#CC0000',       # Red (outdated/superseded)
    'archived': '#CC0000',     # Red (mildest - final cold storage)
    # Stages (greens/blues - workflow progression)
    'concept': '#66CC00',      # Lime green - RGB(102, 204, 0)
    'planning': '#00CC66',     # Emerald (combines approved/planned)
    'implementing': '#0099CC', # Cerulean (formerly executing)
    'testing': '#0066CC',      # Azure (combines reviewing/verifying)
    'releasing': '#3300CC',    # Electric Indigo (final active stage)
    # Positive terminus
    'shipped': '#00CC00',      # Green (successfully completed - positive terminus)
    # Hold reasons (gradient: reddish-orange to yellow for readability on gray)
    'broken': '#CC4400',       # RGB(204, 68, 0) - reddish orange (most urgent)
    'conflicted': '#D25B00',   # RGB(210, 91, 0) - dark orange (scope overlap, incompatible)
    'blocked': '#DB7100',      # RGB(219, 113, 0) - orange (external dependency)
    'escalated': '#E28B00',    # RGB(226, 139, 0) - golden orange (needs human review)
    'paused': '#E4A000',       # RGB(228, 160, 0) - gold
    'polish': '#E6B200',       # RGB(230, 178, 0) - dark gold
    'queued': '#E8C200',       # RGB(232, 194, 0) - dark yellow
    'wishlisted': '#EAD000',   # RGB(234, 208, 0) - yellow (low priority, parked)
    'ready': '#888888',        # Grey (no blockers)
    # Active status (no terminus set - story is still in pipeline)
    'active': '#888888',       # Grey (like 'ready')
}

# All possible statuses (canonical order)
ALL_STATUSES = [
    'epic',     # Container-only stage (no workflow)
    'shipped',  # Positive terminus (moved to front of terminus section)
    'infeasible', 'rejected', 'duplicative',
    'concept', 'broken', 'conflicted', 'blocked', 'polish', 'wishlisted',
    'escalated', 'planning', 'paused',
    'implementing', 'testing', 'releasing',
    'legacy', 'deprecated', 'archived'
]

# Three-field system: classify each status into its field type
STAGE_VALUES = {'epic', 'concept', 'planning', 'implementing', 'testing', 'releasing'}
STATUS_VALUES_HOLDS = {'escalated', 'paused', 'blocked', 'broken', 'polish', 'conflicted', 'wishlisted', 'queued'}
TERMINUS_VALUES = {'shipped', 'rejected', 'infeasible', 'duplicative', 'legacy', 'deprecated', 'archived'}

# Ordered lists for UI display (urgency order for statuses)
STAGE_ORDER = ['epic', 'concept', 'planning', 'implementing', 'testing', 'releasing']
STATUS_ORDER_HOLDS = ['ready', 'broken', 'conflicted', 'blocked', 'escalated', 'paused', 'polish', 'queued', 'wishlisted']
TERMINUS_ORDER = ['active', 'shipped', 'infeasible', 'rejected', 'duplicative', 'deprecated', 'legacy', 'archived']

# Hold reason icons for visual indication in tree view
HOLD_ICONS = {
    'queued': '⏳',      # Queued - waiting in line
    'escalated': '🙋',    # Escalated - needs human review/approval
    'paused': '⏸',      # Paused - work temporarily stopped
    'blocked': '🚧',     # Blocked - external dependency
    'broken': '🔥',      # Broken - needs fix
    'polish': '💎',      # Polish - needs refinement
    'conflicted': '⚔',   # Conflicted - scope overlaps incompatibly
    'wishlisted': '💭',  # Wishlisted - low priority, parked
}

# Terminus icons for visual indication in tree view (override hold icons)
TERMINUS_ICONS = {
    'shipped': '🚀',       # Shipped - successfully completed
    'rejected': '❌',      # Rejected - explicitly declined
    'infeasible': '🚫',    # Infeasible - cannot be done
    'duplicative': '👯',   # Duplicative - duplicate of another
    'legacy': '🛑',        # Legacy - old/outdated
    'deprecated': '⚠️',    # Deprecated - no longer recommended
    'archived': '📦',      # Archived - stored away
}


def calculate_stage_color(stage: str) -> QColor:
    """
    Get the color for a stage from STATUS_COLORS.

    Args:
        stage: The stage value from STAGE_ORDER

    Returns:
        QColor representing the stage color (matches stage filter colors)
    """
    if stage in STATUS_COLORS:
        return QColor(STATUS_COLORS[stage])

    # Default to concept color for unknown stages
    return QColor(STATUS_COLORS.get('concept', '#66CC00'))


def calculate_gradient_colors(node: 'StoryNode') -> Tuple[QColor, QColor]:
    """
    Calculate the gradient start and end colors for a tree node.

    Color Logic:
    - Terminus active → Solid terminus color (no gradient)
    - Status active (non-ready, no terminus) → Gradient from stage color to black
    - Default → Solid stage color (no gradient)

    Args:
        node: StoryNode object with stage, status, and terminus

    Returns:
        Tuple of (start_color, end_color) as QColor objects
    """
    # Determine color based on priority: terminus > status > stage
    if node.terminus:
        # Terminus active → Use terminus color (solid, no gradient)
        color_hex = STATUS_COLORS.get(node.terminus, '#CC3300')  # Default to rejected color
        start_color = QColor(color_hex)
        end_color = start_color
        return start_color, end_color

    # Calculate start color based on stage
    start_color = calculate_stage_color(node.stage)

    # Determine end color based on status
    if node.status and node.status != 'ready':
        # Status active (non-ready) → Gradient to black
        end_color = QColor()
        end_color.setHslF(0 / 360.0, 0.0, 0.0)  # Black
    else:
        # Default → Solid stage color (no gradient)
        end_color = start_color

    return start_color, end_color


class GradientTextDelegate(QStyledItemDelegate):
    """
    Custom delegate for rendering tree node text with gradient colors.

    Renders node labels with colors based on:
    - Stage (determines base color: green → blue progression)
    - Status (if active non-ready and no terminus, gradient ends in black)
    - Terminus (if active, solid stage color - terminus shown in Stage column)
    """

    def __init__(self, parent=None, app=None):
        super().__init__(parent)
        self.app = app  # Reference to XstoryExplorer for node lookup

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index):
        """Custom paint method for gradient text rendering."""
        # Get the node ID from column 0 of the same row
        tree_widget = option.widget
        item = tree_widget.itemFromIndex(index)
        if not item:
            super().paint(painter, option, index)
            return

        node_id = item.text(0)  # ID is always in column 0

        # Get the node data
        if not self.app or node_id not in self.app.nodes:
            super().paint(painter, option, index)
            return

        node = self.app.nodes[node_id]

        # Check if this node is a faded ancestor
        is_faded = item.data(0, Qt.UserRole) == 'faded'

        # Get text to display
        text = index.data(Qt.DisplayRole) or ''

        # Save painter state
        painter.save()

        # Draw selection/hover background if needed
        if option.state & QStyle.State_Selected:
            painter.fillRect(option.rect, option.palette.highlight())
        elif option.state & QStyle.State_MouseOver:
            painter.fillRect(option.rect, option.palette.light())

        # Calculate text rectangle with padding
        text_rect = option.rect.adjusted(4, 0, -4, 0)

        # Get font metrics
        font = option.font
        painter.setFont(font)
        fm = QFontMetrics(font)

        # For faded nodes, still use stage color (no gradient) for consistency
        if is_faded:
            stage_color = calculate_stage_color(node.stage)
            painter.setPen(stage_color)
            painter.drawText(text_rect, Qt.AlignLeft | Qt.AlignVCenter, text)
            painter.restore()
            return

        # Calculate gradient colors
        start_color, end_color = calculate_gradient_colors(node)

        # Check if this is a solid color (start == end)
        if start_color == end_color:
            painter.setPen(start_color)
            painter.drawText(text_rect, Qt.AlignLeft | Qt.AlignVCenter, text)
            painter.restore()
            return

        # Create gradient for text
        # We need to render character by character with interpolated colors
        text_width = fm.horizontalAdvance(text)
        if text_width == 0:
            painter.restore()
            return

        # Draw text with gradient effect using character-by-character rendering
        x_pos = text_rect.left()
        y_pos = text_rect.top() + (text_rect.height() + fm.ascent() - fm.descent()) // 2

        total_width = min(text_width, text_rect.width())
        current_x = 0

        for char in text:
            char_width = fm.horizontalAdvance(char)
            if current_x + char_width > text_rect.width():
                break

            # Calculate interpolation factor (0.0 at start, 1.0 at end)
            t = current_x / total_width if total_width > 0 else 0

            # Interpolate color
            r = int(start_color.red() + t * (end_color.red() - start_color.red()))
            g = int(start_color.green() + t * (end_color.green() - start_color.green()))
            b = int(start_color.blue() + t * (end_color.blue() - start_color.blue()))

            painter.setPen(QColor(r, g, b))
            painter.drawText(x_pos + current_x, y_pos, char)

            current_x += char_width

        painter.restore()


# Filter Mode transitions: approval, quality, priority, end-of-life decisions
FILTER_TRANSITIONS = {
    'infeasible': ['concept', 'wishlisted', 'archived'],
    'rejected': ['concept', 'wishlisted', 'archived'],
    'wishlisted': ['concept', 'rejected', 'archived'],
    'concept': ['planning', 'escalated', 'rejected', 'wishlisted', 'polish'],
    'polish': ['concept', 'releasing', 'rejected', 'wishlisted'],
    # 'escalated' handled by ESCALATED_FILTER_TRANSITIONS (stage-aware)
    'planning': ['escalated', 'rejected'],
    'blocked': ['escalated'],
    'paused': ['escalated'],
    'testing': ['releasing'],
    'releasing': ['shipped', 'polish'],  # Can mark as shipped (terminus) or send to polish
    'legacy': ['deprecated', 'archived'],  # Remove shipped since it's terminus
    'deprecated': ['archived', 'legacy'],
    'archived': ['deprecated', 'wishlisted'],
}

# Respond Mode transitions: workflow, blockers, bugs, progress
RESPOND_TRANSITIONS = {
    'planning': ['implementing'],
    'blocked': ['planning', 'implementing'],
    'broken': ['implementing', 'paused', 'blocked'],
    'paused': ['implementing', 'blocked'],
    'implementing': ['testing', 'paused', 'broken', 'blocked'],
    'testing': ['implementing', 'broken', 'releasing'],
    'releasing': ['testing', 'broken'],  # Releasing replaces shipped as final active stage
    'polish': ['testing'],
}

# Stage-aware transitions for escalated nodes (keyed by stage, not effective_status)
# These are used when node.status == 'escalated' to provide appropriate options
ESCALATED_FILTER_TRANSITIONS = {
    'concept': ['planning', 'polish', 'wishlisted', 'rejected', 'paused'],
    'planning': ['queued', 'polish', 'wishlisted', 'rejected'],
    'implementing': ['wishlisted', 'rejected', 'broken'],
    'testing': ['releasing', 'polish'],
    'releasing': ['shipped', 'polish'],
}

ESCALATED_RESPOND_TRANSITIONS = {
    'concept': ['planning'],
    'planning': ['implementing'],
    'implementing': ['testing', 'broken'],
    'testing': ['releasing'],
    'releasing': ['shipped'],
}


def create_checkbox_pixmap(color_hex: str, checked: bool) -> QPixmap:
    """Create a custom checkbox pixmap with white checkmark on colored background."""
    size = 18
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)

    if checked:
        # Draw colored background with border
        painter.setBrush(QBrush(QColor(color_hex)))
        painter.setPen(QPen(QColor(color_hex), 1))
        painter.drawRoundedRect(0, 0, size-1, size-1, 3, 3)

        # Draw white checkmark
        painter.setPen(QPen(QColor(Qt.white), 2.5, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        # Checkmark path
        painter.drawLine(4, 9, 7, 13)
        painter.drawLine(7, 13, 14, 4)
    else:
        # Draw white background with gray border
        painter.setBrush(QBrush(QColor(Qt.white)))
        painter.setPen(QPen(QColor('#999999'), 1))
        painter.drawRoundedRect(0, 0, size-1, size-1, 3, 3)

    painter.end()
    return pixmap


class ColoredCheckBox(QCheckBox):
    """Custom checkbox with colored background and white checkmark when checked."""

    def __init__(self, text: str, color: str, parent=None):
        super().__init__(text, parent)
        self.status_color = color
        self.checkbox_size = 18
        self.checkbox_margin = 4

    def paintEvent(self, event):
        """Custom paint to draw checkbox with colored background and white checkmark."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Calculate positions
        indicator_y = (self.height() - self.checkbox_size) // 2
        text_x = self.checkbox_margin + self.checkbox_size + 8  # 8px spacing

        # Draw custom checkbox indicator
        if self.isChecked():
            # Draw colored background
            painter.setBrush(QBrush(QColor(self.status_color)))
            painter.setPen(QPen(QColor(self.status_color), 1))
            painter.drawRoundedRect(self.checkbox_margin, indicator_y, self.checkbox_size - 1, self.checkbox_size - 1, 3, 3)

            # Draw white checkmark
            painter.setPen(QPen(QColor(Qt.white), 2.5, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            painter.drawLine(self.checkbox_margin + 4, indicator_y + 9,
                           self.checkbox_margin + 7, indicator_y + 13)
            painter.drawLine(self.checkbox_margin + 7, indicator_y + 13,
                           self.checkbox_margin + 14, indicator_y + 4)
        else:
            # Draw white background with gray border
            painter.setBrush(QBrush(QColor(Qt.white)))
            painter.setPen(QPen(QColor('#999999'), 1))
            painter.drawRoundedRect(self.checkbox_margin, indicator_y, self.checkbox_size - 1, self.checkbox_size - 1, 3, 3)

        # Draw text in status color
        painter.setPen(QColor(self.status_color))
        font = self.font()
        painter.setFont(font)
        text_rect = self.rect()
        text_rect.setLeft(text_x)
        painter.drawText(text_rect, Qt.AlignLeft | Qt.AlignVCenter, self.text())

        painter.end()

    def hitButton(self, pos):
        """Override to make the entire widget clickable."""
        return self.rect().contains(pos)

    def sizeHint(self):
        """Calculate proper size for checkbox and text."""
        fm = self.fontMetrics()
        text_width = fm.horizontalAdvance(self.text())
        width = self.checkbox_margin + self.checkbox_size + 8 + text_width + 5
        height = max(self.checkbox_size + 4, fm.height())
        return QSize(width, height)


class StoryNode:
    """Represents a story node from the database."""
    def __init__(self, id: str, feature: str, effective_status: str, capacity: Optional[int],
                 description: str = '', depth: int = 0, parent_id: Optional[str] = None,
                 notes: str = '', project_path: str = '', created_at: str = '',
                 updated_at: str = '', last_implemented: str = '',
                 stage: str = '', status: str = 'ready',
                 terminus: Optional[str] = None, descendants_count: int = 0,
                 success_criteria: str = '', story: str = ''):
        self.id = id
        self.feature = feature
        self.effective_status = effective_status  # COALESCE(terminus, status when not 'ready', stage)
        self.capacity = capacity
        self.description = description
        self.depth = depth
        self.parent_id = parent_id
        self.notes = notes
        self.project_path = project_path
        self.created_at = created_at
        self.updated_at = updated_at
        self.last_implemented = last_implemented
        # Three-field system components
        self.stage = stage
        self.status = status  # Status condition: ready, queued, escalated, blocked, etc.
        self.terminus = terminus
        self.descendants_count = descendants_count
        self.success_criteria = success_criteria
        self.story = story
        self.children: List['StoryNode'] = []


class StatusChangeDialog(QDialog):
    """Dialog for entering notes when changing story status."""

    def __init__(self, parent, node_id: str, new_status: str, mandatory: bool = False):
        super().__init__(parent)
        self.node_id = node_id
        self.new_status = new_status
        self.mandatory = mandatory
        self.result_notes: Optional[str] = None

        self.setWindowTitle(f"Change Status to '{new_status}'")
        self.setFixedSize(400, 250)
        self.setModal(True)

        self._setup_ui()

    def _setup_ui(self):
        """Set up the dialog UI."""
        layout = QVBoxLayout(self)

        # Header
        header_text = f"Changing '{self.node_id}' to status: {self.new_status}"
        header_label = QLabel(header_text)
        header_label.setStyleSheet("font-weight: bold; font-size: 10pt;")
        layout.addWidget(header_label)

        # Separator line
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        layout.addWidget(line)

        # Prompt text based on status
        if self.new_status == 'planning':
            prompt_text = "Please note how high a priority this story is:"
        elif self.new_status == 'polish':
            prompt_text = "Please explain what needs refinement (required):"
        else:
            prompt_text = "Add a note about this decision (optional):"

        layout.addWidget(QLabel(prompt_text))

        # Text area for notes
        self.notes_text = QTextEdit()
        self.notes_text.setPlaceholderText("Enter notes here...")
        layout.addWidget(self.notes_text)

        # Buttons
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self._on_confirm)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def _on_confirm(self):
        """Handle confirm button click."""
        notes = self.notes_text.toPlainText().strip()

        if self.mandatory and not notes:
            QMessageBox.warning(
                self,
                "Notes Required",
                f"Notes are required when changing status to '{self.new_status}'."
            )
            self.notes_text.setFocus()
            return

        self.result_notes = notes
        self.accept()

    def get_notes(self) -> Optional[str]:
        """Return the entered notes if dialog was accepted."""
        return self.result_notes


class StateDiagramDialog(QDialog):
    """Dialog for displaying the state transition diagram."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("State Transitions")
        self.resize(900, 700)
        self.setModal(False)

        self._setup_ui()

    def _setup_ui(self):
        """Set up the dialog UI matching DetailView styling."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Header bar
        header_widget = QWidget()
        header_widget.setFixedHeight(30)
        header_widget.setStyleSheet("""
            QWidget {
                background-color: #f8f9fa;
                border-bottom: 1px solid #dee2e6;
            }
        """)
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(12, 0, 12, 0)

        title_label = QLabel("State Transitions")
        title_label.setStyleSheet("font-weight: bold; font-size: 10pt;")
        header_layout.addWidget(title_label)
        header_layout.addStretch()

        # Sort button (top-right)
        sort_btn = QPushButton("Sort")
        sort_btn.setFixedWidth(60)
        sort_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: 1px solid #ced4da;
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 9pt;
            }
            QPushButton:hover { background-color: #e9ecef; }
        """)
        sort_btn.clicked.connect(self._on_sort_clicked)
        header_layout.addWidget(sort_btn)

        main_layout.addWidget(header_widget)

        # Interactive diagram view with draggable nodes
        try:
            from .interactive_diagram import InteractiveStateDiagram
        except ImportError:
            from interactive_diagram import InteractiveStateDiagram
        self.diagram_view = InteractiveStateDiagram()
        main_layout.addWidget(self.diagram_view)

        # Footer with Close button
        footer_widget = QWidget()
        footer_widget.setStyleSheet("""
            QWidget {
                background-color: #f8f9fa;
                border-top: 1px solid #dee2e6;
            }
        """)
        footer_layout = QHBoxLayout(footer_widget)
        footer_layout.setContentsMargins(16, 12, 16, 12)
        footer_layout.addStretch()

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.close)
        close_btn.setFixedWidth(80)
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: 1px solid #ced4da;
                border-radius: 4px;
                padding: 6px 12px;
            }
            QPushButton:hover { background-color: #e9ecef; }
        """)
        footer_layout.addWidget(close_btn)

        main_layout.addWidget(footer_widget)

    def _on_sort_clicked(self):
        """Trigger force-directed layout algorithm."""
        self.diagram_view.force_directed_layout()


class KanbanCard(QFrame):
    """A clickable card representing a story in the Kanban board."""
    doubleClicked = Signal(str)

    def __init__(self, node_id: str, feature: str, status: str = 'ready',
                 terminus: str = None, parent=None):
        super().__init__(parent)
        self.node_id = node_id
        self.setFrameShape(QFrame.StyledPanel)
        self.setCursor(Qt.PointingHandCursor)

        # Determine badge text and color
        badge_text = None
        badge_color = None
        if terminus:
            badge_text = terminus
            badge_color = "#dc3545"  # Red for terminus
        elif status and status != "ready":
            badge_text = status
            badge_color = "#fd7e14"  # Orange for non-ready status

        self.setStyleSheet(f"""
            KanbanCard {{
                background-color: white;
                border: 1px solid #dee2e6;
                border-radius: 4px;
                padding: 8px;
                margin: 4px;
            }}
            KanbanCard:hover {{
                border-color: #adb5bd;
                background-color: #f8f9fa;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # Node ID
        id_label = QLabel(node_id)
        id_label.setStyleSheet("font-weight: bold; font-size: 9pt; color: #495057;")
        layout.addWidget(id_label)

        # Feature text (truncated)
        feature_text = feature[:60] + "..." if len(feature) > 60 else feature
        feature_label = QLabel(feature_text)
        feature_label.setWordWrap(True)
        feature_label.setStyleSheet("font-size: 9pt; color: #212529;")
        layout.addWidget(feature_label)

        # Badge for hold/terminus
        if badge_text:
            badge = QLabel(badge_text)
            badge.setStyleSheet(f"""
                background-color: {badge_color};
                color: white;
                font-size: 8pt;
                padding: 2px 6px;
                border-radius: 3px;
            """)
            badge.setFixedWidth(badge.sizeHint().width() + 12)
            layout.addWidget(badge)

    def mouseDoubleClickEvent(self, event):
        """Emit signal on double-click."""
        self.doubleClicked.emit(self.node_id)
        super().mouseDoubleClickEvent(event)


class KanbanDialog(QDialog):
    """Dialog for displaying the Kanban view of stories."""

    # Stage colors (matching state_graph.py)
    STAGE_COLORS = {
        "concept": "#66CC00",
        "planning": "#00CC66",
        "implementing": "#00CCCC",
        "testing": "#0099CC",
        "releasing": "#0066CC",
        "shipped": "#0033CC",
    }

    STAGES = ["concept", "planning", "implementing", "testing", "releasing", "shipped"]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.app = parent  # Reference to XstoryExplorer
        self.setWindowTitle("Kanban View")
        self.resize(1200, 700)
        self.setModal(False)

        self.column_widgets: Dict[str, QWidget] = {}
        self._setup_ui()
        self._populate_board()

    def _setup_ui(self):
        """Set up the dialog UI with Kanban columns."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Header bar
        header_widget = QWidget()
        header_widget.setFixedHeight(30)
        header_widget.setStyleSheet("""
            QWidget {
                background-color: #f8f9fa;
                border-bottom: 1px solid #dee2e6;
            }
        """)
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(12, 0, 12, 0)

        title_label = QLabel("Kanban View")
        title_label.setStyleSheet("font-weight: bold; font-size: 10pt;")
        header_layout.addWidget(title_label)
        header_layout.addStretch()

        # Refresh button
        refresh_btn = QPushButton("Refresh")
        refresh_btn.setFixedWidth(70)
        refresh_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: 1px solid #ced4da;
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 9pt;
            }
            QPushButton:hover { background-color: #e9ecef; }
        """)
        refresh_btn.clicked.connect(self._populate_board)
        header_layout.addWidget(refresh_btn)

        main_layout.addWidget(header_widget)

        # Kanban board container with horizontal scroll
        board_scroll = QScrollArea()
        board_scroll.setWidgetResizable(True)
        board_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        board_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        board_scroll.setStyleSheet("QScrollArea { border: none; background-color: #e9ecef; }")

        board_widget = QWidget()
        board_widget.setStyleSheet("background-color: #e9ecef;")
        board_layout = QHBoxLayout(board_widget)
        board_layout.setContentsMargins(8, 8, 8, 8)
        board_layout.setSpacing(8)

        # Create columns for each stage
        for stage in self.STAGES:
            column = self._create_column(stage)
            board_layout.addWidget(column)
            self.column_widgets[stage] = column

        board_scroll.setWidget(board_widget)
        main_layout.addWidget(board_scroll)

        # Footer with Close button
        footer_widget = QWidget()
        footer_widget.setStyleSheet("""
            QWidget {
                background-color: #f8f9fa;
                border-top: 1px solid #dee2e6;
            }
        """)
        footer_layout = QHBoxLayout(footer_widget)
        footer_layout.setContentsMargins(16, 12, 16, 12)
        footer_layout.addStretch()

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.close)
        close_btn.setFixedWidth(80)
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: 1px solid #ced4da;
                border-radius: 4px;
                padding: 6px 12px;
            }
            QPushButton:hover { background-color: #e9ecef; }
        """)
        footer_layout.addWidget(close_btn)

        main_layout.addWidget(footer_widget)

    def _create_column(self, stage: str) -> QWidget:
        """Create a Kanban column for a stage."""
        column = QWidget()
        column.setFixedWidth(200)
        column.setStyleSheet(f"""
            QWidget {{
                background-color: #f8f9fa;
                border-radius: 6px;
            }}
        """)

        layout = QVBoxLayout(column)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Column header with stage color
        header = QWidget()
        header.setFixedHeight(36)
        color = self.STAGE_COLORS.get(stage, "#6c757d")
        header.setStyleSheet(f"""
            QWidget {{
                background-color: {color};
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
            }}
        """)

        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(12, 0, 12, 0)

        title = QLabel(stage.capitalize())
        title.setStyleSheet("font-weight: bold; font-size: 10pt; color: white;")
        header_layout.addWidget(title)

        # Count label (will be updated)
        count_label = QLabel("0")
        count_label.setObjectName(f"{stage}_count")
        count_label.setStyleSheet("""
            background-color: rgba(255, 255, 255, 0.3);
            color: white;
            font-size: 9pt;
            padding: 2px 8px;
            border-radius: 10px;
        """)
        header_layout.addWidget(count_label)

        layout.addWidget(header)

        # Scrollable card container
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: #f8f9fa;
            }
            QScrollArea > QWidget > QWidget {
                background-color: #f8f9fa;
            }
        """)

        cards_widget = QWidget()
        cards_widget.setObjectName(f"{stage}_cards")
        cards_layout = QVBoxLayout(cards_widget)
        cards_layout.setContentsMargins(4, 4, 4, 4)
        cards_layout.setSpacing(4)
        cards_layout.addStretch()

        scroll.setWidget(cards_widget)
        layout.addWidget(scroll)

        return column

    def _populate_board(self):
        """Populate the Kanban board with story cards."""
        if not self.app or not hasattr(self.app, 'nodes'):
            return

        # Group nodes by stage
        stage_nodes: Dict[str, List] = {stage: [] for stage in self.STAGES}

        for node in self.app.nodes.values():
            # Skip root node
            if node.id == 'root':
                continue
            # Skip terminal nodes (they have terminus set)
            if node.terminus:
                continue
            # Group by stage
            stage = node.stage if node.stage in self.STAGES else None
            if stage:
                stage_nodes[stage].append(node)

        # Populate each column
        for stage in self.STAGES:
            column = self.column_widgets.get(stage)
            if not column:
                continue

            # Find cards container
            cards_widget = column.findChild(QWidget, f"{stage}_cards")
            if not cards_widget:
                continue

            # Clear existing cards (keep stretch)
            layout = cards_widget.layout()
            while layout.count() > 1:  # Keep the stretch
                item = layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()

            # Add cards for this stage
            nodes = stage_nodes[stage]

            for node in sorted(nodes, key=lambda n: n.id):
                card = KanbanCard(
                    node_id=node.id,
                    feature=node.feature,
                    status=node.status,
                    terminus=node.terminus
                )
                card.doubleClicked.connect(self._on_card_double_clicked)
                layout.insertWidget(layout.count() - 1, card)  # Insert before stretch

            # Update count label
            count_label = column.findChild(QLabel, f"{stage}_count")
            if count_label:
                count_label.setText(str(len(nodes)))

    def _on_card_double_clicked(self, node_id: str):
        """Handle double-click on a card to show detail view."""
        if self.app and hasattr(self.app, 'show_detail_view'):
            self.app.show_detail_view(node_id)


class HeatmapDialog(QDialog):
    """Dialog for displaying stage x status heatmap to identify bottlenecks."""

    STAGES = ["concept", "planning", "implementing", "testing", "releasing"]
    STATUSES = ["ready", "escalated", "blocked", "queued", "broken",
                "paused", "polish", "conflicted", "wishlisted"]

    # Heat colors from white (0) to red (max)
    HEAT_COLORS = [
        "#ffffff",  # 0: white
        "#fff3cd",  # 1-2: light yellow
        "#ffc107",  # 3-5: yellow
        "#fd7e14",  # 6-10: orange
        "#dc3545",  # 11+: red
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.app = parent  # Reference to XstoryExplorer
        self.setWindowTitle("Bottleneck Heatmap")
        self.resize(900, 600)
        self.setModal(False)

        self.cell_labels: Dict[Tuple[str, str], QLabel] = {}
        self._setup_ui()
        self._populate_heatmap()

    def _setup_ui(self):
        """Set up the dialog UI with heatmap grid."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Header bar
        header_widget = QWidget()
        header_widget.setFixedHeight(30)
        header_widget.setStyleSheet("""
            QWidget {
                background-color: #f8f9fa;
                border-bottom: 1px solid #dee2e6;
            }
        """)
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(12, 0, 12, 0)

        title_label = QLabel("Bottleneck Heatmap")
        title_label.setStyleSheet("font-weight: bold; font-size: 10pt;")
        header_layout.addWidget(title_label)
        header_layout.addStretch()

        # Refresh button
        refresh_btn = QPushButton("Refresh")
        refresh_btn.setFixedWidth(70)
        refresh_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: 1px solid #ced4da;
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 9pt;
            }
            QPushButton:hover { background-color: #e9ecef; }
        """)
        refresh_btn.clicked.connect(self._populate_heatmap)
        header_layout.addWidget(refresh_btn)

        main_layout.addWidget(header_widget)

        # Scrollable heatmap area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background-color: #f8f9fa; }")

        grid_widget = QWidget()
        grid_widget.setStyleSheet("background-color: #f8f9fa;")
        self.grid_layout = QGridLayout(grid_widget)
        self.grid_layout.setContentsMargins(16, 16, 16, 16)
        self.grid_layout.setSpacing(2)

        # Create header row (stages)
        self.grid_layout.addWidget(QLabel(""), 0, 0)  # Empty corner
        for col, stage in enumerate(self.STAGES):
            header = QLabel(stage.capitalize())
            header.setAlignment(Qt.AlignCenter)
            header.setFixedHeight(30)
            header.setStyleSheet("""
                font-weight: bold;
                font-size: 9pt;
                background-color: #e9ecef;
                padding: 4px 8px;
                border-radius: 4px;
            """)
            self.grid_layout.addWidget(header, 0, col + 1)

        # Row totals header
        total_header = QLabel("TOTAL")
        total_header.setAlignment(Qt.AlignCenter)
        total_header.setFixedHeight(30)
        total_header.setStyleSheet("""
            font-weight: bold;
            font-size: 9pt;
            background-color: #dee2e6;
            padding: 4px 8px;
            border-radius: 4px;
        """)
        self.grid_layout.addWidget(total_header, 0, len(self.STAGES) + 1)

        # Create data rows (statuses)
        for row, status_val in enumerate(self.STATUSES):
            # Row label
            row_label = QLabel(status_val.replace("_", " "))
            row_label.setFixedWidth(80)
            row_label.setStyleSheet("font-size: 9pt; padding: 4px;")
            self.grid_layout.addWidget(row_label, row + 1, 0)

            # Data cells
            for col, stage in enumerate(self.STAGES):
                cell = QLabel("0")
                cell.setAlignment(Qt.AlignCenter)
                cell.setFixedSize(70, 35)
                cell.setStyleSheet("""
                    font-size: 10pt;
                    font-weight: bold;
                    border: 1px solid #dee2e6;
                    border-radius: 4px;
                """)
                cell.setCursor(Qt.PointingHandCursor)
                cell.setProperty("stage", stage)
                cell.setProperty("status", status_val)
                cell.mousePressEvent = lambda e, s=stage, st=status_val: self._on_cell_clicked(s, st)
                self.cell_labels[(stage, status_val)] = cell
                self.grid_layout.addWidget(cell, row + 1, col + 1)

            # Row total
            row_total = QLabel("0")
            row_total.setAlignment(Qt.AlignCenter)
            row_total.setFixedSize(70, 35)
            row_total.setObjectName(f"row_total_{status_val}")
            row_total.setStyleSheet("""
                font-size: 10pt;
                font-weight: bold;
                background-color: #e9ecef;
                border: 1px solid #dee2e6;
                border-radius: 4px;
            """)
            self.grid_layout.addWidget(row_total, row + 1, len(self.STAGES) + 1)

        # Column totals row
        total_row = len(self.STATUSES) + 1
        total_label = QLabel("TOTAL")
        total_label.setFixedWidth(80)
        total_label.setStyleSheet("font-weight: bold; font-size: 9pt; padding: 4px;")
        self.grid_layout.addWidget(total_label, total_row, 0)

        for col, stage in enumerate(self.STAGES):
            col_total = QLabel("0")
            col_total.setAlignment(Qt.AlignCenter)
            col_total.setFixedSize(70, 35)
            col_total.setObjectName(f"col_total_{stage}")
            col_total.setStyleSheet("""
                font-size: 10pt;
                font-weight: bold;
                background-color: #e9ecef;
                border: 1px solid #dee2e6;
                border-radius: 4px;
            """)
            self.grid_layout.addWidget(col_total, total_row, col + 1)

        # Grand total
        grand_total = QLabel("0")
        grand_total.setAlignment(Qt.AlignCenter)
        grand_total.setFixedSize(70, 35)
        grand_total.setObjectName("grand_total")
        grand_total.setStyleSheet("""
            font-size: 10pt;
            font-weight: bold;
            background-color: #dee2e6;
            border: 1px solid #ced4da;
            border-radius: 4px;
        """)
        self.grid_layout.addWidget(grand_total, total_row, len(self.STAGES) + 1)

        scroll.setWidget(grid_widget)
        main_layout.addWidget(scroll)

        # Footer with Close button
        footer_widget = QWidget()
        footer_widget.setStyleSheet("""
            QWidget {
                background-color: #f8f9fa;
                border-top: 1px solid #dee2e6;
            }
        """)
        footer_layout = QHBoxLayout(footer_widget)
        footer_layout.setContentsMargins(16, 12, 16, 12)
        footer_layout.addStretch()

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.close)
        close_btn.setFixedWidth(80)
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: 1px solid #ced4da;
                border-radius: 4px;
                padding: 6px 12px;
            }
            QPushButton:hover { background-color: #e9ecef; }
        """)
        footer_layout.addWidget(close_btn)

        main_layout.addWidget(footer_widget)

    def _on_cell_clicked(self, stage: str, status_val: str):
        """Handle click on a heatmap cell - show stories in that cell."""
        if not self.app or not hasattr(self.app, 'nodes'):
            return

        # Find nodes matching this stage + status
        matching_nodes = []
        for node in self.app.nodes.values():
            if node.id == 'root' or node.terminus:
                continue
            node_status = node.status or "ready"
            if node.stage == stage and node_status == status_val:
                matching_nodes.append(node)

        if not matching_nodes:
            return

        # Show simple list dialog
        list_dialog = QDialog(self)
        list_dialog.setWindowTitle(f"{stage}:{status_val.replace('_', ' ')} ({len(matching_nodes)})")
        list_dialog.resize(400, 300)

        layout = QVBoxLayout(list_dialog)
        list_widget = QListWidget()

        for node in sorted(matching_nodes, key=lambda n: n.id):
            item = QListWidgetItem(f"{node.id} - {node.feature}")
            list_widget.addItem(item)

        list_widget.itemDoubleClicked.connect(
            lambda item: self._show_node_detail(item.text().split(" - ")[0])
        )
        layout.addWidget(list_widget)
        list_dialog.exec()

    def _show_node_detail(self, node_id: str):
        """Show detail view for a node."""
        if self.app and hasattr(self.app, 'show_detail_view'):
            self.app.show_detail_view(node_id)

    def _populate_heatmap(self):
        """Populate the heatmap with current node counts."""
        if not self.app or not hasattr(self.app, 'nodes'):
            return

        # Count nodes by (stage, status)
        counts: Dict[Tuple[str, str], int] = {}
        for stage in self.STAGES:
            for status_val in self.STATUSES:
                counts[(stage, status_val)] = 0

        for node in self.app.nodes.values():
            # Skip root and terminal nodes
            if node.id == 'root':
                continue
            if node.terminus:
                continue

            stage = node.stage
            status_val = node.status or "ready"

            if stage in self.STAGES and status_val in self.STATUSES:
                counts[(stage, status_val)] = counts.get((stage, status_val), 0) + 1

        # Update cells with counts and heat colors
        for (stage, status_val), count in counts.items():
            cell = self.cell_labels.get((stage, status_val))
            if cell:
                cell.setText(str(count) if count > 0 else "-")
                color = self._get_heat_color(count)
                cell.setStyleSheet(f"""
                    font-size: 10pt;
                    font-weight: bold;
                    background-color: {color};
                    border: 1px solid #dee2e6;
                    border-radius: 4px;
                """)

        # Calculate and update row totals
        for status_val in self.STATUSES:
            row_total = sum(counts.get((stage, status_val), 0) for stage in self.STAGES)
            row_label = self.findChild(QLabel, f"row_total_{status_val}")
            if row_label:
                row_label.setText(str(row_total) if row_total > 0 else "-")

        # Calculate and update column totals
        for stage in self.STAGES:
            col_total = sum(counts.get((stage, status_val), 0) for status_val in self.STATUSES)
            col_label = self.findChild(QLabel, f"col_total_{stage}")
            if col_label:
                col_label.setText(str(col_total) if col_total > 0 else "-")

        # Calculate and update grand total
        grand_total = sum(counts.values())
        grand_label = self.findChild(QLabel, "grand_total")
        if grand_label:
            grand_label.setText(str(grand_total))

    def _get_heat_color(self, count: int) -> str:
        """Get heat color for a count value."""
        if count == 0:
            return self.HEAT_COLORS[0]
        elif count <= 2:
            return self.HEAT_COLORS[1]
        elif count <= 5:
            return self.HEAT_COLORS[2]
        elif count <= 10:
            return self.HEAT_COLORS[3]
        else:
            return self.HEAT_COLORS[4]


class SwimlanesDialog(QDialog):
    """Dialog for displaying stories in a stage x status matrix."""

    STAGE_COLORS = {
        "concept": "#66CC00",
        "planning": "#00CC66",
        "implementing": "#00CCCC",
        "testing": "#0099CC",
        "releasing": "#0066CC",
        "shipped": "#0033CC",
    }

    STAGES = ["concept", "planning", "implementing", "testing", "releasing", "shipped"]

    # Display order for statuses (ready first, then alphabetical)
    STATUSES = ["ready", "blocked", "broken", "escalated", "paused", "polish", "queued", "wishlisted"]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.app = parent  # Reference to XstoryExplorer
        self.setWindowTitle("Swimlanes View")
        self.resize(1400, 800)
        self.setModal(False)

        self.cell_widgets: Dict[Tuple[str, str], QWidget] = {}  # (status, stage) -> widget
        self._setup_ui()
        self._populate_grid()

    def _setup_ui(self):
        """Set up the dialog UI with grid layout."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Header bar
        header_widget = QWidget()
        header_widget.setFixedHeight(30)
        header_widget.setStyleSheet("""
            QWidget {
                background-color: #f8f9fa;
                border-bottom: 1px solid #dee2e6;
            }
        """)
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(12, 0, 12, 0)

        title_label = QLabel("Swimlanes View")
        title_label.setStyleSheet("font-weight: bold; font-size: 10pt;")
        header_layout.addWidget(title_label)
        header_layout.addStretch()

        # Refresh button
        refresh_btn = QPushButton("Refresh")
        refresh_btn.setFixedWidth(70)
        refresh_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: 1px solid #ced4da;
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 9pt;
            }
            QPushButton:hover { background-color: #e9ecef; }
        """)
        refresh_btn.clicked.connect(self._populate_grid)
        header_layout.addWidget(refresh_btn)

        main_layout.addWidget(header_widget)

        # Main scrollable area for the grid
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setStyleSheet("QScrollArea { border: none; background-color: #e9ecef; }")

        # Grid container
        self.grid_widget = QWidget()
        self.grid_widget.setStyleSheet("background-color: #e9ecef;")
        self.grid_layout = QGridLayout(self.grid_widget)
        self.grid_layout.setContentsMargins(8, 8, 8, 8)
        self.grid_layout.setSpacing(4)

        scroll_area.setWidget(self.grid_widget)
        main_layout.addWidget(scroll_area)

        # Footer with Close button
        footer_widget = QWidget()
        footer_widget.setStyleSheet("""
            QWidget {
                background-color: #f8f9fa;
                border-top: 1px solid #dee2e6;
            }
        """)
        footer_layout = QHBoxLayout(footer_widget)
        footer_layout.setContentsMargins(16, 12, 16, 12)
        footer_layout.addStretch()

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.close)
        close_btn.setFixedWidth(80)
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: 1px solid #ced4da;
                border-radius: 4px;
                padding: 6px 12px;
            }
            QPushButton:hover { background-color: #e9ecef; }
        """)
        footer_layout.addWidget(close_btn)

        main_layout.addWidget(footer_widget)

    def _populate_grid(self):
        """Populate the grid with story cards."""
        if not self.app or not hasattr(self.app, 'nodes'):
            return

        # Clear existing grid
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.cell_widgets.clear()

        # Group nodes by (status, stage)
        # status 'ready' is the default (equivalent to no special condition)
        matrix: Dict[str, Dict[str, List]] = {st: {s: [] for s in self.STAGES} for st in self.STATUSES}

        for node in self.app.nodes.values():
            if node.id == 'root':
                continue
            if node.terminus:  # Skip terminal nodes
                continue
            stage = node.stage if node.stage in self.STAGES else None
            if not stage:
                continue
            status_val = node.status if node.status else "ready"
            if status_val not in matrix:
                matrix[status_val] = {s: [] for s in self.STAGES}
            matrix[status_val][stage].append(node)

        # Determine which statuses have items (only show non-empty rows)
        active_statuses = [st for st in self.STATUSES if any(matrix.get(st, {}).get(s, []) for s in self.STAGES)]

        # Also include any statuses not in STATUSES but present in data
        for st in matrix:
            if st not in self.STATUSES and any(matrix[st].get(s, []) for s in self.STAGES):
                active_statuses.append(st)

        if not active_statuses:
            # No items to display
            empty_label = QLabel("No active stories to display")
            empty_label.setAlignment(Qt.AlignCenter)
            empty_label.setStyleSheet("font-size: 12pt; color: #6c757d; padding: 40px;")
            self.grid_layout.addWidget(empty_label, 0, 0)
            return

        # Build grid header row (stage names)
        # Row 0: empty corner cell + stage headers
        corner = QLabel("")
        corner.setFixedWidth(100)
        self.grid_layout.addWidget(corner, 0, 0)

        for col_idx, stage in enumerate(self.STAGES):
            header = QLabel(stage.capitalize())
            header.setFixedWidth(180)
            header.setFixedHeight(30)
            header.setAlignment(Qt.AlignCenter)
            color = self.STAGE_COLORS.get(stage, "#6c757d")
            header.setStyleSheet(f"""
                QLabel {{
                    background-color: {color};
                    color: white;
                    font-weight: bold;
                    font-size: 10pt;
                    border-radius: 4px;
                }}
            """)
            self.grid_layout.addWidget(header, 0, col_idx + 1)

        # Build rows for each active status
        for row_idx, status_val in enumerate(active_statuses):
            row_count = sum(len(matrix.get(status_val, {}).get(s, [])) for s in self.STAGES)

            # Row label with count
            row_label = QLabel(f"{status_val}\n({row_count})")
            row_label.setFixedWidth(100)
            row_label.setAlignment(Qt.AlignCenter)
            row_label.setStyleSheet("""
                QLabel {
                    background-color: #f8f9fa;
                    font-size: 9pt;
                    font-weight: bold;
                    border: 1px solid #dee2e6;
                    border-radius: 4px;
                    padding: 4px;
                }
            """)
            self.grid_layout.addWidget(row_label, row_idx + 1, 0)

            # Cells for each stage
            for col_idx, stage in enumerate(self.STAGES):
                cell = self._create_cell(status_val, stage, matrix.get(status_val, {}).get(stage, []))
                self.grid_layout.addWidget(cell, row_idx + 1, col_idx + 1)
                self.cell_widgets[(status_val, stage)] = cell

    def _create_cell(self, status_val: str, stage: str, nodes: List) -> QWidget:
        """Create a cell widget containing cards for the given nodes."""
        cell = QWidget()
        cell.setFixedWidth(180)
        cell.setMinimumHeight(80)
        cell.setStyleSheet("""
            QWidget {
                background-color: #f8f9fa;
                border: 1px solid #dee2e6;
                border-radius: 4px;
            }
        """)

        if not nodes:
            # Empty cell
            layout = QVBoxLayout(cell)
            layout.setContentsMargins(4, 4, 4, 4)
            dash = QLabel("-")
            dash.setAlignment(Qt.AlignCenter)
            dash.setStyleSheet("color: #adb5bd; border: none;")
            layout.addWidget(dash)
            return cell

        # Scrollable container for cards
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: transparent;
            }
            QScrollArea > QWidget > QWidget {
                background-color: transparent;
            }
        """)

        cards_widget = QWidget()
        cards_widget.setStyleSheet("background-color: transparent; border: none;")
        cards_layout = QVBoxLayout(cards_widget)
        cards_layout.setContentsMargins(2, 2, 2, 2)
        cards_layout.setSpacing(2)

        # Sort nodes by ID and add cards
        for node in sorted(nodes, key=lambda n: n.id):
            card = KanbanCard(
                node_id=node.id,
                feature=node.feature,
                status=node.status,
                terminus=node.terminus
            )
            card.doubleClicked.connect(self._on_card_double_clicked)
            cards_layout.addWidget(card)

        cards_layout.addStretch()
        scroll.setWidget(cards_widget)

        cell_layout = QVBoxLayout(cell)
        cell_layout.setContentsMargins(0, 0, 0, 0)
        cell_layout.addWidget(scroll)

        return cell

    def _on_card_double_clicked(self, node_id: str):
        """Handle double-click on a card to show detail view."""
        if self.app and hasattr(self.app, 'show_detail_view'):
            self.app.show_detail_view(node_id)


class ClickableLabel(QLabel):
    """A QLabel that emits a signal when double-clicked."""
    doubleClicked = Signal(str)

    def __init__(self, text: str, node_id: str, parent=None):
        super().__init__(text, parent)
        self.node_id = node_id
        self.setCursor(Qt.PointingHandCursor)
        self.setStyleSheet("color: #0066CC;")

    def mouseDoubleClickEvent(self, event):
        self.doubleClicked.emit(self.node_id)

    def enterEvent(self, event):
        font = self.font()
        font.setUnderline(True)
        self.setFont(font)

    def leaveEvent(self, event):
        font = self.font()
        font.setUnderline(False)
        self.setFont(font)


class DetailView(QWidget):
    """Detail view panel showing all information about a story node."""
    closeRequested = Signal()

    def __init__(self, app: 'XstoryExplorer', parent=None):
        super().__init__(parent)
        self.app = app
        self.current_node_id: Optional[str] = None

        self._setup_ui()

    def _setup_ui(self):
        """Set up the detail view UI with two-column layout."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Combined header bar with navigation, db label, and breadcrumbs
        header_widget = QWidget()
        header_widget.setFixedHeight(30)
        header_widget.setStyleSheet("""
            QWidget {
                background-color: #f8f9fa;
                border-bottom: 1px solid #dee2e6;
            }
        """)
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(8, 2, 8, 2)
        header_layout.setSpacing(4)

        # Breadcrumb area (inline with header)
        self.breadcrumb_widget = QWidget()
        self.breadcrumb_layout = QHBoxLayout(self.breadcrumb_widget)
        self.breadcrumb_layout.setContentsMargins(0, 0, 0, 0)
        self.breadcrumb_layout.setSpacing(4)
        header_layout.addWidget(self.breadcrumb_widget)

        header_layout.addStretch()

        main_layout.addWidget(header_widget)

        # Two-column layout (main content + sidebar)
        content_splitter = QSplitter(Qt.Horizontal)
        content_splitter.setStyleSheet("QSplitter::handle { background-color: #dee2e6; }")

        # Left: Main content area
        main_content_widget = QWidget()
        main_content_widget.setStyleSheet("background-color: #ffffff;")
        main_content_layout = QVBoxLayout(main_content_widget)
        main_content_layout.setContentsMargins(0, 0, 0, 0)
        main_content_layout.setSpacing(0)

        # Scrollable content area
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.NoFrame)
        scroll_area.setStyleSheet("QScrollArea { border: none; background-color: #ffffff; }")

        self.content_widget = QWidget()
        self.content_widget.setStyleSheet("background-color: #ffffff;")
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(24, 16, 24, 16)
        self.content_layout.setSpacing(16)
        self.content_layout.setAlignment(Qt.AlignTop)

        scroll_area.setWidget(self.content_widget)
        main_content_layout.addWidget(scroll_area)

        # Footer with status buttons
        footer_widget = QWidget()
        footer_widget.setStyleSheet("""
            QWidget {
                background-color: #f8f9fa;
                border-top: 1px solid #dee2e6;
            }
        """)
        self.footer_layout = QHBoxLayout(footer_widget)
        self.footer_layout.setContentsMargins(16, 12, 16, 12)
        self.footer_layout.setSpacing(8)

        # Escalated navigation buttons (for Respond mode)
        nav_button_style = """
            QPushButton {
                background-color: #666666;
                color: white;
                font-weight: bold;
                border: none;
                border-radius: 4px;
                padding: 4px 12px;
            }
            QPushButton:hover {
                background-color: #555555;
            }
            QPushButton:pressed {
                background-color: #444444;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #888888;
            }
        """
        self.prev_escalated_btn = QPushButton("< Previous")
        self.prev_escalated_btn.setFixedHeight(32)
        self.prev_escalated_btn.setStyleSheet(nav_button_style)
        self.prev_escalated_btn.clicked.connect(self._go_prev_escalated)
        self.footer_layout.addWidget(self.prev_escalated_btn)

        self.next_escalated_btn = QPushButton("Next >")
        self.next_escalated_btn.setFixedHeight(32)
        self.next_escalated_btn.setStyleSheet(nav_button_style)
        self.next_escalated_btn.clicked.connect(self._go_next_escalated)
        self.footer_layout.addWidget(self.next_escalated_btn)

        # Separator between nav and status buttons
        self.nav_separator = QFrame()
        self.nav_separator.setFrameShape(QFrame.VLine)
        self.nav_separator.setStyleSheet("color: #dee2e6;")
        self.footer_layout.addWidget(self.nav_separator)

        # Container for status buttons (left-aligned)
        self.status_buttons_widget = QWidget()
        self.status_buttons_widget.setStyleSheet("background: transparent;")
        self.status_buttons_layout = QHBoxLayout(self.status_buttons_widget)
        self.status_buttons_layout.setContentsMargins(0, 0, 0, 0)
        self.status_buttons_layout.setSpacing(8)
        self.footer_layout.addWidget(self.status_buttons_widget)

        self.footer_layout.addStretch()

        # Close button (right-aligned)
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self._close)
        close_btn.setFixedWidth(80)
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: 1px solid #ced4da;
                border-radius: 4px;
                padding: 6px 12px;
            }
            QPushButton:hover { background-color: #e9ecef; }
        """)
        self.footer_layout.addWidget(close_btn)

        main_content_layout.addWidget(footer_widget)
        content_splitter.addWidget(main_content_widget)

        # Right: Sidebar
        self.sidebar_widget = QWidget()
        self.sidebar_widget.setMinimumWidth(280)
        self.sidebar_widget.setMaximumWidth(320)
        self.sidebar_widget.setStyleSheet("background-color: #f8f9fa;")

        sidebar_scroll = QScrollArea()
        sidebar_scroll.setWidgetResizable(True)
        sidebar_scroll.setFrameShape(QFrame.NoFrame)
        sidebar_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        sidebar_scroll.setStyleSheet("QScrollArea { border: none; background-color: #f8f9fa; }")

        sidebar_content = QWidget()
        sidebar_content.setStyleSheet("background-color: #f8f9fa;")
        self.sidebar_layout = QVBoxLayout(sidebar_content)
        self.sidebar_layout.setContentsMargins(16, 16, 16, 16)
        self.sidebar_layout.setSpacing(16)
        self.sidebar_layout.setAlignment(Qt.AlignTop)

        sidebar_scroll.setWidget(sidebar_content)
        sidebar_outer_layout = QVBoxLayout(self.sidebar_widget)
        sidebar_outer_layout.setContentsMargins(0, 0, 0, 0)
        sidebar_outer_layout.addWidget(sidebar_scroll)

        content_splitter.addWidget(self.sidebar_widget)
        content_splitter.setSizes([600, 300])

        # Store reference to content_splitter for show/hide
        self.content_splitter = content_splitter
        main_layout.addWidget(content_splitter, 1)  # stretch factor ensures it takes remaining space

        # Empty state widget (shown when no escalated items in Respond mode)
        self.empty_state_widget = QWidget()
        self.empty_state_widget.setStyleSheet("background-color: #2d2d2d;")
        empty_layout = QVBoxLayout(self.empty_state_widget)
        empty_layout.setAlignment(Qt.AlignCenter)
        empty_label = QLabel("Nothing to respond to.\nCheck back later.")
        empty_label.setStyleSheet("""
            QLabel {
                color: #888888;
                font-size: 16pt;
                font-weight: bold;
            }
        """)
        empty_label.setAlignment(Qt.AlignCenter)
        empty_layout.addWidget(empty_label)
        main_layout.addWidget(self.empty_state_widget, 1)
        self.empty_state_widget.hide()

    def _add_status_row(self, node: StoryNode):
        """Add the inline status row (Stage + Hold/Terminus)."""
        stage_color = STATUS_COLORS.get(node.stage, '#666666')

        row_layout = QHBoxLayout()
        row_layout.setSpacing(30)

        # Stage label
        stage_label = QLabel(f"Stage: <span style='color: {stage_color}; font-weight: bold;'>{node.stage}</span>")
        stage_label.setTextFormat(Qt.RichText)
        row_layout.addWidget(stage_label)

        # Terminus supersedes hold status
        if node.terminus:
            term_color = '#CC0000'  # Always red for terminal states
            term_label = QLabel(f"Terminus: <span style='color: {term_color}; font-weight: bold;'>{node.terminus}</span>")
            term_label.setTextFormat(Qt.RichText)
            row_layout.addWidget(term_label)
        elif node.status and node.status != 'ready':
            status_color = STATUS_COLORS.get(node.status, '#888888')
            status_label = QLabel(f"Status: <span style='color: {status_color}; font-weight: bold;'>{node.status}</span>")
            status_label.setTextFormat(Qt.RichText)
            row_layout.addWidget(status_label)

        row_layout.addStretch()
        self.content_layout.addLayout(row_layout)

    def _parse_user_story(self, description: str) -> Optional[dict]:
        """Parse user story format from description.

        Returns dict with 'as_a', 'i_want', 'so_that', and 'remaining' keys if found, None otherwise.
        The 'remaining' key contains any text after the user story (e.g., acceptance criteria).
        """
        import re

        if not description:
            return None

        # Pattern to match user story format (case insensitive)
        # Captures content up to a double newline or end of string for 'so_that'
        pattern = r'\*?\*?As a\*?\*?\s+(.+?)\s+\*?\*?I want\*?\*?\s+(.+?)\s+\*?\*?So that\*?\*?\s+(.+?)(?:\n\n|$)'
        match = re.search(pattern, description, re.IGNORECASE | re.DOTALL)

        if match:
            # Get the remaining text after the user story
            remaining = description[match.end():].strip()
            return {
                'as_a': match.group(1).strip(),
                'i_want': match.group(2).strip(),
                'so_that': match.group(3).strip(),
                'remaining': remaining
            }
        return None

    def _update_breadcrumbs(self, node: StoryNode):
        """Update breadcrumb navigation showing node hierarchy."""
        # Clear existing breadcrumbs
        while self.breadcrumb_layout.count():
            item = self.breadcrumb_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Build ancestor chain
        ancestors = []
        current = node
        while current.parent_id and current.parent_id in self.app.nodes:
            parent = self.app.nodes[current.parent_id]
            ancestors.insert(0, parent)
            current = parent

        # Add ancestors (root node shows feature only, others show "id - feature")
        is_first = True
        for ancestor in ancestors:
            # Arrow separator (skip for first ancestor)
            if not is_first:
                arrow = QLabel(" > ")
                arrow.setStyleSheet("color: #6c757d; font-size: 9pt;")
                self.breadcrumb_layout.addWidget(arrow)
            is_first = False

            # Ancestor link - root node shows only feature
            feature = ancestor.feature[:25] + '...' if len(ancestor.feature) > 25 else ancestor.feature
            if ancestor.id == 'root':
                btn = QPushButton(feature)
            else:
                btn = QPushButton(f"{ancestor.id} - {feature}")
            btn.setStyleSheet("""
                QPushButton {
                    background: transparent;
                    border: none;
                    color: #0066CC;
                    padding: 4px 8px;
                    font-size: 9pt;
                    text-align: left;
                }
                QPushButton:hover { background-color: #e9ecef; border-radius: 4px; }
            """)
            btn.setCursor(Qt.PointingHandCursor)
            ancestor_id = ancestor.id
            btn.clicked.connect(lambda checked, aid=ancestor_id: self.show_node(aid))
            self.breadcrumb_layout.addWidget(btn)

        # Add current node (not clickable)
        if ancestors:
            arrow = QLabel(" > ")
            arrow.setStyleSheet("color: #6c757d; font-size: 9pt;")
            self.breadcrumb_layout.addWidget(arrow)

        # Current node - root shows feature only, others show "id - feature"
        feature = node.feature[:30] + '...' if len(node.feature) > 30 else node.feature
        if node.id == 'root':
            current_label = QLabel(feature)
        else:
            current_label = QLabel(f"{node.id} - {feature}")
        current_label.setStyleSheet("color: #212529; font-weight: 500; font-size: 9pt; padding: 4px 8px;")
        self.breadcrumb_layout.addWidget(current_label)

        self.breadcrumb_layout.addStretch()

    def _add_feature_section(self, node: StoryNode):
        """Add the feature section with ID badge and stage badge."""
        # Header row with ID badge, stage badge, and feature
        header_widget = QWidget()
        header_widget.setStyleSheet("background: transparent;")
        header_layout = QVBoxLayout(header_widget)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(8)

        # Top row: ID badge + Stage badge
        badges_row = QHBoxLayout()
        badges_row.setSpacing(12)

        # ID badge
        id_badge = QLabel(node.id)
        id_badge.setStyleSheet("""
            background-color: #e9ecef;
            color: #495057;
            padding: 4px 10px;
            border-radius: 4px;
            font-family: monospace;
            font-size: 10pt;
        """)
        badges_row.addWidget(id_badge)

        # Stage badge with icon
        stage_color = STATUS_COLORS.get(node.stage, '#666666')
        stage_icon = self._get_stage_icon(node)
        stage_badge = QLabel(f"{stage_icon} {node.stage}")
        stage_badge.setStyleSheet(f"""
            background-color: {self._lighten_color(stage_color, 0.85)};
            color: {stage_color};
            padding: 4px 12px;
            border-radius: 12px;
            font-weight: bold;
            font-size: 9pt;
            border: 1px solid {self._lighten_color(stage_color, 0.7)};
        """)
        badges_row.addWidget(stage_badge)

        # Hold/Terminus badge if applicable
        if node.terminus:
            term_color = '#CC0000'
            term_icon = TERMINUS_ICONS.get(node.terminus, '')
            term_badge = QLabel(f"{term_icon} {node.terminus}")
            term_badge.setStyleSheet(f"""
                background-color: #fce4e4;
                color: {term_color};
                padding: 4px 12px;
                border-radius: 12px;
                font-weight: bold;
                font-size: 9pt;
                border: 1px solid #f5c6c6;
            """)
            badges_row.addWidget(term_badge)
        elif node.status and node.status != 'ready':
            status_color = STATUS_COLORS.get(node.status, '#888888')
            status_icon = HOLD_ICONS.get(node.status, '')
            status_badge = QLabel(f"{status_icon} {node.status}")
            status_badge.setStyleSheet(f"""
                background-color: {self._lighten_color(status_color, 0.85)};
                color: {status_color};
                padding: 4px 12px;
                border-radius: 12px;
                font-weight: bold;
                font-size: 9pt;
                border: 1px solid {self._lighten_color(status_color, 0.7)};
            """)
            badges_row.addWidget(status_badge)

        badges_row.addStretch()
        header_layout.addLayout(badges_row)

        # Feature
        feature_label = QLabel(node.feature)
        feature_label.setStyleSheet("font-size: 18pt; font-weight: bold; color: #212529;")
        feature_label.setWordWrap(True)
        feature_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        header_layout.addWidget(feature_label)

        self.content_layout.addWidget(header_widget)

    def _get_stage_icon(self, node: StoryNode) -> str:
        """Get appropriate icon for node's stage."""
        stage_icons = {
            'concept': '*',
            'planning': '#',
            'implementing': '>',
            'testing': '?',
            'releasing': '^',
        }
        return stage_icons.get(node.stage, '>')

    def _lighten_color(self, hex_color: str, factor: float = 0.85) -> str:
        """Lighten a hex color by mixing with white."""
        hex_color = hex_color.lstrip('#')
        r = int(hex_color[0:2], 16)
        g = int(hex_color[2:4], 16)
        b = int(hex_color[4:6], 16)
        r = int(r + (255 - r) * factor)
        g = int(g + (255 - g) * factor)
        b = int(b + (255 - b) * factor)
        return f"#{r:02x}{g:02x}{b:02x}"

    def _add_progress_bar(self, node: StoryNode):
        """Add workflow progress bar showing stage progression."""
        progress_widget = QWidget()
        progress_widget.setStyleSheet("background: transparent;")
        progress_layout = QVBoxLayout(progress_widget)
        progress_layout.setContentsMargins(0, 0, 0, 0)
        progress_layout.setSpacing(4)

        # Calculate stage index for progress
        stage_index = STAGE_ORDER.index(node.stage) if node.stage in STAGE_ORDER else 0

        # Progress bar
        progress_percent = ((stage_index + 1) / len(STAGE_ORDER)) * 100
        stage_color = STATUS_COLORS.get(node.stage, '#666666')

        bar_widget = QWidget()
        bar_widget.setFixedHeight(8)
        bar_widget.setStyleSheet(f"""
            background-color: #e9ecef;
            border-radius: 4px;
        """)
        bar_layout = QHBoxLayout(bar_widget)
        bar_layout.setContentsMargins(0, 0, 0, 0)
        bar_layout.setSpacing(0)

        # Filled portion
        filled = QWidget()
        filled.setStyleSheet(f"""
            background-color: {stage_color};
            border-radius: 4px;
        """)
        bar_layout.addWidget(filled, int(progress_percent))

        # Empty portion
        empty = QWidget()
        empty.setStyleSheet("background: transparent;")
        bar_layout.addWidget(empty, int(100 - progress_percent))

        progress_layout.addWidget(bar_widget)

        # Stage labels below bar
        stages_row = QHBoxLayout()
        stages_row.setSpacing(0)
        key_stages = ['concept', 'planning', 'implementing', 'testing', 'releasing']
        for i, stage in enumerate(key_stages):
            stage_lbl = QLabel(stage)
            is_current = stage == node.stage
            is_past = STAGE_ORDER.index(stage) < stage_index if stage in STAGE_ORDER else False
            color = '#212529' if is_current else ('#6c757d' if is_past else '#adb5bd')
            weight = 'bold' if is_current else 'normal'
            stage_lbl.setStyleSheet(f"color: {color}; font-size: 8pt; font-weight: {weight};")
            if i == 0:
                stage_lbl.setAlignment(Qt.AlignLeft)
            elif i == len(key_stages) - 1:
                stage_lbl.setAlignment(Qt.AlignRight)
            else:
                stage_lbl.setAlignment(Qt.AlignCenter)
            stages_row.addWidget(stage_lbl, 1)

        progress_layout.addLayout(stages_row)

        self.content_layout.addWidget(progress_widget)

    def _add_story_section(self, node: StoryNode, story: dict):
        """Add the Story section with user story format and icons.

        Args:
            node: The story node being displayed
            story: Parsed user story dict with 'as_a', 'i_want', 'so_that' keys
        """
        # Story content box with gradient background
        story_widget = QWidget()
        story_widget.setStyleSheet("""
            QWidget {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #fefefe, stop:1 #f8f9fa);
                border-radius: 8px;
            }
        """)
        story_layout = QVBoxLayout(story_widget)
        story_layout.setContentsMargins(16, 12, 16, 12)
        story_layout.setSpacing(12)

        # As a row
        as_a_row = QHBoxLayout()
        as_a_row.setSpacing(12)
        as_a_icon = QLabel("As a")
        as_a_icon.setStyleSheet("""
            color: #6c757d;
            font-size: 9pt;
            font-weight: bold;
            text-transform: uppercase;
        """)
        as_a_row.addWidget(as_a_icon)
        as_a_row.addStretch()
        story_layout.addLayout(as_a_row)

        as_a_text = QLabel(story['as_a'])
        as_a_text.setStyleSheet("color: #212529; font-size: 11pt; margin-left: 20px; background: transparent;")
        as_a_text.setWordWrap(True)
        as_a_text.setTextInteractionFlags(Qt.TextSelectableByMouse)
        story_layout.addWidget(as_a_text)

        # I want row
        i_want_row = QHBoxLayout()
        i_want_row.setSpacing(12)
        i_want_icon = QLabel("I want")
        i_want_icon.setStyleSheet("""
            color: #6c757d;
            font-size: 9pt;
            font-weight: bold;
            text-transform: uppercase;
        """)
        i_want_row.addWidget(i_want_icon)
        i_want_row.addStretch()
        story_layout.addLayout(i_want_row)

        i_want_text = QLabel(story['i_want'])
        i_want_text.setStyleSheet("color: #212529; font-size: 11pt; margin-left: 20px; background: transparent;")
        i_want_text.setWordWrap(True)
        i_want_text.setTextInteractionFlags(Qt.TextSelectableByMouse)
        story_layout.addWidget(i_want_text)

        # So that row
        so_that_row = QHBoxLayout()
        so_that_row.setSpacing(12)
        so_that_icon = QLabel("So that")
        so_that_icon.setStyleSheet("""
            color: #6c757d;
            font-size: 9pt;
            font-weight: bold;
            text-transform: uppercase;
        """)
        so_that_row.addWidget(so_that_icon)
        so_that_row.addStretch()
        story_layout.addLayout(so_that_row)

        so_that_text = QLabel(story['so_that'])
        so_that_text.setStyleSheet("color: #212529; font-size: 11pt; margin-left: 20px; background: transparent;")
        so_that_text.setWordWrap(True)
        so_that_text.setTextInteractionFlags(Qt.TextSelectableByMouse)
        story_layout.addWidget(so_that_text)

        self.content_layout.addWidget(story_widget)

    def _add_user_story_display(self, node: StoryNode):
        """Add the User Story section displaying the story field.

        Args:
            node: The story node being displayed
        """
        # Story content box with gradient background
        story_widget = QWidget()
        story_widget.setStyleSheet("""
            QWidget {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #fefefe, stop:1 #f8f9fa);
                border-radius: 8px;
            }
        """)
        story_layout = QVBoxLayout(story_widget)
        story_layout.setContentsMargins(16, 12, 16, 12)
        story_layout.setSpacing(8)

        # Header
        header = QLabel("User Story")
        header.setStyleSheet("""
            color: #6c757d;
            font-size: 9pt;
            font-weight: bold;
            text-transform: uppercase;
            background: transparent;
        """)
        story_layout.addWidget(header)

        # Story text
        story_text = QLabel(node.story)
        story_text.setStyleSheet("color: #212529; font-size: 11pt; background: transparent;")
        story_text.setWordWrap(True)
        story_text.setTextInteractionFlags(Qt.TextSelectableByMouse)
        story_layout.addWidget(story_text)

        self.content_layout.addWidget(story_widget)

    def _update_sidebar(self, node: StoryNode):
        """Update sidebar with metadata, tree context, and actions."""
        # Clear existing sidebar content
        while self.sidebar_layout.count():
            item = self.sidebar_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                self._clear_layout(item.layout())

        # Metadata Card
        self._add_sidebar_metadata(node)

        # Acceptance Criteria Card
        self._add_acceptance_criteria_card(node)

        self.sidebar_layout.addStretch()

    def _add_sidebar_metadata(self, node: StoryNode):
        """Add metadata card to sidebar with plain text layout."""
        card = QWidget()
        card.setStyleSheet("""
            QWidget {
                background-color: #ffffff;
                border-radius: 8px;
            }
        """)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(16, 12, 16, 12)
        card_layout.setSpacing(8)

        # Header
        header = QLabel("Metadata")
        header.setStyleSheet("""
            color: #6c757d;
            font-size: 9pt;
            font-weight: bold;
            text-transform: uppercase;
            letter-spacing: 1px;
            background: transparent;
        """)
        card_layout.addWidget(header)

        # Parent row
        parent_row = QHBoxLayout()
        parent_row.setSpacing(6)
        parent_label = QLabel("Parent:")
        parent_label.setStyleSheet("color: #6c757d; font-size: 9pt; background: transparent;")
        parent_row.addWidget(parent_label)

        if node.parent_id and node.parent_id in self.app.nodes:
            parent_node = self.app.nodes[node.parent_id]
            parent_feature = parent_node.feature[:20] + '...' if len(parent_node.feature) > 20 else parent_node.feature
            parent_link = ClickableLabel(f"{node.parent_id} - {parent_feature}", node.parent_id)
            parent_link.setStyleSheet("font-size: 9pt; background: transparent;")
            parent_link.doubleClicked.connect(self.show_node)
            parent_row.addWidget(parent_link)
        else:
            no_parent = QLabel("(root)")
            no_parent.setStyleSheet("color: #adb5bd; font-size: 9pt; background: transparent;")
            parent_row.addWidget(no_parent)

        parent_row.addStretch()
        card_layout.addLayout(parent_row)

        # Children row
        children_row = QHBoxLayout()
        children_row.setSpacing(6)
        children_label = QLabel("Children:")
        children_label.setStyleSheet("color: #6c757d; font-size: 9pt; background: transparent;")
        children_row.addWidget(children_label)
        children_value = QLabel(str(len(node.children)))
        children_value.setStyleSheet("color: #212529; font-size: 9pt; background: transparent;")
        children_row.addWidget(children_value)
        children_row.addStretch()
        card_layout.addLayout(children_row)

        # Capacity row
        capacity_row = QHBoxLayout()
        capacity_row.setSpacing(6)
        capacity_label = QLabel("Capacity:")
        capacity_label.setStyleSheet("color: #6c757d; font-size: 9pt; background: transparent;")
        capacity_row.addWidget(capacity_label)

        capacity_type = "dynamic" if node.capacity is None else str(node.capacity)
        max_capacity = node.capacity if node.capacity else 3
        used = len(node.children)
        capacity_value = QLabel(f"{capacity_type} ({used}/{max_capacity})")
        capacity_value.setStyleSheet("color: #212529; font-size: 9pt; background: transparent;")
        capacity_row.addWidget(capacity_value)
        capacity_row.addStretch()
        card_layout.addLayout(capacity_row)

        # Descendants row
        desc_row = QHBoxLayout()
        desc_row.setSpacing(6)
        desc_label = QLabel("Descendants:")
        desc_label.setStyleSheet("color: #6c757d; font-size: 9pt; background: transparent;")
        desc_row.addWidget(desc_label)
        desc_value = QLabel(str(node.descendants_count))
        desc_value.setStyleSheet("color: #212529; font-size: 9pt; background: transparent;")
        desc_row.addWidget(desc_value)
        desc_row.addStretch()
        card_layout.addLayout(desc_row)

        self.sidebar_layout.addWidget(card)

    def _add_acceptance_criteria_card(self, node: StoryNode):
        """Add acceptance criteria card to sidebar."""
        if not node.success_criteria:
            return

        card = QWidget()
        card.setStyleSheet("""
            QWidget {
                background-color: #ffffff;
                border-radius: 8px;
            }
        """)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(16, 12, 16, 12)
        card_layout.setSpacing(8)

        # Header
        header = QLabel("Acceptance Criteria")
        header.setStyleSheet("""
            color: #6c757d;
            font-size: 9pt;
            font-weight: bold;
            text-transform: uppercase;
            letter-spacing: 1px;
            background: transparent;
        """)
        card_layout.addWidget(header)

        # Parse and display criteria items
        criteria_lines = node.success_criteria.strip().split('\n')
        for line in criteria_lines:
            line = line.strip()
            if not line:
                continue

            # Check if this is a checkbox item
            is_checked = False
            display_text = line

            if line.startswith('- [x]') or line.startswith('- [X]'):
                is_checked = True
                display_text = line[5:].strip()
            elif line.startswith('- [ ]'):
                is_checked = False
                display_text = line[5:].strip()
            elif line.startswith('- '):
                display_text = line[2:].strip()

            # Create row for criterion
            row = QHBoxLayout()
            row.setSpacing(6)

            # Checkbox indicator
            checkbox_label = QLabel("✓" if is_checked else "○")
            checkbox_label.setStyleSheet(f"""
                color: {'#28a745' if is_checked else '#adb5bd'};
                font-size: 10pt;
                background: transparent;
            """)
            checkbox_label.setFixedWidth(16)
            row.addWidget(checkbox_label)

            # Criterion text
            text_label = QLabel(display_text)
            text_label.setStyleSheet(f"""
                color: {'#6c757d' if is_checked else '#212529'};
                font-size: 9pt;
                background: transparent;
                {'text-decoration: line-through;' if is_checked else ''}
            """)
            text_label.setWordWrap(True)
            row.addWidget(text_label, 1)

            card_layout.addLayout(row)

        self.sidebar_layout.addWidget(card)

    def _add_metadata_card(self, node: StoryNode):
        """Add the metadata card with Parent, Children, Capacity, Descendants."""
        card_widget = QWidget()
        card_widget.setStyleSheet("""
            QWidget {
                background-color: #f5f5f5;
                border-radius: 4px;
                padding: 8px;
            }
        """)
        card_layout = QVBoxLayout(card_widget)
        card_layout.setContentsMargins(12, 8, 12, 8)
        card_layout.setSpacing(8)

        # Row 1: Parent (clickable)
        parent_row = QHBoxLayout()
        parent_label = QLabel("Parent:")
        parent_label.setStyleSheet("font-weight: bold; background: transparent;")
        parent_row.addWidget(parent_label)

        if node.parent_id:
            parent_node = self.app.nodes.get(node.parent_id)
            if parent_node:
                parent_feature = parent_node.feature[:30] + '...' if len(parent_node.feature) > 30 else parent_node.feature
                link_text = f"{node.parent_id} - {parent_feature}"
            else:
                link_text = node.parent_id
            parent_link = ClickableLabel(link_text, node.parent_id)
            parent_link.doubleClicked.connect(self.show_node)
            parent_row.addWidget(parent_link)
        else:
            parent_value = QLabel("(none)")
            parent_value.setStyleSheet("background: transparent;")
            parent_row.addWidget(parent_value)

        parent_row.addStretch()
        card_layout.addLayout(parent_row)

        # Row 2: Children, Capacity, Descendants
        stats_row = QHBoxLayout()
        stats_row.setSpacing(30)

        # Children
        children_label = QLabel(f"<b>Children:</b> {len(node.children)}")
        children_label.setTextFormat(Qt.RichText)
        children_label.setStyleSheet("background: transparent;")
        stats_row.addWidget(children_label)

        # Capacity
        capacity_text = str(node.capacity) if node.capacity is not None else "dynamic"
        capacity_label = QLabel(f"<b>Capacity:</b> {capacity_text}")
        capacity_label.setTextFormat(Qt.RichText)
        capacity_label.setStyleSheet("background: transparent;")
        stats_row.addWidget(capacity_label)

        # Descendants
        descendants_label = QLabel(f"<b>Descendants:</b> {node.descendants_count}")
        descendants_label.setTextFormat(Qt.RichText)
        descendants_label.setStyleSheet("background: transparent;")
        stats_row.addWidget(descendants_label)

        stats_row.addStretch()
        card_layout.addLayout(stats_row)

        self.content_layout.addWidget(card_widget)

    def show_node(self, node_id: str):
        """Display details for a specific node with improved layout."""
        if node_id not in self.app.nodes:
            return

        self.current_node_id = node_id
        node = self.app.nodes[node_id]

        self._update_escalated_nav_buttons()

        # Update breadcrumbs
        self._update_breadcrumbs(node)

        # Clear main content area (widgets AND layouts)
        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                self._clear_layout(item.layout())

        # Feature section with badges
        self._add_feature_section(node)

        # Display user story from story field, or parse from description as fallback
        if node.story:
            self._add_user_story_display(node)
        else:
            # Fallback: parse user story from description
            story = self._parse_user_story(node.description)
            if story:
                self._add_story_section(node, story)

        # Workflow progress bar
        self._add_progress_bar(node)

        # Success Criteria section
        if node.success_criteria:
            self._add_success_criteria_section(node)

        # Description section - always show if present
        if node.description:
            self._add_description_section(node, node.description)

        # Notes section
        if node.notes:
            self._add_notes_section(node)

        # Add stretch at the end
        self.content_layout.addStretch()

        # Update sidebar
        self._update_sidebar(node)

        # Add status action buttons to footer
        self._add_status_actions(node)

    def _add_description_section(self, node: StoryNode, description_text: str):
        """Add the description section.

        Args:
            node: The story node being displayed
            description_text: The text to display (may be full description or remaining after user story)
        """
        if not description_text:
            return

        desc_widget = QWidget()
        desc_widget.setStyleSheet("background: transparent;")
        desc_layout = QVBoxLayout(desc_widget)
        desc_layout.setContentsMargins(0, 0, 0, 0)
        desc_layout.setSpacing(8)

        header = QLabel("Description")
        header.setStyleSheet("font-size: 12pt; font-weight: bold; color: #212529;")
        desc_layout.addWidget(header)

        text = QLabel(description_text)
        text.setStyleSheet("""
            color: #495057;
            font-size: 10pt;
            line-height: 1.5;
            background-color: #f8f9fa;
            padding: 12px;
            border-radius: 6px;
        """)
        text.setWordWrap(True)
        text.setTextInteractionFlags(Qt.TextSelectableByMouse)
        desc_layout.addWidget(text)

        self.content_layout.addWidget(desc_widget)

    def _add_success_criteria_section(self, node: StoryNode):
        """Add the success criteria section.

        Args:
            node: The story node being displayed
        """
        if not node.success_criteria:
            return

        criteria_widget = QWidget()
        criteria_widget.setStyleSheet("background: transparent;")
        criteria_layout = QVBoxLayout(criteria_widget)
        criteria_layout.setContentsMargins(0, 0, 0, 0)
        criteria_layout.setSpacing(8)

        header = QLabel("Success Criteria")
        header.setStyleSheet("font-size: 12pt; font-weight: bold; color: #212529;")
        criteria_layout.addWidget(header)

        text = QLabel(node.success_criteria)
        text.setStyleSheet("""
            color: #495057;
            font-size: 10pt;
            line-height: 1.5;
            background-color: #f8f9fa;
            padding: 12px;
            border-radius: 6px;
        """)
        text.setWordWrap(True)
        text.setTextInteractionFlags(Qt.TextSelectableByMouse)
        criteria_layout.addWidget(text)

        self.content_layout.addWidget(criteria_widget)

    def _add_notes_section(self, node: StoryNode):
        """Add the notes section."""
        notes_widget = QWidget()
        notes_widget.setStyleSheet("background: transparent;")
        notes_layout = QVBoxLayout(notes_widget)
        notes_layout.setContentsMargins(0, 0, 0, 0)
        notes_layout.setSpacing(8)

        header = QLabel("Notes")
        header.setStyleSheet("font-size: 12pt; font-weight: bold; color: #212529;")
        notes_layout.addWidget(header)

        text = QLabel(node.notes)
        text.setStyleSheet("""
            color: #495057;
            font-size: 10pt;
            background-color: #fff3cd;
            padding: 12px;
            border-radius: 6px;
            border-left: 4px solid #ffc107;
        """)
        text.setWordWrap(True)
        text.setTextInteractionFlags(Qt.TextSelectableByMouse)
        notes_layout.addWidget(text)

        self.content_layout.addWidget(notes_widget)

    def _add_separator(self):
        """Add a horizontal line separator."""
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        self.content_layout.addWidget(line)

    def _add_field(self, label: str, value: str, color: Optional[str] = None):
        """Add a simple label: value field."""
        row_layout = QHBoxLayout()
        label_widget = QLabel(f"{label}:")
        label_widget.setStyleSheet("font-weight: bold;")
        label_widget.setFixedWidth(120)
        row_layout.addWidget(label_widget)

        value_widget = QLabel(value)
        value_widget.setWordWrap(True)
        value_widget.setTextInteractionFlags(Qt.TextSelectableByMouse)
        if color:
            value_widget.setStyleSheet(f"color: {color};")
        row_layout.addWidget(value_widget)
        row_layout.addStretch()

        self.content_layout.addLayout(row_layout)

    def _add_link_field(self, label: str, node_id: str):
        """Add a clickable link field."""
        row_layout = QHBoxLayout()
        label_widget = QLabel(f"{label}:")
        label_widget.setStyleSheet("font-weight: bold;")
        label_widget.setFixedWidth(120)
        row_layout.addWidget(label_widget)

        node = self.app.nodes.get(node_id)
        link_text = node_id
        if node:
            feature = node.feature[:40] + '...' if len(node.feature) > 40 else node.feature
            link_text = f"{node_id} - {feature}"

        link = ClickableLabel(link_text, node_id)
        link.doubleClicked.connect(self.show_node)
        row_layout.addWidget(link)
        row_layout.addStretch()

        self.content_layout.addLayout(row_layout)

    def _add_child_link(self, child: StoryNode):
        """Add a clickable child link."""
        feature = child.feature[:50] + '...' if len(child.feature) > 50 else child.feature
        link_text = f"  {child.id} [{child.status}] - {feature}"

        link = ClickableLabel(link_text, child.id)
        link.doubleClicked.connect(self.show_node)
        self.content_layout.addWidget(link)

    def _add_text_field(self, label: str, text: str):
        """Add a multi-line text field that expands to fit content."""
        label_widget = QLabel(f"{label}:")
        label_widget.setStyleSheet("font-weight: bold;")
        self.content_layout.addWidget(label_widget)

        text_widget = QLabel(text)
        text_widget.setWordWrap(True)
        text_widget.setTextInteractionFlags(Qt.TextSelectableByMouse)
        text_widget.setStyleSheet(
            "background-color: #f5f5f5; padding: 8px; border-radius: 4px;"
        )
        self.content_layout.addWidget(text_widget)

    def _add_status_actions(self, node: StoryNode):
        """Add context-aware status action buttons to footer based on current mode."""
        # Clear existing status buttons from footer
        self._clear_status_buttons()

        # Get available transitions based on Respond mode state
        # For escalated nodes, use stage-aware dictionaries (node.effective_status loses stage context)
        in_respond_mode = self.app.respond_mode_active
        if node.status == 'escalated':
            if in_respond_mode:
                transitions = ESCALATED_RESPOND_TRANSITIONS.get(node.stage, [])
            else:
                transitions = ESCALATED_FILTER_TRANSITIONS.get(node.stage, [])
        elif in_respond_mode:
            transitions = RESPOND_TRANSITIONS.get(node.effective_status, [])
        else:
            transitions = FILTER_TRANSITIONS.get(node.effective_status, [])

        if not transitions:
            return

        # Add status buttons to footer
        for target_status in transitions:
            status_color = STATUS_COLORS.get(target_status, '#666666')
            btn = QPushButton(f"→ {target_status}")
            btn.setFixedHeight(32)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {status_color};
                    color: white;
                    font-weight: bold;
                    border: none;
                    border-radius: 4px;
                    padding: 4px 12px;
                }}
                QPushButton:hover {{
                    background-color: {self._darken_color(status_color)};
                }}
                QPushButton:pressed {{
                    background-color: {self._darken_color(status_color, 0.7)};
                }}
            """)
            btn.clicked.connect(
                lambda checked, ns=target_status, nid=node.id: self._on_status_button_clicked(nid, ns)
            )
            self.status_buttons_layout.addWidget(btn)

    def _clear_status_buttons(self):
        """Clear all status buttons from the footer."""
        while self.status_buttons_layout.count():
            item = self.status_buttons_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _darken_color(self, hex_color: str, factor: float = 0.85) -> str:
        """Darken a hex color by the given factor."""
        hex_color = hex_color.lstrip('#')
        r = int(hex_color[0:2], 16)
        g = int(hex_color[2:4], 16)
        b = int(hex_color[4:6], 16)
        r = int(r * factor)
        g = int(g * factor)
        b = int(b * factor)
        return f"#{r:02x}{g:02x}{b:02x}"

    def _get_nodes_with_status(self, status: str) -> List[str]:
        """Get list of node IDs that have the given effective_status."""
        return [node_id for node_id, node in self.app.nodes.items() if node.effective_status == status]

    def _get_escalated_nodes(self) -> List[str]:
        """Get list of escalated node IDs in tree order."""
        escalated = [
            node_id for node_id, node in self.app.nodes.items()
            if node.status == 'escalated'
        ]
        return sorted(escalated, key=lambda nid: self.app._sort_key(nid))

    def _update_escalated_nav_buttons(self):
        """Update the state of escalated navigation buttons and empty state display."""
        # Hide buttons if not in Respond mode
        in_respond_mode = self.app.respond_mode_active
        self.prev_escalated_btn.setVisible(in_respond_mode)
        self.next_escalated_btn.setVisible(in_respond_mode)
        self.nav_separator.setVisible(in_respond_mode)

        if not in_respond_mode:
            # Not in Respond mode - always show content, hide empty state
            self.content_splitter.show()
            self.empty_state_widget.hide()
            return

        escalated = self._get_escalated_nodes()

        # Show empty state if no escalated nodes
        if not escalated:
            self.content_splitter.hide()
            self.empty_state_widget.show()
            self.prev_escalated_btn.setEnabled(False)
            self.next_escalated_btn.setEnabled(False)
            return

        # Have escalated nodes - show content
        self.content_splitter.show()
        self.empty_state_widget.hide()

        # Check if current node is in escalated list
        if self.current_node_id not in escalated:
            self.prev_escalated_btn.setEnabled(False)
            self.next_escalated_btn.setEnabled(False)
            return

        idx = escalated.index(self.current_node_id)
        self.prev_escalated_btn.setEnabled(idx > 0)
        self.next_escalated_btn.setEnabled(idx < len(escalated) - 1)

    def _go_prev_escalated(self):
        """Navigate to previous escalated node."""
        escalated = self._get_escalated_nodes()
        if self.current_node_id in escalated:
            idx = escalated.index(self.current_node_id)
            if idx > 0:
                self.show_node(escalated[idx - 1])

    def _go_next_escalated(self):
        """Navigate to next escalated node."""
        escalated = self._get_escalated_nodes()
        if self.current_node_id in escalated:
            idx = escalated.index(self.current_node_id)
            if idx < len(escalated) - 1:
                self.show_node(escalated[idx + 1])

    def _on_status_button_clicked(self, node_id: str, new_status: str):
        """Handle status button click - change status and navigate to next node with same original status."""
        # Get the original status before changing
        original_status = self.app.nodes[node_id].status if node_id in self.app.nodes else None

        # Get list of nodes with the original status (before the change)
        nodes_with_original_status = self._get_nodes_with_status(original_status) if original_status else []

        # Find the current node's position and the next node in the list
        next_node_id = None
        if node_id in nodes_with_original_status:
            current_index = nodes_with_original_status.index(node_id)
            # Look for the next node (after this one) with the original status
            if current_index < len(nodes_with_original_status) - 1:
                next_node_id = nodes_with_original_status[current_index + 1]
            elif current_index > 0:
                # If no next, fall back to previous node with original status
                next_node_id = nodes_with_original_status[current_index - 1]

        # Change the status
        self.app._change_node_status(node_id, new_status)

        # Navigate to the next node with the original status, or stay on current if none
        if next_node_id:
            self.show_node(next_node_id)
        elif self.current_node_id:
            # No other nodes with original status - stay on current node
            self.show_node(self.current_node_id)

    def _close(self):
        """Close detail view and return to tree view."""
        self.closeRequested.emit()

    def _clear_layout(self, layout):
        """Recursively clear and delete a layout and its contents."""
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                self._clear_layout(item.layout())

class XstoryExplorer(QMainWindow):
    """Main application class."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Xstory v1.5")
        self.setGeometry(100, 100, 900, 700)

        self.db_path: Optional[str] = None
        self.nodes: Dict[str, StoryNode] = {}
        self.status_checkboxes: Dict[str, QCheckBox] = {}
        self.tree_items: Dict[str, QTreeWidgetItem] = {}  # Maps node_id to QTreeWidgetItem
        self._focused_node_id: Optional[str] = None  # Tracks focused node for "Clear Focus"
        # Two independent toggle states (replacing single current_mode)
        self.filter_sidebar_visible: bool = False  # Whether filter sidebar is shown
        self.respond_mode_active: bool = True  # Whether Respond preset is applied
        self._saved_checkbox_states: Dict[str, bool] = {}  # Last filter-mode checkbox states
        self._checkbox_change_internal: bool = False  # Flag to ignore programmatic checkbox changes

        self._setup_ui()
        self._try_auto_detect_db()

    def _setup_ui(self):
        """Set up the user interface."""
        # Central widget with stacked layout for switching views
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)

        # Top toolbar
        toolbar_layout = QHBoxLayout()

        # Repo name label
        self.repo_label = QLabel("SyncoPaid")
        self.repo_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        toolbar_layout.addWidget(self.repo_label)

        toolbar_layout.addStretch()

        # Two independent toggle buttons
        self._filter_icon = QIcon(str(Path(__file__).parent / "filter.png"))

        # Filter button: toggles sidebar visibility
        self.filter_toggle_btn = QPushButton()
        self.filter_toggle_btn.setIcon(self._filter_icon)
        self.filter_toggle_btn.setCheckable(True)
        self.filter_toggle_btn.setFixedWidth(40)
        self.filter_toggle_btn.setToolTip("Toggle filter sidebar")
        self.filter_toggle_btn.clicked.connect(self._toggle_filter_sidebar)
        toolbar_layout.addWidget(self.filter_toggle_btn)

        # Respond button: applies/removes preset filter
        self.respond_toggle_btn = QPushButton("🙋")
        self.respond_toggle_btn.setCheckable(True)
        self.respond_toggle_btn.setFixedWidth(40)
        self.respond_toggle_btn.setToolTip("Apply Respond preset (Escalated + Shipped)")
        self.respond_toggle_btn.clicked.connect(self._toggle_respond_mode)
        toolbar_layout.addWidget(self.respond_toggle_btn)

        # State diagram button: opens state transition diagram viewer
        self.state_diagram_btn = QPushButton()
        icon_path = Path(__file__).parent / "assets" / "story-tree.ico"
        if icon_path.exists():
            self.state_diagram_btn.setIcon(QIcon(str(icon_path)))
            self.state_diagram_btn.setIconSize(QSize(24, 24))
        else:
            self.state_diagram_btn.setText("🌳")  # Fallback if icon not found
        self.state_diagram_btn.setFixedWidth(40)
        self.state_diagram_btn.setToolTip("View state transitions")
        self.state_diagram_btn.setStyleSheet(
            "QPushButton { background-color: #e9ecef; }"
            "QPushButton:hover { background-color: #dee2e6; }"
        )
        self.state_diagram_btn.clicked.connect(self._show_state_diagram)
        toolbar_layout.addWidget(self.state_diagram_btn)

        # Heatmap button: opens bottleneck heatmap
        self.heatmap_btn = QPushButton("Heatmap")
        self.heatmap_btn.setFixedWidth(65)
        self.heatmap_btn.setToolTip("View bottleneck heatmap")
        self.heatmap_btn.setStyleSheet(
            "QPushButton { background-color: #e9ecef; }"
            "QPushButton:hover { background-color: #dee2e6; }"
        )
        self.heatmap_btn.clicked.connect(self._show_heatmap_view)
        toolbar_layout.addWidget(self.heatmap_btn)

        # Swimlanes button: opens Swimlanes view
        self.swimlanes_btn = QPushButton("Swim")
        self.swimlanes_btn.setFixedWidth(50)
        self.swimlanes_btn.setToolTip("View Swimlanes (stage x status)")
        self.swimlanes_btn.setStyleSheet(
            "QPushButton { background-color: #e9ecef; }"
            "QPushButton:hover { background-color: #dee2e6; }"
        )
        self.swimlanes_btn.clicked.connect(self._show_swimlanes_view)
        toolbar_layout.addWidget(self.swimlanes_btn)

        # Kanban button: opens Kanban view
        self.kanban_btn = QPushButton("Kanban")
        self.kanban_btn.setFixedWidth(60)
        self.kanban_btn.setToolTip("View Kanban board")
        self.kanban_btn.setStyleSheet(
            "QPushButton { background-color: #e9ecef; }"
            "QPushButton:hover { background-color: #dee2e6; }"
        )
        self.kanban_btn.clicked.connect(self._show_kanban_view)
        toolbar_layout.addWidget(self.kanban_btn)

        self._update_toggle_buttons()

        self.main_layout.addLayout(toolbar_layout)

        # Container for switchable views
        self.view_container = QWidget()
        self.view_layout = QVBoxLayout(self.view_container)
        self.view_layout.setContentsMargins(0, 0, 0, 0)

        # Tree view frame
        self.tree_view_frame = QWidget()
        tree_view_layout = QVBoxLayout(self.tree_view_frame)
        tree_view_layout.setContentsMargins(0, 0, 0, 0)

        # Splitter for tree and filters
        splitter = QSplitter(Qt.Horizontal)

        # Left panel: Tree view
        tree_container = QWidget()
        tree_container_layout = QVBoxLayout(tree_container)
        tree_container_layout.setContentsMargins(0, 0, 0, 0)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["ID", "Stage", "Feature"])
        self.tree.setColumnCount(3)
        self.tree.setColumnWidth(0, 180)
        self.tree.setColumnWidth(1, 100)
        self.tree.setColumnWidth(2, 400)
        self.tree.setIndentation(10)  # Reduce indentation from default ~20px
        self.tree.setAlternatingRowColors(True)
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._on_tree_right_click)
        self.tree.itemDoubleClicked.connect(self._on_tree_double_click)

        # Apply gradient text delegate only to Stage column (column 1)
        self.gradient_delegate = GradientTextDelegate(self.tree, app=self)
        self.tree.setItemDelegateForColumn(1, self.gradient_delegate)

        tree_container_layout.addWidget(self.tree)
        splitter.addWidget(tree_container)

        # Right panel: Filters (organized by three-field system)
        self.filter_scroll = QScrollArea()
        self.filter_scroll.setWidgetResizable(True)
        self.filter_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        filter_widget = QWidget()
        filter_main_layout = QVBoxLayout(filter_widget)

        # Vertical layout for filter categories (Stage, Status, Terminus stacked)
        columns_layout = QVBoxLayout()
        columns_layout.setSpacing(8)

        # Stage Filters section (top)
        stage_group = QGroupBox("Stage")
        stage_layout = QVBoxLayout(stage_group)
        stage_btn_layout = QHBoxLayout()
        stage_all_btn = QPushButton("All")
        stage_all_btn.setFixedWidth(50)
        stage_all_btn.clicked.connect(lambda: self._select_category_statuses(STAGE_ORDER, True))
        stage_btn_layout.addWidget(stage_all_btn)
        stage_none_btn = QPushButton("None")
        stage_none_btn.setFixedWidth(50)
        stage_none_btn.clicked.connect(lambda: self._select_category_statuses(STAGE_ORDER, False))
        stage_btn_layout.addWidget(stage_none_btn)
        stage_btn_layout.addStretch()
        stage_layout.addLayout(stage_btn_layout)

        for status in STAGE_ORDER:
            color = STATUS_COLORS.get(status, '#000000')
            cb = ColoredCheckBox(status, color)
            cb.setChecked(True)
            cb.setStyleSheet("QCheckBox::indicator { width: 0px; height: 0px; }")
            cb.stateChanged.connect(lambda state, checkbox=cb: (checkbox.update(), self._on_checkbox_changed(), self._apply_filters()))
            self.status_checkboxes[status] = cb
            stage_layout.addWidget(cb)

        stage_layout.addStretch()
        columns_layout.addWidget(stage_group)

        # Status Filters section (middle)
        status_group = QGroupBox("Status")
        status_layout = QVBoxLayout(status_group)
        status_btn_layout = QHBoxLayout()
        status_all_btn = QPushButton("All")
        status_all_btn.setFixedWidth(50)
        status_all_btn.clicked.connect(lambda: self._select_category_statuses(STATUS_ORDER_HOLDS, True))
        status_btn_layout.addWidget(status_all_btn)
        status_none_btn = QPushButton("None")
        status_none_btn.setFixedWidth(50)
        status_none_btn.clicked.connect(lambda: self._select_category_statuses(STATUS_ORDER_HOLDS, False))
        status_btn_layout.addWidget(status_none_btn)
        status_btn_layout.addStretch()
        status_layout.addLayout(status_btn_layout)

        for status in STATUS_ORDER_HOLDS:
            color = STATUS_COLORS.get(status, '#000000')
            cb = ColoredCheckBox(status, color)
            cb.setChecked(True)
            cb.setStyleSheet("QCheckBox::indicator { width: 0px; height: 0px; }")
            cb.stateChanged.connect(lambda state, checkbox=cb: (checkbox.update(), self._on_checkbox_changed(), self._apply_filters()))
            self.status_checkboxes[status] = cb
            status_layout.addWidget(cb)

        status_layout.addStretch()
        columns_layout.addWidget(status_group)

        # Terminus Filters section (bottom)
        term_group = QGroupBox("Terminus")
        term_layout = QVBoxLayout(term_group)
        term_btn_layout = QHBoxLayout()
        term_all_btn = QPushButton("All")
        term_all_btn.setFixedWidth(50)
        term_all_btn.clicked.connect(lambda: self._select_category_statuses(TERMINUS_ORDER, True))
        term_btn_layout.addWidget(term_all_btn)
        term_none_btn = QPushButton("None")
        term_none_btn.setFixedWidth(50)
        term_none_btn.clicked.connect(lambda: self._select_category_statuses(TERMINUS_ORDER, False))
        term_btn_layout.addWidget(term_none_btn)
        term_btn_layout.addStretch()
        term_layout.addLayout(term_btn_layout)

        for status in TERMINUS_ORDER:
            color = STATUS_COLORS.get(status, '#000000')
            cb = ColoredCheckBox(status, color)
            cb.setChecked(True)
            cb.setStyleSheet("QCheckBox::indicator { width: 0px; height: 0px; }")
            cb.stateChanged.connect(lambda state, checkbox=cb: (checkbox.update(), self._on_checkbox_changed(), self._apply_filters()))
            self.status_checkboxes[status] = cb
            term_layout.addWidget(cb)

        term_layout.addStretch()
        columns_layout.addWidget(term_group)

        filter_main_layout.addLayout(columns_layout)

        filter_main_layout.addStretch()
        self.filter_scroll.setWidget(filter_widget)
        self.filter_scroll.setFixedWidth(200)  # Narrower width for vertical filter panel
        splitter.addWidget(self.filter_scroll)
        splitter.setCollapsible(1, False)  # Prevent filter panel from collapsing

        # Apply initial visibility based on filter_sidebar_visible state
        if not self.filter_sidebar_visible:
            self.filter_scroll.hide()

        # Set splitter proportions (tree view : filter panel)
        splitter.setSizes([500, 400])
        tree_view_layout.addWidget(splitter)

        self.view_layout.addWidget(self.tree_view_frame)

        # Detail view frame
        self.detail_view = DetailView(self)
        self.detail_view.closeRequested.connect(self.show_tree_view)
        self.view_layout.addWidget(self.detail_view)

        self.main_layout.addWidget(self.view_container)

        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready")

        # Show tree view by default
        self.show_tree_view()

    def show_tree_view(self):
        """Switch to tree view."""
        self.detail_view.hide()
        self.tree_view_frame.show()
        self.repo_label.show()
        self.setWindowTitle("Xstory v1.5")
        msg = f"Loaded {len(self.nodes)} nodes" if self.nodes else "Ready"
        self.status_bar.showMessage(msg)

    def show_detail_view(self, node_id: str):
        """Switch to detail view for a specific node."""
        self.tree_view_frame.hide()
        self.repo_label.hide()
        self.detail_view.show()
        self.detail_view.show_node(node_id)
        node = self.nodes.get(node_id)
        if node:
            # Window title shows hierarchy context
            self.setWindowTitle(f"Feature: {node.feature}")
            self.status_bar.showMessage(f"Viewing: {node_id} - {node.feature}")
        else:
            self.setWindowTitle("Feature Details")

    def _on_tree_double_click(self, item: QTreeWidgetItem, column: int):
        """Handle double-click to open detail view."""
        node_id = item.text(0)
        if node_id in self.nodes:
            self.show_detail_view(node_id)

    def _on_tree_right_click(self, position):
        """Handle right-click to show context menu."""
        item = self.tree.itemAt(position)
        if not item:
            return

        node_id = item.text(0)
        node = self.nodes.get(node_id)
        if not node:
            return

        menu = QMenu(self)

        focus_action = QAction("Focus Here", self)
        focus_action.triggered.connect(lambda: self._focus_on_node(node_id))
        menu.addAction(focus_action)

        if self._focused_node_id is not None:
            clear_focus_action = QAction("Clear Focus", self)
            clear_focus_action.triggered.connect(self._clear_focus)
            menu.addAction(clear_focus_action)

        menu.exec(self.tree.mapToGlobal(position))

    def _focus_on_node(self, node_id: str):
        """Focus the tree view on the specified node, showing only its lineage and descendants."""
        if not node_id or node_id not in self.nodes:
            return

        # Build set of visible node IDs
        visible_ids: set[str] = set()

        # Add ancestors (walk parent_id to root)
        current_id = node_id
        while current_id:
            visible_ids.add(current_id)
            node = self.nodes.get(current_id)
            current_id = node.parent_id if node else None

        # Add descendants (recursive)
        def add_descendants(nid: str):
            node = self.nodes.get(nid)
            if node:
                for child in node.children:
                    visible_ids.add(child.id)
                    add_descendants(child.id)

        add_descendants(node_id)

        # Apply visibility to all tree items
        for nid, item in self.tree_items.items():
            item.setHidden(nid not in visible_ids)

        # Track focused node for Clear Focus
        self._focused_node_id = node_id

    def _clear_focus(self):
        """Clear focus and show all tree items."""
        for item in self.tree_items.values():
            item.setHidden(False)
        self._focused_node_id = None

    def _change_node_status(self, node_id: str, new_status: str):
        """Change a node's status with a notes dialog."""
        node = self.nodes.get(node_id)
        if not node:
            return

        # Determine if notes are mandatory
        mandatory = (new_status == 'polish')

        # Show dialog
        dialog = StatusChangeDialog(self, node_id, new_status, mandatory=mandatory)
        if dialog.exec() == QDialog.Accepted:
            notes = dialog.get_notes()
            self._update_node_status_in_db(node_id, new_status, notes or '')

    def _update_node_status_in_db(self, node_id: str, new_status: str, notes: str):
        """Update node status and notes in the database using three-field system."""
        if not self.db_path:
            QMessageBox.critical(self, "Error", "No database loaded.")
            return

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Get current notes to append to
            cursor.execute("SELECT notes FROM story_nodes WHERE id = ?", (node_id,))
            row = cursor.fetchone()
            current_notes = row[0] if row and row[0] else ""

            # Build new notes with timestamp
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")

            if notes:
                new_note_entry = f"[{timestamp}] Status changed to '{new_status}': {notes}"
            else:
                new_note_entry = f"[{timestamp}] Status changed to '{new_status}'"

            if current_notes:
                updated_notes = f"{current_notes}\n{new_note_entry}"
            else:
                updated_notes = new_note_entry

            # Three-field system: determine which field(s) to update
            # - terminus: terminal states (exits pipeline)
            # - status: work stopped (stays in pipeline)
            # - stage: workflow position (active progress)
            if new_status in TERMINUS_VALUES:
                # Setting terminus clears status to ready
                cursor.execute(
                    """UPDATE story_nodes
                       SET terminus = ?, status = 'ready', notes = ?, updated_at = ?
                       WHERE id = ?""",
                    (new_status, updated_notes, datetime.now().isoformat(), node_id)
                )
            elif new_status in STATUS_VALUES_HOLDS:
                # Setting status clears terminus
                cursor.execute(
                    """UPDATE story_nodes
                       SET status = ?, terminus = NULL, notes = ?, updated_at = ?
                       WHERE id = ?""",
                    (new_status, updated_notes, datetime.now().isoformat(), node_id)
                )
            elif new_status in STAGE_VALUES:
                # Setting stage clears both status and terminus
                cursor.execute(
                    """UPDATE story_nodes
                       SET stage = ?, status = 'ready', terminus = NULL, notes = ?, updated_at = ?
                       WHERE id = ?""",
                    (new_status, updated_notes, datetime.now().isoformat(), node_id)
                )
            else:
                raise ValueError(f"Unknown status value: {new_status}")

            conn.commit()
            conn.close()

            self.status_bar.showMessage(f"Updated '{node_id}' status to '{new_status}'")

            # Refresh the tree to show updated status
            self._refresh()

        except Exception as e:
            QMessageBox.critical(self, "Database Error", f"Failed to update status:\n{e}")

    def _toggle_filter_sidebar(self):
        """Toggle the filter sidebar visibility (independent of Respond mode)."""
        self.filter_sidebar_visible = not self.filter_sidebar_visible
        self._update_toggle_buttons()
        if hasattr(self, 'filter_scroll'):
            if self.filter_sidebar_visible:
                self.filter_scroll.show()
            else:
                self.filter_scroll.hide()
        status = "visible" if self.filter_sidebar_visible else "hidden"
        self.status_bar.showMessage(f"Filter sidebar {status}")

    def _toggle_respond_mode(self):
        """Toggle Respond preset on/off with state preservation.

        State management:
        - Filter-mode settings are saved when checkboxes change while respond is OFF
        - Turning respond ON always applies preset (filter settings preserved)
        - Turning respond OFF restores saved filter-mode settings
        - Changes made in respond mode are forgotten when toggling OFF
        """
        if self.respond_mode_active:
            # Turning OFF: restore saved filter-mode settings
            self._restore_checkbox_states()
            self.respond_mode_active = False
            self.status_bar.showMessage("🙋 OFF - filters restored")
        else:
            # Turning ON: apply preset (don't save - filter settings already preserved)
            self._apply_respond_preset()
            self.respond_mode_active = True
            self.status_bar.showMessage("🙋 ON")
        self._update_toggle_buttons()
        self._apply_filters()
        # Update escalated nav buttons if detail view is visible
        if self.detail_view.isVisible():
            self.detail_view._update_escalated_nav_buttons()

    def _show_state_diagram(self):
        """Open the state diagram viewer dialog."""
        svg_path = Path(__file__).parent / "assets" / "state-transitions.svg"
        if not svg_path.exists():
            self.status_bar.showMessage("State diagram SVG not found")
            return
        dialog = StateDiagramDialog(self)
        dialog.show()

    def _show_swimlanes_view(self):
        """Open the Swimlanes view dialog."""
        dialog = SwimlanesDialog(self)
        dialog.show()

    def _show_kanban_view(self):
        """Open the Kanban view dialog."""
        dialog = KanbanDialog(self)
        dialog.show()

    def _show_heatmap_view(self):
        """Open the Bottleneck Heatmap dialog."""
        dialog = HeatmapDialog(self)
        dialog.show()

    def _save_checkbox_states(self):
        """Save current checkbox states as filter-mode settings."""
        self._saved_checkbox_states = {
            name: cb.isChecked()
            for name, cb in self.status_checkboxes.items()
        }

    def _restore_checkbox_states(self):
        """Restore checkbox states to last saved filter-mode settings."""
        if not self._saved_checkbox_states:
            # No saved state - set all checked as default
            self._checkbox_change_internal = True
            for cb in self.status_checkboxes.values():
                cb.setChecked(True)
            self._checkbox_change_internal = False
            return

        self._checkbox_change_internal = True
        for name, cb in self.status_checkboxes.items():
            cb.setChecked(self._saved_checkbox_states.get(name, True))
        self._checkbox_change_internal = False

    def _apply_respond_preset(self):
        """Apply the Respond preset: all Stages, only Escalated status, only Shipped terminus."""
        self._checkbox_change_internal = True
        for name, cb in self.status_checkboxes.items():
            if name in STAGE_ORDER:
                cb.setChecked(True)  # All stages checked
            elif name == 'escalated':
                cb.setChecked(True)  # Only escalated status
            elif name in STATUS_ORDER_HOLDS:
                cb.setChecked(False)  # Other statuses unchecked
            elif name == 'shipped':
                cb.setChecked(True)  # Only shipped terminus
            elif name in TERMINUS_ORDER:
                cb.setChecked(False)  # Other termini unchecked
        self._checkbox_change_internal = False

    def _on_checkbox_changed(self):
        """Handle manual checkbox change.

        - In respond mode: turns off respond mode but doesn't save (changes forgotten on toggle)
        - In filter mode: saves current states as the filter-mode settings
        """
        if self._checkbox_change_internal:
            return  # Ignore programmatic changes
        if self.respond_mode_active:
            # User manually adjusted filters - turn off Respond mode (don't save)
            self.respond_mode_active = False
            self._update_toggle_buttons()
            self.status_bar.showMessage("🙋 OFF - manual filter adjustment")
            # Update escalated nav buttons if detail view is visible
            if self.detail_view.isVisible():
                self.detail_view._update_escalated_nav_buttons()
        else:
            # User adjusted while in filter mode - save as filter-mode settings
            self._save_checkbox_states()

    def _update_toggle_buttons(self):
        """Update both toggle button appearances based on current state."""
        # Filter button: cyan when active (sidebar visible), outline when inactive
        if self.filter_sidebar_visible:
            self.filter_toggle_btn.setChecked(True)
            self.filter_toggle_btn.setStyleSheet(
                "QPushButton { background-color: #0099CC; color: white; }"
                "QPushButton:hover { background-color: #0077AA; }"
            )
        else:
            self.filter_toggle_btn.setChecked(False)
            self.filter_toggle_btn.setStyleSheet(
                "QPushButton { background-color: #e9ecef; color: #adb5bd; }"
                "QPushButton:hover { background-color: #dee2e6; }"
            )

        # Respond button: purple when active, outline when inactive
        if self.respond_mode_active:
            self.respond_toggle_btn.setChecked(True)
            self.respond_toggle_btn.setStyleSheet(
                "QPushButton { background-color: #9900CC; color: white; font-weight: bold; }"
                "QPushButton:hover { background-color: #7700AA; }"
            )
        else:
            self.respond_toggle_btn.setChecked(False)
            self.respond_toggle_btn.setStyleSheet(
                "QPushButton { background-color: #e9ecef; color: #adb5bd; }"
                "QPushButton:hover { background-color: #dee2e6; }"
            )

    def _try_auto_detect_db(self):
        """Try to auto-detect the database file."""
        # Prioritize .storytree/data (standard) over .claude/data (legacy)
        possible_paths = [
            Path(__file__).parent.parent / 'data' / 'story-tree.db',  # .storytree/data relative to xstory.py
            Path.cwd() / '.storytree' / 'data' / 'story-tree.db',
            Path(__file__).parent.parent.parent / '.claude' / 'data' / 'story-tree.db',  # Legacy
            Path.cwd() / '.claude' / 'data' / 'story-tree.db',  # Legacy
        ]

        for path in possible_paths:
            if path.exists():
                self._load_database(str(path.resolve()))
                return

        self.status_bar.showMessage("No database auto-detected.")

    def _open_database(self):
        """Open a database file via file dialog."""
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Story Tree Database",
            str(Path.cwd()),
            "SQLite Database (*.db);;All Files (*.*)"
        )
        if path:
            self._load_database(path)

    def _load_database(self, path: str):
        """Load a database file."""
        if not os.path.exists(path):
            QMessageBox.critical(self, "Error", f"Database file not found:\n{path}")
            return

        self.db_path = path
        self._refresh()

    def _refresh(self):
        """Refresh the tree from the database."""
        if not self.db_path:
            return

        try:
            self._load_nodes_from_db()
            self._apply_filters()
            self.status_bar.showMessage(f"Loaded {len(self.nodes)} nodes from {os.path.basename(self.db_path)}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load database:\n{e}")
            self.status_bar.showMessage(f"Error: {e}")

    def _load_nodes_from_db(self):
        """Load all nodes from the database."""
        self.nodes.clear()

        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Three-field system: effective_status = COALESCE(terminus, status (when not 'ready'), stage)
        # Note: DB uses story_path/title, aliased to id/feature for app compatibility
        query = """
            SELECT
                s.story_path as id, s.title as feature,
                COALESCE(s.terminus, CASE WHEN s.status = 'ready' THEN NULL ELSE s.status END, s.stage) as effective_status,
                s.stage, s.status, s.terminus,
                s.capacity, s.description, s.success_criteria, s.story,
                s.notes, s.project_path, s.created_at, s.updated_at, s.last_implemented,
                COALESCE(
                    (SELECT MIN(depth) FROM story_paths WHERE descendant_id = s.story_path AND ancestor_id != s.story_path),
                    0
                ) as depth,
                (SELECT ancestor_id FROM story_paths WHERE descendant_id = s.story_path AND depth = 1) as parent_id,
                (SELECT COUNT(*) - 1 FROM story_paths WHERE ancestor_id = s.story_path) as descendants_count
            FROM story_nodes s
            ORDER BY s.story_path
        """

        cursor.execute(query)
        rows = cursor.fetchall()

        for row in rows:
            node = StoryNode(
                id=row['id'],
                feature=row['feature'] or '',
                effective_status=row['effective_status'] or 'concept',
                capacity=row['capacity'],
                description=row['description'] or '',
                depth=row['depth'] or 0,
                parent_id=row['parent_id'],
                notes=row['notes'] or '',
                project_path=row['project_path'] or '',
                created_at=row['created_at'] or '',
                updated_at=row['updated_at'] or '',
                last_implemented=row['last_implemented'] or '',
                stage=row['stage'] or 'concept',
                status=row['status'] or 'ready',
                terminus=row['terminus'],
                descendants_count=row['descendants_count'] or 0,
                success_criteria=row['success_criteria'] or '',
                story=row['story'] or ''
            )
            self.nodes[node.id] = node

        conn.close()

        # Build parent-child relationships
        for node in self.nodes.values():
            if node.parent_id and node.parent_id in self.nodes:
                self.nodes[node.parent_id].children.append(node)

        # Sort children by ID
        for node in self.nodes.values():
            node.children.sort(key=lambda n: self._sort_key(n.id))

    def _sort_key(self, node_id: str) -> Tuple:
        """Generate a sort key for node IDs (root first, then numeric order)."""
        if node_id == 'root':
            return (0,)
        try:
            parts = node_id.split('.')
            return (1,) + tuple(int(p) for p in parts)
        except ValueError:
            return (2, node_id)

    def _get_ancestors(self, node_id: str) -> set:
        """Get all ancestor node IDs for a given node."""
        ancestors = set()
        node = self.nodes.get(node_id)
        while node and node.parent_id:
            ancestors.add(node.parent_id)
            node = self.nodes.get(node.parent_id)
        return ancestors

    def _apply_filters(self):
        """Apply status filters and color the tree.

        Always uses checkbox filters. When Respond mode is active, checkboxes
        are set to the Respond preset (Escalated + Shipped).

        Filter logic: (Stage) AND (Status OR Terminus)
        - A node must match at least one checked Stage
        - AND must match either a checked Status OR a checked Terminus
        """
        # Collect checked statuses by category
        checked_stages = {s for s in STAGE_ORDER
                          if s in self.status_checkboxes and self.status_checkboxes[s].isChecked()}
        checked_statuses = {s for s in STATUS_ORDER_HOLDS
                            if s in self.status_checkboxes and self.status_checkboxes[s].isChecked()}
        checked_termini = {s for s in TERMINUS_ORDER
                           if s in self.status_checkboxes and self.status_checkboxes[s].isChecked()}

        # Special filter flags
        show_ready = 'ready' in checked_statuses
        show_active = 'active' in checked_termini

        def node_matches_filter(node):
            """Check if node matches: (Stage) AND (Status OR Terminus)."""
            # Stage check: node.stage must be in checked stages
            if node.stage not in checked_stages:
                return False

            # Status check: node.status in checked statuses, OR 'ready' if status is 'ready'
            status_ok = False
            if node.status and node.status != 'ready' and node.status in checked_statuses:
                status_ok = True
            elif show_ready and (not node.status or node.status == 'ready'):
                status_ok = True

            # Terminus check: node.terminus in checked terminal states, OR 'active' if no terminus
            term_ok = False
            if node.terminus and node.terminus in checked_termini:
                term_ok = True
            elif show_active and not node.terminus:
                term_ok = True

            # Status OR Terminus must match (not both required)
            return status_ok or term_ok

        # Step 1: Find all nodes that directly match the filter
        matching_nodes = {node_id for node_id, node in self.nodes.items()
                         if node_matches_filter(node)}

        # Step 2: Collect ancestors of all matching nodes
        ancestor_nodes = set()
        for node_id in matching_nodes:
            ancestor_nodes.update(self._get_ancestors(node_id))

        # Nodes to show = matching nodes + their ancestors
        visible_nodes = matching_nodes | ancestor_nodes
        # Ancestor-only nodes (shown faded)
        faded_nodes = ancestor_nodes - matching_nodes

        # Clear the tree
        self.tree.clear()
        self.tree_items.clear()

        # Find root nodes that are visible
        root_nodes = [n for n in self.nodes.values()
                     if (not n.parent_id or n.parent_id not in self.nodes)
                     and n.id in visible_nodes]
        root_nodes.sort(key=lambda n: self._sort_key(n.id))

        # Build filtered tree
        for node in root_nodes:
            self._add_filtered_node(node, None, visible_nodes, faded_nodes)

        # Expand all nodes
        self.tree.expandAll()

    def _add_filtered_node(self, node: StoryNode, parent_item: Optional[QTreeWidgetItem],
                           visible_nodes: set, faded_nodes: set):
        """Add a node to the filtered tree with gradient coloring.

        Gradient coloring is applied via the GradientTextDelegate:
        - StartColor: Based on stage (green→blue progression)
        - EndColor: Red if terminus active, black if on hold, else same as start
        - Faded ancestors: Gray text (not gradient)
        """
        if node.id not in visible_nodes:
            return

        # Determine status display text and tooltip
        # Priority: terminus > status (when not 'ready') > stage text only
        if node.terminus and node.terminus in TERMINUS_ICONS:
            # Terminus overrides everything - show terminus icon + terminus name
            icon = TERMINUS_ICONS[node.terminus]
            status_text = f"{icon} {node.terminus}"
            tooltip = f"Stage: {node.stage}"
        elif node.status and node.status != 'ready' and node.status in HOLD_ICONS:
            # Show status icon + stage when status is non-ready
            icon = HOLD_ICONS[node.status]
            status_text = f"{icon} {node.stage}"
            tooltip = f"{node.status.capitalize()} - Stage: {node.stage}"
        else:
            # Ready or no special status - show stage text only (no emoji)
            status_text = node.stage
            tooltip = None

        # Create tree item
        item = QTreeWidgetItem([node.id, status_text, node.feature])

        # Set tooltip if status is non-ready
        if tooltip:
            item.setToolTip(1, tooltip)

        # Mark faded nodes with UserRole data for the delegate
        if node.id in faded_nodes:
            item.setData(0, Qt.UserRole, 'faded')
        else:
            item.setData(0, Qt.UserRole, 'normal')

        # Note: Actual text coloring is handled by GradientTextDelegate
        # which reads node data and applies gradient colors

        # Add to tree
        if parent_item:
            parent_item.addChild(item)
        else:
            self.tree.addTopLevelItem(item)

        # Store reference
        self.tree_items[node.id] = item

        # Add visible children
        visible_children = [c for c in node.children if c.id in visible_nodes]
        visible_children.sort(key=lambda n: self._sort_key(n.id))

        for child in visible_children:
            self._add_filtered_node(child, item, visible_nodes, faded_nodes)

    def _select_all_statuses(self):
        """Select all status filters."""
        for cb in self.status_checkboxes.values():
            cb.setChecked(True)

    def _select_no_statuses(self):
        """Deselect all status filters."""
        for cb in self.status_checkboxes.values():
            cb.setChecked(False)

    def _select_category_statuses(self, statuses: List[str], checked: bool):
        """Select or deselect a category of status filters."""
        for status in statuses:
            if status in self.status_checkboxes:
                self.status_checkboxes[status].setChecked(checked)

    def closeEvent(self, event):
        """Handle window close - return to tree view if in detail view."""
        if self.detail_view.isVisible():
            event.ignore()
            self.show_tree_view()
        else:
            event.accept()

    def keyPressEvent(self, event):
        """Handle key presses - Escape returns to tree view from detail view."""
        if event.key() == Qt.Key_Escape and self.detail_view.isVisible():
            self.show_tree_view()
        else:
            super().keyPressEvent(event)


def main():
    """Main entry point."""
    app = QApplication(sys.argv)
    window = XstoryExplorer()
    window.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
