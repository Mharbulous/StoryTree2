Create TDD implementation plans for stories in the planning stage.

## Arguments

$Arguments

- **With story ID**: Create plan for the specified story
- **Without arguments**: Auto-discover stories with `stage='planning'` and `status='queued'`

## Process

### 1. Find Queued Story

If no story ID provided, query for stories ready for planning:

```python
python -c "
import sqlite3, json
conn = sqlite3.connect('${STORYTREE_DATA_DIR}/story-tree.db')
conn.row_factory = sqlite3.Row

# Find oldest queued story in planning stage (approved by human)
stories = [dict(row) for row in conn.execute('''
    SELECT s.id, s.title, s.description, s.user_journeys,
           (SELECT ancestor_id FROM story_paths WHERE descendant_id = s.id AND depth = 1) as parent_id
    FROM story_nodes s
    WHERE s.stage = 'planning'
      AND s.status = 'queued'
      AND s.terminus IS NULL
    ORDER BY s.created_at ASC
    LIMIT 1
''').fetchall()]

if stories:
    print(json.dumps({'found': True, 'story': stories[0]}, indent=2))
else:
    print(json.dumps({'found': False, 'message': 'No queued stories found in planning stage'}, indent=2))
conn.close()
"
```

If no queued stories found, exit with "No queued stories found in planning stage" message.

### 2. Validate Story

Confirm story is at planning stage with status='queued':

```python
python -c "
import sqlite3, json
conn = sqlite3.connect('${STORYTREE_DATA_DIR}/story-tree.db')
conn.row_factory = sqlite3.Row

story_id = 'STORY_ID'
story = conn.execute('''
    SELECT id, title, description, stage, status, terminus, user_journeys
    FROM story_nodes WHERE id = ?
''', (story_id,)).fetchone()

if story:
    result = dict(story)
    result['valid'] = (result['stage'] == 'planning' and
                       result['status'] == 'queued' and
                       result['terminus'] is None)
    print(json.dumps(result, indent=2))
else:
    print(json.dumps({'error': f'Story {story_id} not found'}, indent=2))
conn.close()
"
```

**Error conditions:**
- Story not found → exit with error
- Story not at planning stage → exit with error
- Story status is not 'queued' → exit with error
- Story has terminus → exit with error

### 3. Load User Journeys and Mockup

Load design outputs from `/design-ux`:

```python
python -c "
import sqlite3, json, os

conn = sqlite3.connect('${STORYTREE_DATA_DIR}/story-tree.db')
conn.row_factory = sqlite3.Row

story_id = 'STORY_ID'
story = conn.execute('''
    SELECT id, title, description, user_journeys
    FROM story_nodes WHERE id = ?
''', (story_id,)).fetchone()

result = dict(story)

# Parse user journeys
if result['user_journeys']:
    result['parsed_journeys'] = json.loads(result['user_journeys'])
else:
    result['parsed_journeys'] = []
    result['warning'] = 'No user journeys found - design may not have been completed'

# Load mockup file
mockup_filename = story_id.replace('.', '_') + '.md'
mockup_path = f'${STORYTREE_DATA_DIR}/mockups/{mockup_filename}'
if os.path.exists(mockup_path):
    with open(mockup_path) as f:
        result['mockup'] = f.read()
    result['mockup_path'] = mockup_path
else:
    result['mockup'] = None
    result['mockup_warning'] = 'No mockup file found'

conn.close()
print(json.dumps(result, indent=2))
"
```

### 4. Research Codebase

Understand existing architecture and patterns:
- Examine relevant directories and files
- Identify existing patterns to follow
- Note conventions used in the codebase
- Find integration points for new functionality

### 5. Draft TDD Plan

Write test scenarios first, then implementation steps:

