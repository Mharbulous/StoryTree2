# Process Mode Workflow

Resume from latest incomplete handover. **Process ONE handover per session.**

## The Iron Rule

```
STOP after finding incomplete work. Do NOT continue cascading.
```

Process mode finds the first incomplete handover and implements it. You do not check additional handovers after finding work to do.

## Workflow

1. Scan `ai_docs/Handovers/` for numbered files, sorted descending (e.g., `079`, `078`, `077`...)
2. Announce: "Checking handover: `ai_docs/Handovers/XXX_task-name.md`"
3. Spawn Haiku subagent to check completion status (see `haiku-subagent.md`)
4. **Cascade ONLY if completed**: If `cascade: true`, move to `Completed/`, announce next file, spawn another subagent. Repeat until `cascade: false`.
5. **STOP cascading when `cascade: false`**
6. Announce: "Resuming handover: `ai_docs/Handovers/XXX_task-name.md`"
7. Read the handover file and begin implementation

## Acting on Haiku Response

| `status` | `cascade` | Action |
|----------|-----------|--------|
| `completed` | `true` | Move to `Completed/`, spawn subagent for next file |
| `partially_completed` | `false` | **STOP cascading.** Resume this handover. |
| `not_begun` | `false` | **STOP cascading.** Resume this handover. |

## Common Rationalizations (All Wrong)

| Excuse | Reality |
|--------|---------|
| "Let me check the next one too" | NO. You found work. Do it. |
| "I'll just scan all of them first" | NO. Process mode = process ONE. |
| "The other handovers might be more urgent" | NO. Handovers are numbered by priority. |
| "I should give the user options" | NO. The user invoked /handover to work, not to choose. |

## Edge Cases

| Condition | Action |
|-----------|--------|
| No handover files exist | Inform: "No handovers found in ai_docs/Handovers/" |
| All handovers completed | Inform: "All handovers completed. Ready for new work." |
| Haiku returns invalid JSON | Read handover yourself to determine status |

## Human Decision Points

When a handover requires human decisions with subagent recommendations:

**MANDATORY**: Read and follow `reference/human-decision-workflow.md`

Key requirements:
- **Never relay** - Counter-recommend or explicitly agree with YOUR reasoning
- **Always summarize** - Assume human has not read handover or key files
- **Both justify** - Subagent AND main agent must persuade

## Completing a Handover

When all tasks in the current handover are complete:

1. Move file to `ai_docs/Handovers/Completed/`
2. Announce: "Handover instructions are complete, so I moved the handover file to the Completed/ folder."

**Do NOT ask** whether to delete or archive - just move it.
**Do NOT** automatically start the next handover - the session is complete.
