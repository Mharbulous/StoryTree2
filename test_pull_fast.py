#!/usr/bin/env python3
"""
Unit tests for pull_fast.py

Tests the logic without actually pulling from remotes.
"""

import subprocess
import unittest
from unittest.mock import patch, MagicMock

# Import the module under test
import pull_fast


class TestHasRemoteChanges(unittest.TestCase):
    """Tests for the has_remote_changes function."""

    @patch('pull_fast.run_git')
    def test_detects_commits_on_remote(self, mock_run_git):
        """Should detect when remote has commits not in local."""
        # First call: fetch (succeeds)
        # Second call: git log shows 3 commits
        mock_run_git.side_effect = [
            (True, "", ""),  # fetch succeeds
            (True, "abc123 commit1\ndef456 commit2\nghi789 commit3", ""),  # 3 commits
        ]

        has_changes, reason = pull_fast.has_remote_changes(".test/prefix", "test-branch")

        self.assertTrue(has_changes)
        self.assertEqual(reason, "3 commit(s)")

    @patch('pull_fast.run_git')
    def test_detects_up_to_date(self, mock_run_git):
        """Should detect when local is up to date with remote."""
        mock_run_git.side_effect = [
            (True, "", ""),  # fetch succeeds
            (True, "", ""),  # no commits on remote not in local
        ]

        has_changes, reason = pull_fast.has_remote_changes(".test/prefix", "test-branch")

        self.assertFalse(has_changes)
        self.assertEqual(reason, "up to date")

    @patch('pull_fast.run_git')
    def test_handles_missing_remote_branch(self, mock_run_git):
        """Should report no changes when remote branch doesn't exist."""
        mock_run_git.side_effect = [
            (True, "", ""),  # fetch succeeds
            (False, "", ""),  # log fails (remote branch not found)
        ]

        has_changes, reason = pull_fast.has_remote_changes(".test/prefix", "test-branch")

        self.assertFalse(has_changes)
        self.assertEqual(reason, "remote branch not found")


class TestPullSubtreeFast(unittest.TestCase):
    """Tests for the pull_subtree_fast function."""

    @patch('pull_fast.find_repo_root')
    @patch('pull_fast.get_conflicted_files')
    @patch('pull_fast.resolve_conflicts')
    @patch('subprocess.run')
    def test_detects_conflict(self, mock_subprocess, mock_resolve, mock_conflicts, mock_find_root):
        """Should detect when pull results in conflicts and abort by default."""
        mock_find_root.return_value = MagicMock()
        mock_find_root.return_value.__truediv__ = lambda self, x: MagicMock(exists=lambda: True)
        mock_conflicts.return_value = ["file1.txt", "file2.txt"]
        mock_resolve.return_value = (False, "aborted")  # Default ABORT behavior

        # Simulate conflict
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "CONFLICT (content): Merge conflict in file1.txt"
        mock_subprocess.return_value = mock_result

        success, message, conflicts = pull_fast.pull_subtree_fast(".test/prefix", "test-branch")

        self.assertFalse(success)
        self.assertEqual(message, "ABORTED")
        self.assertEqual(conflicts, ["file1.txt", "file2.txt"])
        mock_resolve.assert_called_once_with(pull_fast.ResolveMode.ABORT)

    @patch('pull_fast.find_repo_root')
    @patch('subprocess.run')
    def test_detects_successful_pull(self, mock_subprocess, mock_find_root):
        """Should detect successful pull."""
        mock_find_root.return_value = MagicMock()
        mock_find_root.return_value.__truediv__ = lambda self, x: MagicMock(exists=lambda: True)

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "Squash commit -- not updating HEAD\nMerge made by the 'recursive' strategy."
        mock_result.stderr = ""
        mock_subprocess.return_value = mock_result

        success, message, conflicts = pull_fast.pull_subtree_fast(".test/prefix", "test-branch")

        self.assertTrue(success)
        self.assertEqual(message, "OK (pulled)")
        self.assertEqual(conflicts, [])

    @patch('pull_fast.find_repo_root')
    @patch('subprocess.run')
    def test_detects_up_to_date(self, mock_subprocess, mock_find_root):
        """Should detect when already up to date."""
        mock_find_root.return_value = MagicMock()
        mock_find_root.return_value.__truediv__ = lambda self, x: MagicMock(exists=lambda: True)

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "Already up to date."
        mock_result.stderr = ""
        mock_subprocess.return_value = mock_result

        success, message, conflicts = pull_fast.pull_subtree_fast(".test/prefix", "test-branch")

        self.assertTrue(success)
        self.assertEqual(message, "OK (up to date)")
        self.assertEqual(conflicts, [])

    @patch('pull_fast.find_repo_root')
    def test_skips_missing_directory(self, mock_find_root):
        """Should skip if subtree directory doesn't exist."""
        mock_find_root.return_value = MagicMock()
        mock_find_root.return_value.__truediv__ = lambda self, x: MagicMock(exists=lambda: False)

        success, message, conflicts = pull_fast.pull_subtree_fast(".nonexistent/prefix", "test-branch")

        self.assertTrue(success)
        self.assertEqual(message, "skipped (not found)")
        self.assertEqual(conflicts, [])

    @patch('pull_fast.find_repo_root')
    @patch('pull_fast.has_remote_changes')
    def test_dry_run_with_changes(self, mock_has_changes, mock_find_root):
        """Should report what would be pulled in dry run mode."""
        mock_find_root.return_value = MagicMock()
        mock_find_root.return_value.__truediv__ = lambda self, x: MagicMock(exists=lambda: True)
        mock_has_changes.return_value = (True, "5 commit(s)")

        success, message, conflicts = pull_fast.pull_subtree_fast(".test/prefix", "test-branch", dry_run=True)

        self.assertTrue(success)
        self.assertEqual(message, "would pull (5 commit(s))")
        self.assertEqual(conflicts, [])


