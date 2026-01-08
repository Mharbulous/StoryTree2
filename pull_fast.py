#!/usr/bin/env python3
"""
Fast StoryTree Pull Script

Optimized version that:
1. Checks if remote has changes before doing expensive pull
2. Skips subtrees with no incoming changes
3. Uses --squash for cleaner history
4. Supports automatic conflict resolution

Usage:
  python pull_fast.py              # Pull all subtrees with changes
  python pull_fast.py --dry-run    # Show what would be pulled
  python pull_fast.py --force      # Skip change detection, pull all
  python pull_fast.py --subtree .storytree/gui  # Pull single subtree
  python pull_fast.py --strategy local   # Keep local on conflicts
  python pull_fast.py --strategy remote  # Accept remote on conflicts
  python pull_fast.py --stash      # Stash uncommitted changes first
"""

import argparse
import subprocess
import sys
from enum import Enum
from pathlib import Path


class ResolveMode(Enum):
    """Conflict resolution strategy."""
    ABORT = "abort"   # Abort merge, let user resolve manually (default)
    LOCAL = "local"   # Prefer local changes (--ours)
    REMOTE = "remote" # Prefer remote changes (--theirs)


# Subtree configuration: (prefix, branch)
SUBTREES = [
    (".claude/skills/storytree", "dist-skills"),
    (".claude/commands/storytree", "dist-commands"),
    (".claude/scripts/storytree", "dist-scripts"),
    (".github/actions/storytree", "dist-actions"),
    (".storytree/gui", "dist-gui"),
]

REMOTE_NAME = "storytree"


def run_git(*args, check=False):
    """Run git command, return (success, stdout, stderr)."""
    result = subprocess.run(
        ["git"] + list(args),
        capture_output=True,
        text=True,
    )
    if check and result.returncode != 0:
        raise subprocess.CalledProcessError(result.returncode, args, result.stdout, result.stderr)
    return result.returncode == 0, result.stdout.strip(), result.stderr.strip()


def find_repo_root():
    """Find git repo root."""
    success, stdout, _ = run_git("rev-parse", "--show-toplevel")
    return Path(stdout) if success else None


def has_remote_changes(prefix, branch):
    """
    Quick check: does remote branch have commits not in local?

    Uses git log to check if any commits touch the prefix since
    our HEAD, without doing a full subtree pull.
    """
    # Fetch the remote branch first
    run_git("fetch", REMOTE_NAME, branch)

    # Check if remote has any commits touching this prefix that aren't in local
    # This is MUCH faster than doing a full subtree pull
    success, stdout, _ = run_git(
        "log", "--oneline", f"HEAD..{REMOTE_NAME}/{branch}", "--", prefix
    )

    if not success:
        # Remote branch might not exist, assume no changes
        return False, "remote branch not found"

    if stdout:
        lines = [l for l in stdout.split('\n') if l.strip()]
        return True, f"{len(lines)} commit(s)"

    return False, "up to date"


def get_conflicted_files():
    """Get list of files with merge conflicts."""
    success, output, _ = run_git('diff', '--name-only', '--diff-filter=U')
    if success and output:
        return output.split('\n')
    return []


def abort_merge():
    """Abort an in-progress merge."""
    run_git('merge', '--abort')


def has_uncommitted_changes():
    """Check if working tree has uncommitted changes."""
    success, output, _ = run_git('status', '--porcelain')
    return bool(output.strip())


def is_operation_in_progress():
    """
    Check if a git operation (rebase, cherry-pick, merge) is in progress.
    Returns (in_progress, operation_name) tuple.
    """
    repo_root = find_repo_root()
    if not repo_root:
        return False, None

    git_dir = repo_root / '.git'

    # Check for rebase
    if (git_dir / 'rebase-merge').exists() or (git_dir / 'rebase-apply').exists():
        return True, 'rebase'

    # Check for cherry-pick
    if (git_dir / 'CHERRY_PICK_HEAD').exists():
        return True, 'cherry-pick'

    # Check for merge
    if (git_dir / 'MERGE_HEAD').exists():
        return True, 'merge'

    return False, None


def stash_changes():
    """Stash uncommitted changes, return True if anything stashed."""
    success, output, _ = run_git('stash', 'push', '-m', 'pull_fast auto-stash')
    return 'No local changes' not in output


