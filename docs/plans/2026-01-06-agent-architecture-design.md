# StoryTree Agent Architecture Design

## Overview

This document defines the combinatorial agent architecture for StoryTree distribution. The design maximizes flexibility by separating concerns into distinct layers that can be freely combined.

## Design Principles

1. **Agents are subtractive** - They provide clean-slate environments by removing irrelevant system prompt content, not by adding specialized instructions
2. **Skills are additive** - They provide mission-specific instructions that can be freely composed
3. **Minimum Viable Persona** - Agents defined by the minimal toolset + behavioral style needed for a cognitive task category

## Three-Layer Architecture

| Layer | What It Defines | Composition Method |
|-------|-----------------|-------------------|
| **Agent** | Toolset + Persona | Baked together in `.md` file |
| **Skills** | Mission-specific instructions | Attached via `skills:` field, freely composable |

### Layer 1: Agents (Toolset + Persona)

Agents combine two dimensions:

**Toolsets** (capabilities):
| Toolset | Tools | Purpose |
|---------|-------|---------|
| Reviewer | READ | Analyze, critique, report findings |
| Explorer | READ, Grep, Glob | Search, discover, map |
| Implementer | All | Execute plans, write code |
| Communicator | None (output only) | Synthesize, explain, summarize |

**Personas** (behavioral styles):
| Persona | Cognitive Mode |
|---------|---------------|
| Nitpicker | Detail-obsessed, finds small deviations |
| Curmudgeon | Critical, always finds a better way, grudgingly acknowledges elegance |
| Cribber | Pattern-harvester, looks for good ideas to copy/reuse |

**Naming Convention:** `ST-{toolset}-{persona}.md`

**Examples:**
- `ST-reviewer-nitpicker.md` - READ-only + detail-obsessed behavioral guidance
- `ST-reviewer-curmudgeon.md` - READ-only + critical/skeptical behavioral guidance
- `ST-explorer-cribber.md` - READ/Grep/Glob + pattern-harvesting behavioral guidance

### Layer 2: Skills (Mission-Specific)

Skills define specific tasks and are composed via the agent's `skills:` frontmatter field.

**Planned Skills:**
| Skill | Purpose |
|-------|---------|
| `double-checker` | Verify plan was fully implemented without error or unrequested additions |
| `conflict-checker` | Compare two plans for overlap, determine implementation order or parallelization |
| `mermaid-diagramming` | Identify syntax errors and anti-patterns in Mermaid diagrams |

### Combinatorial Power

With 4 toolsets × 3 personas = 12 agents, each composable with N skills:

```
Combinations = Agents × Skill-combinations = 12 × 2^N
```

For 3 skills: 12 × 8 = 96 distinct agent configurations from 15 authored components.

## Implementation Notes

### Agent File Structure

```yaml
---
name: ST-reviewer-nitpicker
description: Detail-obsessed code reviewer that finds small deviations
tools: Read
model: sonnet
skills: double-checker
---

# Reviewer - Nitpicker

You are a meticulous reviewer focused on finding details others miss.

## Behavioral Guidance

- Exhaustively verify every item, don't sample
- Report discrepancies precisely with file:line references
- Don't rationalize mismatches - if code differs from expectation, that's a finding
- Small deviations matter as much as large ones

## Constraints

- READ-only: You observe and report, you do not modify
- Stay focused on the specific verification task in your skill instructions
```

### Claude Code Limitations

- **No dynamic composition**: Agents are static definitions, cannot be composed at runtime
- **Skills CAN be composed**: Multiple skills via comma-separated `skills:` field
- **No inheritance**: Each agent is standalone, no extension mechanism

### Discovery Strategy

New agents and skills will be discovered through dogfooding in the SyncoPaid application rather than speculated upfront.

## References

- [Claude Code Subagents Documentation](https://code.claude.com/docs/en/sub-agents)
- Handover 031: Initial agents infrastructure setup
