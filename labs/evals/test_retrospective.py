import concurrent.futures
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
        for operation in ("reviewed", "declined", "clear"):
            self.assertIn(operation, capabilities["operations"])
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

    def test_note_accepts_arbitrary_adapter_without_session_implementation(self):
        result = self.run_cli(
            "note",
            "--adapter",
            "future-agent",
            "--text",
            "Keep this adapter-neutral note.",
            "--context",
            "No native current-session lookup exists for this adapter.",
            "--approve",
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        saved = json.loads((self.state / "inbox.jsonl").read_text(encoding="utf-8"))
        self.assertEqual(saved["adapter"], "future-agent")
        self.assertIsNone(saved["session_id"])

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

    def test_reviewed_sessions_keep_complete_opaque_ids_and_namespace_adapters(self):
        session_id = "native/session:with-a-complete-opaque-id-123456789"

        for adapter in ("qwen", "kimi"):
            result = self.run_cli(
                "reviewed",
                "--adapter",
                adapter,
                "--session-id",
                session_id,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(
                json.loads(result.stdout)["sessions"],
                [{"adapter": adapter, "session_id": session_id, "reviewed": True}],
            )

        for adapter, expected in (("qwen", True), ("kimi", True), ("claude", False)):
            result = self.run_cli(
                "reviewed",
                "--adapter",
                adapter,
                "--session-id",
                session_id,
                "--check",
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(
                json.loads(result.stdout)["sessions"][0]["reviewed"], expected
            )

        records = (self.state / "reviewed.txt").read_text(encoding="utf-8").splitlines()
        self.assertEqual(
            records,
            [f"qwen:{session_id}", f"kimi:{session_id}"],
        )

    def test_legacy_claude_reviewed_ids_are_read_without_rewriting_ledger(self):
        legacy_id = "123e4567-e89b-42d3-a456-426614174000"
        original = f"{legacy_id}\n# retain this hand-edited line\n"
        self.state.mkdir()
        ledger = self.state / "reviewed.txt"
        ledger.write_text(original, encoding="utf-8")

        for adapter, expected in (("claude", True), ("qwen", False)):
            result = self.run_cli(
                "reviewed",
                "--adapter",
                adapter,
                "--session-id",
                legacy_id,
                "--check",
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(
                json.loads(result.stdout)["sessions"][0]["reviewed"], expected
            )
            self.assertEqual(ledger.read_text(encoding="utf-8"), original)

    def test_declined_retro_candidates_are_shared_across_adapters(self):
        retro_candidate = "rule:AGENTS.md:preserve-explicit-approval"

        result = self.run_cli(
            "declined", "--adapter", "qwen", "--retro_candidate", retro_candidate
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            json.loads(result.stdout)["retro_candidates"],
            [{"retro_candidate": retro_candidate, "declined": True}],
        )

        for adapter, retro_candidate_to_check, expected in (
            ("kimi", retro_candidate, True),
            ("claude", "rule:AGENTS.md:a-different-retro_candidate", False),
        ):
            result = self.run_cli(
                "declined",
                "--adapter",
                adapter,
                "--retro_candidate",
                retro_candidate_to_check,
                "--check",
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(
                json.loads(result.stdout)["retro_candidates"][0]["declined"], expected
            )

        self.assertEqual(
            (self.state / "declined.txt").read_text(encoding="utf-8").splitlines(),
            [retro_candidate],
        )

    def test_clear_removes_only_selected_notes_and_preserves_hand_edits(self):
        saved = []
        for adapter in ("qwen", "kimi"):
            result = self.run_cli(
                "note",
                "--adapter",
                adapter,
                "--text",
                f"Note from {adapter}.",
                "--context",
                "The shared inbox contains both adapters' notes.",
                "--approve",
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            saved.append(json.loads(result.stdout)["note"])

        inbox = self.state / "inbox.jsonl"
        original_lines = inbox.read_text(encoding="utf-8").splitlines()
        hand_edit = '{"hand":"edited","purpose":"preserve unknown records"}'
        trailing_edit = "trailing hand edit without a newline"
        inbox.write_text(
            "hand-edited preamble\n"
            + original_lines[0]
            + "\n"
            + hand_edit
            + "\n"
            + original_lines[1]
            + "\n"
            + trailing_edit,
            encoding="utf-8",
        )

        result = self.run_cli("clear", "--note-id", saved[0]["id"])

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            json.loads(result.stdout),
            {"cleared": [saved[0]["id"]], "missing": [], "status": "cleared"},
        )
        self.assertEqual(
            inbox.read_text(encoding="utf-8"),
            "hand-edited preamble\n"
            + hand_edit
            + "\n"
            + original_lines[1]
            + "\n"
            + trailing_edit,
        )

    def test_appends_preserve_unterminated_hand_edited_lines(self):
        self.state.mkdir()
        hand_edits = {
            "inbox.jsonl": "inbox hand edit without a newline",
            "reviewed.txt": "reviewed hand edit without a newline",
            "declined.txt": "declined hand edit without a newline",
        }
        for filename, content in hand_edits.items():
            (self.state / filename).write_text(content, encoding="utf-8")

        commands = (
            (
                "note",
                "--adapter",
                "future-agent",
                "--text",
                "Preserve the existing inbox line.",
                "--context",
                "Appending must not merge two records.",
                "--approve",
            ),
            ("reviewed", "--adapter", "qwen", "--session-id", "opaque-id"),
            ("declined", "--retro_candidate", "declined-retro_candidate"),
        )
        for command in commands:
            result = self.run_cli(*command)
            self.assertEqual(result.returncode, 0, result.stderr)

        for filename, original in hand_edits.items():
            lines = (self.state / filename).read_text(encoding="utf-8").splitlines()
            self.assertEqual(lines[0], original)
            self.assertEqual(len(lines), 2)

    def test_concurrent_external_state_operations_do_not_lose_updates(self):
        operation_count = 40
        seeded = []
        for index in range(operation_count):
            result = self.run_cli(
                "note",
                "--adapter",
                "claude",
                "--text",
                f"Seed note {index}.",
                "--context",
                "This note will be cleared concurrently.",
                "--approve",
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            seeded.append(json.loads(result.stdout)["note"])

        commands = []
        for index, note in enumerate(seeded):
            commands.append(("clear", "--note-id", note["id"]))
            commands.append(
                (
                    "note",
                    "--adapter",
                    "future-agent",
                    "--text",
                    f"Concurrent note {index}.",
                    "--context",
                    "This note must survive concurrent clears.",
                    "--approve",
                )
            )
            commands.append(
                (
                    "reviewed",
                    "--adapter",
                    "qwen" if index % 2 else "kimi",
                    "--session-id",
                    f"opaque-session-{index}-123456789",
                )
            )
            commands.append(("declined", "--retro_candidate", f"retro_candidate-{index}"))

        with concurrent.futures.ThreadPoolExecutor(max_workers=len(commands)) as executor:
            results = list(executor.map(lambda command: self.run_cli(*command), commands))

        for result in results:
            self.assertEqual(result.returncode, 0, result.stderr)
        inbox_records = [
            json.loads(line)
            for line in (self.state / "inbox.jsonl").read_text(encoding="utf-8").splitlines()
        ]
        self.assertEqual(
            {record["text"] for record in inbox_records},
            {f"Concurrent note {index}." for index in range(operation_count)},
        )
        reviewed = (self.state / "reviewed.txt").read_text(encoding="utf-8").splitlines()
        self.assertEqual(
            set(reviewed),
            {
                f"{'qwen' if index % 2 else 'kimi'}:opaque-session-{index}-123456789"
                for index in range(operation_count)
            },
        )
        declined = (self.state / "declined.txt").read_text(encoding="utf-8").splitlines()
        self.assertEqual(
            set(declined), {f"retro_candidate-{index}" for index in range(operation_count)}
        )

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
