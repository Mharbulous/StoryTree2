Create a new story concept for a node with capacity.

## Arguments

$Arguments

- **With story ID**: Write concept for the specified node
- **Without arguments**: Auto-discover a node with capacity

## Process

### 1. Find Target Node

If no story ID provided, find a node with capacity:

```python
python .claude/scripts/story_workflow.py --ci
```

If the output shows "No nodes need concepts", exit with success message.

### 2. Gather Context

Read parent scope and sibling stories:

```python
python -c "
import sqlite3, json
conn = sqlite3.connect('${STORYTREE_DATA_DIR}/story-tree.db')
conn.row_factory = sqlite3.Row

parent_id = 'TARGET_NODE_ID'

# Get parent story
parent = conn.execute('SELECT id, title, description FROM story_nodes WHERE id = ?', (parent_id,)).fetchone()

# Get sibling stories (children of same parent)
siblings = [dict(row) for row in conn.execute('''
    SELECT s.id, s.title, s.description, COALESCE(s.terminus, CASE WHEN s.status = 'ready' THEN NULL ELSE s.status END, s.stage) as effective_status
    FROM story_nodes s
    JOIN story_paths p ON s.id = p.descendant_id
    WHERE p.ancestor_id = ? AND p.depth = 1
''', (parent_id,)).fetchall()]

print(json.dumps({'parent': dict(parent) if parent else None, 'siblings': siblings}, indent=2))
conn.close()
"
```

Read goals for alignment:

```python
python -c "
import os, json
result = {}
for key, path in [('goals', '${STORYTREE_DATA_DIR}/goals/goals.md'), ('non_goals', '${STORYTREE_DATA_DIR}/goals/non-goals.md')]:
    if os.path.exists(path):
        with open(path) as f: result[key] = f.read()
print(json.dumps(result, indent=2))
"
```

### 3. Gap Analysis (Evidence-Based Discovery)

Analyze git commits for the last 30 days:

```python
python -c "
import subprocess
result = subprocess.run(['git', 'log', '--since=30 days ago',
    '--pretty=format:%h|%ai|%s', '--no-merges'], capture_output=True, text=True)
print(result.stdout)
"
```

Identify gap type:

| Type | Description |
|------|-------------|
| **Functional** | Missing capability in parent scope |
| **Pattern** | Commits exist without corresponding stories |
| **User Journey** | Incomplete workflow |
| **Technical** | Infrastructure gaps |

Apply goals-aware filtering:
- Reject if conflicts with non-goals
- Prioritize if aligns with stated goals

### 4. Draft Concept

Write story in user story format:

```markdown
**As a** [specific user role]
**I want** [specific capability]
**So that** [specific benefit]

**Acceptance Criteria:**
- [ ] [Specific, testable criterion]
- [ ] [Specific, testable criterion]
- [ ] [Specific, testable criterion]

**Related context:** [Evidence from commits or gap type identified]
```

### 5. Validate Before Insertion

Run validation checks:

| Check | Failure Condition |
|-------|-------------------|
| User story format | Missing "As a" / "I want" / "So that" |
| Specific role | Generic "user", "someone", "anyone" |
| Acceptance criteria | Fewer than 3, or untestable |
| Evidence grounding | No commits cited, no gap identified |
| Scope containment | Story exceeds parent scope |
| ID format | Root child with dots, nested without prefix |
| Goals alignment | Conflicts with non-goals.md |

If any validation fails, fix the issue before proceeding.

### 6. Insert Story

Generate next available ID and insert:

```python
python -c "
import sqlite3

conn = sqlite3.connect('${STORYTREE_DATA_DIR}/story-tree.db')
cursor = conn.cursor()

parent_id = 'PARENT_ID'
new_id = 'NEW_STORY_ID'
title = '''STORY_TITLE'''
description = '''STORY_DESCRIPTION'''

# Insert story node
cursor.execute('''
    INSERT INTO story_nodes (id, title, description, stage, created_at, updated_at)
    VALUES (?, ?, ?, 'concept', datetime('now'), datetime('now'))
''', (new_id, title, description))

# Insert closure table paths
cursor.execute('''
    INSERT INTO story_paths (ancestor_id, descendant_id, depth)
    SELECT ancestor_id, ?, depth + 1
    FROM story_paths WHERE descendant_id = ?
    UNION ALL SELECT ?, ?, 0
''', (new_id, parent_id, new_id, new_id))

conn.commit()
conn.close()
print(f'Created story {new_id}')
"
```

## Output

Report the new story ID or explain why no concept was created:
- "Created concept [ID]: [Title]"
- "No nodes with capacity found"
- "Validation failed: [specific errors]"

## Does NOT

- Vet for conflicts (handled by `/vet-concept`)
- Retry on duplicate detection
- Handle polish stories (handled by `/refine-concept`)

## ID Format Rules

| Parent | Format | Example |
|--------|--------|---------|
| `root` | Plain integer | `1`, `2`, `15` |
| Any other | `[parent].[N]` | `1.1`, `8.4`, `15.2.1` |

**Critical:** Primary epics (children of root) must have plain integer IDs.

## References

- **Workflow diagram:** `claude/skills/story-tree/references/workflow1-concept.md`
- **Three-field model:** `claude/skills/story-tree/references/workflow-three-field-model.md`
- **Database:** `${STORYTREE_DATA_DIR}/story-tree.db`
- **Goals:** `${STORYTREE_DATA_DIR}/goals/goals.md`, `${STORYTREE_DATA_DIR}/goals/non-goals.md`
