Create TDD implementation plans for stories in the planning stage.

## Arguments

$Arguments

## CI Mode

CI mode auto-activates when `CI=true` env var is set or trigger includes "(ci)".
Uses compact template (~60% token reduction).

## Argument Handling

- **Specific ID(s)**: `/ci-create-plan 1.8.2` or `/ci-create-plan 1.2 1.3 1.4`
- **Count**: `/ci-create-plan 3` → plan top 3 priority stories
- **No arguments**: Plan single highest-priority story in planning stage

## Constraints

- Maximum 5 plans per invocation
- Only stories with `stage = 'planning'` and `status = 'queued'` (human-approved)
- Skip non-existent/non-queued IDs with error message, continue with remaining
- If fewer queued stories than requested, plan all available

## Workflow

For detailed planning workflow, see: `claude/commands/create-plan.md`

1. **Query stories** - Find stories in planning stage with status='queued'
2. **Load design** - Read user_journeys field and mockup file from `/design-ux`
3. **Research codebase** - Understand existing architecture and patterns
4. **Draft TDD plan** - Write test scenarios first, then implementation steps
5. **Check dependencies** - Identify third-party deps (→ blocked) or prerequisite stories (→ queued)
6. **Generate plan file** - Output to `${STORYTREE_DATA_DIR}/plans/NNN_[story-slug].md`
7. **Update story** - Set stage='executing', populate dependencies/prerequisites fields
8. **Set exit status** - Based on blockers: blocked (3rd-party), queued (prereqs), or ready

## Exit Transitions

| Condition | Transition |
|-----------|------------|
| Has 3rd-party dependencies | → `executing:blocked` |
| Has prerequisite stories | → `executing:queued` |
| No blockers | → `executing:ready` |

## Output

- Process stories sequentially
- Create separate plan files
- Update each story's stage to `executing` with appropriate status
- Summary report at end listing all plans created and their exit states

## References

- **Detailed command:** `claude/commands/create-plan.md`
- **Workflow diagram:** `claude/skills/story-tree/references/workflow2-planning.md`
- **Three-field model:** `claude/skills/story-tree/references/workflow-three-field-model.md`
