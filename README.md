# StoryTree

**Version 2.0** | Story-driven development orchestration tool for Claude Code.

> **v2.0 Milestone (January 2026)**: Complete transition from git submodules + symlinks to git subtrees. Files are now real, editable, and work everywhere — CI, Windows, Linux, and Claude Code web.

## Overview

StoryTree provides a complete workflow for managing development stories in Claude Code projects:

- **Story Tree**: Hierarchical story management with closure table pattern
- **CI/CD Integration**: GitHub Actions workflows for automated story processing
- **Xstory GUI**: Visual story tree explorer and editor (PySide6)
- **Skills & Commands**: Claude Code integration for story operations

## Installation

StoryTree is distributed via **git subtrees** — real files that can be edited in place and upstreamed back to StoryTree.

### Prerequisites

StoryTree maintains split branches for subtree consumption:
- `dist-skills` — Skills from `distributables/skills/`
- `dist-commands` — Commands from `distributables/commands/`
- `dist-scripts` — Scripts from `distributables/scripts/`
- `dist-actions` — GitHub Actions from `distributables/actions/`
- `dist-gui` — Xstory GUI from `distributables/gui/`

### Adding StoryTree to a New Project

```bash
cd /path/to/your-project

# 1. Add StoryTree as a remote
git remote add storytree https://github.com/Mharbulous/StoryTree.git

# 2. Add subtrees from split branches
git subtree add --prefix=.claude/skills/storytree storytree dist-skills --squash
git subtree add --prefix=.claude/commands/storytree storytree dist-commands --squash
git subtree add --prefix=.claude/scripts/storytree storytree dist-scripts --squash
git subtree add --prefix=.github/actions/storytree storytree dist-actions --squash
git subtree add --prefix=.storytree/gui storytree dist-gui --squash

# 3. Create data directory
mkdir -p .storytree/local
cp /path/to/StoryTree/templates/story-tree.db.empty .storytree/local/story-tree.db

# 4. Commit the setup
git add .storytree/
git commit -m "chore: add StoryTree data directory"
```

### Configuration

StoryTree uses convention over configuration — no config file needed. The database is always at `.storytree/local/story-tree.db`.

### Project Structure After Installation

```
YourProject/
├── xstory.sh                    ← GUI launcher (Unix/Mac)
├── xstory.bat                   ← GUI launcher (Windows)
├── .storytree/
│   ├── data/                    ← REPO-SPECIFIC (not in subtree)
│   │   ├── story-tree.db        ← This repo's story database
│   │   ├── concepts/
│   │   ├── designs/
│   │   ├── plans/
│   │   └── goals/
│   └── gui/                     ← SUBTREE: Xstory visual explorer
│       ├── xstory.py
│       ├── requirements.txt
│       └── build.py
│
├── .claude/
│   ├── skills/
│   │   ├── storytree/           ← SUBTREE: shared skills
│   │   │   ├── SKILL.md         ← Router skill
│   │   │   ├── story-tree/
│   │   │   ├── story-arborist/
│   │   │   └── ...
│   │   └── my-local-skill/      ← Project-specific skill
│   │
│   ├── commands/
│   │   ├── storytree/           ← SUBTREE: shared commands
│   │   │   ├── write-story.md
│   │   │   └── ...
│   │   └── my-command.md        ← Project-specific command
│   │
│   └── scripts/
│       ├── storytree/           ← SUBTREE: shared scripts
│       │   ├── config.py
│       │   └── ...
│       └── local_helper.py      ← Project-specific script
│
└── .github/
    ├── actions/
    │   └── storytree/           ← SUBTREE: composite actions
    │       └── ...
    └── workflows/
        └── *.yml                ← Project-specific (thin wrappers)
```

**Key separation:**
- `.claude/*/storytree/` = subtree-owned (shared tools)
- `.storytree/gui/` = subtree-owned (Xstory visual explorer)
- `.storytree/local/` = repo-specific (database, plans, etc.)

## Daily Workflow

### Editing Files

Subtree files are real files — edit them normally:

```bash
# Edit a skill in your project
code .claude/skills/storytree/story-tree/SKILL.md

# Commit as usual
git add .claude/skills/storytree/story-tree/SKILL.md
git commit -m "fix: improve story-tree error handling"
```

### Upstreaming Changes to StoryTree

Push improvements back to StoryTree's split branches:

```bash
git subtree push --prefix=.claude/skills/storytree storytree dist-skills
git subtree push --prefix=.claude/commands/storytree storytree dist-commands
git subtree push --prefix=.claude/scripts/storytree storytree dist-scripts
git subtree push --prefix=.github/actions/storytree storytree dist-actions
git subtree push --prefix=.storytree/gui storytree dist-gui
```

After pushing, StoryTree maintainers can merge changes from split branches to main.

### Pulling Updates from StoryTree

When StoryTree has updates, pull them into your project:

