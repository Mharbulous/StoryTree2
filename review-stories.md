Review user story concepts one at a time for approval.

## Query Concept Stories

Prioritize by depth (shallower first), then creation date (oldest first):

```python
python -c "
import sqlite3

conn = sqlite3.connect('${STORYTREE_DATA_DIR}/story-tree.db')
cursor = conn.cursor()

cursor.execute('''
    SELECT s.id, s.title, s.description, s.created_at,
           (SELECT MIN(depth) FROM story_paths WHERE descendant_id = s.id) as node_depth,
           (SELECT title FROM story_nodes p
            JOIN story_paths sp ON p.id = sp.ancestor_id
            WHERE sp.descendant_id = s.id AND sp.depth = 1) as parent_title
    FROM story_nodes s
    WHERE s.stage = 'concept'
      AND s.status = 'ready'
      AND s.terminus IS NULL
    ORDER BY node_depth ASC, s.created_at ASC
    LIMIT 1
''')

row = cursor.fetchone()
conn.close()

if row:
    id, title, desc, created, depth, parent = row
    print(f'ID: {id}')
    print(f'Title: {title}')
    print(f'Parent: {parent or \"root\"}')
    print(f'Depth: {depth}')
    print(f'Created: {created}')
    print(f'---DESCRIPTION---')
    print(desc)
else:
    print('NO_CONCEPTS_FOUND')
"
```

## Present for Review

```markdown
## Story for Review: **[Title]**

| Field | Value |
|-------|-------|
| **ID** | [id] |
| **Parent** | [parent_title] |
| **Stage** | concept |
| **Created** | [created_at] |

### User Story

[Full description]

---

**Options:** Approve | Reject | Refine | Wishlist
```

## Handle Response

Use three-field system (stage + status + terminus):

- **Approve**: `SET stage = 'planning'`
- **Reject**: `SET terminus = 'rejected'`
- **Polish**: `SET status = 'polish', human_review = 1`
- **Wishlisted**: `SET status = 'wishlisted'`

```python
# For APPROVE:
python -c "
import sqlite3
conn = sqlite3.connect('${STORYTREE_DATA_DIR}/story-tree.db')
cursor = conn.cursor()
cursor.execute('''
    UPDATE story_nodes
    SET stage = 'planning', updated_at = datetime('now')
    WHERE id = '[STORY_ID]'
''')
conn.commit()
conn.close()
print('Story [STORY_ID] approved')
"

# For REJECT:
python -c "
import sqlite3
conn = sqlite3.connect('${STORYTREE_DATA_DIR}/story-tree.db')
cursor = conn.cursor()
cursor.execute('''
    UPDATE story_nodes
    SET terminus = 'rejected', notes = COALESCE(notes || char(10), '') || '[REASON]', updated_at = datetime('now')
    WHERE id = '[STORY_ID]'
''')
conn.commit()
conn.close()
print('Story [STORY_ID] rejected')
"

# For POLISH:
python -c "
import sqlite3
conn = sqlite3.connect('${STORYTREE_DATA_DIR}/story-tree.db')
cursor = conn.cursor()
cursor.execute('''
    UPDATE story_nodes
    SET status = 'polish', human_review = 1, updated_at = datetime('now')
    WHERE id = '[STORY_ID]'
''')
conn.commit()
conn.close()
print('Story [STORY_ID] marked for refinement')
"

# For WISHLISTED:
python -c "
import sqlite3
conn = sqlite3.connect('${STORYTREE_DATA_DIR}/story-tree.db')
cursor = conn.cursor()
cursor.execute('''
    UPDATE story_nodes
    SET status = 'wishlisted', updated_at = datetime('now')
    WHERE id = '[STORY_ID]'
''')
conn.commit()
conn.close()
print('Story [STORY_ID] moved to wishlisted')
"
```

## Commit

```
git add ${STORYTREE_DATA_DIR}/story-tree.db
git commit -m "feat(stories): [action] story [id] - [title]"
git push
```

## Constraints

- Review ONE story per invocation
- If no concepts: suggest `/write-stories` or `story-writing` skill
