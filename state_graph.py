"""Graph data model for state diagram - 27 states from state-transitions-flat-L.md"""
from dataclasses import dataclass
from typing import Dict, List, Tuple


@dataclass
class StateNode:
    id: str
    label: str
    stage: str
    x: float
    y: float


# Stage colors (from mermaid classDef)
STAGE_COLORS = {
    "concept": "#66CC00",
    "planning": "#00CC66",
    "implementing": "#00CCCC",
    "testing": "#0099CC",
    "releasing": "#0066CC",
    "shipped": "#0033CC",
}

# Layout: 7 columns (concept), spacing ~150px horizontal, ~80px vertical
NODES: Dict[str, StateNode] = {
    # Concept stage (row 0-1)
    "concept_nohold": StateNode("concept_nohold", "concept:no_hold", "concept", 400, 50),
    "concept_escalated": StateNode("concept_escalated", "concept:escalated", "concept", 400, 130),
    "concept_polish": StateNode("concept_polish", "concept:polish", "concept", 250, 130),
    "concept_conflicted": StateNode("concept_conflicted", "concept:conflicted", "concept", 550, 50),
    "concept_duplicative": StateNode("concept_duplicative", "concept:duplicative", "concept", 700, 50),
    "concept_paused": StateNode("concept_paused", "concept:paused", "concept", 550, 130),
    "concept_wishlisted": StateNode("concept_wishlisted", "concept:wishlisted", "concept", 700, 130),

    # Planning stage (row 2-3)
    "planning_nohold": StateNode("planning_nohold", "planning:no_hold", "planning", 400, 230),
    "planning_escalated": StateNode("planning_escalated", "planning:escalated", "planning", 400, 310),
    "planning_polish": StateNode("planning_polish", "planning:polish", "planning", 250, 310),
    "planning_queued": StateNode("planning_queued", "planning:queued", "planning", 550, 310),
    "planning_wishlisted": StateNode("planning_wishlisted", "planning:wishlisted", "planning", 700, 310),

    # Implementing stage (row 4-5)
    "impl_nohold": StateNode("impl_nohold", "implementing:no_hold", "implementing", 400, 410),
    "impl_blocked": StateNode("impl_blocked", "implementing:blocked", "implementing", 700, 410),
    "impl_queued": StateNode("impl_queued", "implementing:queued", "implementing", 550, 410),
    "impl_broken": StateNode("impl_broken", "implementing:broken", "implementing", 250, 410),
    "impl_escalated": StateNode("impl_escalated", "implementing:escalated", "implementing", 100, 410),

    # Testing stage (row 6-7)
    "test_nohold": StateNode("test_nohold", "testing:no_hold", "testing", 400, 510),
    "test_queued": StateNode("test_queued", "testing:queued", "testing", 250, 510),
    "test_polish": StateNode("test_polish", "testing:polish", "testing", 550, 590),
    "test_escalated": StateNode("test_escalated", "testing:escalated", "testing", 550, 510),

    # Releasing stage (row 8-9)
    "rel_queued": StateNode("rel_queued", "releasing:queued", "releasing", 400, 690),
    "rel_nohold": StateNode("rel_nohold", "releasing:no_hold", "releasing", 400, 770),
    "rel_broken": StateNode("rel_broken", "releasing:broken", "releasing", 250, 690),
    "rel_polish": StateNode("rel_polish", "releasing:polish", "releasing", 700, 770),
    "rel_escalated": StateNode("rel_escalated", "releasing:escalated", "releasing", 550, 770),

    # Shipped (row 10)
    "shipped": StateNode("shipped", "shipped", "shipped", 400, 870),
}

# Edges: (source_id, target_id, label)
EDGES: List[Tuple[str, str, str]] = [
    # Concept transitions
    ("concept_nohold", "concept_escalated", "vet passes"),
    ("concept_nohold", "concept_conflicted", "conflict"),
    ("concept_nohold", "concept_duplicative", "duplicate"),
    ("concept_escalated", "concept_polish", "refine"),
    ("concept_escalated", "concept_paused", "pause"),
    ("concept_escalated", "concept_wishlisted", "wishlist"),
    ("concept_polish", "concept_escalated", "re-vet clear"),
    ("concept_polish", "concept_conflicted", "re-vet conflict"),
    ("concept_polish", "concept_duplicative", "re-vet duplicate"),

    # Concept -> Planning
    ("concept_escalated", "planning_nohold", "approve"),

    # Planning transitions
    ("planning_nohold", "planning_escalated", "design done"),
    ("planning_escalated", "planning_polish", "refine"),
    ("planning_escalated", "planning_wishlisted", "wishlist"),
    ("planning_escalated", "planning_queued", "approve"),
    ("planning_polish", "planning_escalated", "re-review"),

    # Planning -> Implementing
    ("planning_queued", "impl_nohold", "no deps"),
    ("planning_queued", "impl_queued", "prereqs"),
    ("planning_queued", "impl_blocked", "3rd party"),

    # Implementing transitions
    ("impl_blocked", "impl_queued", "deps ready"),
    ("impl_queued", "impl_nohold", "prereqs done"),
    ("impl_nohold", "impl_broken", "impl fails"),
    ("impl_broken", "impl_nohold", "fixed"),
    ("impl_broken", "impl_escalated", "5 fails"),

    # Implementing -> Testing
    ("impl_nohold", "test_nohold", "impl done"),
    ("impl_escalated", "test_nohold", "approve"),

    # Testing transitions
    ("test_nohold", "test_escalated", "verify pass"),
    ("test_nohold", "test_queued", "verify fail"),
    ("test_queued", "test_nohold", "corrected"),
    ("test_escalated", "test_polish", "refine"),
    ("test_polish", "impl_nohold", "plan-refactor (no deps)"),
    ("test_polish", "impl_queued", "plan-refactor (prereqs)"),
    ("test_polish", "impl_blocked", "plan-refactor (3rd party)"),

    # Testing -> Releasing
    ("test_escalated", "rel_queued", "approve"),

    # Releasing transitions
    ("rel_queued", "rel_nohold", "children ready"),
    ("rel_queued", "rel_broken", "integration fail"),
    ("rel_broken", "rel_nohold", "fixed"),
    ("rel_broken", "test_nohold", "5 fails"),
    ("rel_nohold", "rel_escalated", "docs done"),
    ("rel_escalated", "rel_polish", "refine"),
    ("rel_escalated", "rel_broken", "issues"),
    ("rel_polish", "rel_escalated", "cleaned"),

    # Releasing -> Shipped
    ("rel_escalated", "shipped", "approve"),
]
