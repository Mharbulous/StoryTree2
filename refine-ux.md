Refine user journeys and mockup based on human feedback.

## Arguments

$Arguments

- **With story ID**: Refine the specified story's design
- **Without arguments**: Auto-discover stories with `stage='planning'` and `status='polish'`

## Process

### 1. Find Polish Story

If no story ID provided, query for stories needing refinement:

```python
python -c "
import sqlite3, json
conn = sqlite3.connect('${STORYTREE_DATA_DIR}/story-tree.db')
conn.row_factory = sqlite3.Row

# Find oldest polish story in planning stage
stories = [dict(row) for row in conn.execute('''
    SELECT s.id, s.title, s.description, s.notes, s.user_journeys,
           (SELECT ancestor_id FROM story_paths WHERE descendant_id = s.id AND depth = 1) as parent_id
    FROM story_nodes s
    WHERE s.stage = 'planning'
      AND s.status = 'polish'
      AND s.terminus IS NULL
    ORDER BY s.updated_at ASC
    LIMIT 1
''').fetchall()]

if stories:
    print(json.dumps({'found': True, 'story': stories[0]}, indent=2))
else:
    print(json.dumps({'found': False, 'message': 'No polish stories found in planning stage'}, indent=2))
conn.close()
"
```

If no polish stories found, exit with "No polish stories found in planning stage" message.

### 2. Validate Story

Confirm story is at planning stage with polish hold:

```python
python -c "
import sqlite3, json
conn = sqlite3.connect('${STORYTREE_DATA_DIR}/story-tree.db')
conn.row_factory = sqlite3.Row

story_id = 'STORY_ID'
story = conn.execute('''
    SELECT id, title, description, stage, status, terminus, user_journeys, notes
    FROM story_nodes WHERE id = ?
''', (story_id,)).fetchone()

if story:
    result = dict(story)
    result['valid'] = (result['stage'] == 'planning' and
                       result['status'] == 'polish' and
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
- Story status is not 'polish' → exit with error
- Story has terminus → exit with error

### 3. Load Current Design

Load existing user journeys and mockup:

```python
python -c "
import sqlite3, json, os

conn = sqlite3.connect('${STORYTREE_DATA_DIR}/story-tree.db')
conn.row_factory = sqlite3.Row

story_id = 'STORY_ID'
story = conn.execute('''
    SELECT id, title, description, user_journeys, notes
    FROM story_nodes WHERE id = ?
''', (story_id,)).fetchone()

result = dict(story)

# Parse user journeys
if result['user_journeys']:
    result['parsed_journeys'] = json.loads(result['user_journeys'])

# Load mockup file
mockup_filename = story_id.replace('.', '_') + '.md'
mockup_path = f'${STORYTREE_DATA_DIR}/mockups/{mockup_filename}'
if os.path.exists(mockup_path):
    with open(mockup_path) as f:
        result['mockup'] = f.read()
    result['mockup_path'] = mockup_path

conn.close()
print(json.dumps(result, indent=2))
"
```

### 4. Analyze Feedback

Parse human comments from the notes field:
- Identify specific concerns to address
- Check for requested changes to user journeys
- Note any mockup modifications needed
- Review alignment with patterns and anti-patterns

### 5. Gather Context

Read design patterns for reference:

```python
python -c "
import os, json
result = {}

# Read design patterns (from synthesize-designs output)
for key, path in [('patterns', '${STORYTREE_DATA_DIR}/design/patterns.md'), ('anti_patterns', '${STORYTREE_DATA_DIR}/design/anti-patterns.md')]:
    if os.path.exists(path):
        with open(path) as f: result[key] = f.read()

print(json.dumps(result, indent=2))
"
```

### 6. Revise Design

Address each concern from feedback while maintaining:
- User journey structure (title, actor, goal, steps, success criteria, edge cases)
- Mockup format (overview, layout, components, states, interactions, accessibility)
- Alignment with design patterns
- Avoidance of anti-patterns

**Revision Notes:**
Include a summary of what changed from the previous version.

### 7. Save Refined Outputs

Update user journeys in database:

```python
python -c "
import sqlite3, json
from datetime import datetime

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

# Get current notes
cursor.execute('SELECT notes FROM story_nodes WHERE id = ?', (story_id,))
current_notes = cursor.fetchone()[0] or ''

# Archive previous version in notes
timestamp = datetime.now().strftime('%Y-%m-%d %H:%M')
archive_entry = f'''

---
**Design Revision ({timestamp}):**
[Summary of changes made]
---
'''

# Update story - clear polish hold and escalate for review
cursor.execute('''
    UPDATE story_nodes
    SET user_journeys = ?,
        notes = ?,
        status = 'escalated',
        human_review = 1,
        updated_at = datetime('now')
    WHERE id = ?
''', (user_journeys, current_notes + archive_entry, story_id))

conn.commit()
conn.close()
print(f'Updated story {story_id} with refined design')
"
```

Update mockup file at `${STORYTREE_DATA_DIR}/mockups/{story_id}.md`.

### 8. Escalate for Review

The story is now at `planning (escalated)` awaiting human review of the refined design.

## Output

Report the refinement status:
- "Refined design for story [ID]: [Title]"
- "Updated [N] user journeys"
- "Mockup updated at ${STORYTREE_DATA_DIR}/mockups/[filename].md"
- "Story re-escalated for human review"

Or:
- "No polish stories found in planning stage"
- "Error: [specific issue]"

## Does NOT

- Create initial designs (handled by `/design-ux`)
- Create implementation plans (handled by `/create-plan`)
- Process stories not in polish hold

## Refinement Cycle

Human can request multiple rounds of refinement:
1. `/design-ux` → `planning (escalated)`
2. Human review → `planning (polish)` with feedback in notes
3. `/refine-ux` → `planning (escalated)`
4. Repeat 2-3 until approved → `planning (queued)`
5. `/create-plan` → transition to executing

## References

- **Workflow diagram:** `claude/skills/story-tree/references/workflow2-planning.md`
- **Three-field model:** `claude/skills/story-tree/references/workflow-three-field-model.md`
- **Design patterns:** `${STORYTREE_DATA_DIR}/design/patterns.md`
- **Database:** `${STORYTREE_DATA_DIR}/story-tree.db`
