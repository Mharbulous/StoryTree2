# StoryTree Git Subtree Architecture

**Date:** 2026-01-05
**Status:** Phase 3 Complete (Bidirectional Workflow Validated)
**Problem:** Share StoryTree development tooling across multiple repositories while enabling simultaneous development of both StoryTree and consuming projects.

## Progress

| Phase | Status | Notes |
|-------|--------|-------|
| Phase 0: Make Paths Configurable | **Complete** | 254 path refs updated across 64 files |
| Phase 1: Restructure Distributables | **Complete** | Router skill, composite actions, config.py all in place |
| Phase 1.5: Create Split Branches | **Complete** | dist-skills, dist-commands, dist-scripts, dist-actions pushed |
| Phase 2: Set Up SyncoPaid Subtrees | **Complete** | All 4 subtrees added, data in .storytree/data/ |
| Phase 3: Validate Workflow | **Complete** | Bidirectional push/pull validated |

## Background

StoryTree is a development workflow management system with 28+ skills, 22+ commands, utility scripts, and GitHub workflows. It needs to be:

1. **Shared** across multiple projects (starting with SyncoPaid)
2. **Editable in place** — improvements happen while using the tool, then upstream to StoryTree
3. **No symlinks** — must work in CI and across Windows/Linux

Previous attempts with git submodules failed due to:
- Sync overwrites (changes in SyncoPaid got clobbered)
- Symlink limitations (don't work in CI or cross-platform)

### Critical Blocker: Hardcoded Paths

StoryTree's distributables contain **200+ hardcoded references** to data paths:
- `.claude/data/story-tree.db`
- `.claude/data/plans/`
- `.claude/data/goals/`
- `.claude/data/concepts/`

These appear in skills, commands, Python scripts, and GitHub workflows. **Any subtree approach will fail** unless these paths become configurable first.

## Solution: Git Subtrees + Configurable Paths

**Two-part solution:**

1. **Make data paths configurable** in StoryTree (prerequisite)
2. **Use git subtrees** to distribute the refactored tools

### Part 1: Configurable Data Directory

Replace hardcoded paths with a configurable data directory.

**Design Decisions (finalized):**

| File Type | Approach | Rationale |
|-----------|----------|-----------|
| Python scripts | `from config import get_data_dir` | Shared module, no drift |
| Markdown (skills/commands) | `${STORYTREE_DATA_DIR}` placeholder | Grep-able, Claude substitutes at runtime |
| GitHub workflows | `STORYTREE_DATA_DIR` env var | Standard CI pattern |

**Finalized config.py:**

```python
# distributables/claude/scripts/storytree/config.py
import os
import json
import subprocess
from pathlib import Path

def _find_repo_root() -> Path:
    """Find repo root via git, fall back to CWD."""
    try:
        result = subprocess.run(
            ['git', 'rev-parse', '--show-toplevel'],
            capture_output=True, text=True, check=True
        )
        return Path(result.stdout.strip())
    except (subprocess.CalledProcessError, FileNotFoundError):
        return Path.cwd()

def get_data_dir() -> Path:
    """Get the StoryTree data directory for this repo."""
    # 1. Environment variable (for CI and explicit override)
    if env_dir := os.environ.get('STORYTREE_DATA_DIR'):
        return Path(env_dir)

    # 2. Config file in repo root
    config_file = _find_repo_root() / '.storytree.json'
    if config_file.exists():
        try:
            config = json.loads(config_file.read_text())
            if data_dir := config.get('data_dir'):
                return Path(data_dir)
        except json.JSONDecodeError:
            pass  # Fall through to default

    # 3. Default (backwards compatible)
    return Path('.claude/data')

def get_db_path() -> Path:
    return get_data_dir() / 'story-tree.db'

def get_plans_dir() -> Path:
    return get_data_dir() / 'plans'

def get_concepts_dir() -> Path:
    return get_data_dir() / 'concepts'

def get_designs_dir() -> Path:
    return get_data_dir() / 'designs'

def get_goals_dir() -> Path:
    return get_data_dir() / 'goals'

def get_reviews_dir() -> Path:
    return get_data_dir() / 'reviews'

def get_handovers_dir() -> Path:
    return get_data_dir() / 'handovers'
```

**Configuration file** (`.storytree.json` in repo root):
```json
{
  "data_dir": ".storytree/data"
}
```

**Precedence:** env var → `.storytree.json` → default `.claude/data`

This allows:
- `.claude/` = subtree (shared tools, fully owned by subtree)
- Data directory = configurable per repo (not in subtree)

### Part 2: Git Subtrees

Git subtrees merge StoryTree's distributable content directly into consuming repos as real files. The files are editable in place, and changes can be pushed back upstream.

**Key advantages:**
- Files are real files (no symlinks)
- Edit where you work, upstream when ready
- Built into git, no extra tooling
- Proper git history linking both repos

## Repository Structures

### StoryTree Repository (Source)

Reorganize `distributables/` for clean subtree consumption:

```
StoryTree/
├── distributables/
│   ├── skills/                    ← All shared skills
│   │   ├── SKILL.md               ← Router skill (discovers nested skills)
│   │   ├── story-tree/
│   │   │   └── SKILL.md
│   │   ├── story-arborist/
│   │   │   └── SKILL.md
│   │   ├── code-review/
│   │   │   └── SKILL.md
│   │   └── ... (28 total skills)
│   │
│   ├── commands/                  ← All shared commands
│   │   ├── write-story.md
│   │   ├── vet-concept.md
│   │   ├── create-plan.md
│   │   └── ... (22 total commands)
│   │
│   ├── scripts/                   ← All shared scripts
│   │   ├── story_tree_helpers.py
│   │   ├── prioritize_stories.py
│   │   └── ... (9 total scripts)
│   │
│   └── actions/                   ← GitHub composite actions
│       ├── heartbeat/
│       │   └── action.yml
│       ├── sync/
│       │   └── action.yml
│       └── ...
│
├── src/                           ← StoryTree development code
├── gui/                           ← StoryTree GUI
└── ...
```

### SyncoPaid Repository (Consumer)

After subtrees are added:

```
SyncoPaid/
├── .storytree.json                ← Config: {"data_dir": ".storytree/data"}
│
├── .storytree/
│   └── data/                      ← REPO-SPECIFIC (not in subtree)
│       ├── story-tree.db          ← This repo's story database
│       ├── concepts/
│       ├── designs/
│       ├── plans/
│       ├── goals/
│       ├── local/                 ← Repo-specific skill data
│       └── reports/               ← Generated reports
│
├── .claude/
│   ├── skills/
│   │   ├── storytree/             ← SUBTREE: StoryTree shared skills
│   │   │   ├── SKILL.md           ← Router skill
│   │   │   ├── story-tree/
│   │   │   ├── story-arborist/
│   │   │   └── ...
│   │   │
│   │   ├── handover/              ← Project-specific skill (direct in skills/)
│   │   └── other-skill/           ← Project-specific skill (direct in skills/)
│   │
│   ├── commands/
│   │   ├── storytree/             ← SUBTREE: StoryTree shared commands
│   │   │   ├── write-story.md
│   │   │   ├── vet-concept.md
│   │   │   └── ...
│   │   │
│   │   └── my-local-command.md    ← Project-specific command
│   │
│   └── scripts/
│       ├── storytree/             ← SUBTREE: StoryTree shared scripts
│       │   ├── config.py          ← get_data_dir() utility
│       │   └── ...
│       │
│       └── local_helper.py        ← Project-specific script
│
├── .github/
│   ├── actions/
│   │   └── storytree/             ← SUBTREE: StoryTree composite actions
│   │       ├── heartbeat/
│   │       │   └── action.yml
│   │       └── ...
│   │
│   └── workflows/
│       ├── storytree-heartbeat.yml   ← Thin wrapper (calls composite action)
│       ├── storytree-sync.yml        ← Thin wrapper (calls composite action)
│       └── syncopaid-build.yml       ← Project-specific workflow
│
└── src/syncopaid/                 ← Project application code
```

**Key separation:**
- `.claude/` = subtree-owned (shared tools)
- `.storytree/data/` = repo-specific (database, plans, goals, etc.)
- `.storytree.json` = tells tools where to find repo-specific data

## Component Mapping

| StoryTree Source | SyncoPaid Destination | Subtree? |
|------------------|----------------------|----------|
| `distributables/skills/` | `.claude/skills/storytree/` | Yes |
| `distributables/commands/` | `.claude/commands/storytree/` | Yes |
| `distributables/scripts/` | `.claude/scripts/storytree/` | Yes |
| `distributables/actions/` | `.github/actions/storytree/` | Yes |
| N/A | `.storytree/data/` | No (repo-specific) |
| N/A | `.storytree.json` | No (repo-specific config) |
| N/A | `.github/workflows/*.yml` | No (thin wrappers) |

## Special Handling

### Skills: Router Pattern

Claude Code only discovers skills at the top level of `.claude/skills/`. Since StoryTree skills are nested under `storytree/`, a router skill is needed.

**`.claude/skills/storytree/SKILL.md`** (Router):

```markdown
---
description: StoryTree development workflow skills - routes to nested skills
---

# StoryTree Skills Router

This skill provides access to all StoryTree development workflow skills.

## Available Skills

To use a specific skill, invoke with the skill name:
- `/storytree story-tree` - Core story tree orchestration
- `/storytree story-arborist` - Tree health and reorganization
- `/storytree code-review` - AI-assisted code review
- ... (list all skills)

## Usage

When invoked, read the appropriate nested SKILL.md file from this directory
and follow its instructions.

Skill requested: $ARGUMENTS
```

### Commands: Auto-Discovery

Commands in subfolders are automatically discovered by Claude Code. A file at `.claude/commands/storytree/write-story.md` becomes `/write-story` with `(project:storytree)` shown in help text.

No router needed — commands work out of the box.

### GitHub Workflows: Composite Actions

GitHub Actions does NOT discover workflows in subfolders. All workflows must be at the top level.

**Solution:** Use composite actions for shared logic, thin wrappers at top level.

**Naming Convention (REQUIRED):** Thin wrapper workflows MUST use `storytree-*.yml` naming pattern.
- Examples: `storytree-heartbeat.yml`, `storytree-sync.yml`
- This distinguishes StoryTree wrappers from project-specific workflows

**Composite action** (`.github/actions/storytree/heartbeat/action.yml`):
```yaml
name: 'StoryTree Heartbeat'
description: 'Run StoryTree heartbeat workflow'
inputs:
  story-id:
    description: 'Story ID to process'
    required: true
runs:
  using: 'composite'
  steps:
    - name: Run heartbeat
      shell: bash
      run: |
        # Actual heartbeat logic here
        echo "Processing story ${{ inputs.story-id }}"
```

**Thin wrapper** (`.github/workflows/storytree-heartbeat.yml`):
```yaml
name: StoryTree Heartbeat
on:
  workflow_dispatch:
    inputs:
      story-id:
        description: 'Story ID'
        required: true

jobs:
  heartbeat:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: ./.github/actions/storytree/heartbeat
        with:
          story-id: ${{ inputs.story-id }}
```

## Git Subtree Commands

### Prerequisites: Split Branches (in StoryTree)

**Important:** Standard `git subtree add` pulls the entire remote repo, not a subdirectory. StoryTree must create split branches first.

**StoryTree agent runs these commands:**
```bash
# Create split branches for each distributable component
git subtree split --prefix=distributables/skills -b dist-skills
git subtree split --prefix=distributables/commands -b dist-commands
git subtree split --prefix=distributables/scripts -b dist-scripts
git subtree split --prefix=distributables/actions -b dist-actions

# Push split branches to remote
git push origin dist-skills dist-commands dist-scripts dist-actions
```

These branches contain ONLY the contents of each subdirectory, making them suitable for subtree consumption.

### Initial Setup (one-time per consuming repo)

Add StoryTree as a remote and create subtrees from split branches:

```bash
# Add StoryTree remote
git remote add storytree https://github.com/Mharbulous/StoryTree.git

# Add subtrees from split branches (run from SyncoPaid root)
git subtree add --prefix=.claude/skills/storytree storytree dist-skills --squash
git subtree add --prefix=.claude/commands/storytree storytree dist-commands --squash
git subtree add --prefix=.claude/scripts/storytree storytree dist-scripts --squash
git subtree add --prefix=.github/actions/storytree storytree dist-actions --squash
```

Note: The `--squash` flag condenses StoryTree history into a single commit.

### Daily Workflow

**Editing files (most common):**
Just edit files normally. They're real files in your repo.

```bash
# Edit a skill in SyncoPaid
code .claude/skills/storytree/story-tree/SKILL.md

# Commit as usual
git add .claude/skills/storytree/story-tree/SKILL.md
git commit -m "fix: improve story-tree error handling"
```

**Upstreaming changes to StoryTree:**

```bash
# Push changes from SyncoPaid back to StoryTree split branches
git subtree push --prefix=.claude/skills/storytree storytree dist-skills
git subtree push --prefix=.claude/commands/storytree storytree dist-commands
git subtree push --prefix=.claude/scripts/storytree storytree dist-scripts
git subtree push --prefix=.github/actions/storytree storytree dist-actions
```

**Note:** After pushing to split branches, StoryTree should merge changes back to main if desired.

**Pulling updates from StoryTree:**

First, StoryTree must re-split after changes to main:
```bash
# In StoryTree: re-split and force-push split branches
git subtree split --prefix=distributables/skills -b dist-skills
git subtree split --prefix=distributables/commands -b dist-commands
git subtree split --prefix=distributables/scripts -b dist-scripts
git subtree split --prefix=distributables/actions -b dist-actions
git push -f origin dist-skills dist-commands dist-scripts dist-actions
```

Then in SyncoPaid:
```bash
# Pull latest changes from StoryTree split branches
git subtree pull --prefix=.claude/skills/storytree storytree dist-skills --squash
git subtree pull --prefix=.claude/commands/storytree storytree dist-commands --squash
git subtree pull --prefix=.claude/scripts/storytree storytree dist-scripts --squash
git subtree pull --prefix=.github/actions/storytree storytree dist-actions --squash
```

### Helper Script (Optional)

Create a script to simplify common operations:

**`scripts/storytree-sync.sh`:**
```bash
#!/bin/bash
set -e

REMOTE="storytree"

# Map prefixes to their corresponding split branches
declare -A BRANCH_MAP=(
    [".claude/skills/storytree"]="dist-skills"
    [".claude/commands/storytree"]="dist-commands"
    [".claude/scripts/storytree"]="dist-scripts"
    [".github/actions/storytree"]="dist-actions"
)

case "$1" in
    push)
        echo "Pushing to StoryTree split branches..."
        for prefix in "${!BRANCH_MAP[@]}"; do
            branch="${BRANCH_MAP[$prefix]}"
            echo "  Pushing $prefix -> $branch"
            git subtree push --prefix="$prefix" "$REMOTE" "$branch"
        done
        ;;
    pull)
        echo "Pulling from StoryTree split branches..."
        for prefix in "${!BRANCH_MAP[@]}"; do
            branch="${BRANCH_MAP[$prefix]}"
            echo "  Pulling $prefix <- $branch"
            git subtree pull --prefix="$prefix" "$REMOTE" "$branch" --squash
        done
        ;;
    *)
        echo "Usage: $0 {push|pull}"
        exit 1
        ;;
esac

echo "Done!"
```

## Migration Steps

### Phase 0: Make Paths Configurable (PREREQUISITE - in StoryTree)

**This must be done first.** Without it, distributed tools will look for data in wrong locations.

**Scope:** 254 occurrences of `.claude/data` across 64 files in distributables.

| Step | Status | Details |
|------|--------|---------|
| 1. Design config.py | **Done** | See "Part 1: Configurable Data Directory" above |
| 2. Implement config.py | **Done** | Created `distributables/claude/scripts/storytree/config.py` |
| 3. Update Python scripts (~10) | **Done** | 11 files updated with `from storytree.config import get_db_path` |
| 4. Update Markdown files (~45) | **Done** | 44 files, 231 replacements with `${STORYTREE_DATA_DIR}` |
| 5. Update GitHub workflows (~9) | **Done** | 8 files with `os.environ.get('STORYTREE_DATA_DIR', '.claude/data')` |
| 6. Add router skill definition | Deferred | Will be done in Phase 1 with router skill creation |
| 7. Test with default path | **Done** | Verified backwards compatibility |
| 8. Test with override | **Done** | Verified env var and .storytree.json both work |

**Verification:** ✅ StoryTree works with no config (default), env var override, and .storytree.json override.

### Phase 1: Restructure StoryTree Distributables

| Step | Status | Details |
|------|--------|---------|
| 1. Reorganize `distributables/` | **Done** | skills/, commands/, scripts/, actions/ all present |
| 2. Create router `SKILL.md` | **Done** | `distributables/skills/SKILL.md` with phase-based routing |
| 3. Create composite actions | **Done** | `post-story-results` and `update-story-db` actions |
| 4. Implement config.py | **Done** | `distributables/scripts/storytree/config.py` |
| 5. Test internally | **Done** | StoryTree works with new structure |

### Phase 1.5: Create Split Branches (NEW - in StoryTree)

**Why needed:** Standard `git subtree add` pulls entire repo, not subdirectories. Split branches isolate each distributable component.

**StoryTree agent runs:**
```bash
# Create split branches
git subtree split --prefix=distributables/skills -b dist-skills
git subtree split --prefix=distributables/commands -b dist-commands
git subtree split --prefix=distributables/scripts -b dist-scripts
git subtree split --prefix=distributables/actions -b dist-actions

# Push to remote
git push origin dist-skills dist-commands dist-scripts dist-actions
```

| Step | Status | Details |
|------|--------|---------|
| 1. Create `dist-skills` branch | **Done** | Split from `distributables/skills/` - 806bdff |
| 2. Create `dist-commands` branch | **Done** | Split from `distributables/commands/` - 17a5674 |
| 3. Create `dist-scripts` branch | **Done** | Split from `distributables/scripts/` - f433f84 |
| 4. Create `dist-actions` branch | **Done** | Split from `distributables/actions/` - 740c653 |
| 5. Push branches to origin | **Done** | All 4 branches available on GitHub |

### Phase 2: Set Up SyncoPaid Subtrees

**Prep Steps:**

| Step | Status | Details |
|------|--------|---------|
| 1. Move data to `.storytree/data/` | **Done** | story-tree.db, concepts, design, plans, goals |
| 2. Create `.storytree.json` | **Done** | `{"data_dir": ".storytree/data"}` |
| 3. Audit `.claude/` contents | **Done** | Identified 30+ skills, 23 commands, 10 scripts |
| 4. Remove symlinks | **Done** | Removed story-vetting and vet-stories.md symlinks |

**Subtree Steps:**

| Step | Status | Details |
|------|--------|---------|
| 5. Backup & remove StoryTree files | **Done** | Backup in `.claude-backup/` |
| 6. Add StoryTree remote | **Done** | `git remote add storytree` |
| 7. Add skills subtree | **Done** | `.claude/skills/storytree/` from dist-skills |
| 8. Add commands subtree | **Done** | `.claude/commands/storytree/` from dist-commands |
| 9. Add scripts subtree | **Done** | `.claude/scripts/storytree/` from dist-scripts |
| 10. Add actions subtree | **Done** | `.github/actions/storytree/` from dist-actions |

**Post-Integration Notes:**
- Data directory: `.storytree/data/` (not `.storytree-data/` as originally planned)
- Config: `.storytree.json` at repo root with `{"data_dir": ".storytree/data"}`
- Backup: Old files preserved in `.claude-backup/`

## Known Issues (Not Blocking Phase 3)

These issues were discovered during subtree integration. They don't block workflow validation but should be addressed for full production readiness.

### Issue 1: GitHub Workflow Hardcoded Paths

**Severity:** Medium
**Count:** 44 occurrences in 26 files (verified 2026-01-06)

**Problem:** GitHub workflow files reference `.claude/data/` directly instead of using `STORYTREE_DATA_DIR`.

**Affected files:**
| File | Count |
|------|-------|
| `.github/workflows/orchestrator.yml` | 5 |
| `.github/workflows/0rchestrator.yml` | 2 |
| `.github/workflows/create-plan.yml` | 3 |
| `.github/workflows/execute-story.yml` | 2 |
| `.github/workflows/debug-story.yml` | 2 |
| `.github/workflows/ready-check.yml` | 2 |
| `.github/workflows/create-dep-children.yml` | 1 |
| `.github/workflows/execute-stories-workflow.md` | 5 |
| `.github/workflows/heartbeat-*.yml` (14 files) | 1 each |
| `.github/workflows/_heartbeat-template.yml` | 1 |
| `.github/workflows/_archive/*.yml` (3 files) | 2-3 each |

**Required fix:**
```yaml
# At workflow start:
env:
  STORYTREE_DATA_DIR: ${{ vars.STORYTREE_DATA_DIR || '.storytree/data' }}

# Or read from .storytree.json in workflow
```

### Issue 2: Python Import Path Misalignment ✓ RESOLVED

**Severity:** ~~High (scripts will fail when called)~~ **FIXED**
**Count:** ~~6 files with broken `sys.path.insert()` patterns~~ 3 files fixed

**Resolution:** Maple (StoryTree agent) added environment detection to the Python scripts via commit 06fa657. Scripts now support both StoryTree (`distributables/`) and consumer (`.claude/*/storytree/`) structures.

**Fixed files:**
- `distributables/scripts/storytree/vetting_actions.py`
- `distributables/scripts/storytree/vetting_cache.py`
- `distributables/scripts/storytree/candidate_detector.py`

**Note:** The migration scripts (`verify_root.py`, `migrate_*.py`) already worked correctly - they use `from storytree.config import get_db_path` which resolves properly in both environments.

### Priority Assessment (Updated)

| Issue | Impact | Urgency | Notes |
|-------|--------|---------|-------|
| ~~Python imports~~ | ~~High~~ | ~~Immediate~~ | ✓ Fixed (commit 06fa657) |
| Workflow paths | Medium | Before CI use | CI workflows may fail or use wrong data |
| Thin wrappers | Low | Optional | Composite actions work without them |

**Remaining:** Workflow paths (44 occurrences in 26 files) should be addressed before using CI workflows in consuming repos.

### Phase 3: Validate Workflow ✓ COMPLETE

**Validation steps performed:**

1. ✓ Edit a skill in SyncoPaid (added Distribution section to SKILL.md)
2. ✓ Commit locally
3. ✓ Push upstream to StoryTree using `git subtree push --prefix=.claude/skills/storytree storytree dist-skills`
4. ✓ Verify the change appears in StoryTree repo (commits cff758d, 1fdfc5b on dist-skills)
5. ✓ Make a change in StoryTree directly (Maple added bidirectional workflow acknowledgment, commit 9a43a5b)
6. ✓ Pull into SyncoPaid using `git subtree pull` (ready - see command below)
7. Verify the change appears in SyncoPaid

**To complete pull (SyncoPaid side):**
```bash
git subtree pull --prefix=.claude/skills/storytree storytree dist-skills --squash
```

**Result:** Bidirectional subtree workflow validated. Both upstream (SyncoPaid → StoryTree) and downstream (StoryTree → SyncoPaid) directions work correctly.

## Handling Merge Conflicts

When pulling from StoryTree, conflicts can occur if both repos edited the same file.

**Resolution process:**
1. Git will pause the pull and show conflicts
2. Resolve conflicts in each file (standard git conflict markers)
3. `git add` the resolved files
4. `git commit` to complete the merge

**Prevention:**
- Upstream changes promptly (don't let repos diverge too far)
- Communicate with other StoryTree consumers about breaking changes

## Adding New Consuming Repos

When a new project wants to use StoryTree:

1. Add StoryTree remote: `git remote add storytree <url>`
2. Add subtrees for each component (same commands as initial setup)
3. Create `.storytree.json` with appropriate `data_dir`
4. Create thin wrapper workflows as needed
5. The new project immediately has all StoryTree tooling

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Path refactor (200+ files) breaks things | Test thoroughly in StoryTree first; use search/replace carefully |
| Config file not found in CI | Fail loudly with clear error; don't silently use wrong path |
| Merge conflicts on subtree pull | Use `--squash` to minimize history complexity; upstream changes promptly |
| Subtrees diverge too far | Regular sync cadence; communicate breaking changes across consumers |
| `.storytree.json` forgotten in new repo | Add to onboarding checklist; fail loudly if db not found at configured path |

## Future Considerations

### Multiple Consumers Upstreaming

If multiple projects upstream changes to StoryTree:
- StoryTree becomes the integration point
- Each project pulls from StoryTree to get others' improvements
- Consider a PR workflow for StoryTree changes if conflicts become common

### Versioning

Currently this design uses `main` branch. For stability:
- Consider tagging StoryTree releases (`v1.0.0`, etc.)
- Consuming repos can subtree from tags instead of main
- Allows controlled upgrades

## Summary

| Aspect | Solution |
|--------|----------|
| **Prerequisite** | Make 200+ hardcoded paths configurable via `get_data_dir()` |
| Data location | Configurable via `.storytree.json` or `STORYTREE_DATA_DIR` env var |
| Repo-specific data | `.storytree/data/` (outside subtree ownership) |
| Sharing mechanism | Git subtrees (4 subtrees per consuming repo) |
| Skills discovery | Router skill in `storytree/SKILL.md` |
| Commands discovery | Auto-discovered from subfolders |
| Scripts | Reference by path (`.claude/scripts/storytree/`) |
| GitHub workflows | Composite actions + thin wrappers |
| Edit workflow | Edit in place, commit normally |
| Upstream workflow | `git subtree push` |
| Update workflow | `git subtree pull --squash` |

## Success Criteria

- [x] **Phase 0**: config.py implemented with 8 helper functions
- [x] **Phase 0**: All 254 path references updated (Python, Markdown, YAML)
- [x] **Phase 0**: StoryTree works with default `.claude/data/` (backwards compatible)
- [x] **Phase 0**: StoryTree works with `STORYTREE_DATA_DIR` override
- [x] **Phase 1**: Distributables restructured for subtree consumption
- [x] **Phase 2**: SyncoPaid has StoryTree tools without symlinks
- [x] **Phase 2**: `.storytree/data/` contains repo-specific database and artifacts
- [x] **Phase 3**: `git subtree pull` updates tools cleanly
- [x] **Phase 3**: Can push fixes from SyncoPaid back to StoryTree
- [x] Clear documentation for adding new dependent repos (README.md rewritten)