class TestConflictResolution(unittest.TestCase):
    """Tests for automatic conflict resolution strategies."""

    @patch('pull_fast.run_git')
    def test_resolve_conflicts_abort(self, mock_run_git):
        """Should abort merge when strategy is ABORT."""
        mock_run_git.return_value = (True, "", "")

        success, message = pull_fast.resolve_conflicts(pull_fast.ResolveMode.ABORT)

        self.assertFalse(success)
        self.assertEqual(message, "aborted")
        mock_run_git.assert_called_with('merge', '--abort')

    @patch('pull_fast.run_git')
    @patch('pull_fast.get_conflicted_files')
    def test_resolve_conflicts_local(self, mock_conflicts, mock_run_git):
        """Should resolve conflicts using local (ours) preference."""
        mock_conflicts.return_value = ["file1.txt", "file2.txt"]
        mock_run_git.return_value = (True, "", "")

        success, message = pull_fast.resolve_conflicts(pull_fast.ResolveMode.LOCAL)

        self.assertTrue(success)
        self.assertEqual(message, "resolved (local)")
        # Should checkout --ours for each conflicted file
        calls = mock_run_git.call_args_list
        checkout_calls = [c for c in calls if c[0][0] == 'checkout']
        self.assertEqual(len(checkout_calls), 2)
        self.assertEqual(checkout_calls[0][0], ('checkout', '--ours', '--', 'file1.txt'))

    @patch('pull_fast.run_git')
    @patch('pull_fast.get_conflicted_files')
    def test_resolve_conflicts_remote(self, mock_conflicts, mock_run_git):
        """Should resolve conflicts using remote (theirs) preference."""
        mock_conflicts.return_value = ["file1.txt"]
        mock_run_git.return_value = (True, "", "")

        success, message = pull_fast.resolve_conflicts(pull_fast.ResolveMode.REMOTE)

        self.assertTrue(success)
        self.assertEqual(message, "resolved (remote)")
        calls = mock_run_git.call_args_list
        checkout_calls = [c for c in calls if c[0][0] == 'checkout']
        self.assertEqual(checkout_calls[0][0], ('checkout', '--theirs', '--', 'file1.txt'))

    @patch('pull_fast.run_git')
    @patch('pull_fast.get_conflicted_files')
    def test_resolve_conflicts_no_conflicts(self, mock_conflicts, mock_run_git):
        """Should succeed immediately if no conflicts found."""
        mock_conflicts.return_value = []

        success, message = pull_fast.resolve_conflicts(pull_fast.ResolveMode.LOCAL)

        self.assertTrue(success)
        self.assertEqual(message, "no conflicts")


