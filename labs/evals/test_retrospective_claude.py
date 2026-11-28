import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import date


ROOT = Path(__file__).resolve().parents[2]
CANDIDATE = ROOT / "labs" / "retrospective"


def user(text, timestamp, human=True, cwd="/work/project"):
    record = {
        "type": "user",
        "timestamp": timestamp,
        "cwd": cwd,
        "message": {"role": "user", "content": text},
    }
    if human:
        record["origin"] = {"kind": "human"}
    return record


def assistant(timestamp, tools=(), skill=None, cwd="/work/project"):
    content = [{"type": "text", "text": "synthetic assistant response"}]
    for name, input_value in tools:
        content.append({"type": "tool_use", "id": "tool", "name": name, "input": input_value})
    record = {
        "type": "assistant",
        "timestamp": timestamp,
        "cwd": cwd,
        "message": {"role": "assistant", "content": content},
    }
    if skill:
        record["attributionSkill"] = skill
    return record


def tool_result(timestamp, error=False, text="ok", cwd="/work/project"):
    return {
        "type": "user",
        "timestamp": timestamp,
        "cwd": cwd,
        "message": {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": "tool",
                    "content": text,
                    "is_error": error,
                }
            ]
        },
    }


class ClaudeRetrospectiveCliTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name)
        self.home = self.root / "home"
        self.install = self.home / ".claude" / "skills" / "retrospective"
        self.install.parent.mkdir(parents=True)
        shutil.copytree(CANDIDATE, self.install)
        self.entrypoint = self.install / "scripts" / "retrospective.py"
        self.state = self.root / "state"

    def run_cli(self, *args, env=None, input_text=None):
        clean_env = {
            "HOME": str(self.home),
            "PATH": os.environ.get("PATH", ""),
            "RETROSPECTIVE_STATE_DIR": str(self.state),
        }
        if env:
            clean_env.update(env)
        return subprocess.run(
            [sys.executable, str(self.entrypoint), *args],
            cwd=self.root,
            env=clean_env,
            input=input_text,
            text=True,
            capture_output=True,
            check=False,
        )

    def transcript_directory(self, slug="project"):
        transcripts = self.home / ".claude" / "projects" / slug
        transcripts.mkdir(parents=True, exist_ok=True)
        return transcripts

    def write_session(self, session_id, records, folder=None):
        folder = folder or self.transcript_directory()
        path = folder / f"{session_id}.jsonl"
        path.write_text(
            "\n".join(json.dumps(record) for record in records) + "\n",
            encoding="utf-8",
        )
        return path

    def rich_session(self, session_id="aaaaaaaa-1111", day="2026-10-16", cwd="/work/project"):
        records = [
            {"type": "ai-title", "aiTitle": "Fix the drain"},
            user(
                "<command-name>/drain</command-name>\n<command-args>now</command-args>",
                f"{day}T09:00:00Z",
                cwd=cwd,
            ),
            assistant(
                f"{day}T09:00:05Z",
                [("Bash", {"command": "ls"}), ("Skill", {"skill": "obsidian-markdown"})],
                skill="drain",
                cwd=cwd,
            ),
            tool_result(f"{day}T09:00:06Z", error=True, text="Exit code 1\nboom", cwd=cwd),
            user("[Request interrupted by user]", f"{day}T09:01:00Z", cwd=cwd),
            user("no, file it under travel instead", f"{day}T09:02:00Z", cwd=cwd),
            user("<command-name>/clear</command-name>", f"{day}T09:03:00Z", cwd=cwd),
            user("thanks, commit it", f"{day}T09:04:00Z", cwd=cwd),
        ]
        return self.write_session(session_id, records)

    def test_full_session_preserves_claude_prompts_tools_errors_and_skills(self):
        self.rich_session()

        result = self.run_cli(
            "digest", "--adapter", "claude", "--session", "aaaaaaaa", "--lang", "zh"
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("### aaaaaaaa · Fix the drain", result.stdout)
        self.assertIn("/drain now", result.stdout)
        self.assertIn("⚑ no, file it under travel instead", result.stdout)
        self.assertIn("thanks, commit it", result.stdout)
        self.assertNotIn("⚑ /drain", result.stdout)
        self.assertNotIn("<command-name>/clear</command-name>", result.stdout)
        self.assertIn("Bash×1", result.stdout)
        self.assertIn("errors: 1 · interruptions: 1", result.stdout)
        self.assertIn("error: Exit code 1 boom", result.stdout)
        self.assertIn("skills: drain, obsidian-markdown", result.stdout)
        self.assertIn("Insight language: zh; Retro candidate language: destination", result.stdout)

    def test_discovery_filters_window_projects_temp_and_subagent_transcripts(self):
        today = date.today().isoformat()
        self.rich_session("aaaaaaaa-1111", today)
        self.rich_session("bbbbbbbb-2222", "2000-01-01")
        self.write_session("cccccccc-3333", [user("hi", f"{today}T10:00:00Z")])
        temp_project = Path(tempfile.gettempdir()) / "retrospective-synthetic-temp"
        self.rich_session("eval0000-1111", today, cwd=str(temp_project))
        subagents = self.transcript_directory() / "aaaaaaaa-1111" / "subagents"
        subagents.mkdir(parents=True)
        self.write_session(
            "agent-synthetic",
            [user("nested", f"{today}T10:00:00Z") for _ in range(5)],
            folder=subagents,
        )

        digest = self.run_cli("digest", "--adapter", "claude", "--window", "today")
        self.assertEqual(digest.returncode, 0, digest.stderr)
        self.assertIn("aaaaaaaa", digest.stdout)
        self.assertNotIn("bbbbbbbb", digest.stdout)
        self.assertNotIn("cccccccc", digest.stdout)
        self.assertNotIn("eval0000", digest.stdout)
        self.assertNotIn("agent-synthetic", digest.stdout)

        included = self.run_cli(
            "digest", "--adapter", "claude", "--window", "today", "--include-temp"
        )
        self.assertIn("eval0000", included.stdout)
        filtered = self.run_cli(
            "digest", "--adapter", "claude", "--window", "today", "--project", "other"
        )
        self.assertIn("0 sessions across 0 projects", filtered.stdout)
        full = self.run_cli("digest", "--adapter", "claude", "--session", "bbbbbbbb")
        self.assertIn("bbbbbbbb · Fix the drain", full.stdout)

    def test_optional_signals_state_and_notes_render_only_when_available(self):
        today = date.today().isoformat()
        transcript = self.rich_session("aaaaaaaa-1111", today)
        facets = self.home / ".claude" / "usage-data" / "facets"
        facets.mkdir(parents=True)
        facet_file = facets / "aaaaaaaa-1111.json"
        facet_file.write_text(
            json.dumps(
                {
                    "outcome": "partially_achieved",
                    "friction_detail": "wrong folder",
                }
            ),
            encoding="utf-8",
        )
        queue_file = transcript.parent / "learnings-queue.json"
        queue_file.write_text(
            json.dumps(
                [
                    {
                        "type": "auto",
                        "message": "use uv not pip",
                        "timestamp": f"{today}T09:00:00Z",
                        "project": "/work/project",
                    }
                ]
            ),
            encoding="utf-8",
        )
        original_facets = facet_file.read_bytes()
        original_queue = queue_file.read_bytes()
        reviewed = self.run_cli(
            "reviewed", "--adapter", "claude", "--session-id", "aaaaaaaa-1111"
        )
        self.assertEqual(reviewed.returncode, 0, reviewed.stderr)
        note = self.run_cli(
            "note",
            "--adapter",
            "claude",
            "--text",
            "drain misfiled travel",
            "--context",
            "Synthetic note context",
            "--approve",
        )
        self.assertEqual(note.returncode, 0, note.stderr)
        declined = self.run_cli(
            "declined", "--retro-candidate", "never use emoji"
        )
        self.assertEqual(declined.returncode, 0, declined.stderr)

        result = self.run_cli("digest", "--adapter", "claude", "--window", "today")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("outcome=partially_achieved", result.stdout)
        self.assertIn("friction: wrong folder", result.stdout)
        self.assertIn("· reviewed", result.stdout)
        self.assertIn("## Retro notes (1)", result.stdout)
        self.assertIn("drain misfiled travel", result.stdout)
        self.assertIn("## claude-reflect queue (1, read-only)", result.stdout)
        self.assertIn("use uv not pip", result.stdout)
        self.assertIn("## Declined before (1) — do not re-propose", result.stdout)
        self.assertIn("never use emoji", result.stdout)
        self.assertEqual(facet_file.read_bytes(), original_facets)
        self.assertEqual(queue_file.read_bytes(), original_queue)

        facet_file.unlink()
        queue_file.unlink()
        absent = self.run_cli("digest", "--adapter", "claude", "--window", "today")
        self.assertNotIn("insights facets", absent.stdout)
        self.assertNotIn("claude-reflect queue", absent.stdout)

    def test_plain_folder_install_reports_claude_capabilities_as_json(self):
        result = self.run_cli("capabilities", "--adapter", "claude")

        self.assertEqual(result.returncode, 0, result.stderr)
        capabilities = json.loads(result.stdout)
        self.assertEqual(capabilities["adapter"], "claude")
        for operation in (
            "current-session",
            "note",
            "notes",
            "digest",
            "prepare",
            "report",
            "execute",
            "reviewed",
            "declined",
            "clear",
        ):
            self.assertIn(operation, capabilities["operations"])
        for destination in ("retro_inbox", "memory", "rule", "skill_edit", "issue"):
            self.assertIn(destination, capabilities["destinations"])
        self.assertIsInstance(capabilities["signals"], list)

    def test_runtime_environment_selects_the_claude_adapter(self):
        result = self.run_cli("capabilities", env={"RETROSPECTIVE_RUNTIME": "claude"})

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["adapter"], "claude")

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

    def test_current_conversation_notes_filter_by_complete_session_id(self):
        today = date.today().isoformat()
        older = self.rich_session("old-0000", today)
        newer = self.rich_session("new-1111", today)
        os.utime(older, (100, 100))
        os.utime(newer, (200, 200))
        first = self.run_cli(
            "note",
            "--adapter",
            "claude",
            "--text",
            "new session note",
            "--context",
            "Synthetic current conversation",
            "--approve",
        )
        self.assertEqual(first.returncode, 0, first.stderr)
        os.utime(older, (300, 300))
        os.utime(newer, (100, 100))
        second = self.run_cli(
            "note",
            "--adapter",
            "claude",
            "--text",
            "old session note",
            "--context",
            "Synthetic current conversation",
            "--approve",
        )
        self.assertEqual(second.returncode, 0, second.stderr)

        result = self.run_cli("notes", "--session-id", "new-1111")

        self.assertEqual(result.returncode, 0, result.stderr)
        notes = json.loads(result.stdout)["notes"]
        self.assertEqual([note["text"] for note in notes], ["new session note"])
        self.assertEqual(notes[0]["session_id"], "new-1111")

    def test_full_session_prefix_must_be_nonempty_and_unambiguous(self):
        today = date.today().isoformat()
        self.rich_session("shared-0001", today)
        self.rich_session("shared-0002", today)

        for prefix in ("", "shared"):
            with self.subTest(prefix=prefix):
                result = self.run_cli("digest", "--adapter", "claude", "--session", prefix)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("session", result.stderr.lower())

    def test_digest_notes_follow_project_and_full_session_scope(self):
        today = date.today().isoformat()
        self.rich_session("session-one", today, cwd="/work/one")
        self.rich_session("session-two", today, cwd="/work/two")
        self.state.mkdir()
        notes = [
            {
                "id": "one-note",
                "project": "/work/one",
                "session_id": "session-one",
                "text": "one project note",
                "context": "synthetic",
                "created_at": f"{today}T10:00:00+00:00",
            },
            {
                "id": "two-note",
                "project": "/work/two",
                "session_id": "session-two",
                "text": "two project note",
                "context": "synthetic",
                "created_at": f"{today}T10:00:00+00:00",
            },
            {
                "id": "unbound-note",
                "project": "/work/one",
                "session_id": None,
                "text": "unbound one project note",
                "context": "synthetic",
                "created_at": f"{today}T10:00:00+00:00",
            },
        ]
        (self.state / "inbox.jsonl").write_text(
            "\n".join(json.dumps(note) for note in notes) + "\n", encoding="utf-8"
        )

        project = self.run_cli(
            "digest", "--adapter", "claude", "--window", "today", "--project", "/work/one"
        )
        self.assertEqual(project.returncode, 0, project.stderr)
        self.assertIn("one project note", project.stdout)
        self.assertIn("unbound one project note", project.stdout)
        self.assertNotIn("two project note", project.stdout)

        full = self.run_cli("digest", "--adapter", "claude", "--session", "session-one")
        self.assertEqual(full.returncode, 0, full.stderr)
        self.assertIn("one project note", full.stdout)
        self.assertNotIn("unbound one project note", full.stdout)
        self.assertNotIn("two project note", full.stdout)

    def test_invalid_sessions_warn_instead_of_silently_disappearing(self):
        today = date.today().isoformat()
        folder = self.transcript_directory()
        self.write_session(
            "missing-time",
            [user("synthetic prompt without time", "not-a-date")],
            folder=folder,
        )
        self.write_session(
            "too-short", [user("only one prompt", f"{today}T10:00:00Z")], folder=folder
        )
        self.rich_session("unknown-project", today, cwd="")

        result = self.run_cli("digest", "--adapter", "claude", "--window", "today")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("missing-time", result.stderr)
        self.assertIn("timestamp", result.stderr)
        self.assertIn("too-short", result.stderr)
        self.assertIn("prompt", result.stderr)
        self.assertIn("unknown-project", result.stderr)
        self.assertIn("project", result.stderr)
        self.assertIn("unknown-", result.stdout)

    def test_digest_allows_at_most_five_full_session_drilldowns(self):
        result = self.run_cli(
            "digest",
            "--adapter",
            "claude",
            "--session",
            "one",
            "--session",
            "two",
            "--session",
            "three",
            "--session",
            "four",
            "--session",
            "five",
            "--session",
            "six",
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("at most five", result.stderr)

if __name__ == "__main__":
    unittest.main()
