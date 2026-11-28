"""Synthetic fixtures for the Qwen Agent adapter.

Every transcript here is hand-written in the shapes Qwen Code 0.28.3 records, in a home of
the test's own. No real conversation body, credential or live retrospective state is read.
"""

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


def human(text, timestamp, cwd="/work/project"):
    return {
        "type": "user",
        "provenance": "real_user",
        "timestamp": timestamp,
        "cwd": cwd,
        "message": {"role": "user", "parts": [{"text": text}]},
    }


def injected(text, timestamp, cwd="/work/project"):
    """A `user` record the runtime wrote, not the human: Qwen marks it `system`."""
    return {
        "type": "user",
        "provenance": "system",
        "subtype": "system_payload",
        "deliveredTurn": 1,
        "timestamp": timestamp,
        "cwd": cwd,
        "message": {"role": "user", "parts": [{"text": text}]},
    }


def assistant(timestamp, calls=(), cwd="/work/project", thought=False):
    parts = [{"text": "synthetic assistant response"}]
    if thought:
        parts.insert(0, {"text": "synthetic hidden reasoning", "thought": True})
    for name, args in calls:
        parts.append({"functionCall": {"name": name, "args": dict(args)}})
    return {
        "type": "assistant",
        "provenance": "assistant_output",
        "timestamp": timestamp,
        "cwd": cwd,
        "message": {"role": "assistant", "parts": parts},
    }


def tool_result(timestamp, status="success", execution=None, error="", error_type="",
                cwd="/work/project"):
    result = {
        "callId": "call-1",
        "status": status,
        "executionStatus": execution or status,
        "resultDisplay": "ok",
    }
    if error:
        result["error"] = error
    if error_type:
        result["errorType"] = error_type
    return {
        "type": "tool_result",
        "provenance": "tool_result",
        "timestamp": timestamp,
        "cwd": cwd,
        "toolCallResult": result,
        "message": {"role": "user", "parts": [{"functionResponse": {"name": "run_shell_command"}}]},
    }


def slash(raw_command, timestamp, phase="invocation", sent=True, hidden=False,
          cwd="/work/project"):
    payload = {"phase": phase, "rawCommand": raw_command}
    if phase == "invocation":
        payload["sentToModel"] = sent
        payload["hiddenInvocation"] = hidden
    return {
        "type": "system",
        "provenance": "system",
        "subtype": "slash_command",
        "timestamp": timestamp,
        "cwd": cwd,
        "systemPayload": payload,
    }


def custom_title(title, timestamp, cwd="/work/project"):
    return {
        "type": "system",
        "provenance": "system",
        "subtype": "custom_title",
        "timestamp": timestamp,
        "cwd": cwd,
        "systemPayload": {"customTitle": title, "titleSource": "prompt"},
    }


def rich_session(day="2026-10-16", cwd="/work/project"):
    """One session holding every record shape the parser must tell apart."""
    return [
        {"type": "ui_telemetry_only", "unexpected": {"nested": [1, 2]}},
        injected("<memory-tree>do not count me</memory-tree>", f"{day}T08:59:00Z", cwd=cwd),
        slash("/drain now", f"{day}T09:00:00Z", cwd=cwd),
        human("/drain now", f"{day}T09:00:01Z", cwd=cwd),
        assistant(
            f"{day}T09:00:05Z",
            [("run_shell_command", {"command": "ls"}), ("skill", {"skill": "domain-modeling"})],
            cwd=cwd,
            thought=True,
        ),
        tool_result(
            f"{day}T09:00:06Z",
            status="error",
            error="Command failed with exit code 1",
            error_type="shell_execute_error",
            cwd=cwd,
        ),
        slash("/effort medium", f"{day}T09:00:40Z", sent=False, cwd=cwd),
        human("/effort medium", f"{day}T09:00:41Z", cwd=cwd),
        tool_result(f"{day}T09:00:50Z", status="cancelled", execution="cancelled", cwd=cwd),
        injected("a second injected prompt", f"{day}T09:01:00Z", cwd=cwd),
        human("no, file it under travel instead", f"{day}T09:02:00Z", cwd=cwd),
        custom_title("Drain the travel folder", f"{day}T09:02:30Z", cwd=cwd),
        human("thanks, commit it", f"{day}T09:04:00Z", cwd=cwd),
    ]


class QwenRetrospectiveCliTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name)
        self.home = self.root / "home"
        self.install = self.home / ".qwen" / "skills" / "retrospective"
        self.install.parent.mkdir(parents=True)
        shutil.copytree(CANDIDATE, self.install)
        self.entrypoint = self.install / "scripts" / "retrospective.py"
        self.state = self.root / "state"
        self.projects = self.home / ".qwen" / "projects"
        self.project = self.root / "originating-project"
        self.project.mkdir()

    def run_cli(self, *args, env=None):
        clean_env = {
            "HOME": str(self.home),
            "PATH": os.environ.get("PATH", ""),
            "RETROSPECTIVE_STATE_DIR": str(self.state),
        }
        for name in list(os.environ):
            if name.startswith(("CLAUDE", "QWEN", "RETROSPECTIVE_")):
                clean_env.pop(name, None)
        if env:
            clean_env.update(env)
        return subprocess.run(
            [sys.executable, str(self.entrypoint), *args],
            cwd=self.root,
            env=clean_env,
            text=True,
            capture_output=True,
            check=False,
        )

    def transcript_directory(self, slug="-work-project"):
        chats = self.projects / slug / "chats"
        chats.mkdir(parents=True, exist_ok=True)
        return chats

    def write_session(self, session_id, records, folder=None, title=None, runtime=None,
                      slug="-work-project"):
        folder = folder or self.transcript_directory(slug)
        path = folder / f"{session_id}.jsonl"
        lines = []
        for record in records:
            if isinstance(record, str):
                lines.append(record)
            else:
                lines.append(json.dumps({**record, "sessionId": session_id, "uuid": f"u{len(lines)}"}))
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        if title is not None:
            (folder / f"{session_id}.title.json").write_text(
                json.dumps(title), encoding="utf-8"
            )
        if runtime is not None:
            (folder / f"{session_id}.runtime.json").write_text(
                json.dumps(runtime), encoding="utf-8"
            )
        return path

    def rule_candidate(self, **extra):
        candidate = {
            "type": "rule",
            "key": "rule:verify-contracts",
            "project": str(self.project),
            "text": "## Contract verification\n\nRun contract tests without cache.\n",
        }
        candidate.update(extra)
        return candidate

    def prepare(self, candidates, adapter="qwen"):
        args = ["prepare", "--adapter", adapter]
        for candidate in candidates:
            args.extend(["--retro-candidate", json.dumps(candidate)])
        result = self.run_cli(*args)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)["retro_candidates"]

    def digest(self, *args, **env):
        return self.run_cli("digest", "--adapter", "qwen", *args, env=env or None)

    # --- discovery and normalization ---

    def test_records_are_split_into_human_assistant_tool_and_system(self):
        today = date.today().isoformat()
        self.write_session("aaaaaaaa-1111", rich_session(today), title={"displayName": "Drain the travel folder"})

        result = self.digest("--window", "today", "--session", "aaaaaaaa")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("### aaaaaaaa · Drain the travel folder", result.stdout)
        self.assertIn("1. /drain now", result.stdout)
        self.assertIn("⚑ no, file it under travel instead", result.stdout)
        self.assertIn("thanks, commit it", result.stdout)
        self.assertNotIn("do not count me", result.stdout)
        self.assertNotIn("synthetic hidden reasoning", result.stdout)
        self.assertIn("run_shell_command×1", result.stdout)
        self.assertIn("errors: 1 · interruptions: 1", result.stdout)
        self.assertIn("shell_execute_error: Command failed with exit code 1", result.stdout)
        self.assertIn("skills: drain, domain-modeling", result.stdout)
        self.assertIn("- slash commands: /drain now, /effort medium", result.stdout)

    def test_a_local_slash_command_is_not_a_human_prompt(self):
        today = date.today().isoformat()
        records = rich_session(today)
        self.write_session("bbbbbbbb-2222", records)

        result = self.digest("--window", "today")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("· 3 prompts", result.stdout)
        self.assertIn("(partial: recorded slash commands and Skill tool calls only)", result.stdout)
        self.assertNotIn("a second injected prompt", result.stdout)

    def test_unknown_fields_and_event_subtypes_are_tolerated(self):
        today = date.today().isoformat()
        records = rich_session(today) + [
            {
                "type": "system",
                "subtype": "brand_new_signal",
                "timestamp": f"{today}T10:00:00Z",
                "cwd": "/work/project",
                "systemPayload": {"unexpected": {"deep": [{"also": "unknown"}]}},
            },
            {
                "type": "some_future_record",
                "timestamp": f"{today}T10:00:01Z",
                "cwd": "/work/project",
                "message": {"role": "unknown", "parts": [{"brand_new_part": True}]},
            },
            {
                "type": "user",
                "provenance": "a_future_origin",
                "timestamp": f"{today}T10:00:02Z",
                "cwd": "/work/project",
                "message": {"role": "user", "parts": [{"text": "not the human's own words"}]},
            },
        ]
        self.write_session("cccccccc-3333", records)

        result = self.digest("--window", "today")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("cccccccc", result.stdout)
        self.assertNotIn("not the human's own words", result.stdout)
        self.assertNotIn("brand_new_signal", result.stdout)
        self.assertNotIn("some_future_record", result.stdout)

    def test_malformed_records_and_sidecars_warn_without_hiding_the_session(self):
        today = date.today().isoformat()
        path = self.write_session(
            "dddddddd-4444",
            rich_session(today)[:6] + ["{not json at all", "[1, 2, 3]", "null"] + rich_session(today)[6:],
        )
        path.with_name("dddddddd-4444.title.json").write_text("{broken", encoding="utf-8")

        result = self.digest("--window", "today")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("dddddddd", result.stdout)
        self.assertIn("dddddddd-4444.jsonl:7: malformed JSON record skipped", result.stderr)
        self.assertIn("non-object record skipped", result.stderr)
        self.assertIn("dddddddd-4444.title.json: unreadable title metadata ignored", result.stderr)

    def test_a_session_with_no_valid_cwd_blocks_project_bound_writes(self):
        today = date.today().isoformat()
        records = [
            {**record, "cwd": "work/relative"} if isinstance(record, dict) and "cwd" in record else record
            for record in rich_session(today)
        ]
        self.write_session("eeeeeeee-5555", records)

        result = self.digest("--window", "today")

        self.assertIn("eeeeeeee", result.stdout)
        self.assertIn("originating project unavailable; project-bound writes are blocked", result.stderr)
        self.assertIn("## -work-project — ?", result.stdout)

    def test_the_earliest_valid_working_directory_wins(self):
        today = date.today().isoformat()
        records = [
            {**rich_session(today)[0], "cwd": "relative/path"},
            human("first real prompt", f"{today}T09:00:01Z", cwd=str(self.project)),
            human("moved elsewhere", f"{today}T09:00:02Z", cwd=str(self.root / "later-project")),
            human("third prompt", f"{today}T09:00:03Z", cwd=str(self.root / "later-project")),
        ]
        self.write_session("ffffffff-6666", records)

        result = self.digest("--window", "today", "--include-temp")

        self.assertIn(f"## originating-project — {self.project}", result.stdout)
        self.assertNotIn("later-project — ", result.stdout)

    def test_runtime_metadata_disagreement_is_reported_not_silently_used(self):
        today = date.today().isoformat()
        self.write_session(
            "gggggggg-7777",
            rich_session(today),
            runtime={"session_id": "gggggggg-7777", "work_dir": str(self.root / "other-place"), "pid": 42},
        )

        result = self.digest("--window", "today")

        self.assertIn("gggggggg", result.stdout)
        self.assertIn("runtime work_dir", result.stderr)
        self.assertIn("other-place", result.stderr)
        self.assertIn("## project — /work/project", result.stdout)

    def test_a_lossy_project_slug_is_never_decoded_into_a_path(self):
        ambiguous = self.root / "Users" / "x" / "work"
        ambiguous.mkdir(parents=True)
        also = self.root / "Users" / "x-work"
        also.mkdir()
        today = date.today().isoformat()
        records = [{**record, "cwd": ""} if isinstance(record, dict) and "cwd" in record else record for record in rich_session(today)]
        self.write_session("hhhhhhhh-8888", records, slug="-Users-x-work-project")

        result = self.digest("--window", "today")

        self.assertIn("hhhhhhhh", result.stdout)
        self.assertIn("-Users-x-work-project — ?", result.stdout)
        self.assertIn("originating project unavailable", result.stderr)
        prepared = self.prepare([{**self.rule_candidate(), "project": None}])
        self.assertEqual(prepared[0]["status"], "skipped")
        self.assertIn("originating project is unavailable", prepared[0]["warning"])
        self.assertFalse((ambiguous / "QWEN.md").exists())
        self.assertFalse((also / "QWEN.md").exists())

    def test_subagent_transcripts_are_not_sessions_and_add_no_human_prompts(self):
        today = date.today().isoformat()
        chats = self.transcript_directory()
        self.write_session("iiiiiiii-9999", rich_session(today))
        nested = chats.parent / "subagents" / "iiiiiiii-9999"
        nested.mkdir(parents=True)
        (nested / "agent-general-purpose-call_1.jsonl").write_text(
            "\n".join(
                json.dumps({**human("nested work", f"{today}T11:0{i}:00Z"), "sessionId": "nested"})
                for i in range(5)
            )
            + "\n",
            encoding="utf-8",
        )
        (chats / "agent-leftover.jsonl").write_text(
            "\n".join(json.dumps(human("also nested", f"{today}T12:00:0{i}Z")) for i in range(4)) + "\n",
            encoding="utf-8",
        )

        result = self.digest("--window", "today")

        self.assertIn("1 sessions across 1 projects", result.stdout)
        self.assertNotIn("nested work", result.stdout)
        self.assertNotIn("also nested", result.stdout)
        self.assertNotIn("agent-general-purpose", result.stdout)

    def test_the_process_registry_is_never_read(self):
        today = date.today().isoformat()
        self.write_session("jjjjjjjj-0000", rich_session(today))
        registry = self.home / ".qwen" / "sessions"
        registry.mkdir(parents=True)
        (registry / "4242.json").write_text(
            json.dumps(
                {
                    "pid": 4242,
                    "sessionId": "registry-only-session",
                    "cwd": "/registry/project",
                    "ipcToken": "sentinel-token",
                }
            ),
            encoding="utf-8",
        )
        unreadable = registry / "4243.json"
        unreadable.write_text("{}", encoding="utf-8")
        unreadable.chmod(0o000)

        result = self.digest("--window", "today")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("jjjjjjjj", result.stdout)
        self.assertNotIn("registry-only-session", result.stdout)
        self.assertNotIn("sentinel-token", result.stdout + result.stderr)
        self.assertNotIn("4243.json", result.stdout + result.stderr)
        unreadable.chmod(0o600)

    def test_window_project_and_temp_filters_select_sessions(self):
        today = date.today().isoformat()
        self.write_session("kkkkkkkk-1111", rich_session(today))
        self.write_session("llllllll-2222", rich_session("2000-01-01"))
        temp = Path(tempfile.gettempdir()) / "retrospective-synthetic-temp"
        self.write_session("mmmmmmmm-3333", rich_session(today, cwd=str(temp)), slug="-private-tmp-x")

        window = self.digest("--window", "today")
        self.assertIn("kkkkkkkk", window.stdout)
        self.assertNotIn("llllllll", window.stdout)
        self.assertNotIn("mmmmmmmm", window.stdout)

        filtered = self.digest("--window", "today", "--project", "other-place")
        self.assertIn("0 sessions across 0 projects", filtered.stdout)

        with_temp = self.run_cli(
            "digest", "--adapter", "qwen", "--window", "today", "--include-temp"
        )
        self.assertIn("mmmmmmmm", with_temp.stdout)

        full = self.digest("--session", "llllllll")
        self.assertIn("llllllll · ", full.stdout)

        empty = self.run_cli("digest", "--adapter", "qwen", "--window", "today", "--session", "")
        self.assertNotEqual(empty.returncode, 0)
        self.assertIn("must not be empty", empty.stderr)

    def test_an_ambiguous_session_prefix_is_refused(self):
        today = date.today().isoformat()
        self.write_session("nnnnnnnn-1111", rich_session(today))
        self.write_session("nnnnnnnn-2222", rich_session(today))

        result = self.digest("--session", "nnnnnnnn")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("ambiguous", result.stderr)

    def test_an_empty_storage_root_says_recording_may_be_disabled(self):
        result = self.digest("--window", "14d")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("0 sessions across 0 projects", result.stdout)
        self.assertIn("recording may be disabled", result.stderr)
        self.assertIn("data limitation", result.stderr)

    def test_the_runtime_output_setting_moves_the_storage_root(self):
        today = date.today().isoformat()
        redirect = self.root / "runtime-redirect"
        chats = redirect / "projects" / "-work-project" / "chats"
        chats.mkdir(parents=True)
        self.write_session("wwwwwwww-1111", rich_session(today), folder=chats)
        settings = self.home / ".qwen" / "settings.json"
        settings.parent.mkdir(parents=True, exist_ok=True)
        settings.write_text(
            json.dumps(
                {
                    "advanced": {"runtimeOutputDir": str(redirect)},
                    "env": {"ANTHROPIC_API_KEY": "not-read-by-the-adapter"},
                }
            ),
            encoding="utf-8",
        )

        result = self.digest("--window", "today")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("wwwwwwww", result.stdout)
        self.assertNotIn("not-read-by-the-adapter", result.stdout + result.stderr)

    def test_qwen_home_and_runtime_dir_move_the_storage_root(self):
        today = date.today().isoformat()
        other = self.root / "redirected" / "projects" / "-work-project" / "chats"
        other.mkdir(parents=True)
        lines = [
            json.dumps({**record, "sessionId": "oooooooo-1111"})
            for record in rich_session(today)
        ]
        (other / "oooooooo-1111.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")

        default = self.digest("--window", "today")
        self.assertNotIn("oooooooo", default.stdout)

        redirected = self.run_cli(
            "digest", "--adapter", "qwen", "--window", "today",
            env={"QWEN_RUNTIME_DIR": str(self.root / "redirected")},
        )
        self.assertIn("oooooooo", redirected.stdout)

        home = self.run_cli(
            "digest", "--adapter", "qwen", "--window", "today",
            env={"QWEN_HOME": str(self.root / "redirected")},
        )
        self.assertIn("oooooooo", home.stdout)

    # --- current identity ---

    def test_a_tool_call_that_never_ran_is_an_error_not_an_interruption(self):
        today = date.today().isoformat()
        self.write_session("vvvvvvvv-1111", [
            human("first prompt", f"{today}T09:00:00Z"),
            assistant(f"{today}T09:00:01Z", [("brand_new_tool", {})]),
            tool_result(
                f"{today}T09:00:02Z", status="error", execution="not_started",
                error_type="tool_not_registered", error="Tool brand_new_tool is not registered",
            ),
            tool_result(
                f"{today}T09:00:03Z", status="error", execution="not_started",
                error_type="execution_denied", error="The human refused this command",
            ),
            tool_result(f"{today}T09:00:04Z", status="cancelled", execution="cancelled"),
            human("keep going", f"{today}T09:00:05Z"),
            human("and now", f"{today}T09:00:06Z"),
        ])

        result = self.digest("--window", "today")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("errors: 2 · interruptions: 1", result.stdout)
        self.assertIn("- error: tool_not_registered: Tool brand_new_tool is not registered", result.stdout)
        self.assertIn("- error: execution_denied: The human refused this command", result.stdout)

    def test_current_identity_comes_from_the_native_session_environment(self):
        chats = self.transcript_directory()
        self.write_session("pppppppp-1111", rich_session())

        result = self.run_cli(
            "current-session",
            "--adapter", "qwen",
            env={
                "QWEN_CODE_SESSION_ID": "pppppppp-1111",
                "QWEN_CODE_PROJECT_DIR": str(chats.parent),
                "QWEN_CODE_STARTUP_VERSION": "0.28.3",
            },
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        identity = json.loads(result.stdout)
        self.assertEqual(identity["adapter"], "qwen")
        self.assertEqual(identity["session_id"], "pppppppp-1111")
        self.assertEqual(identity["status"], "available")
        self.assertEqual(identity["identity_source"], "environment")
        self.assertEqual(identity["qwen_version"], "0.28.3")
        self.assertEqual(Path(identity["transcript_path"]).name, "pppppppp-1111.jsonl")

    def test_the_storage_root_is_the_documented_fallback_for_the_project_pointer(self):
        chats = self.transcript_directory(slug="-elsewhere-project")
        self.write_session("qqqqqqqq-1111", rich_session(), folder=chats)

        result = self.run_cli(
            "current-session",
            "--adapter", "qwen",
            env={
                "QWEN_CODE_SESSION_ID": "qqqqqqqq-1111",
                "QWEN_CODE_PROJECT_DIR": str(self.root / "no-such-project-dir"),
            },
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        identity = json.loads(result.stdout)
        self.assertEqual(Path(identity["transcript_path"]).parent.parent.name, "-elsewhere-project")

    def test_identity_without_a_transcript_reports_the_recording_gap(self):
        result = self.run_cli(
            "current-session", "--adapter", "qwen",
            env={"QWEN_CODE_SESSION_ID": "rrrrrrrr-1111"},
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        identity = json.loads(result.stdout)
        self.assertEqual(identity["session_id"], "rrrrrrrr-1111")
        self.assertEqual(identity["status"], "available")
        self.assertEqual(identity["recording"], "absent")
        self.assertNotIn("transcript_path", identity)

    def test_a_session_id_is_opaque_and_never_a_path(self):
        escape = self.root / "outside.jsonl"
        escape.write_text(json.dumps(human("not a session", "2026-10-16T09:00:00Z")), encoding="utf-8")

        result = self.run_cli(
            "current-session", "--adapter", "qwen",
            env={"QWEN_CODE_SESSION_ID": f"..{os.sep}..{os.sep}{escape.name}"},
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        identity = json.loads(result.stdout)
        self.assertEqual(identity["status"], "available")
        self.assertNotIn("transcript_path", identity)
        exists = self.run_cli(
            "reviewed", "--adapter", "qwen", "--check",
            "--session-id", f"{self.root}/outside",
        )
        self.assertEqual(exists.returncode, 0, exists.stderr)

    def test_notes_use_the_native_identity_and_survive_its_absence(self):
        with_identity = self.run_cli(
            "note", "--adapter", "qwen",
            "--text", "Keep the rollback copy until the Library install is verified.",
            "--context", "The migration plan archives the source skill.",
            "--approve",
            env={"QWEN_CODE_SESSION_ID": "ssssssss-1111"},
        )
        self.assertEqual(with_identity.returncode, 0, with_identity.stderr)
        saved = json.loads(with_identity.stdout)
        self.assertEqual(saved["status"], "saved")
        self.assertEqual(saved["note"]["adapter"], "qwen")
        self.assertEqual(saved["note"]["session_id"], "ssssssss-1111")

        without = self.run_cli(
            "note", "--adapter", "qwen",
            "--text", "A note filed when the CLI exported no session.",
            "--context", "Identity is unavailable, the note is not.",
            "--approve",
        )
        self.assertEqual(without.returncode, 0, without.stderr)
        self.assertIsNone(json.loads(without.stdout)["note"]["session_id"])
        records = [json.loads(line) for line in (self.state / "inbox.jsonl").read_text(encoding="utf-8").splitlines()]
        self.assertEqual([record["session_id"] for record in records], ["ssssssss-1111", None])

    def test_the_runtime_environment_selects_the_qwen_adapter(self):
        for env in ({"QWEN_CODE_SESSION_ID": "tttttttt-1111"}, {"QWEN_CODE": "1"}):
            with self.subTest(env=env):
                result = self.run_cli("capabilities", env=env)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(json.loads(result.stdout)["adapter"], "qwen")

    def test_explicit_selection_overrides_the_detected_runtime(self):
        result = self.run_cli(
            "capabilities", "--adapter", "claude", env={"QWEN_CODE_SESSION_ID": "uuuuuuuu-1111"}
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["adapter"], "claude")

    # --- capabilities ---

    def test_capabilities_omit_memory_and_disclose_the_limits(self):
        result = self.run_cli("capabilities", "--adapter", "qwen")

        self.assertEqual(result.returncode, 0, result.stderr)
        capabilities = json.loads(result.stdout)
        self.assertEqual(capabilities["adapter"], "qwen")
        self.assertEqual(capabilities["supported_version"], "0.28.3")
        self.assertNotIn("memory", capabilities["destinations"])
        self.assertEqual(capabilities["unsupported_destinations"], ["memory"])
        for operation in ("current-session", "digest", "prepare", "report", "execute", "clear"):
            self.assertIn(operation, capabilities["operations"])
        self.assertEqual(
            capabilities["rule_destinations"],
            {"project": "QWEN.md", "cross_tool": "AGENTS.md", "global": "explicit user direction only"},
        )
        joined = " ".join(capabilities["disclosures"]).lower()
        self.assertIn("skill attribution is partial", joined)
        self.assertIn("custom slash command", joined)
        self.assertIn("subagent", joined)
        self.assertIn("recording", joined)
        for signal in capabilities["signals"]:
            self.assertIn(signal, ("current_session_identity", "session_titles", "slash_commands", "skill_attribution"))

    # --- destinations ---

    def test_qwen_rules_go_to_the_native_instruction_file(self):
        prepared = self.prepare([self.rule_candidate()])
        self.assertEqual(prepared[0]["status"], "ready")
        self.assertEqual(Path(prepared[0]["target"]), self.project.resolve() / "QWEN.md")

        result = self.run_cli(
            "execute", "--adapter", "qwen", "--approval", "all",
            "--retro-candidate", json.dumps(prepared[0]),
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["actions"][0]["status"], "saved")
        self.assertEqual(
            (self.project / "QWEN.md").read_text(encoding="utf-8"),
            self.rule_candidate()["text"],
        )
        self.assertFalse((self.project / "AGENTS.md").exists())
        self.assertFalse((self.project / "CLAUDE.md").exists())

    def test_a_deliberately_cross_tool_rule_names_the_shared_file(self):
        (self.project / "AGENTS.md").write_text("# Project instructions\n", encoding="utf-8")
        prepared = self.prepare([self.rule_candidate(key="rule:cross-tool", scope="cross_tool")])
        self.assertEqual(Path(prepared[0]["target"]), self.project.resolve() / "AGENTS.md")

        result = self.run_cli(
            "execute", "--adapter", "qwen", "--approval", "1",
            "--retro-candidate", json.dumps(prepared[0]),
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["actions"][0]["status"], "saved")
        self.assertIn("Run contract tests without cache.", (self.project / "AGENTS.md").read_text(encoding="utf-8"))
        self.assertFalse((self.project / "QWEN.md").exists())

    def test_a_personal_or_global_rule_needs_explicit_direction(self):
        candidate = self.rule_candidate(key="rule:global", scope="global", text="Global rule.\n")
        prepared = self.prepare([candidate])[0]
        self.assertEqual(prepared["status"], "skipped")
        self.assertIn("explicit user direction", prepared["warning"])

        result = self.run_cli(
            "execute", "--adapter", "qwen", "--approval", "1",
            "--retro-candidate", json.dumps(prepared),
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["actions"][0]["status"], "skipped")
        self.assertFalse((self.home / ".qwen" / "QWEN.md").exists())

        directed = self.prepare([dict(candidate, explicit_user_direction=True)])[0]
        self.assertEqual(Path(directed["target"]), self.home / ".qwen" / "QWEN.md")
        approved = self.run_cli(
            "execute", "--adapter", "qwen", "--approval", "1",
            "--retro-candidate", json.dumps(directed),
        )
        self.assertEqual(approved.returncode, 0, approved.stderr)
        self.assertEqual(json.loads(approved.stdout)["actions"][0]["status"], "saved")
        self.assertIn("Global rule.", (self.home / ".qwen" / "QWEN.md").read_text(encoding="utf-8"))

    def test_an_unknown_rule_scope_is_refused(self):
        prepared = self.prepare([self.rule_candidate(scope="team")])[0]
        self.assertEqual(prepared["status"], "skipped")
        self.assertIn("unsupported Rule scope: team", prepared["warning"])

    def test_memory_candidates_are_disclosed_and_never_written(self):
        memories = self.home / ".qwen" / "memories"
        memories.mkdir(parents=True)
        index = memories / "MEMORY.md"
        index.write_text("# generated index\n", encoding="utf-8")
        before = index.read_bytes()
        candidate = {
            "type": "memory",
            "key": "memory:cache-hides-schema",
            "project": str(self.project),
            "name": "cache-hides-schema",
            "description": "Cached fixtures hid a schema change twice.",
            "memory_type": "feedback",
            "text": "Re-run contract tests without cache after a schema change.",
            "why": "Cached fixtures hid the change.",
            "how_to_apply": "Use --no-cache whenever a fixture changes.",
        }

        prepared = self.prepare([candidate])[0]
        self.assertEqual(prepared["status"], "skipped")
        self.assertIn("Memory is unsupported", prepared["warning"])
        self.assertNotIn("target", prepared)

        result = self.run_cli(
            "execute", "--adapter", "qwen", "--approval", "all",
            "--retro-candidate", json.dumps(prepared),
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["actions"][0]["status"], "skipped")
        self.assertEqual(index.read_bytes(), before)
        self.assertEqual(list(memories.iterdir()), [index])
        self.assertFalse((self.project / "QWEN.md").exists())

    def test_skill_edits_use_the_canonical_source_and_refuse_upstream_copies(self):
        canonical = self.root / "canonical" / "drain" / "SKILL.md"
        canonical.parent.mkdir(parents=True)
        canonical.write_text("# Drain\n\nRun the check.\n", encoding="utf-8")
        installed = self.project / ".qwen" / "skills" / "drain" / "SKILL.md"
        installed.parent.mkdir(parents=True)
        installed.symlink_to(canonical)
        agents_dir = self.project / ".agents" / "skills" / "route" / "SKILL.md"
        agents_dir.parent.mkdir(parents=True)
        agents_dir.write_text("# Route\n\nPick the file.\n", encoding="utf-8")
        extension = self.home / ".qwen" / "extensions" / "pack" / "skills" / "grilling" / "SKILL.md"
        extension.parent.mkdir(parents=True)
        extension.write_text("# Grilling\n\nUpstream pack.\n", encoding="utf-8")
        extension_link = self.project / ".qwen" / "skills" / "grilling" / "SKILL.md"
        extension_link.parent.mkdir(parents=True)
        extension_link.symlink_to(extension)
        bundled = self.home / ".nvm" / "versions" / "node" / "node_modules" / "bundled" / "skills" / "new" / "SKILL.md"
        bundled.parent.mkdir(parents=True)
        bundled.write_text("# Bundled\n\nBuilt in.\n", encoding="utf-8")
        bundled_link = self.project / ".qwen" / "skills" / "new" / "SKILL.md"
        bundled_link.parent.mkdir(parents=True)
        bundled_link.symlink_to(bundled)
        candidates = [
            {
                "type": "skill_edit", "key": "skill:drain:fixture", "project": str(self.project),
                "name": "drain", "old": "Run the check.\n",
                "text": "Run the check with a synthetic fixture.\n",
            },
            {
                "type": "skill_edit", "key": "skill:route:agents-dir", "project": str(self.project),
                "name": "route", "old": "Pick the file.\n", "text": "Pick the file the note names.\n",
            },
            {
                "type": "skill_edit", "key": "skill:grilling:upstream", "project": str(self.project),
                "name": "grilling", "old": "Upstream pack.\n", "text": "Do not edit the pack.\n",
            },
            {
                "type": "skill_edit", "key": "skill:new:upstream", "project": str(self.project),
                "name": "new", "old": "Built in.\n", "text": "Do not edit the built-in.\n",
            },
            {
                "type": "skill_edit", "key": "skill:absent:no-blind-write", "project": str(self.project),
                "name": "absent", "old": "old", "text": "new",
            },
            {
                "type": "skill_edit", "key": "skill:retrospective:self", "project": str(self.project),
                "name": "outer/skill", "old": "old", "text": "new",
            },
        ]

        prepared = self.prepare(candidates)
        self.assertEqual(prepared[0]["status"], "ready")
        self.assertEqual(Path(prepared[0]["target"]), canonical.resolve())
        self.assertEqual(prepared[1]["status"], "ready")
        self.assertEqual(prepared[2]["status"], "upstream")
        self.assertEqual(prepared[3]["status"], "upstream")
        self.assertEqual(prepared[4]["status"], "skipped")
        self.assertIn("Skill source not found: absent", prepared[4]["warning"])
        self.assertEqual(prepared[5]["status"], "skipped")
        self.assertIn("invalid Skill name", prepared[5]["warning"])

        result = self.run_cli(
            "execute", "--adapter", "qwen", "--approval", "all",
            *[item for candidate in prepared for item in ("--retro-candidate", json.dumps(candidate))],
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            [action["status"] for action in json.loads(result.stdout)["actions"]],
            ["saved", "saved", "upstream", "upstream", "skipped", "skipped"],
        )
        self.assertEqual(canonical.read_text(encoding="utf-8"), "# Drain\n\nRun the check with a synthetic fixture.\n")
        self.assertEqual(agents_dir.read_text(encoding="utf-8"), "# Route\n\nPick the file the note names.\n")
        self.assertEqual(extension.read_text(encoding="utf-8"), "# Grilling\n\nUpstream pack.\n")
        self.assertEqual(bundled.read_text(encoding="utf-8"), "# Bundled\n\nBuilt in.\n")
        self.assertTrue(installed.is_symlink())

    def test_a_user_level_skill_source_is_the_editable_canonical(self):
        canonical = self.home / ".agents" / "skills" / "reflect" / "SKILL.md"
        canonical.parent.mkdir(parents=True)
        canonical.write_text("# Reflect\n\nAsk what changed.\n", encoding="utf-8")
        candidate = {
            "type": "skill_edit", "key": "skill:reflect:user-level", "project": str(self.project),
            "name": "reflect", "old": "Ask what changed.\n",
            "text": "Ask what changed since the last review.\n",
        }

        prepared = self.prepare([candidate])[0]
        self.assertEqual(prepared["status"], "ready")
        self.assertEqual(Path(prepared["target"]), canonical.resolve())

        result = self.run_cli(
            "execute", "--adapter", "qwen", "--approval", "1",
            "--retro-candidate", json.dumps(prepared),
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["actions"][0]["status"], "saved")
        self.assertEqual(
            canonical.read_text(encoding="utf-8"),
            "# Reflect\n\nAsk what changed since the last review.\n",
        )

    def test_the_loaded_retrospective_skill_is_never_a_destination(self):
        before = (self.install / "SKILL.md").read_bytes()
        candidate = {
            "type": "skill_edit", "key": "skill:retrospective:self",
            "project": str(self.project), "name": "retrospective",
            "old": "# Retrospective\n", "text": "Rewrite the skill from a run.\n",
        }
        (self.project / ".qwen" / "skills").mkdir(parents=True)
        (self.project / ".qwen" / "skills" / "retrospective").symlink_to(self.install)

        prepared = self.prepare([candidate])[0]
        self.assertEqual(prepared["status"], "skipped")
        self.assertIn("retrospective's own Skill is not a write destination", prepared["warning"])
        self.assertEqual((self.install / "SKILL.md").read_bytes(), before)

    def test_duplicate_and_post_report_conflict_skip_rule_writes_with_warnings(self):
        (self.project / "QWEN.md").write_text("# Project\n", encoding="utf-8")
        original = (self.project / "QWEN.md").read_text(encoding="utf-8")
        prepared = self.prepare([self.rule_candidate()])[0]
        (self.project / "QWEN.md").write_text(original + "Human edit after the report\n", encoding="utf-8")

        conflict = self.run_cli(
            "execute", "--adapter", "qwen", "--approval", "1",
            "--retro-candidate", json.dumps(prepared),
        )
        self.assertEqual(conflict.returncode, 0, conflict.stderr)
        self.assertEqual(json.loads(conflict.stdout)["actions"][0]["status"], "conflict")
        self.assertIn("changed after the report", conflict.stderr)
        self.assertEqual(
            (self.project / "QWEN.md").read_text(encoding="utf-8"),
            original + "Human edit after the report\n",
        )

        (self.project / "QWEN.md").write_text(original + self.rule_candidate()["text"], encoding="utf-8")
        duplicate = self.prepare([self.rule_candidate()])[0]
        self.assertEqual(duplicate["status"], "duplicate")
        before = (self.project / "QWEN.md").read_bytes()
        skipped = self.run_cli(
            "execute", "--adapter", "qwen", "--approval", "1",
            "--retro-candidate", json.dumps(duplicate),
        )
        self.assertEqual(json.loads(skipped.stdout)["actions"][0]["status"], "duplicate")
        self.assertEqual((self.project / "QWEN.md").read_bytes(), before)

    def test_a_rule_candidate_for_an_unknown_project_is_skipped(self):
        prepared = self.prepare([self.rule_candidate(project=str(self.root / "gone"))])[0]
        self.assertEqual(prepared["status"], "skipped")
        self.assertIn("originating project is unavailable", prepared["warning"])
        self.assertFalse((self.root / "gone").exists())

    def test_issues_run_only_through_the_fenced_github_boundary(self):
        binary = self.root / "fake-bin"
        binary.mkdir()
        git_log = self.root / "git.log"
        gh_log = self.root / "gh.log"
        git = binary / "git"
        git.write_text(
            "#!/bin/bash\n"
            "printf '%s\\n' \"$*\" >> \"$FAKE_GIT_LOG\"\n"
            "printf '%s\\n' 'https://github.com/example/originating-repo.git'\n",
            encoding="utf-8",
        )
        gh = binary / "gh"
        gh.write_text(
            f"#!{sys.executable}\n"
            "import json, os, sys\n"
            "with open(os.environ['FAKE_GH_LOG'], 'a', encoding='utf-8') as log:\n"
            "    log.write(json.dumps(sys.argv[1:]) + '\\n')\n"
            "if sys.argv[1] == 'label':\n"
            "    print(json.dumps([{'name': 'needs-triage'}]))\n"
            "elif sys.argv[1] == 'issue':\n"
            "    print('https://github.com/example/originating-repo/issues/77')\n",
            encoding="utf-8",
        )
        git.chmod(0o755)
        gh.chmod(0o755)
        env = {"PATH": str(binary), "FAKE_GIT_LOG": str(git_log), "FAKE_GH_LOG": str(gh_log)}
        candidate = {
            "type": "issue", "key": "issue:cache-hides-schema", "project": str(self.project),
            "title": "Cached fixtures hide schema changes",
            "text": "Problem: cache hid two schema changes.\n\nEvidence: qwen session aaaaaaaa.",
        }
        prepared = self.prepare([candidate])[0]
        self.assertEqual(prepared["status"], "ready")

        none = self.run_cli(
            "execute", "--adapter", "qwen", "--approval", "none",
            "--retro-candidate", json.dumps(prepared), env=env,
        )
        self.assertEqual(none.returncode, 0, none.stderr)
        self.assertFalse(git_log.exists())
        self.assertFalse(gh_log.exists())

        blanket = self.run_cli(
            "execute", "--adapter", "qwen", "--approval", "all",
            "--retro-candidate", json.dumps(prepared), env=env,
        )
        self.assertNotEqual(blanket.returncode, 0)
        self.assertIn("numeric", blanket.stderr)
        self.assertFalse(gh_log.exists())

        approved = self.run_cli(
            "execute", "--adapter", "qwen", "--approval", "1",
            "--retro-candidate", json.dumps(prepared), env=env,
        )
        self.assertEqual(approved.returncode, 0, approved.stderr)
        action = json.loads(approved.stdout)["actions"][0]
        self.assertEqual(action["status"], "saved")
        self.assertEqual(action["url"], "https://github.com/example/originating-repo/issues/77")
        self.assertIn(f"-C {self.project.resolve()} remote get-url origin", git_log.read_text(encoding="utf-8"))
        commands = [json.loads(line) for line in gh_log.read_text(encoding="utf-8").splitlines()]
        self.assertEqual(commands[0], ["label", "list", "--repo", "example/originating-repo", "--json", "name"])
        self.assertEqual(commands[1][:2], ["issue", "create"])
        self.assertIn("--label", commands[1])
        self.assertIn("needs-triage", commands[1])

    # --- report and bookkeeping ---

    def test_report_and_execute_finish_qwen_bookkeeping_on_the_shared_state(self):
        today = date.today().isoformat()
        first = self.write_session("aaaaaaaa-0001", rich_session(today))
        second_chats = self.transcript_directory(slug="-second-project")
        second = self.write_session(
            "bbbbbbbb-0002", rich_session(today, cwd=str(self.project)), folder=second_chats
        )
        note = self.run_cli(
            "note", "--adapter", "qwen",
            "--text", "Cache hid the schema change again.",
            "--context", "Two sessions in the originating project.",
            "--approve",
            env={"QWEN_CODE_SESSION_ID": "cccccccc-0003"},
        )
        self.assertEqual(note.returncode, 0, note.stderr)
        note_id = json.loads(note.stdout)["note"]["id"]

        digest = self.digest("--window", "today", "--include-temp")
        self.assertIn("aaaaaaaa", digest.stdout)
        self.assertIn("bbbbbbbb", digest.stdout)
        self.assertIn("## Retro notes (1)", digest.stdout)
        self.assertIn("Cache hid the schema change again.", digest.stdout)

        rule = self.rule_candidate(
            key="rule:no-cache",
            text="## Contract verification\n\nRun contract tests without cache.\n",
            session_ids=["aaaaaaaa-0001"],
            citations=["project · aaaaaaaa"],
        )
        reviewed_rule = self.rule_candidate(
            key="rule:reviewed-only",
            text="Must not be written.\n",
            session_ids=["bbbbbbbb-0002"],
            citations=["project · bbbbbbbb"],
        )
        declined_rule = self.rule_candidate(
            key="rule:declined-before",
            text="Never propose this again.\n",
            session_ids=["aaaaaaaa-0001"],
            citations=["project · aaaaaaaa"],
        )
        self.run_cli("reviewed", "--adapter", "qwen", "--session-id", "bbbbbbbb-0002")
        self.run_cli("declined", "--retro-candidate", "rule:declined-before")
        prepared = self.prepare([rule, reviewed_rule, declined_rule])

        insights = [
            {
                "text": f"Synthetic Insight {index}",
                "session_ids": ["aaaaaaaa-0001", "bbbbbbbb-0002"],
                "citations": ["project · aaaaaaaa", "project · bbbbbbbb"],
            }
            for index in range(1, 5)
        ]
        args = ["report", "--adapter", "qwen"]
        for insight in insights:
            args.extend(["--insight", json.dumps(insight)])
        for session_id in ("aaaaaaaa-0001", "bbbbbbbb-0002"):
            args.extend(["--digest-session-id", session_id])
        args.extend(["--digest-note-id", note_id])
        for candidate in prepared:
            args.extend(["--retro-candidate", json.dumps(candidate)])
        reported = self.run_cli(*args)
        self.assertEqual(reported.returncode, 0, reported.stderr)
        report = json.loads(reported.stdout)
        self.assertEqual([item["key"] for item in report["retro_candidates"]], ["rule:no-cache"])
        self.assertEqual(
            {item["key"] for item in report["suppressed"]},
            {"rule:reviewed-only", "rule:declined-before"},
        )
        self.assertIn("1. Rule → " + str(self.project), report["report"])

        unselected = self.rule_candidate(key="rule:unselected", text="Not approved.\n")
        candidates = report["retro_candidates"] + self.prepare([unselected])
        executed = self.run_cli(
            "execute", "--adapter", "qwen", "--approval", "1",
            *[item for candidate in candidates for item in ("--retro-candidate", json.dumps(candidate))],
            "--session-id", "aaaaaaaa-0001", "--session-id", "bbbbbbbb-0002",
            "--note-id", note_id,
        )
        self.assertEqual(executed.returncode, 0, executed.stderr)
        outcome = json.loads(executed.stdout)
        self.assertEqual([action["status"] for action in outcome["actions"]], ["saved"])
        self.assertEqual(
            (self.project / "QWEN.md").read_text(encoding="utf-8"),
            "## Contract verification\n\nRun contract tests without cache.\n",
        )
        ledger = (self.state / "reviewed.txt").read_text(encoding="utf-8").splitlines()
        self.assertEqual(ledger, ["qwen:bbbbbbbb-0002", "qwen:aaaaaaaa-0001"])
        self.assertEqual(
            (self.state / "declined.txt").read_text(encoding="utf-8").splitlines(),
            ["rule:declined-before", "rule:unselected"],
        )
        self.assertNotIn(
            note_id,
            (self.state / "inbox.jsonl").read_text(encoding="utf-8"),
        )
        self.assertTrue(first.exists() and second.exists())

    def test_a_legacy_claude_ledger_line_is_not_a_qwen_review(self):
        (self.state).mkdir(parents=True, exist_ok=True)
        ledger = self.state / "reviewed.txt"
        ledger.write_text("7c9e6679-7425-40de-944b-e07fc1f90ae7\n", encoding="utf-8")

        result = self.run_cli(
            "reviewed", "--adapter", "qwen", "--check",
            "--session-id", "7c9e6679-7425-40de-944b-e07fc1f90ae7",
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(json.loads(result.stdout)["sessions"][0]["reviewed"])
        self.assertEqual(
            ledger.read_text(encoding="utf-8"), "7c9e6679-7425-40de-944b-e07fc1f90ae7\n"
        )


if __name__ == "__main__":
    unittest.main()
