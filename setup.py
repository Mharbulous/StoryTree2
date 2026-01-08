#!/usr/bin/env python3
"""
StoryTree Setup Script

Non-interactive script to set up StoryTree in a consuming repository.
Adds git subtrees for StoryTree components and initializes the database.

Usage:
    python setup.py           # Run setup
    python setup.py --dry-run # Show what would happen without executing
"""

import argparse
import os
import subprocess
import sys
import urllib.request
import urllib.error
from pathlib import Path


# Configuration
STORYTREE_REMOTE_URL = "https://github.com/Mharbulous/StoryTree2.git"
STORYTREE_REMOTE_NAME = "storytree"
DB_TEMPLATE_URL = "https://raw.githubusercontent.com/Mharbulous/StoryTree2/main/templates/story-tree.db.empty"

# Subtree mappings: (local_path, remote_branch)
SUBTREES = [
    (".claude/skills/storytree", "dist-skills"),
    (".claude/commands/storytree", "dist-commands"),
    (".claude/scripts/storytree", "dist-scripts"),
    (".github/actions/storytree", "dist-actions"),
    (".storytree/gui", "dist-gui"),
]


class SetupError(Exception):
    """Custom exception for setup errors."""
    pass


def run_command(cmd: list[str], capture: bool = True, check: bool = True) -> subprocess.CompletedProcess:
    """Run a shell command and return the result."""
    try:
        result = subprocess.run(
            cmd,
            capture_output=capture,
            text=True,
            check=check
        )
        return result
    except subprocess.CalledProcessError as e:
        raise SetupError(f"Command failed: {' '.join(cmd)}\n{e.stderr}")
    except FileNotFoundError:
        raise SetupError(f"Command not found: {cmd[0]}")


def is_git_repo() -> bool:
    """Check if current directory is in a git repository."""
    try:
        result = run_command(["git", "rev-parse", "--git-dir"], check=False)
        return result.returncode == 0
    except SetupError:
        return False


def get_repo_root() -> Path:
    """Get the root directory of the git repository."""
    result = run_command(["git", "rev-parse", "--show-toplevel"])
    return Path(result.stdout.strip())


def get_remote_url(remote_name: str) -> str | None:
    """Get the URL of a git remote, or None if it doesn't exist."""
    result = run_command(["git", "remote", "get-url", remote_name], check=False)
    if result.returncode == 0:
        return result.stdout.strip()
    return None


def subtree_exists(prefix: str) -> bool:
    """Check if a subtree already exists at the given prefix."""
    # A subtree exists if the directory exists and has commits in git history
    # We check if the path exists and is tracked by git
    prefix_path = Path(prefix)
    if not prefix_path.exists():
        return False

    # Check if there are any commits touching this path
    result = run_command(
        ["git", "log", "--oneline", "-1", "--", prefix],
        check=False
    )
    return result.returncode == 0 and result.stdout.strip() != ""


def validate_environment(dry_run: bool) -> None:
    """Step 1: Validate environment."""
    print("[1/5] Validating environment...", end=" ", flush=True)

    if dry_run:
        print("(dry-run) Would check for git repo")
        return

    # Check git is available
    try:
        run_command(["git", "--version"])
    except SetupError:
        print("FAILED")
        raise SetupError("Git is not available. Please install git and try again.")

    # Check we're in a git repo root
    if not is_git_repo():
        print("FAILED")
        raise SetupError(
            "Not in a git repository.\n"
            "Please run this script from the root of a git repository."
        )

    # Verify we're at the repo root
    repo_root = get_repo_root()
    cwd = Path.cwd().resolve()
    if cwd != repo_root.resolve():
        print("FAILED")
        raise SetupError(
            f"Please run this script from the repository root.\n"
            f"  Current directory: {cwd}\n"
            f"  Repository root:   {repo_root}"
        )

    print("OK")