def pop_stash():
    """Restore stashed changes. Returns (success, message)."""
    success, output, stderr = run_git('stash', 'pop')
    if not success:
        return False, stderr[:60] if stderr else 'stash pop failed'
    return True, 'stash restored'


def is_merge_in_progress():
    """Check if a merge is currently in progress."""
    success, output, _ = run_git('rev-parse', '--verify', 'MERGE_HEAD')
    return success


def resolve_conflicts(mode: ResolveMode):
    """
    Resolve merge conflicts using specified strategy.

    Args:
        mode: ResolveMode enum value

    Returns:
        (success, message)
    """
    if mode == ResolveMode.ABORT:
        if is_merge_in_progress():
            abort_merge()
        return False, 'aborted'

    conflicts = get_conflicted_files()
    if not conflicts:
        return True, 'no conflicts'

    checkout_flag = '--ours' if mode == ResolveMode.LOCAL else '--theirs'

    for file in conflicts:
        success, _, stderr = run_git('checkout', checkout_flag, '--', file)
        if not success:
            # Abort to avoid partial state
            if is_merge_in_progress():
                abort_merge()
            return False, f'checkout failed: {file}'

        success, _, stderr = run_git('add', file)
        if not success:
            if is_merge_in_progress():
                abort_merge()
            return False, f'add failed: {file}'

    # Complete the merge
    success, _, stderr = run_git('commit', '--no-edit')
    if not success:
        return False, f'commit failed: {stderr[:40]}'

    return True, f'resolved ({mode.value})'


def pull_subtree_fast(prefix, branch, dry_run=False, resolve_mode=ResolveMode.ABORT):
    """
    Pull subtree with optimizations.

    Args:
        prefix: Subtree prefix path
        branch: Remote branch name
        dry_run: If True, only show what would be pulled
        resolve_mode: How to handle conflicts (ABORT, LOCAL, REMOTE)

    Returns (success, message, conflicts).
    """
    repo_root = find_repo_root()
    subtree_path = repo_root / prefix.replace("/", "\\")

    if not subtree_path.exists():
        return True, "skipped (not found)", []

    if dry_run:
        has_changes, reason = has_remote_changes(prefix, branch)
        if has_changes:
            return True, f"would pull ({reason})", []
        return True, "up to date", []

    # Run subtree pull with squash
    result = subprocess.run(
        ["git", "subtree", "pull", f"--prefix={prefix}", REMOTE_NAME, branch, "--squash"],
        capture_output=True,
        text=True,
    )

    stdout = result.stdout.strip()
    stderr = result.stderr.strip()
    combined = f"{stdout}\n{stderr}"

    if result.returncode == 0:
        if "up to date" in combined.lower() or "up-to-date" in combined.lower():
            return True, "OK (up to date)", []
        return True, "OK (pulled)", []

    # Check for merge conflicts
    conflicts = get_conflicted_files()
    if conflicts:
        success, message = resolve_conflicts(resolve_mode)
        if success:
            return True, f"OK ({message})", []
        return False, message.upper(), conflicts

    # Other error
    error_msg = stderr if stderr else "unknown error"
    return False, error_msg[:80], []


def pull_single_subtree(prefix, branch, dry_run=False, resolve_mode=ResolveMode.ABORT, use_stash=False):
    """
    Pull a single subtree - useful for testing one at a time.
    """
    print(f"Checking {prefix}...")
    has_changes, reason = has_remote_changes(prefix, branch)

    if not has_changes:
        print(f"  No changes to pull ({reason})")
        return True

    print(f"  Found changes: {reason}")

    if dry_run:
        print(f"  Would pull from {REMOTE_NAME}/{branch}")
        return True

    # Stash uncommitted changes if requested
    stashed = False
    if use_stash and has_uncommitted_changes():
        print("  Stashing uncommitted changes...")
        stashed = stash_changes()

    print(f"  Pulling from {REMOTE_NAME}/{branch}...")

    success, message, conflicts = pull_subtree_fast(prefix, branch, dry_run=False, resolve_mode=resolve_mode)
    print(f"  {message}")

    if conflicts:
        print("  Conflicted files:")
        for f in conflicts:
            print(f"    - {f}")

    # Restore stashed changes
    if stashed:
        print("  Restoring stashed changes...")
        pop_success, pop_msg = pop_stash()
        if not pop_success:
            print(f"  Warning: {pop_msg}")

    return success


