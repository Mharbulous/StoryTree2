#!/usr/bin/env python3
"""
Unit tests for push_fast.py

Tests the logic without actually pushing to remotes.
"""

import subprocess
import unittest
from unittest.mock import patch, MagicMock

# Import the module under test
import push_fast


class TestHasLocalChanges(unittest.TestCase):
    """Tests for the has_local_changes function."""

    @patch('push_fast.run_git')
    def test_detects_commits_ahead(self, mock_run_git):
        """Should detect when local has commits not on remote."""
        # First call: fetch (succeeds)
        # Second call: git log shows 3 commits
        mock_run_git.side_effect = [
            (True, "", ""),  # fetch succeeds
            (True, "abc123 commit1\ndef456 commit2\nghi789 commit3", ""),  # 3 commits
        ]

        has_changes, reason = push_fast.has_local_changes(".test/prefix", "test-branch")

        self.assertTrue(has_changes)
        self.assertEqual(reason, "3 commit(s)")

    @patch('push_fast.run_git')
    def test_detects_up_to_date(self, mock_run_git):
        """Should detect when local is up to date with remote."""
        mock_run_git.side_effect = [
            (True, "", ""),  # fetch succeeds
            (True, "", ""),  # no commits ahead
        ]

        has_changes, reason = push_fast.has_local_changes(".test/prefix", "test-branch")

        self.assertFalse(has_changes)
        self.assertEqual(reason, "up to date")

    @patch('push_fast.run_git')
    def test_handles_missing_remote_branch(self, mock_run_git):
        """Should assume changes exist when remote branch doesn't exist."""
        mock_run_git.side_effect = [
            (True, "", ""),  # fetch succeeds
            (False, "", ""),  # log fails (remote branch not found)
        ]

        has_changes, reason = push_fast.has_local_changes(".test/prefix", "test-branch")

        self.assertTrue(has_changes)
        self.assertEqual(reason, "remote branch not found")


class TestPushSubtreeFast(unittest.TestCase):
    """Tests for the push_subtree_fast function."""

    @patch('push_fast.find_repo_root')
    @patch('subprocess.run')
    def test_detects_rejection(self, mock_subprocess, mock_find_root):
        """Should detect when push is rejected due to diverged branches."""
        mock_find_root.return_value = MagicMock()
        mock_find_root.return_value.__truediv__ = lambda self, x: MagicMock(exists=lambda: True)

        # Simulate rejected push
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "error: failed to push some refs\nhint: Updates were rejected because the tip of your current branch is behind"
        mock_subprocess.return_value = mock_result

        success, message = push_fast.push_subtree_fast(".test/prefix", "test-branch")

        self.assertFalse(success)
        self.assertEqual(message, "rejected (diverged) - use --retry to auto-recover")

    @patch('push_fast.find_repo_root')
    @patch('subprocess.run')
    def test_detects_successful_push(self, mock_subprocess, mock_find_root):
        """Should detect successful push."""
        mock_find_root.return_value = MagicMock()
        mock_find_root.return_value.__truediv__ = lambda self, x: MagicMock(exists=lambda: True)

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "abc123\ndef456"
        mock_result.stderr = ""
        mock_subprocess.return_value = mock_result

        success, message = push_fast.push_subtree_fast(".test/prefix", "test-branch")

        self.assertTrue(success)
        self.assertEqual(message, "OK (pushed)")

    @patch('push_fast.find_repo_root')
    @patch('subprocess.run')
    def test_detects_up_to_date(self, mock_subprocess, mock_find_root):
        """Should detect when already up to date."""
        mock_find_root.return_value = MagicMock()
        mock_find_root.return_value.__truediv__ = lambda self, x: MagicMock(exists=lambda: True)

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "Everything up-to-date"
        mock_result.stderr = ""
        mock_subprocess.return_value = mock_result

        success, message = push_fast.push_subtree_fast(".test/prefix", "test-branch")

        self.assertTrue(success)
        self.assertEqual(message, "OK (up to date)")

    @patch('push_fast.find_repo_root')
    def test_skips_missing_directory(self, mock_find_root):
        """Should skip if subtree directory doesn't exist."""
        mock_find_root.return_value = MagicMock()
        mock_find_root.return_value.__truediv__ = lambda self, x: MagicMock(exists=lambda: False)

        success, message = push_fast.push_subtree_fast(".nonexistent/prefix", "test-branch")

        self.assertTrue(success)
        self.assertEqual(message, "skipped (not found)")