class TestStashHandling(unittest.TestCase):
    """Tests for stash save/restore functionality."""

    @patch('pull_fast.run_git')
    def test_stash_changes_success(self, mock_run_git):
        """Should return True when changes are stashed."""
        mock_run_git.return_value = (True, "Saved working directory", "")

        result = pull_fast.stash_changes()

        self.assertTrue(result)

    @patch('pull_fast.run_git')
    def test_stash_changes_nothing_to_stash(self, mock_run_git):
        """Should return False when no local changes to stash."""
        mock_run_git.return_value = (True, "No local changes to save", "")

        result = pull_fast.stash_changes()

        self.assertFalse(result)

    @patch('pull_fast.run_git')
    def test_pop_stash_success(self, mock_run_git):
        """Should return success when stash pop works."""
        mock_run_git.return_value = (True, "Dropped refs/stash", "")

        success, message = pull_fast.pop_stash()

        self.assertTrue(success)
        self.assertEqual(message, "stash restored")

    @patch('pull_fast.run_git')
    def test_pop_stash_failure(self, mock_run_git):
        """Should return failure with message when stash pop fails."""
        mock_run_git.return_value = (False, "", "CONFLICT in file.txt")

        success, message = pull_fast.pop_stash()

        self.assertFalse(success)
        self.assertIn("CONFLICT", message)

    @patch('pull_fast.run_git')
    def test_has_uncommitted_changes_true(self, mock_run_git):
        """Should detect uncommitted changes."""
        mock_run_git.return_value = (True, " M file.txt\n?? new.txt", "")

        result = pull_fast.has_uncommitted_changes()

        self.assertTrue(result)

    @patch('pull_fast.run_git')
    def test_has_uncommitted_changes_false(self, mock_run_git):
        """Should detect clean working tree."""
        mock_run_git.return_value = (True, "", "")

        result = pull_fast.has_uncommitted_changes()

        self.assertFalse(result)


class TestPullWithStrategy(unittest.TestCase):
    """Tests for pull_subtree_fast with conflict resolution strategies."""

    @patch('pull_fast.find_repo_root')
    @patch('pull_fast.get_conflicted_files')
    @patch('pull_fast.resolve_conflicts')
    @patch('subprocess.run')
    def test_uses_strategy_on_conflict(self, mock_subprocess, mock_resolve, mock_conflicts, mock_find_root):
        """Should use specified strategy when conflicts occur."""
        mock_find_root.return_value = MagicMock()
        mock_find_root.return_value.__truediv__ = lambda self, x: MagicMock(exists=lambda: True)
        mock_conflicts.return_value = ["file1.txt"]
        mock_resolve.return_value = (True, "resolved (local)")

        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "CONFLICT"
        mock_subprocess.return_value = mock_result

        success, message, conflicts = pull_fast.pull_subtree_fast(
            ".test/prefix", "test-branch",
            resolve_mode=pull_fast.ResolveMode.LOCAL
        )

        self.assertTrue(success)
        self.assertEqual(message, "OK (resolved (local))")
        mock_resolve.assert_called_once_with(pull_fast.ResolveMode.LOCAL)


class TestErrorHandling(unittest.TestCase):
    """Tests for error handling edge cases."""

    @patch('pull_fast.find_repo_root')
    @patch('pull_fast.get_conflicted_files')
    @patch('subprocess.run')
    def test_unknown_error_truncated(self, mock_subprocess, mock_conflicts, mock_find_root):
        """Should truncate long error messages."""
        mock_find_root.return_value = MagicMock()
        mock_find_root.return_value.__truediv__ = lambda self, x: MagicMock(exists=lambda: True)
        mock_conflicts.return_value = []  # No conflicts, just a regular error

        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "x" * 200  # Long error message
        mock_subprocess.return_value = mock_result

        success, message, conflicts = pull_fast.pull_subtree_fast(".test/prefix", "test-branch")

        self.assertFalse(success)
        self.assertEqual(len(message), 80)  # Truncated to 80 chars

    @patch('pull_fast.run_git')
    def test_single_commit_grammar(self, mock_run_git):
        """Should use singular 'commit' for single commit."""
        mock_run_git.side_effect = [
            (True, "", ""),  # fetch succeeds
            (True, "abc123 single commit", ""),  # 1 commit
        ]

        has_changes, reason = pull_fast.has_remote_changes(".test/prefix", "test-branch")

        self.assertTrue(has_changes)
        self.assertEqual(reason, "1 commit(s)")


