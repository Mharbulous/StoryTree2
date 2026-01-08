Context-aware handover management: resume previous work or create a handover for the next session.

## Mode Detection

**Automatically determine mode based on conversation state:**

| Conversation State | Mode | Behavior |
|-------------------|------|----------|
| Empty or minimal (just `/handover`) | **Get** | Find latest handover, ask to implement |
| Progress has been made | **Create** | Generate handover from conversation |

## Get Mode (Start of Session)

When the conversation has little to no history:

1. Scan `ai_docs/Handovers/` for the highest-numbered file (e.g., `077_task-name.md`)
2. **Do NOT read the file yet**
3. Ask: "Shall I implement this handover prompt? `ai_docs/Handovers/077_task-name.md`"
4. Wait for confirmation before reading and proceeding

## Create Mode (After Progress)

### Arguments

- `file` - Write to file only, suppress chat output
- `chat` - Output to chat only, skip file creation
- (none) - Both file and chat (default)

### Instructions

Analyze this conversation to generate a handover prompt optimized for Sonnet 4.5. Include enough instruction and context to pick up where we left off. Omit obvious details that go without saying.

### Context Gathering

Extract from conversation:
- **Key Files**: Files read or edited during this session
- **Red Herrings**: Files examined but found irrelevant (explain why)
- **Failed Approaches**: Errors encountered, approaches abandoned (with reasons)
- **Key Discoveries**: Non-obvious insights from trial and error
- **Useful URLs**: Web searches, documentation links that helped
- **Current State**: What's done vs what remains (from todos, discussion)
- **Next Step**: The immediate action to take

### Cumulative Failure Tracking

**Critical**: Check if the first user message contains "Failed Approaches:". If found, copy that entire section verbatim and prepend it to the new Failed Approaches. This prevents repeating the same dead ends across debugging sessions.

### Exclusions

- Branch information
- Verbose explanations
- Details obvious to Sonnet 4.5

### Output Format

```markdown
# Handover: {Task Summary}

## Task
{1-2 sentence description of what we're doing}

## Current State
{What's done vs what remains}

## Key Files
- path/to/relevant-file.py
- path/to/another.md

## Red Herrings
- path/to/misleading-file.py - {why it's not relevant}

## Failed Approaches
1. {approach} → {why it failed}
2. {approach} → {why it failed}

## Key Discoveries
- {non-obvious insight from trial and error}
- {technical constraint discovered}

## Useful URLs
- [description](url)

## Next Step
{Specific immediate action to take}
```

### File Output

When writing to file:
1. Scan `ai_docs/Handovers/` for existing files
2. Find highest numeric prefix (e.g., `077` from `077_foo.md`)
3. Increment by 1 for new file number
4. Generate slug from task summary (lowercase, hyphens, max ~40 chars)
5. Write to `ai_docs/Handovers/{NNN}_{slug}.md`
6. Report the file path created

### Behavior by Argument

| Argument | File | Chat |
|----------|------|------|
| (default) | Write to `ai_docs/Handovers/` | Output handover text |
| `file` | Write to `ai_docs/Handovers/` | Suppress |
| `chat` | Skip | Output handover text |