class TestRetryOnRejection(unittest.TestCase):
    """Tests for automatic retry logic when push is rejected."""

    @patch('push_fast.find_repo_root')
    @patch('push_fast.recover_rejected_push')
    @patch('subprocess.run')
    def test_retry_success(self, mock_subprocess, mock_recover, mock_find_root):
        """Should recover from rejection when --retry is enabled."""
        mock_find_root.return_value = MagicMock()
        mock_find_root.return_value.__truediv__ = lambda self, x: MagicMock(exists=lambda: True)
        mock_recover.return_value = (True, "recovered (pulled diverged changes)")

        # First push: rejected, second push (after recovery): success
        mock_result_rejected = MagicMock()
        mock_result_rejected.returncode = 1
        mock_result_rejected.stdout = ""
        mock_result_rejected.stderr = "rejected"

        mock_result_success = MagicMock()
        mock_result_success.returncode = 0
        mock_result_success.stdout = "pushed"
        mock_result_success.stderr = ""

        mock_subprocess.side_effect = [mock_result_rejected, mock_result_success]

        success, message = push_fast.push_subtree_fast(
            ".test/prefix", "test-branch",
            retry_on_reject=True
        )

        self.assertTrue(success)
        self.assertEqual(message, "OK (recovered and pushed)")
        mock_recover.assert_called_once()

    @patch('push_fast.find_repo_root')
    @patch('push_fast.recover_rejected_push')
    @patch('subprocess.run')
    def test_retry_recovery_fails(self, mock_subprocess, mock_recover, mock_find_root):
        """Should report failure when recovery fails."""
        mock_find_root.return_value = MagicMock()
        mock_find_root.return_value.__truediv__ = lambda self, x: MagicMock(exists=lambda: True)
        mock_recover.return_value = (False, "pull conflicts: aborted")

        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "rejected"
        mock_subprocess.return_value = mock_result

        success, message = push_fast.push_subtree_fast(
            ".test/prefix", "test-branch",
            retry_on_reject=True
        )

        self.assertFalse(success)
        self.assertEqual(message, "rejected (pull conflicts: aborted)")

    @patch('push_fast.find_repo_root')
    @patch('subprocess.run')
    def test_no_retry_by_default(self, mock_subprocess, mock_find_root):
        """Should not retry when --retry is not specified."""
        mock_find_root.return_value = MagicMock()
        mock_find_root.return_value.__truediv__ = lambda self, x: MagicMock(exists=lambda: True)

        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "rejected"
        mock_subprocess.return_value = mock_result

        success, message = push_fast.push_subtree_fast(
            ".test/prefix", "test-branch",
            retry_on_reject=False
        )

        self.assertFalse(success)
        self.assertIn("use --retry", message)


class TestRecoverRejectedPush(unittest.TestCase):
    """Tests for the recover_rejected_push function."""

    @patch('push_fast.has_uncommitted_in_prefix')
    @patch('subprocess.run')
    def test_recovery_success(self, mock_subprocess, mock_uncommitted):
        """Should succeed when pull works without conflicts."""
        mock_uncommitted.return_value = False

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "Merge made"
        mock_result.stderr = ""
        mock_subprocess.return_value = mock_result

        success, message = push_fast.recover_rejected_push(".test/prefix", "test-branch")

        self.assertTrue(success)
        self.assertEqual(message, "recovered (pulled diverged changes)")

    @patch('push_fast.has_uncommitted_in_prefix')
    def test_fails_with_uncommitted_changes(self, mock_uncommitted):
        """Should fail if there are uncommitted changes in prefix."""
        mock_uncommitted.return_value = True

        success, message = push_fast.recover_rejected_push(".test/prefix", "test-branch")

        self.assertFalse(success)
        self.assertEqual(message, "uncommitted changes in prefix")

    @patch('push_fast.has_uncommitted_in_prefix')
    @patch('push_fast.get_conflicted_files')
    @patch('push_fast.resolve_conflicts')
    @patch('subprocess.run')
    def test_recovery_with_conflict_resolution(self, mock_subprocess, mock_resolve, mock_conflicts, mock_uncommitted):
        """Should use conflict resolution strategy on conflicts."""
        mock_uncommitted.return_value = False
        mock_conflicts.return_value = ["file.txt"]
        mock_resolve.return_value = (True, "resolved (local)")

        mock_result = MagicMock()
        mock_result.returncode = 1  # Pull failed due to conflict
        mock_result.stdout = ""
        mock_result.stderr = "CONFLICT"
        mock_subprocess.return_value = mock_result

        success, message = push_fast.recover_rejected_push(
            ".test/prefix", "test-branch",
            resolve_mode=push_fast.ResolveMode.LOCAL
        )

        self.assertTrue(success)
        mock_resolve.assert_called_once_with(push_fast.ResolveMode.LOCAL)

    @patch('push_fast.has_uncommitted_in_prefix')
    @patch('push_fast.get_conflicted_files')
    @patch('push_fast.resolve_conflicts')
    @patch('subprocess.run')
    def test_recovery_conflict_abort(self, mock_subprocess, mock_resolve, mock_conflicts, mock_uncommitted):
        """Should abort and report when conflict resolution fails."""
        mock_uncommitted.return_value = False
        mock_conflicts.return_value = ["file.txt"]
        mock_resolve.return_value = (False, "aborted")

        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "CONFLICT"
        mock_subprocess.return_value = mock_result

        success, message = push_fast.recover_rejected_push(".test/prefix", "test-branch")

        self.assertFalse(success)
        self.assertEqual(message, "pull conflicts: aborted")


