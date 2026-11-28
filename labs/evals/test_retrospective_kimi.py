"""Synthetic Kimi Code 2.7.2 sessions through the shared retrospective entrypoint.

No real conversation body, credential, generic agent resource, or retrospective state is read.
"""

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


def at(day, hour, minute, second=0):
    from datetime import datetime, timezone

    return int(datetime.fromisoformat(f"{day}T{hour:02}:{minute:02}:{second:02}+00:00").replace(tzinfo=timezone.utc).timestamp() * 1000)


def prompt(text, moment, kind="user", **origin_fields):
    return {
        "type": "turn.prompt",
        "input": [{"type": "text", "text": text}],
        "origin": {"kind": kind, **origin_fields},
        "time": moment,
    }


def message(role, moment, text="synthetic message", **fields):
    return {
        "type": "context.append_message",
        "message": {
            "role": role,
            "content": [{"type": "text", "text": text}],
            **fields,
        },
        "time": moment,
    }


def three_prompts(day):
    return [
        prompt("first synthetic prompt", at(day, 9, 0)),
        message("assistant", at(day, 9, 1), "first synthetic answer"),
        prompt("second synthetic prompt", at(day, 9, 2)),
        message("assistant", at(day, 9, 3), "second synthetic answer"),
        prompt("third synthetic prompt", at(day, 9, 4)),
    ]


class KimiRetrospectiveCliTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name)
        self.home = self.root / "home"
        self.kimi_home = self.home / ".kimi-code"
        self.install = self.kimi_home / "skills" / "retrospective"
        self.install.parent.mkdir(parents=True)
        shutil.copytree(CANDIDATE, self.install)
        self.entrypoint = self.install / "scripts" / "retrospective.py"
        self.state = self.root / "state"
        self.project = self.root / "originating-project"
        self.project.mkdir()

    def run_cli(self, *args, env=None):
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
            text=True,
            capture_output=True,
            check=False,
        )

    def write_session(self, session_id, records, workspace="wd_native", title="Synthetic Kimi", cwd=None, indexed=True):
        directory = self.kimi_home / "sessions" / workspace / session_id
        wire = directory / "agents" / "main" / "wire.jsonl"
        wire.parent.mkdir(parents=True)
        wire.write_text("\n".join(json.dumps(record) for record in records) + "\n", encoding="utf-8")
        cwd = cwd or str(self.project)
        (directory / "state.json").write_text(json.dumps({
            "createdAt": "2026-01-01T09:00:00.000Z",
            "updatedAt": "2026-01-01T10:00:00.000Z",
            "title": title,
            "cwd": cwd,
        }), encoding="utf-8")
        if indexed:
            with (self.kimi_home / "session_index.jsonl").open("a", encoding="utf-8") as index:
                index.write(json.dumps({
                    "sessionId": session_id,
                    "sessionDir": str(directory),
                    "workDir": cwd,
                }) + "\n")
        return wire

    def rule_candidate(self, **extra):
        candidate = {
            "type": "rule",
            "key": "rule:verify-native-events",
            "project": str(self.project),
            "text": "## Native verification\n\nParse only explicit human-origin events.\n",
        }
        candidate.update(extra)
        return candidate

    def prepare(self, candidates):
        args = ["prepare", "--adapter", "kimi"]
        for candidate in candidates:
            args.extend(["--retro-candidate", json.dumps(candidate)])
        result = self.run_cli(*args)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)["retro_candidates"]

    def test_native_environment_supplies_complete_current_identity(self):
        result = self.run_cli(
            "current-session",
            env={
                "KIMI_CODE_SESSION_ID": "session_opaque/full-id",
                "KIMI_CODE_WORKSPACE_ID": "wd_workspace_opaque",
            },
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        identity = json.loads(result.stdout)
        self.assertEqual(identity["adapter"], "kimi")
        self.assertEqual(identity["session_id"], "session_opaque/full-id")
        self.assertEqual(identity["workspace_id"], "wd_workspace_opaque")
        self.assertEqual(identity["status"], "available")
        self.assertEqual(identity["identity_source"], "environment")

    def test_native_index_discovers_main_wire_and_separates_event_origins(self):
        from datetime import date

        today = date.today().isoformat()
        records = [
            {"type": "metadata", "protocol_version": "1.5", "created_at": at(today, 8, 59)},
            {"type": "future.event", "future": {"unknown": True}, "time": at(today, 8, 59, 30)},
            prompt("inspect the synthetic contract", at(today, 9, 0)),
            message("user", at(today, 9, 0, 1), "inspect the synthetic contract"),
            {
                "type": "skill.activated", "skillName": "retrospective",
                "activationId": "activation-1", "trigger": "user-slash", "time": at(today, 9, 0, 2),
            },
            message("assistant", at(today, 9, 1), "checking", toolCalls=[{
                "id": "call-1", "name": "Bash", "arguments": "{\"command\":\"true\"}",
            }]),
            message("tool", at(today, 9, 2), "synthetic failure", isError=True, toolCallId="call-1"),
            prompt("an injected task prompt", at(today, 9, 3), kind="task", taskId="task-1"),
            prompt("an injection", at(today, 9, 4), kind="injection", variant="system-reminder"),
            prompt("skill body, not human input", at(today, 9, 5), kind="skill_activation", skillName="retrospective"),
            prompt("no, test the native boundary", at(today, 9, 6)),
            {"type": "subagent.spawned", "subagentId": "agent-0", "time": at(today, 9, 7)},
            {"type": "subagent.completed", "subagentId": "agent-0", "resultSummary": "nested", "time": at(today, 9, 8)},
            {"type": "turn.ended", "reason": "cancelled", "time": at(today, 9, 9)},
            prompt("file the evidence", at(today, 9, 10)),
        ]
        self.write_session("session-native-1234", records)

        result = self.run_cli(
            "digest", "--adapter", "kimi", "--window", "today", "--include-temp",
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("1 sessions across 1 projects", result.stdout)
        self.assertIn("session-native-1234", result.stdout)
        self.assertIn("workspace-id: wd_native", result.stdout)
        self.assertIn("3 prompts", result.stdout)
        self.assertIn("skills: retrospective", result.stdout)
        self.assertIn("Bash×1", result.stdout)
        self.assertIn("errors: 1 · interruptions: 1", result.stdout)
        self.assertIn("no, test the native boundary", result.stdout)
        for excluded in ("an injected task prompt", "an injection", "skill body", "nested"):
            self.assertNotIn(excluded, result.stdout)

    def test_storage_fallback_recovers_unindexed_sessions_and_warns_about_malformed_data(self):
        from datetime import date

        today = date.today().isoformat()
        wire = self.write_session("fallback-session-5678", three_prompts(today), indexed=False)
        with wire.open("a", encoding="utf-8") as stream:
            stream.write("{broken json\n[]\n")
        index = self.kimi_home / "session_index.jsonl"
        index.write_text('{broken\n[]\n{"sessionId":"outside","sessionDir":"/outside"}\n', encoding="utf-8")
        nested = wire.parents[1] / "agent-0" / "wire.jsonl"
        nested.parent.mkdir()
        nested.write_text(json.dumps(prompt("subagent human-looking prompt", at(today, 10, 0))) + "\n", encoding="utf-8")

        result = self.run_cli(
            "digest", "--adapter", "kimi", "--window", "today", "--include-temp",
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("fallback-session-5678", result.stdout)
        self.assertIn("1 sessions across 1 projects", result.stdout)
        self.assertNotIn("subagent human-looking prompt", result.stdout)
        self.assertIn("malformed JSON session metadata skipped", result.stderr)
        self.assertIn("non-object session metadata skipped", result.stderr)
        self.assertIn("incomplete or unsafe session metadata skipped", result.stderr)
        self.assertIn("malformed JSON event skipped", result.stderr)
        self.assertIn("non-object event skipped", result.stderr)

    def test_current_identity_finds_only_the_exact_native_session(self):
        from datetime import date

        wire = self.write_session("session-current-1234", three_prompts(date.today().isoformat()))
        found = self.run_cli(
            "current-session", "--adapter", "kimi",
            env={"KIMI_CODE_SESSION_ID": "session-current-1234", "KIMI_CODE_WORKSPACE_ID": "wd_native"},
        )
        self.assertEqual(found.returncode, 0, found.stderr)
        identity = json.loads(found.stdout)
        self.assertEqual(Path(identity["transcript_path"]), wire.resolve())
        self.assertEqual(identity["workspace_id"], "wd_native")

        outside = self.root / "outside.jsonl"
        outside.write_text("not a native session", encoding="utf-8")
        missing = self.run_cli(
            "current-session", "--adapter", "kimi",
            env={"KIMI_CODE_SESSION_ID": "../../outside"},
        )
        self.assertEqual(missing.returncode, 0, missing.stderr)
        self.assertNotIn("transcript_path", json.loads(missing.stdout))

    def test_capabilities_disclose_native_writes_and_omit_memory(self):
        result = self.run_cli("capabilities", "--adapter", "kimi")

        self.assertEqual(result.returncode, 0, result.stderr)
        capabilities = json.loads(result.stdout)
        self.assertEqual(capabilities["supported_version"], "2.7.2")
        self.assertNotIn("memory", capabilities["destinations"])
        self.assertEqual(capabilities["unsupported_destinations"], ["memory"])
        self.assertEqual(
            capabilities["rule_destinations"],
            {
                "project": ".kimi-code/AGENTS.md",
                "cross_tool": "AGENTS.md",
                "global": "explicit user direction only",
            },
        )
        disclosures = " ".join(capabilities["disclosures"]).lower()
        self.assertIn("durable observations", disclosures)
        self.assertIn("not instructions", disclosures)
        self.assertIn("subagent", disclosures)
        self.assertIn("print sessions", disclosures)

    def test_approved_native_and_cross_tool_rules_land_in_their_own_destinations(self):
        native, cross_tool = self.prepare([
            self.rule_candidate(),
            self.rule_candidate(key="rule:cross-tool", scope="cross_tool", text="Shared by every tool.\n"),
        ])
        self.assertEqual(Path(native["target"]), self.project.resolve() / ".kimi-code" / "AGENTS.md")
        self.assertEqual(Path(cross_tool["target"]), self.project.resolve() / "AGENTS.md")

        result = self.run_cli(
            "execute", "--adapter", "kimi", "--approval", "all",
            "--retro-candidate", json.dumps(native),
            "--retro-candidate", json.dumps(cross_tool),
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual([a["status"] for a in json.loads(result.stdout)["actions"]], ["saved", "saved"])
        self.assertIn("Parse only explicit human-origin events.", (self.project / ".kimi-code" / "AGENTS.md").read_text(encoding="utf-8"))
        self.assertEqual((self.project / "AGENTS.md").read_text(encoding="utf-8"), "Shared by every tool.\n")
        self.assertFalse((self.project / "CLAUDE.md").exists())
        self.assertFalse((self.project / "QWEN.md").exists())

    def test_skill_edits_resolve_canonical_sources_and_refuse_upstream(self):
        canonical = self.root / "canonical" / "drain" / "SKILL.md"
        canonical.parent.mkdir(parents=True)
        canonical.write_text("# Drain\n\nRun the native check.\n", encoding="utf-8")
        installed = self.project / ".kimi-code" / "skills" / "drain" / "SKILL.md"
        installed.parent.mkdir(parents=True)
        installed.symlink_to(canonical)
        upstream = self.kimi_home / "plugins" / "managed" / "pack" / "skills" / "grilling" / "SKILL.md"
        upstream.parent.mkdir(parents=True)
        upstream.write_text("# Upstream\n", encoding="utf-8")
        upstream_link = self.project / ".agents" / "skills" / "grilling" / "SKILL.md"
        upstream_link.parent.mkdir(parents=True)
        upstream_link.symlink_to(upstream)
        candidates = [
            {
                "type": "skill_edit", "key": "skill:drain:native", "project": str(self.project),
                "name": "drain", "old": "Run the native check.\n", "text": "Run the native check with fixtures.\n",
            },
            {
                "type": "skill_edit", "key": "skill:grilling:upstream", "project": str(self.project),
                "name": "grilling", "old": "# Upstream\n", "text": "Never written.\n",
            },
            {
                "type": "skill_edit", "key": "skill:absent", "project": str(self.project),
                "name": "absent", "old": "old", "text": "new",
            },
        ]

        prepared = self.prepare(candidates)
        self.assertEqual(Path(prepared[0]["target"]), canonical.resolve())
        self.assertEqual(prepared[1]["status"], "upstream")
        self.assertEqual(prepared[2]["status"], "skipped")
        result = self.run_cli(
            "execute", "--adapter", "kimi", "--approval", "all",
            *[item for candidate in prepared for item in ("--retro-candidate", json.dumps(candidate))],
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual([a["status"] for a in json.loads(result.stdout)["actions"]], ["saved", "upstream", "skipped"])
        self.assertEqual(canonical.read_text(encoding="utf-8"), "# Drain\n\nRun the native check with fixtures.\n")
        self.assertEqual(upstream.read_text(encoding="utf-8"), "# Upstream\n")
        self.assertTrue(installed.is_symlink())

    def test_issues_require_numeric_approval_and_stay_behind_a_fake_boundary(self):
        binary = self.root / "fake-bin"
        binary.mkdir()
        git_log = self.root / "git.log"
        gh_log = self.root / "gh.log"
        git = binary / "git"
        git.write_text(
            "#!/bin/bash\nprintf '%s\\n' \"$*\" >> \"$FAKE_GIT_LOG\"\n"
            "printf '%s\\n' 'https://github.com/example/originating-repo.git'\n",
            encoding="utf-8",
        )
        gh = binary / "gh"
        gh.write_text(
            f"#!{sys.executable}\nimport json, os, sys\n"
            "with open(os.environ['FAKE_GH_LOG'], 'a', encoding='utf-8') as log:\n"
            "    log.write(json.dumps(sys.argv[1:]) + '\\n')\n"
            "if sys.argv[1] == 'label': print(json.dumps([{'name': 'needs-triage'}]))\n"
            "elif sys.argv[1] == 'issue': print('https://github.com/example/originating-repo/issues/34')\n",
            encoding="utf-8",
        )
        git.chmod(0o755)
        gh.chmod(0o755)
        env = {"PATH": str(binary), "FAKE_GIT_LOG": str(git_log), "FAKE_GH_LOG": str(gh_log)}
        prepared = self.prepare([{
            "type": "issue", "key": "issue:native-events", "project": str(self.project),
            "title": "Native events need an explicit origin",
            "text": "Problem: role alone is insufficient. Evidence: synthetic Kimi session.",
        }])[0]

        none = self.run_cli(
            "execute", "--adapter", "kimi", "--approval", "none",
            "--retro-candidate", json.dumps(prepared), env=env,
        )
        self.assertEqual(none.returncode, 0, none.stderr)
        self.assertFalse(git_log.exists())
        self.assertFalse(gh_log.exists())
        blanket = self.run_cli(
            "execute", "--adapter", "kimi", "--approval", "all",
            "--retro-candidate", json.dumps(prepared), env=env,
        )
        self.assertNotEqual(blanket.returncode, 0)
        self.assertFalse(gh_log.exists())

        approved = self.run_cli(
            "execute", "--adapter", "kimi", "--approval", "1",
            "--retro-candidate", json.dumps(prepared), env=env,
        )
        self.assertEqual(approved.returncode, 0, approved.stderr)
        action = json.loads(approved.stdout)["actions"][0]
        self.assertEqual(action["status"], "saved")
        self.assertEqual(action["url"], "https://github.com/example/originating-repo/issues/34")
        commands = [json.loads(line) for line in gh_log.read_text(encoding="utf-8").splitlines()]
        self.assertEqual(commands[1][:2], ["issue", "create"])
        self.assertIn("needs-triage", commands[1])

    def test_memory_and_undirected_global_writes_are_refused(self):
        memory = self.prepare([{
            "type": "memory", "key": "memory:durable-observation", "project": str(self.project),
            "name": "durable-observation", "description": "Synthetic observation.",
            "memory_type": "project", "text": "This must not become an instruction.",
            "why": "Kimi has no supported durable memory destination.", "how_to_apply": "Do not write it.",
        }])[0]
        global_rule = self.prepare([self.rule_candidate(key="rule:global", scope="global")])[0]
        self.assertEqual(memory["status"], "skipped")
        self.assertIn("Memory is unsupported", memory["warning"])
        self.assertEqual(global_rule["status"], "skipped")
        self.assertIn("explicit user direction", global_rule["warning"])

        result = self.run_cli(
            "execute", "--adapter", "kimi", "--approval", "all",
            "--retro-candidate", json.dumps(memory),
            "--retro-candidate", json.dumps(global_rule),
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual([a["status"] for a in json.loads(result.stdout)["actions"]], ["skipped", "skipped"])
        self.assertFalse((self.kimi_home / "AGENTS.md").exists())
        self.assertFalse((self.project / ".kimi-code" / "AGENTS.md").exists())

    def test_notes_carry_native_workspace_identity_and_survive_without_it(self):
        saved = self.run_cli(
            "note", "--text", "Keep native workspace identity.",
            "--context", "The note must remain attributable to its Kimi session.", "--approve",
            env={
                "KIMI_CODE_SESSION_ID": "session_opaque/full-id",
                "KIMI_CODE_WORKSPACE_ID": "wd_workspace_opaque",
            },
        )
        self.assertEqual(saved.returncode, 0, saved.stderr)
        note = json.loads(saved.stdout)["note"]
        self.assertEqual(note["adapter"], "kimi")
        self.assertEqual(note["session_id"], "session_opaque/full-id")
        self.assertEqual(note["workspace_id"], "wd_workspace_opaque")

        without = self.run_cli(
            "note", "--adapter", "kimi", "--text", "File without a session.",
            "--context", "Unavailable identity does not discard an explicit note.", "--approve",
        )
        self.assertEqual(without.returncode, 0, without.stderr)
        self.assertIsNone(json.loads(without.stdout)["note"]["session_id"])

    def test_report_numeric_approval_and_bookkeeping_use_complete_kimi_identity(self):
        from datetime import date

        today = date.today().isoformat()
        self.write_session("session-evidence-0001", three_prompts(today))
        self.write_session("session-evidence-0002", three_prompts(today), workspace="wd_second")
        noted = self.run_cli(
            "note", "--adapter", "kimi", "--text", "Native origins must stay distinct.",
            "--context", "Two synthetic sessions support this rule.", "--approve",
            env={"KIMI_CODE_SESSION_ID": "session-note-0003", "KIMI_CODE_WORKSPACE_ID": "wd_note"},
        )
        note_id = json.loads(noted.stdout)["note"]["id"]
        digest = self.run_cli("digest", "--adapter", "kimi", "--window", "today", "--include-temp")
        self.assertIn("session-evidence-0001", digest.stdout)
        self.assertIn("session-evidence-0002", digest.stdout)
        self.assertIn(note_id, digest.stdout)

        rule = self.rule_candidate(
            session_ids=["session-evidence-0001"], note_ids=[note_id],
            citations=["project · session-evidence-0001", note_id],
        )
        reviewed_rule = self.rule_candidate(
            key="rule:reviewed-only", text="Do not write this.\n",
            session_ids=["session-evidence-0002"], citations=["project · session-evidence-0002"],
        )
        self.run_cli("reviewed", "--adapter", "kimi", "--session-id", "session-evidence-0002")
        prepared = self.prepare([rule, reviewed_rule])
        args = ["report", "--adapter", "kimi"]
        for index in range(4):
            args.extend(["--insight", json.dumps({
                "text": f"Synthetic Insight {index}",
                "session_ids": ["session-evidence-0001", "session-evidence-0002"],
                "citations": ["project · session-evidence-0001", "second · session-evidence-0002"],
            })])
        for session_id in ("session-evidence-0001", "session-evidence-0002"):
            args.extend(["--digest-session-id", session_id])
        args.extend(["--digest-note-id", note_id])
        for candidate in prepared:
            args.extend(["--retro-candidate", json.dumps(candidate)])
        reported = self.run_cli(*args)
        self.assertEqual(reported.returncode, 0, reported.stderr)
        report = json.loads(reported.stdout)
        self.assertEqual([c["key"] for c in report["retro_candidates"]], ["rule:verify-native-events"])
        self.assertEqual(report["suppressed"][0]["reason"], "reviewed sessions inform Insights only")

        unselected = self.prepare([self.rule_candidate(key="rule:declined", text="Not selected.\n")])
        executed = self.run_cli(
            "execute", "--adapter", "kimi", "--approval", "1",
            *[item for candidate in report["retro_candidates"] + unselected for item in ("--retro-candidate", json.dumps(candidate))],
            "--session-id", "session-evidence-0001", "--session-id", "session-evidence-0002",
            "--note-id", note_id,
        )
        self.assertEqual(executed.returncode, 0, executed.stderr)
        outcome = json.loads(executed.stdout)
        self.assertEqual(outcome["actions"][0]["status"], "saved")
        reviewed = (self.state / "reviewed.txt").read_text(encoding="utf-8").splitlines()
        self.assertIn("kimi:session-evidence-0001", reviewed)
        self.assertIn("kimi:session-evidence-0002", reviewed)
        self.assertTrue(all(len(line.split(":", 1)[1]) > 8 for line in reviewed))
        self.assertIn("rule:declined", (self.state / "declined.txt").read_text(encoding="utf-8"))
        self.assertNotIn(note_id, (self.state / "inbox.jsonl").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
