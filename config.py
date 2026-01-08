# distributables/scripts/config.py
"""
StoryTree configuration module.

Provides configurable paths for StoryTree data directory, enabling the same
tools to work across different repositories with different data locations.

Configuration precedence:
1. STORYTREE_DATA_DIR environment variable (for CI and explicit override)
2. Standard location .storytree/data (convention for consuming repos)
3. Legacy .claude/data (StoryTree repo itself)
"""

import os
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

    # 2. Standard location for consuming repos
    standard_path = _find_repo_root() / '.storytree' / 'data'
    if standard_path.exists():
        return standard_path

    # 3. Legacy location (StoryTree repo itself)
    return Path('.claude/data')


def get_db_path() -> Path:
    """Get path to the story-tree.db database."""
    return get_data_dir() / 'story-tree.db'


def get_plans_dir() -> Path:
    """Get path to the plans directory."""
    return get_data_dir() / 'plans'


def get_concepts_dir() -> Path:
    """Get path to the concepts directory."""
    return get_data_dir() / 'concepts'


def get_designs_dir() -> Path:
    """Get path to the designs directory."""
    return get_data_dir() / 'designs'


def get_goals_dir() -> Path:
    """Get path to the goals directory."""
    return get_data_dir() / 'goals'


def get_reviews_dir() -> Path:
    """Get path to the reviews directory."""
    return get_data_dir() / 'reviews'


def get_handovers_dir() -> Path:
    """Get path to the handovers directory."""
    return get_data_dir() / 'handovers'