```bash
git subtree pull --prefix=.claude/skills/storytree storytree dist-skills --squash
git subtree pull --prefix=.claude/commands/storytree storytree dist-commands --squash
git subtree pull --prefix=.claude/scripts/storytree storytree dist-scripts --squash
git subtree pull --prefix=.github/actions/storytree storytree dist-actions --squash
git subtree pull --prefix=.storytree/gui storytree dist-gui --squash
```

### Helper Script (Optional)

Create `scripts/storytree-sync.sh` for convenience:

```bash
#!/bin/bash
set -e

REMOTE="storytree"

declare -A BRANCH_MAP=(
    [".claude/skills/storytree"]="dist-skills"
    [".claude/commands/storytree"]="dist-commands"
    [".claude/scripts/storytree"]="dist-scripts"
    [".github/actions/storytree"]="dist-actions"
    [".storytree/gui"]="dist-gui"
)

case "$1" in
    push)
        echo "Pushing to StoryTree..."
        for prefix in "${!BRANCH_MAP[@]}"; do
            git subtree push --prefix="$prefix" "$REMOTE" "${BRANCH_MAP[$prefix]}"
        done
        ;;
    pull)
        echo "Pulling from StoryTree..."
        for prefix in "${!BRANCH_MAP[@]}"; do
            git subtree pull --prefix="$prefix" "$REMOTE" "${BRANCH_MAP[$prefix]}" --squash
        done
        ;;
    *)
        echo "Usage: $0 {push|pull}"
        exit 1
        ;;
esac
```

## StoryTree Repository Structure

```
StoryTree/
├── README.md
├── CLAUDE.md
│
├── distributables/              ← Source for split branches
│   ├── xstory.sh                ← GUI launcher (Unix/Mac)
│   ├── xstory.bat               ← GUI launcher (Windows)
│   ├── skills/                  ← → dist-skills branch
│   │   ├── SKILL.md             ← Router skill
│   │   ├── story-tree/
│   │   ├── story-arborist/
│   │   └── ...
│   ├── commands/                ← → dist-commands branch
│   ├── scripts/                 ← → dist-scripts branch
│   ├── actions/                 ← → dist-actions branch
│   └── gui/                     ← → dist-gui branch
│       ├── xstory.py            ← Visual story tree explorer
│       ├── requirements.txt
│       └── build.py
│
├── .storytree/                  ← StoryTree's own data
│   └── data/
│       └── story-tree.db        ← StoryTree's story database
│
└── templates/
    └── story-tree.db.empty      ← Empty database template
```

## Maintaining Split Branches (StoryTree Maintainers)

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

## CI Configuration

For GitHub Actions, use the StoryTree composite actions:

```yaml
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: ./.github/actions/storytree/your-action
```

## Database Schema

The story tree uses SQLite with a closure table pattern for efficient hierarchical queries.

Key tables:
- `story_nodes`: Story definitions with three-field workflow system
- `story_paths`: Closure table for ancestor/descendant relationships
- `story_commits`: Commit tracking per story
- `vetting_decisions`: Entity resolution cache

See `distributables/skills/story-tree/references/schema.sql` for full schema.

## Workflow Stages

Stories progress through these stages:

```
concept → planning → executing → reviewing → verifying → implemented → ready → released
```

Stories can be held (queued, pending, blocked, etc.) or disposed (rejected, archived, etc.) at any stage.

## Xstory GUI

Xstory is a visual story tree explorer built with PySide6 (Qt for Python). It is distributed via subtree to `.storytree/gui/`.

### Running Xstory

```bash
# Install dependencies (one-time)
pip install -r .storytree/gui/requirements.txt

# Run the GUI
./xstory.sh        # Unix/Mac
xstory.bat         # Windows
```

### Features

- Visual tree navigation with expand/collapse
- Story node editing (title, description, stage, hold/dispose status)
- Stage progression tracking
- Parent-child relationship management
- Database integrity verification

### Building Standalone Executable

```bash
cd .storytree/gui
python build.py
```

## Troubleshooting

### Subtree Push Fails with "Updates were rejected"

This usually means the split branch has diverged. Re-split in StoryTree first:

```bash
# In StoryTree repo
git subtree split --prefix=distributables/skills -b dist-skills
git push -f origin dist-skills
```

Then retry the push from your project.

### Merge Conflicts on Subtree Pull

When both repos edited the same file:

1. Git will pause and show conflict markers
2. Resolve conflicts in each file
3. `git add` the resolved files
4. `git commit` to complete the merge

**Prevention:** Upstream changes promptly to avoid divergence.

### Scripts Can't Find Database

Check your data directory:

```bash
# Verify database exists at standard path
ls -la .storytree/local/story-tree.db
```

If missing, re-run setup or copy from the template:
```bash
cp /path/to/StoryTree/templates/story-tree.db.empty .storytree/local/story-tree.db
```

## License

MIT
