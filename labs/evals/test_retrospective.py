import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
CANDIDATE = ROOT / "labs" / "retrospective"


class RetrospectiveCliTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.home = Path(self.temp_dir.name) / "home"
        self.install = self.home / ".claude" / "skills" / "retrospective"
        self.install.parent.mkdir(parents=True)
        shutil.copytree(CANDIDATE, self.install)
        self.entrypoint = self.install / "scripts" / "retrospective.py"
        self.state = Path(self.temp_dir.name) / "state"

    def run_cli(self, *args, env=None):
        clean_env = {
            "HOME": str(self.home),
            "PATH": os.environ.get("PATH", ""),
            "RETROSPECTIVE_STATE_DIR": str(self.state),
        }
        for name in list(os.environ):
            if name.startswith("CLAUDE") or name.startswith("RETROSPECTIVE_"):
                clean_env.pop(name, None)
        if env:
            clean_env.update(env)
        return subprocess.run(
            [sys.executable, str(self.entrypoint), *args],
            cwd=self.temp_dir.name,
            env=clean_env,
            text=True,
            capture_output=True,
            check=False,
        )

    def transcript_directory(self):
        transcripts = self.home / ".claude" / "projects" / "project"
        transcripts.mkdir(parents=True)
        return transcripts

    def test_plain_folder_install_reports_claude_capabilities_as_json(self):
        result = self.run_cli("capabilities", "--adapter", "claude")

        self.assertEqual(result.returncode, 0, result.stderr)
        capabilities = json.loads(result.stdout)
        self.assertEqual(capabilities["adapter"], "claude")
        self.assertIn("current-session", capabilities["operations"])
        self.assertIn("note", capabilities["operations"])
        self.assertIn("retro_inbox", capabilities["destinations"])
        self.assertIsInstance(capabilities["signals"], list)

    def test_runtime_environment_selects_the_claude_adapter(self):
        result = self.run_cli("capabilities", env={"RETROSPECTIVE_RUNTIME": "claude"})

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["adapter"], "claude")

    def test_unknown_runtime_does_not_use_foreign_claude_transcripts(self):
        transcripts = self.transcript_directory()
        (transcripts / "foreign-session.jsonl").write_text("{}\n", encoding="utf-8")

        result = self.run_cli("current-session", env={"RETROSPECTIVE_RUNTIME": "unknown"})

        self.assertEqual(result.returncode, 0, result.stderr)
        identity = json.loads(result.stdout)
        self.assertIsNone(identity["adapter"])
        self.assertIsNone(identity["session_id"])
        self.assertEqual(identity["status"], "unavailable")

    def test_explicit_claude_selection_overrides_runtime_and_uses_newest_transcript(self):
        transcripts = self.transcript_directory()
        older = transcripts / "older-session.jsonl"
        newer = transcripts / "newer-session.jsonl"
        older.write_text("{}\n", encoding="utf-8")
        newer.write_text("{}\n", encoding="utf-8")
        os.utime(older, (100, 100))
        os.utime(newer, (200, 200))

        result = self.run_cli(
            "current-session",
            "--adapter",
            "claude",
            env={"RETROSPECTIVE_RUNTIME": "unknown"},
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        identity = json.loads(result.stdout)
        self.assertEqual(identity["adapter"], "claude")
        self.assertEqual(identity["session_id"], "newer-session")
        self.assertEqual(identity["status"], "available")

    def test_agent_drafted_note_is_only_proposed_without_approval(self):
        result = self.run_cli(
            "note",
            "--adapter",
            "claude",
            "--text",
            "Check the migration rollback path.",
            "--context",
            "The release plan currently names deployment but not rollback.",
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        proposal = json.loads(result.stdout)
        self.assertEqual(proposal["status"], "approval_required")
        self.assertEqual(proposal["note"]["text"], "Check the migration rollback path.")
        self.assertFalse((self.state / "inbox.jsonl").exists())

    def test_approved_note_persists_without_current_session_identity(self):
        result = self.run_cli(
            "note",
            "--adapter",
            "claude",
            "--text",
            "Keep the rollout reversible.",
            "--context",
            "The deployment discussion did not name a rollback owner.",
            "--approve",
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        confirmation = json.loads(result.stdout)
        self.assertEqual(confirmation["status"], "saved")
        self.assertIsNone(confirmation["note"]["session_id"])
        records = (self.state / "inbox.jsonl").read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(records), 1)
        saved = json.loads(records[0])
        self.assertEqual(saved["adapter"], "claude")
        self.assertEqual(saved["text"], "Keep the rollout reversible.")
        self.assertEqual(
            saved["context"],
            "The deployment discussion did not name a rollback owner.",
        )
        self.assertIsNone(saved["session_id"])
        self.assertEqual(confirmation["note"], saved)

    def test_saved_note_includes_current_session_identity_when_available(self):
        transcripts = self.transcript_directory()
        (transcripts / "current-id.jsonl").write_text("{}\n", encoding="utf-8")

        result = self.run_cli(
            "note",
            "--adapter",
            "claude",
            "--text",
            "Preserve the session link.",
            "--context",
            "This note should remain traceable to its originating session.",
            "--approve",
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        saved = json.loads((self.state / "inbox.jsonl").read_text(encoding="utf-8"))
        self.assertEqual(saved["session_id"], "current-id")

    def test_core_skill_instructions_use_only_the_shared_entrypoint(self):
        instructions = (self.install / "SKILL.md").read_text(encoding="utf-8")

        self.assertTrue(instructions.startswith("---\nname: retrospective\n"))
        self.assertIn("scripts/retrospective.py", instructions)
        self.assertNotIn("scripts/adapters/", instructions)
        self.assertNotIn("claude.py", instructions)

    def test_note_context_must_be_one_short_line(self):
        result = self.run_cli(
            "note",
            "--adapter",
            "claude",
            "--text",
            "Keep this note.",
            "--context",
            "x" * 241,
            "--approve",
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.state / "inbox.jsonl").exists())


if __name__ == "__main__":
    unittest.main()