def add_remote(dry_run: bool) -> None:
    """Step 2: Add storytree remote."""
    print("[2/5] Adding storytree remote...", end=" ", flush=True)

    existing_url = get_remote_url(STORYTREE_REMOTE_NAME) if not dry_run else None

    if dry_run:
        print(f"(dry-run) Would add remote '{STORYTREE_REMOTE_NAME}' -> {STORYTREE_REMOTE_URL}")
        return

    if existing_url:
        if existing_url == STORYTREE_REMOTE_URL:
            print("SKIPPED (already exists)")
            return
        else:
            print("FAILED")
            raise SetupError(
                f"Remote '{STORYTREE_REMOTE_NAME}' already exists with a different URL.\n"
                f"  Existing URL: {existing_url}\n"
                f"  Expected URL: {STORYTREE_REMOTE_URL}\n\n"
                f"To fix, either:\n"
                f"  1. Remove the existing remote: git remote remove {STORYTREE_REMOTE_NAME}\n"
                f"  2. Or update its URL: git remote set-url {STORYTREE_REMOTE_NAME} {STORYTREE_REMOTE_URL}"
            )

    run_command(["git", "remote", "add", STORYTREE_REMOTE_NAME, STORYTREE_REMOTE_URL])
    print("OK")


def add_subtrees(dry_run: bool) -> None:
    """Step 3: Add subtrees."""
    print("[3/5] Adding subtrees...")

    if not dry_run:
        # Fetch from remote first
        print("      Fetching from storytree remote...", end=" ", flush=True)
        try:
            run_command(["git", "fetch", STORYTREE_REMOTE_NAME])
            print("OK")
        except SetupError as e:
            print("FAILED")
            raise SetupError(f"Failed to fetch from remote: {e}")

    for local_path, branch in SUBTREES:
        print(f"      {local_path}...", end=" ", flush=True)

        if dry_run:
            print(f"(dry-run) Would add subtree from {branch}")
            continue

        if subtree_exists(local_path):
            print("SKIPPED (already exists)")
            continue

        # Create parent directories if needed
        parent_dir = Path(local_path).parent
        parent_dir.mkdir(parents=True, exist_ok=True)

        try:
            run_command([
                "git", "subtree", "add",
                "--prefix", local_path,
                STORYTREE_REMOTE_NAME, branch,
                "--squash"
            ])
            print("OK")
        except SetupError as e:
            print("FAILED")
            raise SetupError(f"Failed to add subtree {local_path}: {e}")


def create_data_directory(dry_run: bool) -> None:
    """Step 4: Create data directory."""
    print("[4/5] Creating .storytree/data/...", end=" ", flush=True)

    data_dir = Path(".storytree") / "data"

    if dry_run:
        print(f"(dry-run) Would create {data_dir}")
        return

    data_dir.mkdir(parents=True, exist_ok=True)
    print("OK")


def initialize_database(dry_run: bool) -> None:
    """Step 5: Initialize database."""
    print("[5/5] Initializing database...", end=" ", flush=True)

    db_path = Path(".storytree") / "data" / "story-tree.db"

    if dry_run:
        print(f"(dry-run) Would download {DB_TEMPLATE_URL} to {db_path}")
        return

    if db_path.exists():
        print("SKIPPED (already exists)")
        return

    try:
        with urllib.request.urlopen(DB_TEMPLATE_URL, timeout=30) as response:
            db_content = response.read()

        with open(db_path, "wb") as f:
            f.write(db_content)

        print("OK")
    except urllib.error.URLError as e:
        print("FAILED")
        raise SetupError(f"Failed to download database template: {e}")
    except IOError as e:
        print("FAILED")
        raise SetupError(f"Failed to write database file: {e}")


def print_completion_message() -> None:
    """Print setup completion message with next steps."""
    print()
    print("Setup complete! Next steps:")
    print("  - Review .storytree/USAGE.md for usage instructions")
    print('  - Commit the changes: git add -A && git commit -m "chore: add StoryTree"')


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Set up StoryTree in a consuming repository."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would happen without executing"
    )
    args = parser.parse_args()

    try:
        validate_environment(args.dry_run)
        add_remote(args.dry_run)
        add_subtrees(args.dry_run)
        create_data_directory(args.dry_run)
        initialize_database(args.dry_run)
        print_completion_message()
        return 0
    except SetupError as e:
        print(f"\nError: {e}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\n\nSetup interrupted by user.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())