class TestOperationInProgressChecks(unittest.TestCase):
    """Tests for detecting in-progress git operations."""

    @patch('pull_fast.find_repo_root')
    def test_detects_rebase_in_progress(self, mock_find_root):
        """Should detect when rebase is in progress."""
        mock_root = MagicMock()
        mock_find_root.return_value = mock_root

        # Create mock path that reports rebase-merge exists
        mock_git_dir = MagicMock()
        mock_rebase_merge = MagicMock()
        mock_rebase_merge.exists.return_value = True
        mock_git_dir.__truediv__ = lambda self, x: mock_rebase_merge if x in ['rebase-merge', 'rebase-apply'] else MagicMock(exists=lambda: False)
        mock_root.__truediv__ = lambda self, x: mock_git_dir if x == '.git' else MagicMock()

        in_progress, op_name = pull_fast.is_operation_in_progress()

        self.assertTrue(in_progress)
        self.assertEqual(op_name, 'rebase')

    @patch('pull_fast.find_repo_root')
    def test_detects_no_operation(self, mock_find_root):
        """Should return False when no operation in progress."""
        mock_root = MagicMock()
        mock_find_root.return_value = mock_root

        # All paths return exists=False
        mock_no_exist = MagicMock()
        mock_no_exist.exists.return_value = False
        mock_git_dir = MagicMock()
        mock_git_dir.__truediv__ = lambda self, x: mock_no_exist
        mock_root.__truediv__ = lambda self, x: mock_git_dir if x == '.git' else MagicMock()

        in_progress, op_name = pull_fast.is_operation_in_progress()

        self.assertFalse(in_progress)
        self.assertIsNone(op_name)

    @patch('pull_fast.run_git')
    def test_is_merge_in_progress_true(self, mock_run_git):
        """Should detect merge in progress via MERGE_HEAD."""
        mock_run_git.return_value = (True, "abc123", "")

        result = pull_fast.is_merge_in_progress()

        self.assertTrue(result)
        mock_run_git.assert_called_with('rev-parse', '--verify', 'MERGE_HEAD')

    @patch('pull_fast.run_git')
    def test_is_merge_in_progress_false(self, mock_run_git):
        """Should return False when no merge in progress."""
        mock_run_git.return_value = (False, "", "")

        result = pull_fast.is_merge_in_progress()

        self.assertFalse(result)


class TestResolveConflictsErrorHandling(unittest.TestCase):
    """Tests for error handling in resolve_conflicts."""

    @patch('pull_fast.run_git')
    @patch('pull_fast.get_conflicted_files')
    @patch('pull_fast.is_merge_in_progress')
    def test_checkout_failure_aborts_merge(self, mock_merge_check, mock_conflicts, mock_run_git):
        """Should abort merge and return error when checkout fails."""
        mock_conflicts.return_value = ["file1.txt"]
        mock_merge_check.return_value = True

        # First call: checkout fails, second call: merge --abort
        mock_run_git.side_effect = [
            (False, "", "checkout failed"),  # checkout fails
            (True, "", ""),  # merge --abort succeeds
        ]

        success, message = pull_fast.resolve_conflicts(pull_fast.ResolveMode.LOCAL)

        self.assertFalse(success)
        self.assertIn("checkout failed", message)

    @patch('pull_fast.run_git')
    @patch('pull_fast.get_conflicted_files')
    @patch('pull_fast.is_merge_in_progress')
    def test_add_failure_aborts_merge(self, mock_merge_check, mock_conflicts, mock_run_git):
        """Should abort merge and return error when add fails."""
        mock_conflicts.return_value = ["file1.txt"]
        mock_merge_check.return_value = True

        # checkout succeeds, add fails
        mock_run_git.side_effect = [
            (True, "", ""),   # checkout succeeds
            (False, "", ""),  # add fails
            (True, "", ""),   # merge --abort succeeds
        ]

        success, message = pull_fast.resolve_conflicts(pull_fast.ResolveMode.LOCAL)

        self.assertFalse(success)
        self.assertIn("add failed", message)

    @patch('pull_fast.run_git')
    @patch('pull_fast.is_merge_in_progress')
    def test_abort_only_when_merge_in_progress(self, mock_merge_check, mock_run_git):
        """Should only call merge --abort when merge is actually in progress."""
        mock_merge_check.return_value = False
        mock_run_git.return_value = (True, "", "")

        success, message = pull_fast.resolve_conflicts(pull_fast.ResolveMode.ABORT)

        self.assertFalse(success)
        self.assertEqual(message, "aborted")
        # merge --abort should NOT have been called
        mock_run_git.assert_not_called()


if __name__ == "__main__":
    unittest.main()
