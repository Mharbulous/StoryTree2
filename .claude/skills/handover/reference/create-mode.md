# Create Mode Workflow

Generate handover from conversation for the next session.

## Pre-Creation Analysis (MANDATORY)

### Step 1: Task Separation

Are there conceptually distinct tasks that should be separate handovers?

| Indicator | Single Handover | Multiple Handovers |
|-----------|-----------------|-------------------|
| Scope | One cohesive goal | Multiple independent goals |
| Files touched | Overlapping file sets | Disjoint file sets |
| Completion | All-or-nothing | Can complete one without other |
| Context | Shared discoveries | Separate problem domains |

### Step 2: Dependency Analysis

For each pair of handovers:
- Does one DEPEND on the other? (uses outputs, requires changes made by other)
- Can they be done in any order? (independent)

### Step 3: Number Assignment

**Critical**: Handovers are processed in descending order (highest number first).

| Dependency | Number Assignment | Result |
|------------|-------------------|--------|
| A must complete before B | A gets HIGHER number | A processed first |
| Independent | Any order | Either works |

**Example**: "Update diagrams" before "Update transitions":
- `083_update-workflow-diagrams.md` (higher = first)
- `082_update-xstory-transitions.md` (lower = second)

## Dependency Blocking Instructions

For ANY handover that depends on another, add immediately after `## Task`:

```markdown
## Blocking Dependency

**DO NOT START** until completed:
- `ai_docs/Handovers/083_prerequisite-task.md`

If that file exists in `ai_docs/Handovers/` (not in `Completed/`), work on it first.
```

## Context Gathering

Extract from conversation:
- **Key Files**: Files read or edited
- **Red Herrings**: Files examined but irrelevant (explain why)
- **Failed Approaches**: Errors encountered, approaches abandoned (with reasons)
- **Key Discoveries**: Non-obvious insights from trial and error
- **Useful URLs**: Web searches, documentation links
- **Current State**: What's done vs what remains
- **Next Step**: Immediate action to take

### Cumulative Failure Tracking

Check if first user message contains "Failed Approaches:". If found, copy that section verbatim and prepend to new Failed Approaches.

## Exclusions

- Branch information
- Verbose explanations
- Details obvious to Sonnet 4.5

## Output Format

```markdown
# Handover: {Task Summary}

## Task
{1-2 sentence description}

## Blocking Dependency
{ONLY if depends on another handover}

**DO NOT START** until completed:
- `ai_docs/Handovers/NNN_prerequisite-task.md`

## Current State
{Done vs remaining}

## Key Files
- path/to/file.py

## Red Herrings
- path/to/file.py - {why irrelevant}

## Failed Approaches
1. {approach} - {why failed}

## Key Discoveries
- {non-obvious insight}

## Useful URLs
- [description](url)

## Next Step
{Specific immediate action}
```

## File Output

**Single handover:**
1. Scan `ai_docs/Handovers/` for highest numeric prefix
2. Increment by 1
3. Generate slug (lowercase, hyphens, max ~40 chars)
4. Write to `ai_docs/Handovers/{NNN}_{slug}.md`

**Multiple with dependencies:**
1. Find highest numeric prefix
2. Assign in REVERSE execution order (first to execute = highest number)
3. Add Blocking Dependency to dependent handovers
4. Report all paths with execution order

## Behavior by Argument

| Argument | File | Chat |
|----------|------|------|
| (default) | Write | Output |
| `file` | Write | Suppress |
| `chat` | Skip | Output |
