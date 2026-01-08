#!/usr/bin/env python3
"""
Fast StoryTree Push Script

Optimized version that:
1. Checks if subtree has changes before doing expensive split
2. Uses --rejoin to create markers for faster future splits
3. Skips subtrees with no local changes
4. Supports automatic recovery from rejected pushes

Usage:
  python push_fast.py              # Push all subtrees with changes
  python push_fast.py --dry-run    # Show what would be pushed
  python push_fast.py --force      # Skip change detection, push all
  python push_fast.py --retry      # Auto-recover from rejections by pulling first
  python push_fast.py --strategy local   # If --retry conflicts, keep local
  python push_fast.py --stash      # Stash uncommitted changes first
"""

import argparse
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from enum import Enum
from pathlib import Path


class ResolveMode(Enum):
    """Conflict resolution strategy for pull during recovery."""
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


def has_local_changes(prefix, branch):
    """
    Quick check: does local subtree have commits not on remote?

    Uses git log to check if any commits touch the prefix since
    the remote branch, without doing a full subtree split.
    """
    # Fetch the remote branch first
    run_git("fetch", REMOTE_NAME, branch)

    # Check if we have any commits touching this prefix that aren't on remote
    # This is MUCH faster than subtree split
    success, stdout, _ = run_git(
        "log", "--oneline", f"{REMOTE_NAME}/{branch}..HEAD", "--", prefix
    )

    if not success:
        # Remote branch might not exist yet, assume we have changes
        return True, "remote branch not found"

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


def is_merge_in_progress():
    """Check if a merge is currently in progress."""
    success, output, _ = run_git('rev-parse', '--verify', 'MERGE_HEAD')
    return success


def has_uncommitted_in_prefix(prefix):
    """Check if there are uncommitted changes within a subtree prefix."""
    success, output, _ = run_git('status', '--porcelain', '--', prefix)
    return bool(output.strip())


def stash_changes():
    """Stash uncommitted changes, return True if anything stashed."""
    success, output, _ = run_git('stash', 'push', '-m', 'push_fast auto-stash')
    return 'No local changes' not in output


def pop_stash():
    """Restore stashed changes. Returns (success, message)."""
    success, output, stderr = run_git('stash', 'pop')
    if not success:
        return False, stderr[:60] if stderr else 'stash pop failed'
    return True, 'stash restored'


