Generate user journeys and mockup for a story in the planning stage.

## Arguments

$Arguments

- **With story ID**: Design the specified story
- **Without arguments**: Auto-discover stories with `stage='planning'` and `status='ready'`

## Process

### 1. Find Target Story

If no story ID provided, query for stories ready for design:

```python
python -c "
import sqlite3, json
conn = sqlite3.connect('${STORYTREE_DATA_DIR}/story-tree.db')
conn.row_factory = sqlite3.Row

# Find oldest planning story with status='ready'
stories = [dict(row) for row in conn.execute('''
    SELECT s.id, s.title, s.description,
           (SELECT ancestor_id FROM story_paths WHERE descendant_id = s.id AND depth = 1) as parent_id
    FROM story_nodes s
    WHERE s.stage = 'planning'
      AND s.status = 'ready'
      AND s.terminus IS NULL
    ORDER BY s.created_at ASC
    LIMIT 1
''').fetchall()]

if stories:
    print(json.dumps({'found': True, 'story': stories[0]}, indent=2))
else:
    print(json.dumps({'found': False, 'message': 'No planning stories found'}, indent=2))
conn.close()
"
```

If no planning stories found, exit with "No planning stories found" message.

### 2. Validate Story

Confirm story is at planning stage with status='ready':

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
                       result['status'] == 'ready' and
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
- Story has non-ready status → exit with error
- Story has terminus → exit with error

### 3. Gather Context

Read story context and goals:

```python
python -c "
import os, json
result = {}

# Read goals
for key, path in [('goals', '${STORYTREE_DATA_DIR}/goals/goals.md'), ('non_goals', '${STORYTREE_DATA_DIR}/goals/non-goals.md')]:
    if os.path.exists(path):
        with open(path) as f: result[key] = f.read()

# Read design patterns (from synthesize-designs output)
for key, path in [('patterns', '${STORYTREE_DATA_DIR}/design/patterns.md'), ('anti_patterns', '${STORYTREE_DATA_DIR}/design/anti-patterns.md')]:
    if os.path.exists(path):
        with open(path) as f: result[key] = f.read()

print(json.dumps(result, indent=2))
"
```

### 4. Generate User Journeys

Based on the story description and goals, generate 2-4 user journeys that describe how users will interact with the feature:

**User Journey Format:**
```markdown
### Journey: [Title]

**Actor:** [User role]
**Goal:** [What they want to accomplish]

**Steps:**
1. [First action]
2. [Second action]
3. [Third action]
...

**Success Criteria:**
- [Observable outcome]

**Edge Cases:**
- [Potential issue and how it's handled]
```

### 5. Create Mockup

Generate a mockup based on the user journeys and design patterns:

**Mockup Guidelines:**
- Use ASCII/text-based diagrams for UI layouts
- Reference patterns from patterns.md
- Avoid anti-patterns from anti-patterns.md
- Include state transitions for dynamic elements
- Note any accessibility considerations

**Mockup File Format:**
```markdown
# Mockup: [Story Title]

## Overview
[Brief description of the UI/UX approach]

## Layout
[ASCII diagram of the layout]

## Components
[List of UI components needed]

## States
[Different states the UI can be in]

## Interactions
[Key user interactions and responses]

## Accessibility Notes
[A11y considerations]

---
*Generated: [timestamp]*
```

### 6. Save Outputs

Save user journeys to database:

```python
python -c "
import sqlite3, json

conn = sqlite3.connect('${STORYTREE_DATA_DIR}/story-tree.db')
cursor = conn.cursor()

story_id = 'STORY_ID'
user_journeys = json.dumps([
    {
        'title': 'JOURNEY_TITLE',
        'actor': 'ACTOR',
        'goal': 'GOAL',
        'steps': ['STEP1', 'STEP2', 'STEP3'],
        'success_criteria': ['CRITERION1'],
        'edge_cases': ['EDGE_CASE1']
    }
    # ... additional journeys
])

cursor.execute('''
    UPDATE story_nodes
    SET user_journeys = ?,
        status = 'escalated',
        human_review = 1,
        updated_at = datetime('now')
    WHERE id = ?
''', (user_journeys, story_id))

conn.commit()
conn.close()
print(f'Updated story {story_id} with user journeys')
"
```

Create mockup directory and save mockup file:

```python
python -c "
import os
os.makedirs('${STORYTREE_DATA_DIR}/mockups', exist_ok=True)
print('Mockup directory ready')
"
```

Save mockup to `${STORYTREE_DATA_DIR}/mockups/{story_id}.md` (replace `.` with `_` in story_id for filename).

### 7. Escalate for Review

The story is now at `planning:escalated` awaiting human review.

## Output

Report the design status:
- "Designed story [ID]: [Title]"
- "Created [N] user journeys"
- "Mockup saved to ${STORYTREE_DATA_DIR}/mockups/[filename].md"
- "Story escalated for human review"

Or:
- "No planning stories found"
- "Error: [specific issue]"

## Does NOT

- Create implementation plans (handled by `/create-plan`)
- Refine existing designs (handled by `/refine-ux`)
- Process stories with non-ready status

## Human Review Outcomes

After review, human will set one of:
- `planning:queued` → approved, ready for `/create-plan`
- `planning:polish` → needs refinement via `/refine-ux`
- `planning:wishlisted` → deferred indefinitely
- `terminus: rejected` → explicitly declined

## References

- **Workflow diagram:** `claude/skills/story-tree/references/workflow2-planning.md`
- **Three-field model:** `claude/skills/story-tree/references/workflow-three-field-model.md`
- **Design patterns:** `${STORYTREE_DATA_DIR}/design/patterns.md`
- **Database:** `${STORYTREE_DATA_DIR}/story-tree.db`
