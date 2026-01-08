# Testing Stage - Option C: Streamlined Minimal

> For definitions of stages, statuses, and terminal states, see @workflow-three-field-model.md

**Design Philosophy**: Simplest possible flow with essential elements only. Easy to understand at a glance.

---

## Stage Diagram

```mermaid
---
config:
  layout: elk
  elk:
    mergeEdges: true
    nodePlacementStrategy: LINEAR_SEGMENTS
---
flowchart TB
    exec_escalated[executing: escalated] -->|approve| test_ready

    subgraph testing_stage [testing]
        test_ready[ready]
        test_escalated[escalated]
        test_queued[queued]
        test_broken[polish]

        test_ready --> story_verify((🤖 verify-code.yml))
        story_verify -->|Pass| test_escalated
        story_verify -->|Fail| test_queued[queued]
        test_queued --> code_correction((correct-code.yml))
        code_correction --> code_review((review-code.yml))
        code_review --> story_verify
        test_escalated --> human_val((👤 validate-code.yml))
        human_val -->|refine| test_broken
        test_broken --> refine_story((refine-story.yml))
        refine_story --> plan_refactoring((refactor-plan.yml))
    end

    human_val -->|approve| releasing[releasing:ready]
    plan_refactoring -->|3rd-party deps| exec_blocked[executing:blocked]
    plan_refactoring -->|prereq stories| exec_queued[executing:queued]
    plan_refactoring -->|no blockers| exec_ready[executing:ready]

    classDef executingBox fill:#00CCCC,stroke:#00A3A3,color:#fff
    classDef testingBox fill:#0099CC,stroke:#007AA3,color:#fff
    classDef releasingBox fill:#0066CC,stroke:#0052A3,color:#fff
    classDef brokenBox fill:#FF6B6B,stroke:#CC5555,color:#fff
    classDef escalatedBox fill:#FFB84D,stroke:#CC9340,color:#fff
    classDef aiBox fill:#9370DB,stroke:#7B68EE,color:#fff
    classDef humanBox fill:#20B2AA,stroke:#008B8B,color:#fff

    class exec_escalated executingBox
    class testing_stage testingBox
    class releasing releasingBox
    class exec_blocked,exec_queued,exec_ready executingBox
```

---

## Workflow Description

### Entry from Executing

| Outcome from Executing | Entry State |
|------------------------|-------------|
| Human approves escalated implementation | `testing:ready` |

### Core Flow

```
Entry → verify-code.yml ──Pass──→ validate-code.yml ──approve──→ Exit
                            │                            │
                            Fail                         refine
                            ↓                            ↓
                          queued                       broken
                            │                            │
                            ├──→ fixed → retry           ├──→ fixed → retry
                            └──→ unfixable → escalated   └──→ unfixable → escalated
```

### Status Values

Three non-ready statuses used:

| Status | When Used |
|--------|-----------|
| `queued` | Verification fails (tests don't pass) |
| `broken` | Human validation requests refinement |
| `escalated` | Human approves OR queued/broken unfixable |

### Transitions

| From | To | Trigger |
|------|-----|---------|
| `ready` | `broken` | `verify-code.yml` fails |
| `ready` | `escalated` | `validate-code.yml` approves |
| `ready` | `broken` | `validate-code.yml` rejects |
| `broken` | `ready` | Issue fixed |
| `broken` | `escalated` | Issue unfixable (5 attempts) |

### Testing Steps

Two skills are invoked in sequence:

| Step | Skill | Actor | Question Answered |
|------|-------|-------|-------------------|
| 1 | `verify-code.yml` | 🤖 AI | Tests pass? Acceptance criteria met? |
| 2 | `validate-code.yml` | 👤 Human | Did I see it work? |

**Step 1: `verify-code.yml`** (AI Verification)
- Runs tests and checks acceptance criteria
- Verifies user journeys complete successfully
- Generates pass/fail report with evidence
- If pass → proceed to human validation
- If fail → `testing:broken`

**Step 2: `validate-code.yml`** (Human Validation)
- Presents demo scripts and checkpoint questions
- Human reviews evidence and decides
- If approved → `testing:escalated` → `releasing`
- If needs work → `testing:broken`

---

## What's Intentionally Omitted

This minimal design omits:

- **polish hold** — Refinements handled via broken→fixed loop
- **Explicit retry counts** — Delegated to debug-orchestrator
- **AI code review node** — Runs as part of `verify-code.yml`
- **Debug ladder details** — See @workflow-debugging.md
- **Evidence preparation** — Handled by `verify-code.yml` before `validate-code.yml`

### When to Use This Option

- Team prefers simple diagrams
- Debug ladder documented separately
- Orthogonal concerns handled by other docs
- Training/onboarding new team members

---

## Exit to Releasing

| Outcome | Transition |
|---------|------------|
| Human approves | → `releasing:ready` |
