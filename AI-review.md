AI-assisted code review before human escalation. Ensures humans see fresh code analysis at every decision point.

## Arguments

$Arguments

- **story_id** (optional): The story ID to review. If not provided, reviews recent changes.
- **stage** (optional): Current workflow stage (concept, planning, executing, testing, releasing)
- **--bootstrap** (flag): Run bootstrap process to initialize skill references

## Status Check

**First-time setup required.** If reference files don't exist, run:

```
/AI-review --bootstrap
```

This will research best practices and create the reference documentation.

## Process

### 1. Determine Review Scope

If story_id provided:
```python
python -c "
import sqlite3, json
conn = sqlite3.connect('${STORYTREE_DATA_DIR}/story-tree.db')
conn.row_factory = sqlite3.Row
story = conn.execute('''
    SELECT id, title, stage, status, plan_file
    FROM story_nodes WHERE id = ?
''', ('STORY_ID',)).fetchone()
if story:
    print(json.dumps(dict(story), indent=2))
conn.close()
"
```

If no story_id, review recent git changes:
```bash
git diff --name-only HEAD~1
```

### 2. Run Automated Checks

Run available linting/security tools:

```bash
# Python projects
python -m flake8 src/ --count --show-source --statistics 2>/dev/null || true
python -m mypy src/ 2>/dev/null || true

# JavaScript projects
npm run lint 2>/dev/null || true

# Security scan (if available)
semgrep --config auto --json src/ 2>/dev/null || echo '{"results":[]}'
```

### 3. AI Code Analysis

For each changed file, analyze:

#### Security Checklist
- [ ] User input validated before use?
- [ ] No hardcoded secrets/credentials?
- [ ] SQL queries use parameterized statements?
- [ ] Output escaped to prevent XSS?
- [ ] Auth/authz checks present where needed?

#### AI-Generated Code Checklist
- [ ] No calls to non-existent APIs (hallucinations)?
- [ ] Dependencies exist and are current?
- [ ] Follows project's existing patterns?
- [ ] Not over-engineered for the use case?
- [ ] Error handling is appropriate?

#### Logic Checklist
- [ ] Edge cases handled (null, empty, boundaries)?
- [ ] Error paths return appropriate responses?
- [ ] No potential infinite loops?
- [ ] State mutations are safe?

#### Architecture Checklist
- [ ] Follows project naming conventions?
- [ ] Appropriate abstraction level?
- [ ] No circular dependencies?
- [ ] Consistent with existing codebase?

### 4. Generate Report

Create review report:

```markdown
## AI Code Review Report

**Story:** [ID] - [Title] (or "Recent changes")
**Stage:** [stage]
**Files reviewed:** [list]
**Review date:** [timestamp]

### Summary
[Overall assessment - 1-2 sentences]

### Critical Findings (must address)
- [ ] [Finding] — [file:line]

### Warnings (should address)
- [ ] [Finding] — [file:line]

### Suggestions (consider)
- [ ] [Finding] — [file:line]

### Automated Check Results
| Check | Result |
|-------|--------|
| Linting | [pass/fail/N/A] |
| Type check | [pass/fail/N/A] |
| Security scan | [pass/fail/N/A] |

### Recommended Actions
1. [Action item]
2. [Action item]
```

### 5. Attach to Story (if story_id provided)

```python
python -c "
import sqlite3
from datetime import datetime

conn = sqlite3.connect('${STORYTREE_DATA_DIR}/story-tree.db')
story_id = 'STORY_ID'
review_summary = '''AI Review completed. See full report in ${STORYTREE_DATA_DIR}/reviews/'''

conn.execute('''
    UPDATE story_nodes
    SET notes = COALESCE(notes, '') || '\n\n## AI Review (' || ? || ')\n' || ?,
        updated_at = ?
    WHERE id = ?
''', (datetime.now().isoformat()[:10], review_summary, datetime.now().isoformat(), story_id))
conn.commit()
conn.close()
print('Review attached to story')
"
```

Save full report:
```bash
mkdir -p ${STORYTREE_DATA_DIR}/reviews
# Save report to ${STORYTREE_DATA_DIR}/reviews/{story_id}_{date}.md
```

## Bootstrap Process

When `--bootstrap` flag is provided:

### Step 1: Research Best Practices

Search and summarize:
- "AI code review best practices 2024 2025"
- "Security review AI-generated code SAST"
- "Code review checklist solo developer"
- "Common AI code generation mistakes patterns"

Save to: `.claude/skills/code-reviewing/references/best-practices-research.md`

### Step 2: Create Detailed Checklists

Based on research, create comprehensive checklists for:
- Security review (by vulnerability type)
- AI-specific issues (hallucinations, outdated patterns)
- Logic review (edge cases, error handling)
- Architecture review (patterns, conventions)

Save to: `.claude/skills/code-reviewing/references/review-checklist.md`

### Step 3: Document Common AI Mistakes

Catalog patterns specific to AI-generated code:
- Hallucinated APIs
- Outdated library usage
- Over-abstraction
- Missing error handling
- Ignoring project conventions

Save to: `.claude/skills/code-reviewing/references/common-ai-mistakes.md`

### Step 4: Refine with Skill Writing

Use `Skill(skill="superpowers:writing-skills")` to:
- Test the skill against sample code
- Identify gaps
- Refine instructions

## Output

Reports review findings and attaches to story if applicable.

Exit codes:
- 0: Review complete, no critical findings
- 1: Review complete, critical findings present
- 2: Error during review

## Integration Points

This command should be invoked immediately before escalation in each stage:

| Stage | Insert After | Before |
|-------|--------------|--------|
| concept | /vet-concept | escalated |
| planning | /design-story | escalated |
| executing | execution complete | escalated |
| testing | tests pass | escalated |
| releasing | final checks | escalated |

## References

- **Skill file:** `.claude/skills/code-reviewing/SKILL.md`
- **Review checklists:** `.claude/skills/code-reviewing/references/`
- **Saved reviews:** `${STORYTREE_DATA_DIR}/reviews/`
