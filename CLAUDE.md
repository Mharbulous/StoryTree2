# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

StoryTree is a story-driven development orchestration tool for Claude Code. It provides hierarchical story management, CI/CD integration via GitHub Actions, a visual GUI explorer (Xstory), and Claude Code skills/commands for story operations.

**v2.0** uses git subtrees instead of submodules+symlinks, making files real and editable everywhere (CI, Windows, Linux, Claude Code web).

## Architecture

### Distribution Model

StoryTree maintains split branches for subtree consumption by other projects:
- `dist-skills` — Skills from `distributables/skills/`
- `dist-commands` — Commands from `distributables/commands/`
- `dist-scripts` — Scripts from `distributables/scripts/`
- `dist-actions` — GitHub Actions from `distributables/actions/`
- `dist-gui` — Xstory GUI from `distributables/gui/`

Consuming projects add these as subtrees, edit files in place, and can push changes back upstream.

### Key Directories

| Path | Purpose |
|------|---------|
| `distributables/` | Source for split branches (skills, commands, scripts, actions, gui) |
| `.storytree/data/` | StoryTree's own story database and artifacts |
| `.claude/skills/handover/` | Session handover management skill |
| `templates/` | Empty database template for new consumers |

### Database

SQLite with closure table pattern for hierarchical queries:
- `story_nodes` — Story definitions with three-field workflow system (stage, hold_reason, disposition)
- `story_paths` — Closure table for ancestor/descendant relationships
- `story_commits` — Commit tracking per story

### Story Lifecycle

```
concept → planning → executing → reviewing → verifying → implemented → ready → released
```

Stories can be held (queued, pending, blocked) or disposed (rejected, archived) at any stage.

### Agent Architecture

Combinatorial design separating:
- **Toolsets**: Reviewer (READ), Explorer (READ/Grep/Glob), Implementer (All), Communicator (None)
- **Personas**: Nitpicker (detail-obsessed), Curmudgeon (critical), Cribber (pattern-harvester)
- **Skills**: Mission-specific instructions composed via `skills:` frontmatter

Agent naming: `ST-{toolset}-{persona}.md` (e.g., `ST-reviewer-nitpicker.md`)

## Commands

### Git Subtree Operations (Maintainers)

After changes to `distributables/`, re-split and push:

```bash
# Re-create split branches
git subtree split --prefix=distributables/skills -b dist-skills
git subtree split --prefix=distributables/commands -b dist-commands
git subtree split --prefix=distributables/scripts -b dist-scripts
git subtree split --prefix=distributables/actions -b dist-actions
git subtree split --prefix=distributables/gui -b dist-gui

# Push to remote (force required after re-split)
git push -f origin dist-skills dist-commands dist-scripts dist-actions dist-gui
```

### Xstory GUI

```bash
# Install dependencies
pip install -r .storytree/gui/requirements.txt

# Run GUI
./xstory.sh        # Unix/Mac
xstory.bat         # Windows

# Build standalone executable
cd .storytree/gui && python build.py
```

### Python Scripts

```bash
# Generate daily vision doc from story database
python .claude/scripts/generate_vision_doc.py
```

## Claude Code Integration

### Skills

The handover skill (`.claude/skills/handover/`) manages session continuity:
- **Process mode**: Resume from latest incomplete handover (at session start)
- **Create mode**: Generate handover for next session (after making progress)

Mode is auto-detected based on conversation state.

### Skill Router Pattern

Claude Code discovers skills from `.claude/skills/` flatly. StoryTree uses router skills (`SKILL.md`) to expose nested skills, working around flat discovery limitations.
