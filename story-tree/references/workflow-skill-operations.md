# Skill Workflows

Visual representations of the operational workflows executed by story-tree skills.

---

## Definitions

| Term | Definition |
|------|------------|
| **Story node** | A unit of work in the hierarchical backlog—can be an epic, feature, capability, or task depending on depth. May have its own direct work AND children simultaneously. |
| **Depth** | A node's level in the tree (root=0, features=1, capabilities=2, tasks=3+) |
| **Fill rate** | Ratio of current children to capacity; used for prioritization |
| **Checkpoint** | The last analyzed git commit hash; enables incremental scanning |

---

## Main Update Workflow

The primary workflow executes when the skill receives an update command. It proceeds through seven sequential steps.

```mermaid
flowchart TD
    START([User invokes skill]) --> STALE{Database > 3 days old?}
    STALE -->|Yes| FORCE[Force full update first]
    FORCE --> STEP1
    STALE -->|No| STEP1

    STEP1[Step 1: Load Current Tree] --> DB_EXISTS{Database exists?}
    DB_EXISTS -->|No| INIT[Initialize new database]
    INIT --> SEED[Seed root node from project metadata]
    SEED --> STEP2
    DB_EXISTS -->|Yes| STEP2

    STEP2[Step 2: Analyze Git Commits] --> CHECKPOINT{Valid checkpoint exists?}
    CHECKPOINT -->|Yes| INCREMENTAL[Incremental scan from checkpoint]
    CHECKPOINT -->|No| FULL[Full 30-day scan]
    INCREMENTAL --> MATCH
    FULL --> MATCH
    MATCH[Match commits to stories] --> UPDATE_STATUS[Update story statuses]
    UPDATE_STATUS --> SAVE_CHECKPOINT[Save new checkpoint]
    SAVE_CHECKPOINT --> STEP3

    STEP3[Step 3: Calculate Tree Metrics] --> METRICS[Query depth, child count, fill rate per node]
    METRICS --> STEP4

    STEP4[Step 4: Identify Priority Target] --> FILTER[Filter eligible nodes]
    FILTER --> SORT[Sort by depth then fill rate]
    SORT --> SELECT[Select top priority node]
    SELECT --> STEP5

    STEP5[Step 5: Generate Stories] --> CONTEXT[Gather parent and sibling context]
    CONTEXT --> GENERATE[Generate 1-3 concept stories]
    GENERATE --> VALIDATE[Validate against quality checks]
    VALIDATE --> STEP6

    STEP6[Step 6: Update Tree] --> INSERT[Insert new nodes]
    INSERT --> CLOSURE[Populate closure table paths]
    CLOSURE --> TIMESTAMP[Update lastUpdated metadata]
    TIMESTAMP --> STEP7

    STEP7[Step 7: Output Report] --> REPORT([Generate summary report])
```

---

## Priority Algorithm Decision Flow

The priority algorithm determines which node should receive new children. Depth takes absolute precedence over fill rate.

```mermaid
flowchart TD
    START([Find priority target]) --> QUERY[Query all nodes]
    QUERY --> FILTER{Node eligible?}

    FILTER -->|stage = concept| SKIP[Skip this node]
    FILTER -->|status != ready| SKIP
    FILTER -->|terminus set| SKIP
    SKIP --> NEXT_NODE[Check next node]
    NEXT_NODE --> FILTER

    FILTER -->|stage != concept,<br/>no hold, no terminus| CAPACITY{Under capacity?}
    CAPACITY -->|No| SKIP
    CAPACITY -->|Yes| ADD[Add to candidates]
    ADD --> NEXT_NODE

    NEXT_NODE -->|No more nodes| SORT[Sort candidates]
    SORT --> DEPTH[Primary: Sort by depth ascending]
    DEPTH --> FILL[Secondary: Sort by fill rate ascending]
    FILL --> RESULT([Return first candidate])

    style RESULT fill:#90EE90
```

---

## Git Commit Analysis Process

The skill analyzes git history to detect implementation progress and update story statuses.

```mermaid
flowchart TD
    START([Begin git analysis]) --> GET_CHECKPOINT[Get lastAnalyzedCommit from metadata]
    GET_CHECKPOINT --> HAS_CHECKPOINT{Checkpoint exists?}

    HAS_CHECKPOINT -->|No| FULL_SCAN[Run: git log --since 30 days ago]
    HAS_CHECKPOINT -->|Yes| VALIDATE[Validate checkpoint in git history]

    VALIDATE --> VALID{Commit still exists?}
    VALID -->|No| LOG_REASON[Log: checkpoint rebased away]
    LOG_REASON --> FULL_SCAN
    VALID -->|Yes| INCREMENTAL[Run: git log checkpoint..HEAD]

    FULL_SCAN --> PARSE
    INCREMENTAL --> PARSE

    PARSE[Parse commit hash, date, message] --> FOREACH[For each commit]

    FOREACH --> EXTRACT[Extract keywords from message]
    EXTRACT --> QUERY_STORIES[Query non-deprecated stories]
    QUERY_STORIES --> COMPARE[Compare keywords via Jaccard similarity]

    COMPARE --> THRESHOLD{Similarity >= 0.7?}
    THRESHOLD -->|Yes| STRONG[Strong match: link and update status]
    THRESHOLD -->|No| WEAK{Similarity >= 0.4?}
    WEAK -->|Yes| POTENTIAL[Potential match: link only]
    WEAK -->|No| NO_MATCH[No match]

    STRONG --> NEXT_COMMIT
    POTENTIAL --> NEXT_COMMIT
    NO_MATCH --> NEXT_COMMIT

    NEXT_COMMIT[Process next commit] --> MORE{More commits?}
    MORE -->|Yes| FOREACH
    MORE -->|No| SAVE[Save newest commit as checkpoint]
    SAVE --> DONE([Analysis complete])
```

---

## Story Generation Flow

When a priority target is identified, the skill generates contextually appropriate stories.

```mermaid
flowchart TD
    START([Generate stories for target node]) --> GET_DEPTH[Determine target node depth]

    GET_DEPTH --> DEPTH0{Depth 0 - Root?}
    DEPTH0 -->|Yes| ROOT_CONTEXT[Read project vision]
    ROOT_CONTEXT --> GEN_FEATURES[Generate major feature concepts]

    DEPTH0 -->|No| DEPTH1{Depth 1 - Feature?}
    DEPTH1 -->|Yes| FEATURE_CONTEXT[Read feature description]
    FEATURE_CONTEXT --> GEN_CAPABILITIES[Generate capability concepts]

    DEPTH1 -->|No| DETAIL_CONTEXT[Read parent capability]
    DETAIL_CONTEXT --> GEN_DETAILS[Generate implementation concepts]

    GEN_FEATURES --> SIBLINGS
    GEN_CAPABILITIES --> SIBLINGS
    GEN_DETAILS --> SIBLINGS

    SIBLINGS[Review existing sibling nodes] --> GIT_CONTEXT[Analyze relevant git commits]
    GIT_CONTEXT --> CREATE[Create 1-3 new story concepts]

    CREATE --> LIMIT{Exceeded 3 stories?}
    LIMIT -->|Yes| TRIM[Trim to maximum 3]
    LIMIT -->|No| FORMAT
    TRIM --> FORMAT

    FORMAT[Format as user stories] --> QUALITY{Pass quality checks?}

    QUALITY -->|No| REVISE[Revise story content]
    REVISE --> QUALITY

    QUALITY -->|Yes| OUTPUT([Return generated stories])

    style OUTPUT fill:#90EE90
```
