#!/usr/bin/env python3
"""
StoryTree Sync Script

Automates bi-directional sync between consuming repo and StoryTree:
1. Push local changes TO StoryTree (primary direction)
2. Pull any StoryTree-only changes back (secondary)

This order is intentional: the consuming repo (e.g., SyncoPaid) is typically
the working version where improvements are made first.

Usage:
  python sync_storytree.py              # Push then pull (auto-stashes uncommitted changes)
  python sync_storytree.py --dry-run    # Show what would happen
  python sync_storytree.py --parallel   # Push all 5 subtrees simultaneously
  python sync_storytree.py --pull-only  # Skip push, just pull
  python sync_storytree.py --push-only  # Skip pull, just push
  python sync_storytree.py --no-stash   # Fail if uncommitted changes exist
  python sync_storytree.py --strategy local   # On pull conflicts, keep local
  python sync_storytree.py --strategy remote  # On pull conflicts, take remote
"""

import argparse
import subprocess
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).parent


def run_git(*args) -> tuple[bool, str, str]:
    """Run git command, return (success, stdout, stderr)."""
    result = subprocess.run(
        ["git"] + list(args),
        capture_output=True,
        text=True,
    )
    return result.returncode == 0, result.stdout.strip(), result.stderr.strip()


def has_uncommitted_changes() -> bool:
    """Check if working tree has uncommitted changes."""
    success, output, _ = run_git('status', '--porcelain')
    return bool(output.strip())


def stash_changes() -> tuple[bool, str]:
    """
    Stash uncommitted changes.
    Returns (stashed_something, message).
    """
    success, output, stderr = run_git('stash', 'push', '-m', 'sync_storytree auto-stash')
    if not success:
        return False, f"stash failed: {stderr[:60]}"
    if 'No local changes' in output:
        return False, "nothing to stash"
    return True, "changes stashed"


def pop_stash() -> tuple[bool, str]:
    """
    Restore stashed changes.
    Returns (success, message).
    """
    success, output, stderr = run_git('stash', 'pop')
    if not success:
        return False, f"stash pop failed: {stderr[:60]}"
    return True, "stash restored"


def run_script(script_name: str, args: list[str], description: str) -> tuple[bool, str]:
    """
    Run a sibling script with arguments.

    Returns (success, output).
    """
    script_path = SCRIPT_DIR / script_name

    if not script_path.exists():
        return False, f"Script not found: {script_path}"

    cmd = [sys.executable, str(script_path)] + args

    print(f"\n{'='*60}", flush=True)
    print(f"  {description}", flush=True)
    print(f"  Command: python {script_name} {' '.join(args)}", flush=True)
    print(f"{'='*60}\n", flush=True)

    result = subprocess.run(cmd)

    return result.returncode == 0, ""


def main():
    parser = argparse.ArgumentParser(
        description="Sync with StoryTree: push first, then pull",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Order of operations:
  1. PUSH: Send local changes to StoryTree
  2. PULL: Get any StoryTree-only changes

This order assumes the consuming repo is the primary working copy.
If push is rejected due to divergence, use --retry-push to auto-recover.
        """
    )
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would happen without making changes")
    parser.add_argument("--push-only", action="store_true",
                        help="Only push, skip pull")
    parser.add_argument("--pull-only", action="store_true",
                        help="Only pull, skip push")
    parser.add_argument("--retry-push", action="store_true",
                        help="If push rejected, auto-pull diverged changes then retry")
    parser.add_argument("--strategy", choices=["abort", "local", "remote"], default="local",
                        help="Pull conflict resolution: abort, local (default), remote")
    parser.add_argument("--no-stash", action="store_true",
                        help="Don't auto-stash; fail if uncommitted changes exist")
    parser.add_argument("--force-pull", action="store_true",
                        help="Force pull even if change detection says up-to-date")
    parser.add_argument("--parallel", action="store_true",
                        help="Push subtrees in parallel (faster)")
    args = parser.parse_args()

    if args.push_only and args.pull_only:
        print("Error: Cannot use both --push-only and --pull-only")
        sys.exit(1)

    print("StoryTree Sync", flush=True)
    print("==============", flush=True)
    print(f"Direction: {'Push then Pull' if not (args.push_only or args.pull_only) else ('Push only' if args.push_only else 'Pull only')}", flush=True)
    print(f"Mode: {'Dry run' if args.dry_run else 'Live'}", flush=True)
    if not args.push_only:
        print(f"Pull conflict strategy: {args.strategy}", flush=True)

    # Handle uncommitted changes
    stashed = False
    if has_uncommitted_changes():
        if args.no_stash:
            print("\nError: Uncommitted changes detected.", flush=True)
            print("Commit your changes first, or run without --no-stash to auto-stash.", flush=True)
            sys.exit(1)
        elif not args.dry_run:
            print("\nStashing uncommitted changes...", flush=True)
            stashed, stash_msg = stash_changes()
            if stashed:
                print(f"  {stash_msg}", flush=True)
            else:
                print(f"  Warning: {stash_msg}", flush=True)

    success = True

    # Step 1: Push (unless --pull-only)
    if not args.pull_only:
        push_args = []
        if args.dry_run:
            push_args.append("--dry-run")
        if args.retry_push:
            push_args.append("--retry")
            push_args.extend(["--strategy", args.strategy])
        if args.parallel:
            push_args.append("--parallel")

        push_success, _ = run_script(
            "push_fast.py",
            push_args,
            "Step 1: Push local changes to StoryTree"
        )

        if not push_success:
            print("\n" + "!"*60)
            print("  Push failed!")
            if not args.retry_push:
                print("  If rejected due to divergence, try: sync.py --retry-push")
            print("!"*60)
            success = False

            if not args.dry_run:
                # Restore stash before aborting
                if stashed:
                    print("\nRestoring stashed changes...", flush=True)
                    pop_success, pop_msg = pop_stash()
                    if pop_success:
                        print(f"  {pop_msg}", flush=True)
                    else:
                        print(f"  Warning: {pop_msg}", flush=True)
                        print("  Your changes are still in the stash. Run: git stash pop", flush=True)
                # Don't proceed to pull if push failed (unless dry-run)
                print("\nAborting sync. Fix push issues before pulling.")
                sys.exit(1)

    # Step 2: Pull (unless --push-only)
    if not args.push_only:
        pull_args = []
        if args.dry_run:
            pull_args.append("--dry-run")
        if args.force_pull or True:  # Always force due to broken detection
            pull_args.append("--force")
        pull_args.extend(["--strategy", args.strategy])

        pull_success, _ = run_script(
            "pull_fast.py",
            pull_args,
            "Step 2: Pull StoryTree changes (if any)"
        )

        if not pull_success:
            print("\n" + "!"*60)
            print("  Pull failed!")
            print(f"  Conflict strategy was: {args.strategy}")
            if args.strategy == "abort":
                print("  Try: sync.py --strategy local  (keep your changes)")
                print("  Or:  sync.py --strategy remote (take StoryTree's)")
            print("!"*60)
            success = False

    # Restore stashed changes
    if stashed:
        print("\nRestoring stashed changes...", flush=True)
        pop_success, pop_msg = pop_stash()
        if pop_success:
            print(f"  {pop_msg}", flush=True)
        else:
            print(f"  Warning: {pop_msg}", flush=True)
            print("  Your changes are still in the stash. Run: git stash pop", flush=True)

    # Summary
    print("\n" + "="*60)
    if args.dry_run:
        print("  Dry run complete. No changes made.")
    elif success:
        print("  Sync complete!")
    else:
        print("  Sync completed with errors. Review output above.")
    print("="*60)

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