**Plan Format:**
```markdown
# Implementation Plan: [Story Title]

## Story Reference
- **ID:** [story_id]
- **Title:** [title]

## User Journeys Summary
[Brief summary of the user journeys from the design phase]

## Test Scenarios

### 1. [Test Scenario Title]
**Given:** [preconditions]
**When:** [action]
**Then:** [expected outcome]

### 2. [Next Test Scenario]
...

## Implementation Steps

### Phase 1: [Setup/Infrastructure]
1. [Step 1]
2. [Step 2]

### Phase 2: [Core Implementation]
1. [Step 1]
2. [Step 2]

### Phase 3: [Integration]
1. [Step 1]
2. [Step 2]

## Dependencies

### Third-Party Dependencies
- [Library/API name]: [Why needed]

### Prerequisite Stories
- [Story ID]: [Why required first]

## Risks and Mitigations
- **Risk:** [potential issue]
  **Mitigation:** [how to address]

---
*Generated: [timestamp]*
```

### 6. Identify Dependencies

Check for blockers that would prevent immediate execution:

**Third-Party Dependencies:**
- External APIs that need to be integrated
- Libraries that need to be installed
- Services that need to be provisioned
- Credentials or access that need to be obtained

**Prerequisite Stories:**
- Other stories that must complete first
- Shared components that don't exist yet
- Infrastructure that needs to be in place

### 7. Save Plan and Update Story

Create plan file and update story with dependencies:

```python
python -c "
import sqlite3, json, os
from datetime import datetime

conn = sqlite3.connect('${STORYTREE_DATA_DIR}/story-tree.db')
cursor = conn.cursor()

story_id = 'STORY_ID'

# Dependencies identified (populate with actual values)
dependencies = json.dumps(['EXAMPLE_DEP'])  # e.g., ['redis', 'stripe-api'] or []
prerequisites = json.dumps(['EXAMPLE_PREREQ'])  # e.g., ['1.2', '3.1'] or []

# Determine exit status based on blockers
deps_list = json.loads(dependencies)
prereqs_list = json.loads(prerequisites)

if deps_list:
    new_status = 'blocked'  # Has 3rd-party dependencies
    new_stage = 'executing'
elif prereqs_list:
    new_status = 'queued'   # Has prerequisite stories
    new_stage = 'executing'
else:
    new_status = 'ready'    # No blockers
    new_stage = 'executing'

# Update story
cursor.execute('''
    UPDATE story_nodes
    SET stage = ?,
        status = ?,
        dependencies = ?,
        prerequisites = ?,
        human_review = 0,
        updated_at = datetime('now')
    WHERE id = ?
''', (new_stage, new_status, dependencies, prerequisites, story_id))

conn.commit()
conn.close()

print(f'Updated story {story_id}:')
print(f'  Stage: {new_stage}')
print(f'  Status: {new_status}')
print(f'  Dependencies: {deps_list}')
print(f'  Prerequisites: {prereqs_list}')
"
```

Create plan directory and save plan file:

```python
python -c "
import os
os.makedirs('${STORYTREE_DATA_DIR}/plans', exist_ok=True)
print('Plans directory ready')
"
```

Save plan to `${STORYTREE_DATA_DIR}/plans/NNN_{story-slug}.md`.

**Plan Filename Convention:**
- NNN = sequential number (001, 002, etc.)
- story-slug = kebab-case story title

## Output

Report the plan status:
- "Created plan for story [ID]: [Title]"
- "Plan saved to ${STORYTREE_DATA_DIR}/plans/[filename].md"
- "Story transitioned to executing"
- If blocked: "Story blocked on dependencies: [list]"
- If queued: "Story queued behind prerequisites: [list]"
- If clear: "Story ready for execution"

Or:
- "No queued stories found in planning stage"
- "Error: [specific issue]"

## Exit Transitions

| Condition | Transition |
|-----------|------------|
| Has 3rd-party dependencies | → `executing:blocked` |
| Has prerequisite stories (no 3rd-party deps) | → `executing:queued` |
| No blockers | → `executing:ready` |

## Does NOT

- Generate user journeys or mockups (handled by `/design-ux`)
- Process stories not in queued status (they haven't been approved)
- Execute the plan (handled by `/execute-story` or similar)

## References

- **Workflow diagram:** `claude/skills/story-tree/references/workflow2-planning.md`
- **Three-field model:** `claude/skills/story-tree/references/workflow-three-field-model.md`
- **User journeys:** Stored in `user_journeys` field on story_nodes
- **Mockups:** `${STORYTREE_DATA_DIR}/mockups/{story_id}.md`
- **Database:** `${STORYTREE_DATA_DIR}/story-tree.db`
