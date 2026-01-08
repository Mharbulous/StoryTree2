# Database Architecture

Visual representations of the database schema and closure table patterns used by the story-tree system.

---

## Definitions

| Term | Definition |
|------|------------|
| **Story node** | A unit of work in the hierarchical backlog—can be an epic, feature, capability, or task depending on depth. May have its own direct work AND children simultaneously. |
| **Closure table** | A database pattern that stores all ancestor-descendant relationships, enabling efficient hierarchy queries |
| **Capacity** | The maximum number of children a node can have; grows dynamically based on completed work |
| **Depth** | A node's level in the tree (root=0, features=1, capabilities=2, tasks=3+) |

---

## Closure Table Data Structure

The closure table pattern stores all ancestor-descendant relationships, enabling efficient hierarchy queries without recursion.

For details on `stage`, `status`, and `terminus` values, see @workflow-three-field-model.md. For the complete SQL schema including constraints and indexes, see @schema.sql.

```mermaid
erDiagram
    story_nodes {
        text id PK
        text title
        text description
        int capacity
        text stage
        text status
        text terminus
        int human_review
        text project_path
        text last_implemented
        text notes
        text created_at
        text updated_at
        int version
    }

    story_paths {
        text ancestor_id FK
        text descendant_id FK
        int depth
    }

    story_commits {
        text story_id FK
        text commit_hash PK
        text commit_date
        text commit_message
    }

    vetting_decisions {
        text pair_key PK
        text story_a_id FK
        int story_a_version
        text story_b_id FK
        int story_b_version
        text classification
        text action_taken
        text decided_at
    }

    metadata {
        text key PK
        text value
    }

    story_nodes ||--o{ story_paths : "ancestor"
    story_nodes ||--o{ story_paths : "descendant"
    story_nodes ||--o{ story_commits : "linked"
    story_nodes ||--o{ vetting_decisions : "story_a"
    story_nodes ||--o{ vetting_decisions : "story_b"
```

---

## Closure Table Path Example

This diagram illustrates how the closure table stores paths for a simple three-node hierarchy. Note the ID format: first-level children of root are plain integers (`1`, `2`), while deeper nodes use dotted format (`1.1`, `1.1.1`).

```mermaid
flowchart TD
    subgraph Tree Structure
        ROOT[root] --> N1[1]
        N1 --> N2[1.1]
    end

    subgraph Closure Table Entries
        direction LR
        P1["(root, root, 0)"]
        P2["(root, 1, 1)"]
        P3["(root, 1.1, 2)"]
        P4["(1, 1, 0)"]
        P5["(1, 1.1, 1)"]
        P6["(1.1, 1.1, 0)"]
    end

    ROOT -.-> P1
    ROOT -.-> P2
    ROOT -.-> P3
    N1 -.-> P4
    N1 -.-> P5
    N2 -.-> P6
```

Each entry represents a path from ancestor to descendant with the distance between them. Self-references (depth 0) ensure every node appears in queries. This structure allows finding all descendants or ancestors with a single query.

---

## Node Insertion Process

Adding a new node requires updating both the nodes table and the closure table.

```mermaid
sequenceDiagram
    participant S as Skill
    participant N as story_nodes
    participant P as story_paths

    S->>N: INSERT new node (id, title, description, stage)
    N-->>S: Node created

    S->>P: SELECT all paths where descendant = parent_id
    P-->>S: Return parent's ancestor paths

    S->>P: INSERT paths with new_id as descendant, depth + 1
    P-->>S: Ancestor paths copied

    S->>P: INSERT self-reference (new_id, new_id, 0)
    P-->>S: Self-reference added

    Note over S,P: Node is now fully integrated into tree hierarchy
```

---

## Dynamic Capacity Calculation

Capacity grows organically based on completed work rather than speculation.

```mermaid
flowchart LR
    subgraph Formula
        BASE[Base: 3] --> PLUS[+]
        PLUS --> IMPL[Count of implemented/ready children]
        IMPL --> RESULT[= Effective Capacity]
    end

    subgraph Example
        E1["New node: 3 + 0 = 3"]
        E2["1 child done: 3 + 1 = 4"]
        E3["3 children done: 3 + 3 = 6"]
    end

    RESULT --> E1
    RESULT --> E2
    RESULT --> E3
```
