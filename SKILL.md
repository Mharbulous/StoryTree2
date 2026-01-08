---
name: storytree
description: Story-driven development workflow. Use when user mentions stories, concepts, plans, implementation, verification, tree structure, backlog, TDD, acceptance criteria, or development lifecycle. Covers ideation through deployment.
---

# StoryTree - Progressive Skill Router

Route to specialized skills based on task. **Read only the linked SKILL.md that matches the task.**

## Quick Route by Intent

| User intent | Read this skill |
|-------------|-----------------|
| "write story", "add feature", "show tree", status | [story-tree/SKILL.md](story-tree/SKILL.md) |
| "check tree health", "move story", "orphans", "reparent" | [story-arborist/SKILL.md](story-arborist/SKILL.md) |
| "prioritize", "what next", "priority order" | [prioritize-story-nodes/SKILL.md](prioritize-story-nodes/SKILL.md) |
| "new concept", "feature idea", "brainstorm", "backlog" | [concept-building/SKILL.md](concept-building/SKILL.md) |
| "expand concept", "write concept doc" | [concept-writing/SKILL.md](concept-writing/SKILL.md) |
| "refine concept", "improve concept" | [concept-refinement/SKILL.md](concept-refinement/SKILL.md) |
| "vet concepts", "find duplicates", "overlaps" | [concept-vetting/SKILL.md](concept-vetting/SKILL.md) |
| "design story", "create design spec" | [story-design/SKILL.md](story-design/SKILL.md) |
| "refine design", "improve design" | [design-refinement/SKILL.md](design-refinement/SKILL.md) |
| "UI patterns", "UX decisions", "synthesize designs" | [design-synthesis/SKILL.md](design-synthesis/SKILL.md) |
| "create plan", "implementation plan", "plan story" | [plan-creation/SKILL.md](plan-creation/SKILL.md) |
| "decompose plan", "break down plan", "split plan" | [plan-decomposition/SKILL.md](plan-decomposition/SKILL.md) |
| "refactor plan", "restructure plan" | [plan-refactoring/SKILL.md](plan-refactoring/SKILL.md) |
| "synthesize goals", "project direction", "non-goals" | [goal-synthesis/SKILL.md](goal-synthesis/SKILL.md) |
| "implement", "execute plan", "TDD", "start coding" | [story-execution/SKILL.md](story-execution/SKILL.md) |
| "refine story", "iterate implementation" | [story-refinement/SKILL.md](story-refinement/SKILL.md) |
| "streamline", "decompose files", "break down large file" | [streamline/SKILL.md](streamline/SKILL.md) |
| "verify story", "acceptance criteria", "is it ready" | [story-verification/SKILL.md](story-verification/SKILL.md) |
| "run tests", "verify code", "check journeys" | [code-verification/SKILL.md](code-verification/SKILL.md) |
| "demo", "human review", "validate with user" | [code-validation/SKILL.md](code-validation/SKILL.md) |
| "debug", "broken", "fix bug" (implementing stage) | [code-debugging/SKILL.md](code-debugging/SKILL.md) |
| "debug execution", "broken" (executing stage) | [debug-orchestrator/SKILL.md](debug-orchestrator/SKILL.md) |
| "fix failures", "correction", "meet acceptance criteria" | [code-correction/SKILL.md](code-correction/SKILL.md) |
| "anti-pattern", "test_code_patterns.py failed" | [code-sentinel/SKILL.md](code-sentinel/SKILL.md) |
| "code review", "review before merge" | [code-review/SKILL.md](code-review/SKILL.md) |
| "create skill", "update skill", "skill refinement" | [skill-refinement/SKILL.md](skill-refinement/SKILL.md) |
| "generate docs", "user manual" | [user-manual-generator/SKILL.md](user-manual-generator/SKILL.md) |

## Routing Instructions

1. **Match user intent** to a row in the table above using semantic similarity
2. **Read only that skill's SKILL.md** - do not load others
3. **Follow the loaded skill completely** - it has full instructions
4. **If intent spans multiple phases**, see [execute-story-workflow.md](execute-story-workflow.md)

## If No Match

If the user's request doesn't clearly match any row:
1. Ask: "Which phase of development? (concept / design / plan / implement / verify / debug)"
2. Based on answer, load the corresponding skill

## Explicit Invocation

If user says `/storytree <skill-name>`, read `<skill-name>/SKILL.md` directly.

**Requested:** $ARGUMENTS

---

*Distributed via git subtree from StoryTree. Consumer repos pull from `dist-skills` branch.*
