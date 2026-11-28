import concurrent.futures
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import date, timedelta


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

    def test_unknown_runtime_does_not_use_foreign_claude_transcripts(self):
        transcripts = self.transcript_directory()
        (transcripts / "foreign-session.jsonl").write_text("{}\n", encoding="utf-8")

        result = self.run_cli("current-session", env={"RETROSPECTIVE_RUNTIME": "unknown"})

        self.assertEqual(result.returncode, 0, result.stderr)
        identity = json.loads(result.stdout)
        self.assertIsNone(identity["adapter"])
        self.assertIsNone(identity["session_id"])
        self.assertEqual(identity["status"], "unavailable")

    def test_agent_drafted_note_is_only_proposed_without_approval(self):
        result = self.run_cli(
            "note",
            "--adapter",
            "future-agent",
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
            "future-agent",
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
        self.assertEqual(saved["adapter"], "future-agent")
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

    def test_declined_retro_candidates_are_shared_across_adapters(self):
        retro_candidate = "rule:AGENTS.md:preserve-explicit-approval"

        result = self.run_cli(
            "declined", "--adapter", "qwen", "--retro-candidate", retro_candidate
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
                "--retro-candidate",
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
            ("declined", "--retro-candidate", "declined-retro_candidate"),
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
            commands.append(("declined", "--retro-candidate", f"retro_candidate-{index}"))

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

    def test_digest_accepts_named_relative_and_iso_windows(self):
        today = date.today()
        cases = {
            "today": (today, today),
            "yesterday": (today - timedelta(days=1),) * 2,
            "week": (today - timedelta(days=6), today),
            "14d": (today - timedelta(days=13), today),
            "2026-10-12": (date(2026, 10, 12),) * 2,
        }

        for window, (start, end) in cases.items():
            with self.subTest(window=window):
                result = self.run_cli("digest", "--adapter", "claude", "--window", window)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn(f"# Retro digest — {start} → {end}", result.stdout)

    def test_digest_rejects_an_unknown_window(self):
        result = self.run_cli("digest", "--adapter", "claude", "--window", "fortnight")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Unknown window 'fortnight'", result.stderr)

    def test_core_skill_instructions_use_only_the_shared_entrypoint(self):
        instructions = (self.install / "SKILL.md").read_text(encoding="utf-8")

        self.assertTrue(instructions.startswith("---\nname: retrospective\n"))
        self.assertIn("scripts/retrospective.py", instructions)
        self.assertNotIn("scripts/adapters/", instructions)
        self.assertNotIn("claude.py", instructions)
        for contract in (
            "10+ human prompts",
            "4–6 bullets",
            "at most seven",
            "Reply with numbers (e.g. 1 3), all, or none.",
            "--approval '1 3'",
            "originating project",
            "newest transcript modification time",
            "Parallel",
        ):
            self.assertIn(contract, instructions)

    def test_empty_note_is_rejected_without_touching_the_inbox(self):
        result = self.run_cli(
            "note",
            "--adapter",
            "future-agent",
            "--text",
            "   ",
            "--context",
            "An empty note must not be filed.",
            "--approve",
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.state / "inbox.jsonl").exists())

    def test_reviewed_and_declined_ledgers_are_idempotent(self):
        for _ in range(2):
            reviewed = self.run_cli(
                "reviewed", "--adapter", "qwen", "--session-id", "opaque-a"
            )
            self.assertEqual(reviewed.returncode, 0, reviewed.stderr)
            declined = self.run_cli(
                "declined", "--retro-candidate", "rule:one"
            )
            self.assertEqual(declined.returncode, 0, declined.stderr)

        self.assertEqual(
            (self.state / "reviewed.txt").read_text(encoding="utf-8").splitlines(),
            ["qwen:opaque-a"],
        )
        self.assertEqual(
            (self.state / "declined.txt").read_text(encoding="utf-8").splitlines(),
            ["rule:one"],
        )

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