def main():
    parser = argparse.ArgumentParser(description="Fast StoryTree pull with change detection")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be pulled")
    parser.add_argument("--force", action="store_true", help="Skip change detection")
    parser.add_argument("--subtree", help="Pull only this subtree (e.g., '.storytree/gui')")
    parser.add_argument("--strategy", choices=["abort", "local", "remote"], default="abort",
                        help="Conflict resolution: abort (default), local (keep ours), remote (take theirs)")
    parser.add_argument("--stash", action="store_true",
                        help="Stash uncommitted changes before pull, restore after")
    args = parser.parse_args()

    # Convert strategy string to enum
    resolve_mode = ResolveMode(args.strategy)

    repo_root = find_repo_root()
    if not repo_root:
        print("Error: Not in a git repository")
        sys.exit(1)

    # Check for in-progress operations that would interfere
    in_progress, op_name = is_operation_in_progress()
    if in_progress:
        print(f"Error: A {op_name} is in progress. Complete or abort it first.")
        print(f"  To abort: git {op_name} --abort")
        sys.exit(1)

    # Check remote exists
    success, stdout, _ = run_git("remote")
    if REMOTE_NAME not in stdout.split('\n'):
        print(f"Error: Remote '{REMOTE_NAME}' not found")
        print("")
        print("Hint: Run setup.py first to add the storytree remote:")
        print("  python .claude/scripts/storytree/setup.py")
        sys.exit(1)

    # Check network connectivity
    success, _, stderr = run_git("ls-remote", "--exit-code", REMOTE_NAME, "HEAD")
    if not success:
        if "Could not resolve host" in stderr or "unable to access" in stderr.lower():
            print("Error: Network unreachable. Cannot connect to storytree remote.")
        else:
            print(f"Error: Cannot reach remote {REMOTE_NAME}.")
            if stderr:
                print(f"  {stderr}")
        sys.exit(1)

    # Single subtree mode
    if args.subtree:
        for prefix, branch in SUBTREES:
            if prefix == args.subtree or args.subtree in prefix:
                success = pull_single_subtree(
                    prefix, branch, args.dry_run,
                    resolve_mode=resolve_mode, use_stash=args.stash
                )
                sys.exit(0 if success else 1)
        print(f"Error: Subtree '{args.subtree}' not found")
        print("Available:", [p for p, _ in SUBTREES])
        sys.exit(1)

    # Full pull mode
    print("Checking for updates..." if not args.force else "Pulling all subtrees...")

    to_pull = []
    for prefix, branch in SUBTREES:
        if args.force:
            to_pull.append((prefix, branch, "forced"))
        else:
            has_changes, reason = has_remote_changes(prefix, branch)
            if has_changes:
                to_pull.append((prefix, branch, reason))
                print(f"  {prefix}: {reason}")
            else:
                print(f"  {prefix}: up to date")

    if not to_pull:
        print("\nAll subtrees up to date!")
        sys.exit(0)

    print(f"\n{len(to_pull)} subtree(s) have updates")

    if args.dry_run:
        print("\nDry run - would pull:")
        for prefix, branch, reason in to_pull:
            print(f"  {prefix} <- {branch} ({reason})")
        sys.exit(0)

    # Stash uncommitted changes if requested
    stashed = False
    if args.stash and has_uncommitted_changes():
        print("\nStashing uncommitted changes...")
        stashed = stash_changes()

    print("\nPulling...")
    failures = []
    all_conflicts = {}

    for prefix, branch, reason in to_pull:
        print(f"  {prefix}...", end=" ", flush=True)
        success, message, conflicts = pull_subtree_fast(prefix, branch, resolve_mode=resolve_mode)
        print(message)

        if not success:
            failures.append((prefix, message))
            if conflicts:
                all_conflicts[prefix] = conflicts

    # Report conflicts
    if all_conflicts:
        print("")
        for prefix, files in all_conflicts.items():
            print(f"Conflicts in {prefix}:")
            for f in files:
                print(f"  - {f}")
        print("")
        print("Resolve conflicts, then: git add -A && git commit")

    # Restore stashed changes
    if stashed:
        print("\nRestoring stashed changes...")
        pop_success, pop_msg = pop_stash()
        if not pop_success:
            print(f"Warning: {pop_msg}")

    if failures:
        print(f"\n{len(failures)} failure(s)")
        sys.exit(1)

    print("\nPull complete!")


if __name__ == "__main__":
    main()
