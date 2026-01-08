Revise an existing story based on human feedback and goals alignment.

## Arguments

$Arguments

- **With story ID**: Refine the specified story
- **Without arguments**: Auto-discover stories with `status='polish'`

## Process

### 1. Find Polish Story

If no story ID provided, query for stories needing refinement:

```python
python -c "
import sqlite3, json
conn = sqlite3.connect('${STORYTREE_DATA_DIR}/story-tree.db')
conn.row_factory = sqlite3.Row

# Find oldest polish story
stories = [dict(row) for row in conn.execute('''
    SELECT s.id, s.title, s.description, s.notes,
           (SELECT ancestor_id FROM story_paths WHERE descendant_id = s.id AND depth = 1) as parent_id
    FROM story_nodes s
    WHERE s.status = 'polish'
    ORDER BY s.created_at ASC
    LIMIT 1
''').fetchall()]

if stories:
    print(json.dumps({'found': True, 'story': stories[0]}, indent=2))
else:
    print(json.dumps({'found': False, 'message': 'No polish stories found'}, indent=2))
conn.close()
"
```

If no polish stories found, exit with "No polish stories found" message.

### 2. Gather Context

Read current content and feedback:

```python
python -c "
import sqlite3, json
conn = sqlite3.connect('${STORYTREE_DATA_DIR}/story-tree.db')
conn.row_factory = sqlite3.Row

story_id = 'STORY_ID'
story = dict(conn.execute('''
    SELECT id, title, description, notes, stage, status
    FROM story_nodes WHERE id = ?
''', (story_id,)).fetchone())

print(json.dumps(story, indent=2))
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

### 3. Analyze Feedback

Parse human comments from the notes field:
- Identify specific concerns to address
- Check alignment with stated goals
- Note any scope clarifications needed

### 4. Generate Revised Concept

Address each concern from notes while maintaining:
- User story format (As a / I want / So that)
- 3+ testable acceptance criteria
- Evidence grounding
- Goals alignment

### 5. Validate Revision

Apply the same validation checks as `/write-concept`:

| Check | Failure Condition |
|-------|-------------------|
| User story format | Missing "As a" / "I want" / "So that" |
| Specific role | Generic "user", "someone", "anyone" |
| Acceptance criteria | Fewer than 3, or untestable |
| Evidence grounding | No commits cited, no gap identified |
| Scope containment | Story exceeds parent scope |
| Goals alignment | Conflicts with non-goals.md |

Additionally verify the revision addresses the feedback.

### 6. Update Story

Archive previous version and update:

```python
python -c "
import sqlite3
from datetime import datetime

conn = sqlite3.connect('${STORYTREE_DATA_DIR}/story-tree.db')
cursor = conn.cursor()

story_id = 'STORY_ID'
new_description = '''REVISED_DESCRIPTION'''

# Get current description and notes
cursor.execute('SELECT description, notes FROM story_nodes WHERE id = ?', (story_id,))
row = cursor.fetchone()
current_description = row[0]
current_notes = row[1] or ''

# Archive previous version to notes
timestamp = datetime.now().strftime('%Y-%m-%d %H:%M')
archive_entry = f'''

---
**Previous Version ({timestamp}):**
{current_description}
---
'''

# Update story
cursor.execute('''
    UPDATE story_nodes
    SET description = ?,
        notes = ?,
        status = 'ready',
        stage = 'concept',
        updated_at = datetime('now')
    WHERE id = ?
''', (new_description, current_notes + archive_entry, story_id))

conn.commit()
conn.close()
print(f'Refined story {story_id}')
"
```

## Output

Report the updated story ID:
- "Refined concept [ID]: [Title]"
- "No polish stories found"
- "Validation failed: [specific errors]"

## Does NOT

- Vet for conflicts (handled by `/vet-concept`)
- Create new stories (handled by `/write-concept`)

## Story Format

```markdown
**As a** [specific role]
**I want** [specific capability]
**So that** [specific benefit]

**Acceptance Criteria:**
- [ ] [Specific, testable criterion]
- [ ] [Specific, testable criterion]
- [ ] [Specific, testable criterion]

**Related context:** [Evidence or gap type]

**Refinement Notes:** [What changed from previous version]
```

## References

- **Workflow diagram:** `claude/skills/story-tree/references/workflow1-concept.md`
- **Three-field model:** `claude/skills/story-tree/references/workflow-three-field-model.md`
- **Database:** `${STORYTREE_DATA_DIR}/story-tree.db`
