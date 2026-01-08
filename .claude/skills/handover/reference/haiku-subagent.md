# Haiku Subagent Prompt

Spawn a Task agent with:
- **subagent_type**: `general-purpose`
- **model**: `haiku`
- **run_in_background**: `false` (need result immediately for cascade decision)

## Prompt Template

```
Check if this handover has already been completed.

1. Read ONLY this handover file: {filepath}

2. Check for Progress Made section:
   - If "## Progress Made" section exists with checked items `- [x]`:
     - If all tasks in handover appear covered: status = "completed"
     - If some but not all: status = "partially_completed"
   - If no Progress Made section, proceed to git check (step 3)

3. Git commit check (only if no Progress Made section):
   - Get file's last modified date: git log -1 --format="%ci" -- "{filepath}" (or file mtime)
   - Run: git log --oneline --since="{file_date}"
   - Compare commit messages against handover's task description and "Next Step" section

Respond with ONLY this JSON (no other text):
{
  "status": "completed" | "partially_completed" | "not_begun",
  "confidence": 0-100,
  "reason": "brief explanation",
  "cascade": true | false
}

Status definitions:
- "completed": All tasks accomplished (via Progress Made section or git commits)
- "partially_completed": Progress Made section has items OR some related commits but task incomplete
- "not_begun": No Progress Made section AND no related commits

Cascade logic:
- "completed" -> cascade: true (check next handover)
- "partially_completed" -> cascade: false (resume this one)
- "not_begun" -> cascade: false (start this one)
```

## Response Handling

| `status` | `cascade` | Main Agent Action |
|----------|-----------|-------------------|
| `completed` | `true` | Move to `Completed/`, spawn subagent for next |
| `partially_completed` | `false` | **STOP cascading.** Resume this handover only. |
| `not_begun` | `false` | **STOP cascading.** Resume this handover only. |

**Critical**: When `cascade: false`, you have found your work. Do NOT check additional handovers.

If Haiku returns invalid JSON, read the handover yourself to determine status.
