Detect conflicts and duplicates among sibling concepts.

## Arguments

$Arguments

- **story_id** (required): The story ID at concept stage to vet

## Process

### 1. Load Story Content

Verify story exists and is at concept stage:

```python
python -c "
import sqlite3, json
conn = sqlite3.connect('${STORYTREE_DATA_DIR}/story-tree.db')
conn.row_factory = sqlite3.Row

story_id = 'STORY_ID'
story = conn.execute('''
    SELECT id, title, description, stage, status, terminus
    FROM story_nodes WHERE id = ?
''', (story_id,)).fetchone()

if story:
    result = dict(story)
    result['valid'] = story['stage'] == 'concept' and story['terminus'] is None
    print(json.dumps(result, indent=2))
else:
    print(json.dumps({'error': 'Story not found'}, indent=2))
conn.close()
"
```

If story is not at concept stage, exit with error.

### 2. Run Candidate Detection

Use the candidate detector script:

```bash
python .claude/scripts/candidate_detector.py --story-id STORY_ID
```

This will:
- Apply heuristics: keyword overlap, title similarity, description similarity
- Check cache for previously classified pairs
- Output candidate conflict pairs as JSON

### 3. Classify Each Candidate

For each candidate pair, determine conflict type:

| Type | Description |
|------|-------------|
| `duplicate` | Same capability, same scope |
| `scope_overlap` | Partial overlap in functionality |
| `competing` | Same problem, different approaches |
| `incompatible` | Mutually exclusive approaches |
| `false_positive` | Flagged but unrelated |

Read both story descriptions carefully before classifying.

### 4. Determine Action

Use this decision matrix (based on conflict type + other story status):

| Conflict Type | Other Status | Action |
|---------------|--------------|--------|
| duplicate | concept | TRUE_MERGE |
| duplicate | non-concept | DELETE concept |
| scope_overlap | concept | TRUE_MERGE |
| scope_overlap | non-concept | ESCALATE (CI: DEFER_PENDING) |
| competing | mergeable status | TRUE_MERGE |
| competing | blocked status | BLOCK concept |
| competing | other | DUPLICATIVE |
| incompatible | concept | PICK_BETTER |
| false_positive | any | SKIP |

**Status categories:**
- Mergeable: `concept`, `wishlisted`, `polish`, `refine`
- Blocked: `rejected`, `infeasible`, `duplicative`, `broken`, `queued`, `escalated`, `blocked`, `conflicted`

### 5. Execute Action

Use the vetting actions script:

```bash
# Delete a concept
python .claude/scripts/vetting_actions.py delete CONCEPT_ID

# Mark as duplicative
python .claude/scripts/vetting_actions.py duplicative CONCEPT_ID DUPLICATE_OF_ID

# Block a concept
python .claude/scripts/vetting_actions.py block CONCEPT_ID BLOCKING_ID

# Defer for human review (CI mode)
python .claude/scripts/vetting_actions.py defer CONCEPT_ID CONFLICTING_ID

# Merge two concepts
python .claude/scripts/vetting_actions.py merge KEEP_ID DELETE_ID "Merged Title" "Merged Description"

# Cache a decision
python .claude/scripts/vetting_actions.py cache ID_A ID_B CLASSIFICATION ACTION
```

### TRUE_MERGE Process

When merging two concepts:
1. Read both descriptions carefully
2. Create merged title (concise, captures both scopes)
3. Create merged description:
   - Best "As a user..." statement
   - Deduplicated acceptance criteria
   - Combined unique details
4. Keep the story with lower/earlier ID (more established)

### PICK_BETTER Process

For incompatible concepts:
1. Evaluate both based on: clarity, feasibility, project alignment, technical soundness
2. Delete the worse concept
3. Keep the better one

## Output

Report vetting result:
- "Vetting passed: No conflicts found for [ID]"
- "Conflict resolved: [action taken] for [ID]"
- "Escalated: Scope overlap with [conflicting IDs]"

## CI Mode Behavior

When running in CI (non-interactive):
- No interactive prompts
- HUMAN_REVIEW cases become DEFER_PENDING automatically
- Set `status='escalated'` with note listing conflicting IDs
- Use clear exit codes: 0=success, 1=error

## Does NOT

- Create or modify story content (except merge/delete)
- Generate new concepts
- Handle polish stories

## Cache Behavior

The vetting system uses a persistent cache (`vetting_decisions` table):
- Decisions are cached with story versions
- Cache is invalidated when stories change
- False positives are skipped on subsequent runs

```bash
# View cache statistics
python .claude/scripts/vetting_cache.py stats

# Clear cache if needed
python .claude/scripts/vetting_cache.py clear
```

## References

- **Decision matrix:** `deprecated/skills/concept-vetting/SKILL.md`
- **Workflow diagram:** `claude/skills/story-tree/references/workflow1-concept.md`
- **Three-field model:** `claude/skills/story-tree/references/workflow-three-field-model.md`
- **Database:** `${STORYTREE_DATA_DIR}/story-tree.db`