def resolve_conflicts(mode: ResolveMode):
    """
    Resolve merge conflicts using specified strategy.

    Returns (success, message).
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


def recover_rejected_push(prefix, branch, resolve_mode=ResolveMode.ABORT):
    """
    Attempt to recover from a rejected push by pulling first then retrying.

    Args:
        prefix: Subtree prefix path
        branch: Remote branch name
        resolve_mode: How to handle conflicts during pull

    Returns (success, message).
    """
    # Check for uncommitted changes in the prefix
    if has_uncommitted_in_prefix(prefix):
        return False, "uncommitted changes in prefix"

    # Pull from remote with squash to merge diverged changes
    result = subprocess.run(
        ["git", "subtree", "pull", f"--prefix={prefix}", REMOTE_NAME, branch, "--squash"],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        # Check for conflicts
        conflicts = get_conflicted_files()
        if conflicts:
            resolved, resolve_msg = resolve_conflicts(resolve_mode)
            if not resolved:
                return False, f"pull conflicts: {resolve_msg}"
        else:
            return False, f"pull failed: {result.stderr[:60]}"

    return True, "recovered (pulled diverged changes)"


def push_subtree_fast(prefix, branch, dry_run=False, use_rejoin=True, retry_on_reject=False, resolve_mode=ResolveMode.ABORT):
    """
    Push subtree with optimizations.

    Returns (success, message).
    """
    repo_root = find_repo_root()
    subtree_path = repo_root / prefix.replace("/", "\\")

    if not subtree_path.exists():
        return True, "skipped (not found)"

    if dry_run:
        has_changes, reason = has_local_changes(prefix, branch)
        if has_changes:
            return True, f"would push ({reason})"
        return True, "up to date"

    # Build the push command
    # Using --rejoin creates a marker commit for faster future splits
    cmd = ["git", "subtree", "push", f"--prefix={prefix}", REMOTE_NAME, branch]
    if use_rejoin:
        cmd.append("--rejoin")

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode == 0:
        if "up-to-date" in (result.stdout + result.stderr).lower():
            return True, "OK (up to date)"
        return True, "OK (pushed)"
    else:
        stderr = result.stderr.strip()
        if "rejected" in stderr.lower():
            if retry_on_reject:
                # Attempt recovery: pull diverged changes then retry push
                recovered, recover_msg = recover_rejected_push(prefix, branch, resolve_mode)
                if recovered:
                    # Retry the push
                    result = subprocess.run(cmd, capture_output=True, text=True)
                    if result.returncode == 0:
                        return True, "OK (recovered and pushed)"
                    return False, f"push failed after recovery: {result.stderr[:40]}"
                return False, f"rejected ({recover_msg})"
            return False, "rejected (diverged) - use --retry to auto-recover"
        return False, stderr[:80] if stderr else "unknown error"


def push_single_subtree(prefix, branch, dry_run=False, retry_on_reject=False, resolve_mode=ResolveMode.ABORT, use_stash=False):
    """
    Push a single subtree - useful for testing one at a time.
    """
    print(f"Checking {prefix}...")
    has_changes, reason = has_local_changes(prefix, branch)

    if not has_changes:
        print(f"  No changes to push ({reason})")
        return True

    print(f"  Found changes: {reason}")

    if dry_run:
        print(f"  Would push to {REMOTE_NAME}/{branch}")
        return True

    # Stash uncommitted changes if requested
    stashed = False
    if use_stash and has_uncommitted_changes():
        print("  Stashing uncommitted changes...")
        stashed = stash_changes()

    print(f"  Pushing to {REMOTE_NAME}/{branch}...")
    print(f"  (This may take a while on first push - creates rejoin marker)")

    success, message = push_subtree_fast(
        prefix, branch, dry_run=False,
        retry_on_reject=retry_on_reject, resolve_mode=resolve_mode
    )
    print(f"  {message}")

    # Restore stashed changes
    if stashed:
        print("  Restoring stashed changes...")
        pop_success, pop_msg = pop_stash()
        if not pop_success:
            print(f"  Warning: {pop_msg}")

    return success


def main():
    parser = argparse.ArgumentParser(description="Fast StoryTree push with change detection")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be pushed")
    parser.add_argument("--force", action="store_true", help="Skip change detection")
    parser.add_argument("--subtree", help="Push only this subtree (e.g., '.storytree/gui')")
    parser.add_argument("--retry", action="store_true",
                        help="On rejection, pull diverged changes then retry push")
    parser.add_argument("--strategy", choices=["abort", "local", "remote"], default="abort",
                        help="If --retry causes conflicts: abort (default), local, remote")
    parser.add_argument("--stash", action="store_true",
                        help="Stash uncommitted changes before push, restore after")
    parser.add_argument("--parallel", action="store_true",
                        help="Push subtrees in parallel (faster)")
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
        sys.exit(1)

    # Single subtree mode
    if args.subtree:
        for prefix, branch in SUBTREES:
            if prefix == args.subtree or args.subtree in prefix:
                success = push_single_subtree(
                    prefix, branch, args.dry_run,
                    retry_on_reject=args.retry, resolve_mode=resolve_mode, use_stash=args.stash
                )
                sys.exit(0 if success else 1)
        print(f"Error: Subtree '{args.subtree}' not found")
        print("Available:", [p for p, _ in SUBTREES])
        sys.exit(1)

    # Full push mode
    print("Checking for changes..." if not args.force else "Pushing all subtrees...")

    to_push = []
    for prefix, branch in SUBTREES:
        if args.force:
            to_push.append((prefix, branch, "forced"))
        else:
            has_changes, reason = has_local_changes(prefix, branch)
            if has_changes:
                to_push.append((prefix, branch, reason))
                print(f"  {prefix}: {reason}")
            else:
                print(f"  {prefix}: up to date")

    if not to_push:
        print("\nAll subtrees up to date!")
        sys.exit(0)

    print(f"\n{len(to_push)} subtree(s) have changes")

    if args.dry_run:
        print("\nDry run - would push:")
        for prefix, branch, reason in to_push:
            print(f"  {prefix} -> {branch} ({reason})")
        sys.exit(0)

    # Stash uncommitted changes if requested
    stashed = False
    if args.stash and has_uncommitted_changes():
        print("\nStashing uncommitted changes...")
        stashed = stash_changes()

    print("\nPushing...")
    failures = []

    if args.parallel:
        print("  (parallel mode)")

        def push_one(item):
            prefix, branch, reason = item
            success, message = push_subtree_fast(
                prefix, branch,
                use_rejoin=True,
                retry_on_reject=args.retry, resolve_mode=resolve_mode
            )
            return prefix, success, message

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = {executor.submit(push_one, item): item for item in to_push}
            for future in as_completed(futures):
                prefix, success, message = future.result()
                print(f"  {prefix}... {message}")
                if not success:
                    failures.append((prefix, message))
    else:
        for prefix, branch, reason in to_push:
            print(f"  {prefix}...", end=" ", flush=True)
            success, message = push_subtree_fast(
                prefix, branch,
                retry_on_reject=args.retry, resolve_mode=resolve_mode
            )
            print(message)
            if not success:
                failures.append((prefix, message))

    # Restore stashed changes
    if stashed:
        print("\nRestoring stashed changes...")
        pop_success, pop_msg = pop_stash()
        if not pop_success:
            print(f"Warning: {pop_msg}")

    if failures:
        print(f"\n{len(failures)} failure(s)")
        sys.exit(1)

    print("\nPush complete!")


if __name__ == "__main__":
    main()
