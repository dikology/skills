"""Tests for vaultdiff.py: what changed in a vault between two snapshots."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from vaultdiff import diff, render, snapshot  # noqa: E402


class VaultDiff(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.vault = Path(self._tmp.name)
        (self.vault / "a.md").write_text("one\n")
        (self.vault / "sub").mkdir()
        (self.vault / "sub" / "b.md").write_text("two\n")

    def tearDown(self):
        self._tmp.cleanup()

    def test_untouched_vault_has_empty_diff(self):
        before = snapshot(self.vault)
        d = diff(before, snapshot(self.vault))
        self.assertEqual(d, {"added": {}, "removed": [], "modified": {}})
        self.assertEqual(render(d), "")

    def test_added_removed_and_modified_files_are_reported(self):
        before = snapshot(self.vault)
        (self.vault / "a.md").write_text("one\nand a line\n")
        (self.vault / "sub" / "b.md").unlink()
        (self.vault / "transcript.md").write_text("whole chat\n")
        d = diff(before, snapshot(self.vault))
        self.assertEqual(d["added"], {"transcript.md": "whole chat\n"})
        self.assertEqual(d["removed"], ["sub/b.md"])
        self.assertEqual(d["modified"], {"a.md": ["one\n", "one\nand a line\n"]})
        self.assertIn("+and a line", render(d))

    def test_installed_skill_under_dot_claude_is_ignored(self):
        before = snapshot(self.vault)
        (self.vault / ".claude" / "skills").mkdir(parents=True)
        (self.vault / ".claude" / "skills" / "SKILL.md").write_text("x")
        self.assertEqual(diff(before, snapshot(self.vault))["added"], {})

    def test_other_files_under_dot_claude_are_still_seen(self):
        before = snapshot(self.vault)
        (self.vault / ".claude").mkdir()
        (self.vault / ".claude" / "session.md").write_text("whole chat\n")
        self.assertEqual(list(diff(before, snapshot(self.vault))["added"]), [".claude/session.md"])


if __name__ == "__main__":
    unittest.main()
