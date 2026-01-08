# StoryTree Usage Guide

This guide explains how to set up and use StoryTree in your project.

## Quick Start

### Initial Setup

Run these commands from your project root:

```bash
# Download and run the setup script
curl -O https://raw.githubusercontent.com/Mharbulous/StoryTree/main/distributables/scripts/setup.py
python setup.py
rm setup.py

# Commit the changes
git add -A
git commit -m "chore: add StoryTree"
```

The setup script:
- Adds the `storytree` remote
- Adds 6 git subtrees for StoryTree components
- Creates `.storytree/data/` directory
- Initializes an empty story database
- Installs launcher scripts (`xstory.sh` and `xstory.bat`)

### What Gets Installed

```
YourProject/
├── xstory.sh                 # GUI launcher (Unix/Mac)
├── xstory.bat                # GUI launcher (Windows)
├── .claude/
│   ├── skills/storytree/     # Story management skills
│   ├── commands/storytree/   # Slash commands
│   ├── scripts/storytree/    # Helper scripts (including these tools)
│   └── agents/               # Custom subagent definitions (ST-*.md)
├── .github/
│   └── actions/storytree/    # CI/CD actions
└── .storytree/
    ├── gui/                  # Xstory visual explorer
    └── data/
        └── story-tree.db     # Your story database
```

**Note on agents:** Claude Code requires agents to be directly in `.claude/agents/` (no nested subdirectories). StoryTree agents use an `ST-` prefix for identification (e.g., `ST-example.md`).

## Scripts

After setup, these scripts are available at `.claude/scripts/storytree/`:

### Check Status

```bash
python .claude/scripts/storytree/status.py
```

Shows the status of all StoryTree subtrees and your database:
- Which subtrees are installed
- How many commits ahead/behind each subtree is
- Story count in your database

### Pull Updates

```bash
python .claude/scripts/storytree/pull_fast.py
```

Pulls the latest changes from all StoryTree subtrees. Run this periodically to get updates.

If there are merge conflicts, the script will:
- Show which files have conflicts
- Continue pulling other subtrees
- Provide instructions for resolving conflicts

### Push Changes Upstream

```bash
python .claude/scripts/storytree/push_fast.py
```

If you've made improvements to StoryTree components, push them back:

```bash
# Preview what would be pushed
python .claude/scripts/storytree/push_fast.py --dry-run

# Actually push
python .claude/scripts/storytree/push_fast.py

# Force push all subtrees (skip change detection)
python .claude/scripts/storytree/push_fast.py --force

# Auto-recover from rejected pushes by pulling first
python .claude/scripts/storytree/push_fast.py --retry

# If --retry has conflicts, keep local changes
python .claude/scripts/storytree/push_fast.py --retry --strategy local

# Stash uncommitted changes first
python .claude/scripts/storytree/push_fast.py --stash
```

**Note:** You need push access to the StoryTree repository for this to work.

## What StoryTree Provides

### Story Database

StoryTree manages a hierarchical story database using SQLite with a closure table pattern. Stories progress through stages:

```
concept → planning → executing → reviewing → verifying → implemented → ready → released
```

Stories can also be held (queued, blocked, paused) or disposed (rejected, archived).

### Skills

StoryTree includes Claude Code skills for story management:
- Story creation and editing
- Stage progression
- Story tree navigation
- Verification workflows

### Agents

StoryTree includes custom Claude Code subagent definitions (in `.claude/agents/`):
- Use `ST-` prefixed agents via the Task tool
- Example: `Task(subagent_type="ST-example", prompt="...")`

### Xstory GUI

A visual story tree explorer built with PySide6:

```bash
# Install GUI dependencies (one-time)
pip install -r .storytree/gui/requirements.txt

# Run the GUI
./xstory.sh        # Unix/Mac
xstory.bat         # Windows
```

## Troubleshooting

### "Remote 'storytree' not found"

Run setup.py first, or manually add the remote:
```bash
git remote add storytree https://github.com/Mharbulous/StoryTree.git
```

### "Directory already exists" during setup

Setup is idempotent — it skips components that already exist. This is safe.

### Merge conflicts on pull

1. The script shows which files have conflicts
2. Edit the conflicted files to resolve
3. Run: `git add -A && git commit`

### Push rejected

Your local changes have diverged from upstream. Options:
1. Pull first: `python .claude/scripts/storytree/pull_fast.py`
2. Resolve any conflicts
3. Try pushing again

Or use auto-recovery: `python .claude/scripts/storytree/push_fast.py --retry`

### Database not found

The database should be at `.storytree/local/story-tree.db`. If missing, setup may not have completed. Re-run setup.py.