class TestRejectionHandlingEdgeCases(unittest.TestCase):
    """Additional tests for rejection handling edge cases."""

    @patch('push_fast.find_repo_root')
    @patch('subprocess.run')
    def test_rejection_with_non_fast_forward(self, mock_subprocess, mock_find_root):
        """Should detect non-fast-forward rejection."""
        mock_find_root.return_value = MagicMock()
        mock_find_root.return_value.__truediv__ = lambda self, x: MagicMock(exists=lambda: True)

        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "! [rejected]        split -> storytree-skills (non-fast-forward)"
        mock_subprocess.return_value = mock_result

        success, message = push_fast.push_subtree_fast(".test/prefix", "test-branch")

        self.assertFalse(success)
        self.assertEqual(message, "rejected (diverged) - use --retry to auto-recover")

    @patch('push_fast.find_repo_root')
    @patch('subprocess.run')
    def test_unknown_error_truncated(self, mock_subprocess, mock_find_root):
        """Should truncate long error messages."""
        mock_find_root.return_value = MagicMock()
        mock_find_root.return_value.__truediv__ = lambda self, x: MagicMock(exists=lambda: True)

        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "x" * 200  # Long error message
        mock_subprocess.return_value = mock_result

        success, message = push_fast.push_subtree_fast(".test/prefix", "test-branch")

        self.assertFalse(success)
        self.assertEqual(len(message), 80)  # Truncated to 80 chars


class TestOperationInProgressChecks(unittest.TestCase):
    """Tests for detecting in-progress git operations."""

    @patch('push_fast.find_repo_root')
    def test_detects_cherry_pick_in_progress(self, mock_find_root):
        """Should detect when cherry-pick is in progress."""
        mock_root = MagicMock()
        mock_find_root.return_value = mock_root

        # Create mock path that reports CHERRY_PICK_HEAD exists
        def mock_path(name):
            mock = MagicMock()
            if name == 'CHERRY_PICK_HEAD':
                mock.exists.return_value = True
            else:
                mock.exists.return_value = False
            return mock

        mock_git_dir = MagicMock()
        mock_git_dir.__truediv__ = lambda self, x: mock_path(x)
        mock_root.__truediv__ = lambda self, x: mock_git_dir if x == '.git' else MagicMock()

        in_progress, op_name = push_fast.is_operation_in_progress()

        self.assertTrue(in_progress)
        self.assertEqual(op_name, 'cherry-pick')

    @patch('push_fast.run_git')
    def test_is_merge_in_progress_true(self, mock_run_git):
        """Should detect merge in progress via MERGE_HEAD."""
        mock_run_git.return_value = (True, "abc123", "")

        result = push_fast.is_merge_in_progress()

        self.assertTrue(result)


class TestResolveConflictsErrorHandling(unittest.TestCase):
    """Tests for error handling in resolve_conflicts."""

    @patch('push_fast.run_git')
    @patch('push_fast.get_conflicted_files')
    @patch('push_fast.is_merge_in_progress')
    def test_checkout_failure_aborts_merge(self, mock_merge_check, mock_conflicts, mock_run_git):
        """Should abort merge and return error when checkout fails."""
        mock_conflicts.return_value = ["file1.txt"]
        mock_merge_check.return_value = True

        mock_run_git.side_effect = [
            (False, "", "checkout failed"),
            (True, "", ""),  # merge --abort
        ]

        success, message = push_fast.resolve_conflicts(push_fast.ResolveMode.LOCAL)

        self.assertFalse(success)
        self.assertIn("checkout failed", message)

    @patch('push_fast.run_git')
    @patch('push_fast.is_merge_in_progress')
    def test_abort_only_when_merge_in_progress(self, mock_merge_check, mock_run_git):
        """Should only call merge --abort when merge is actually in progress."""
        mock_merge_check.return_value = False

        success, message = push_fast.resolve_conflicts(push_fast.ResolveMode.ABORT)

        self.assertFalse(success)
        self.assertEqual(message, "aborted")
        mock_run_git.assert_not_called()


if __name__ == "__main__":
    unittest.main()
