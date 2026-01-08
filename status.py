#!/usr/bin/env python3
"""
StoryTree Status Script

Shows the status of all StoryTree subtrees and data in a consuming repository.
This script is designed to be run from within a consuming repo to check sync status.

NOTE: This script should be run from a consuming repo that has StoryTree set up
      as subtrees, NOT from within the StoryTree repo itself.

Usage:
  python .claude/scripts/storytree/status.py
  python .storytree/scripts/status.py
"""

import sqlite3
import subprocess
import sys
from pathlib import Path


# Subtree configuration: local_path -> remote_branch
SUBTREES = {
    '.claude/skills/storytree': 'dist-skills',
    '.claude/commands/storytree': 'dist-commands',
    '.claude/scripts/storytree': 'dist-scripts',
    '.github/actions/storytree': 'dist-actions',
    '.storytree/gui': 'dist-gui',
}

REMOTE_NAME = 'storytree'


def find_repo_root() -> Path:
    """Find the git repository root."""
    try:
        result = subprocess.run(
            ['git', 'rev-parse', '--show-toplevel'],
            capture_output=True, text=True, check=True
        )
        return Path(result.stdout.strip())
    except subprocess.CalledProcessError:
        return None
    except FileNotFoundError:
        return None


def get_remote_url(remote_name: str) -> str:
    """Get the URL for a git remote."""
    try:
        result = subprocess.run(
            ['git', 'remote', 'get-url', remote_name],
            capture_output=True, text=True, check=True
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        return None
    except FileNotFoundError:
        return None


def check_remote_exists(remote_name: str) -> bool:
    """Check if a git remote exists."""
    try:
        result = subprocess.run(
            ['git', 'remote'],
            capture_output=True, text=True, check=True
        )
        remotes = result.stdout.strip().split('\n')
        return remote_name in remotes
    except subprocess.CalledProcessError:
        return False
    except FileNotFoundError:
        return False


def fetch_remote(remote_name: str) -> tuple[bool, str]:
    """Fetch from remote. Returns (success, error_message)."""
    try:
        result = subprocess.run(
            ['git', 'fetch', remote_name],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0:
            return True, None
        return False, result.stderr.strip()
    except subprocess.TimeoutExpired:
        return False, 'Network timeout'
    except subprocess.CalledProcessError as e:
        return False, str(e)
    except FileNotFoundError:
        return False, 'git not found'


def get_subtree_status(repo_root: Path, local_path: str, remote_branch: str, network_ok: bool) -> dict:
    """
    Get the status of a subtree.

    Returns dict with:
      - installed: bool
      - ahead: int or None (commits ahead of remote)
      - behind: int or None (commits behind remote)
      - status_text: str (human-readable status)
    """
    full_path = repo_root / local_path.replace('/', '\\')

    if not full_path.exists():
        return {
            'installed': False,
            'ahead': None,
            'behind': None,
            'status_text': 'NOT INSTALLED'
        }

    if not network_ok:
        return {
            'installed': True,
            'ahead': None,
            'behind': None,
            'status_text': 'installed (remote status unknown)'
        }

    # Get the latest commit affecting this subtree path
    try:
        # Get the tree hash for the local subtree content
        result = subprocess.run(
            ['git', 'log', '-1', '--format=%H', '--', local_path],
            capture_output=True, text=True, check=True,
            cwd=str(repo_root)
        )
        local_commit = result.stdout.strip()

        if not local_commit:
            return {
                'installed': True,
                'ahead': None,
                'behind': None,
                'status_text': 'installed (no commits found)'
            }

        # Get the latest commit on the remote branch
        result = subprocess.run(
            ['git', 'rev-parse', f'{REMOTE_NAME}/{remote_branch}'],
            capture_output=True, text=True,
            cwd=str(repo_root)
        )

        if result.returncode != 0:
            return {
                'installed': True,
                'ahead': None,
                'behind': None,
                'status_text': f'installed (branch {remote_branch} not found)'
            }

        remote_commit = result.stdout.strip()

        # Count commits ahead (local commits not in remote)
        result = subprocess.run(
            ['git', 'rev-list', '--count', f'{REMOTE_NAME}/{remote_branch}..HEAD', '--', local_path],
            capture_output=True, text=True,
            cwd=str(repo_root)
        )
        ahead = int(result.stdout.strip()) if result.returncode == 0 and result.stdout.strip() else 0

        # Count commits behind (remote commits not in local)
        # This is trickier with subtrees - we compare the remote branch tip to when we last merged
        result = subprocess.run(
            ['git', 'log', '-1', '--format=%H', f'{REMOTE_NAME}/{remote_branch}'],
            capture_output=True, text=True,
            cwd=str(repo_root)
        )

        if result.returncode == 0:
            remote_tip = result.stdout.strip()
            # Check if remote tip is ancestor of HEAD
            result = subprocess.run(
                ['git', 'merge-base', '--is-ancestor', remote_tip, 'HEAD'],
                capture_output=True, text=True,
                cwd=str(repo_root)
            )
            if result.returncode == 0:
                behind = 0
            else:
                # Count how many commits on remote since our merge base
                result = subprocess.run(
                    ['git', 'rev-list', '--count', f'HEAD..{REMOTE_NAME}/{remote_branch}'],
                    capture_output=True, text=True,
                    cwd=str(repo_root)
                )
                behind = int(result.stdout.strip()) if result.returncode == 0 and result.stdout.strip() else 0
        else:
            behind = 0

        # Generate status text
        if ahead == 0 and behind == 0:
            status_text = 'up to date'
        elif ahead > 0 and behind == 0:
            status_text = f'{ahead} commit{"s" if ahead != 1 else ""} ahead'
        elif ahead == 0 and behind > 0:
            status_text = f'{behind} commit{"s" if behind != 1 else ""} behind'
        else:
            status_text = f'{ahead} ahead, {behind} behind'

        return {
            'installed': True,
            'ahead': ahead,
            'behind': behind,
            'status_text': status_text
        }

    except subprocess.CalledProcessError:
        return {
            'installed': True,
            'ahead': None,
            'behind': None,
            'status_text': 'installed (status check failed)'
        }
    except Exception as e:
        return {
            'installed': True,
            'ahead': None,
            'behind': None,
            'status_text': f'installed (error: {e})'
        }


def get_database_status(repo_root: Path) -> dict:
    """
    Get the status of the story-tree database.

    Returns dict with:
      - exists: bool
      - story_count: int or None
      - path: str
      - status_text: str
    """
    # Check both standard and legacy locations
    standard_path = repo_root / '.storytree' / 'data' / 'story-tree.db'
    legacy_path = repo_root / '.claude' / 'data' / 'story-tree.db'

    db_path = None
    if standard_path.exists():
        db_path = standard_path
    elif legacy_path.exists():
        db_path = legacy_path

    if db_path is None:
        return {
            'exists': False,
            'story_count': None,
            'path': str(standard_path),
            'status_text': 'not found'
        }

    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM story_nodes')
        count = cursor.fetchone()[0]
        conn.close()

        return {
            'exists': True,
            'story_count': count,
            'path': str(db_path),
            'status_text': f'exists ({count} stories)'
        }
    except sqlite3.Error as e:
        return {
            'exists': True,
            'story_count': None,
            'path': str(db_path),
            'status_text': f'exists (error: {e})'
        }


def main() -> int:
    """Main entry point."""
    # Find repo root
    repo_root = find_repo_root()
    if repo_root is None:
        print('Error: Not in a git repository')
        print('Run this script from within a git repository.')
        return 1

    # Check if storytree remote exists
    if not check_remote_exists(REMOTE_NAME):
        print(f'Error: Remote "{REMOTE_NAME}" not found')
        print()
        print('To set up StoryTree, run:')
        print('  python .storytree/scripts/setup.py')
        print()
        print('Or manually add the remote:')
        print(f'  git remote add {REMOTE_NAME} https://github.com/Mharbulous/StoryTree.git')
        return 1

    # Get remote URL
    remote_url = get_remote_url(REMOTE_NAME)

    # Try to fetch from remote
    print('Fetching from remote...')
    network_ok, fetch_error = fetch_remote(REMOTE_NAME)

    # Print header
    print()
    print('StoryTree Status')
    print('================')
    print(f'Remote: {REMOTE_NAME} -> {remote_url}')

    if not network_ok:
        print(f'Warning: Could not fetch from remote ({fetch_error})')
        print('         Showing local status only.')

    print()

    # Print subtree status
    print('Subtrees:')
    max_path_len = max(len(p) for p in SUBTREES.keys())

    for local_path, remote_branch in SUBTREES.items():
        status = get_subtree_status(repo_root, local_path, remote_branch, network_ok)

        # Format the line
        path_padded = local_path.ljust(max_path_len)

        if status['installed']:
            print(f'  {path_padded}  [OK] installed, {status["status_text"]}')
        else:
            print(f'  {path_padded}  [X] NOT INSTALLED')

    print()

    # Print database status
    print('Data:')
    db_status = get_database_status(repo_root)

    # Use relative path for display
    try:
        display_path = Path(db_status['path']).relative_to(repo_root)
    except ValueError:
        display_path = db_status['path']

    if db_status['exists']:
        symbol = '[OK]'
    else:
        symbol = '[X]'

    print(f'  {display_path}  {symbol} {db_status["status_text"]}')

    return 0


if __name__ == '__main__':
    sys.exit(main())
