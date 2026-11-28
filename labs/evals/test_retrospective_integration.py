import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import date

from labs.evals.test_retrospective_claude import assistant, tool_result, user


ROOT = Path(__file__).resolve().parents[2]
CANDIDATE = ROOT / "labs" / "retrospective"


class RetrospectiveWorkflowIntegrationTest(unittest.TestCase):
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
        self.project = self.root / "originating-project"
        self.project.mkdir()
        (self.project / "AGENTS.md").write_text("# Project instructions\n", encoding="utf-8")

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

    def retro_candidate_args(self, retro_candidates):
        args = []
        for retro_candidate in retro_candidates:
            args.extend(["--retro-candidate", json.dumps(retro_candidate)])
        return args

    def create_session(self, session_id="aaaaaaaa-0001"):
        today = date.today().isoformat()
        folder = self.home / ".claude" / "projects" / "origin"
        folder.mkdir(parents=True, exist_ok=True)
        records = [
            user("check the contract tests", f"{today}T09:00:00Z", cwd=str(self.project)),
            assistant(f"{today}T09:00:01Z", cwd=str(self.project)),
            tool_result(f"{today}T09:00:02Z", cwd=str(self.project)),
            user("no, disable the cache", f"{today}T09:01:00Z", cwd=str(self.project)),
            user("thanks", f"{today}T09:02:00Z", cwd=str(self.project)),
        ]
        (folder / f"{session_id}.jsonl").write_text(
            "\n".join(json.dumps(record) for record in records) + "\n",
            encoding="utf-8",
        )
        return session_id

    def memory_retro_candidate(self):
        return {
            "type": "memory",
            "key": "memory:contract-tests-no-cache",
            "project": str(self.project),
            "name": "contract-tests-no-cache",
            "title": "Contract tests without cache",
            "description": "Run contract tests without cache after schema changes.",
            "memory_type": "feedback",
            "text": "Run the contract tests with --no-cache after schema changes.",
            "why": "Cached fixtures hid the schema change twice.",
            "how_to_apply": "Use --no-cache whenever a contract fixture changes.",
        }

    def rule_retro_candidate(self):
        return {
            "type": "rule",
            "key": "rule:contract-tests-no-cache",
            "project": str(self.project),
            "text": "## Contract verification\n\nRun contract tests with --no-cache after schema changes.\n",
        }

    def prepare(self, retro_candidates):
        result = self.run_cli(
            "prepare", "--adapter", "claude", *self.retro_candidate_args(retro_candidates)
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)["retro_candidates"]

    def report(self, insights, retro_candidates):
        args = ["report", "--adapter", "claude"]
        for insight in insights:
            args.extend(["--insight", json.dumps(insight)])
        digest_session_ids = {
            session_id for insight in insights for session_id in insight["session_ids"]
        }
        for session_id in sorted(digest_session_ids):
            args.extend(["--digest-session-id", session_id])
        result = self.run_cli(*args, *self.retro_candidate_args(retro_candidates))
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def insights(self, session_ids=("aaaaaaaa-0001", "bbbbbbbb-0002")):
        return [
            {
                "text": f"Synthetic cross-session Insight {index}",
                "citations": [f"project · {session_id[:8]}" for session_id in session_ids],
                "session_ids": list(session_ids),
            }
            for index in range(1, 5)
        ]

    def test_report_suppresses_reviewed_only_and_declined_retro_candidates(self):
        self.create_session("active-session")
        self.create_session("reviewed-session")
        reviewed = self.run_cli(
            "reviewed", "--adapter", "claude", "--session-id", "reviewed-session"
        )
        self.assertEqual(reviewed.returncode, 0, reviewed.stderr)
        active = self.rule_retro_candidate()
        active.update(
            key="rule:active",
            text="Active exact proposed text.\n",
            session_ids=["active-session"],
            citations=["project · active-s"],
        )
        reviewed_only = self.rule_retro_candidate()
        reviewed_only.update(
            key="rule:reviewed-only",
            text="Reviewed-only text must not appear.\n",
            session_ids=["reviewed-session"],
            citations=["project · reviewed"],
        )
        declined = self.rule_retro_candidate()
        declined.update(
            key="rule:declined-before",
            text="Declined text must not appear.\n",
            session_ids=["active-session"],
            citations=["project · active-s"],
        )
        recorded = self.run_cli(
            "declined", "--retro-candidate", "rule:declined-before"
        )
        self.assertEqual(recorded.returncode, 0, recorded.stderr)
        prepared = self.prepare([active, reviewed_only, declined])

        result = self.report(
            self.insights(("active-session", "reviewed-session")), prepared
        )

        self.assertEqual(len(result["retro_candidates"]), 1)
        self.assertEqual(result["retro_candidates"][0]["key"], "rule:active")
        self.assertEqual(
            {item["key"] for item in result["suppressed"]},
            {"rule:reviewed-only", "rule:declined-before"},
        )
        report = result["report"]
        self.assertEqual(report.count("Synthetic cross-session Insight"), 4)
        self.assertIn("project · active-s", report)
        self.assertIn("1. Rule", report)
        self.assertIn("Active exact proposed text.", report)
        self.assertNotIn("Reviewed-only text must not appear.", report)
        self.assertNotIn("Declined text must not appear.", report)
        self.assertTrue(report.endswith("Reply with numbers (e.g. 1 3), all, or none."))

    def test_report_rejects_fewer_than_four_cross_session_insights(self):
        self.create_session("aaaaaaaa-0001")
        self.create_session("bbbbbbbb-0002")
        retro_candidate = self.rule_retro_candidate()
        retro_candidate.update(
            session_ids=["aaaaaaaa-0001"], citations=["project · aaaaaaaa"]
        )
        prepared = self.prepare([retro_candidate])[0]
        args = [
            "report",
            "--adapter",
            "claude",
            "--digest-session-id",
            "aaaaaaaa-0001",
            "--digest-session-id",
            "bbbbbbbb-0002",
        ]
        for insight in self.insights()[:3]:
            args.extend(["--insight", json.dumps(insight)])
        args.extend(["--retro-candidate", json.dumps(prepared)])

        result = self.run_cli(*args)

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("4–6", result.stderr)

    def test_report_rejects_duplicate_non_digest_and_uncited_evidence(self):
        self.create_session("aaaaaaaa-0001")
        self.create_session("bbbbbbbb-0002")
        base = self.rule_retro_candidate()
        base.update(
            session_ids=["aaaaaaaa-0001"], citations=["project · aaaaaaaa"]
        )
        prepared = self.prepare([base])[0]

        def run_report(insights, retro_candidate):
            args = [
                "report",
                "--adapter",
                "claude",
                "--digest-session-id",
                "aaaaaaaa-0001",
                "--digest-session-id",
                "bbbbbbbb-0002",
            ]
            for insight in insights:
                args.extend(["--insight", json.dumps(insight)])
            args.extend(["--retro-candidate", json.dumps(retro_candidate)])
            return self.run_cli(*args)

        cases = [
            (self.insights(("aaaaaaaa-0001", "aaaaaaaa-0001")), prepared, "distinct"),
            (self.insights(("aaaaaaaa-0001", "cccccccc-0003")), prepared, "digest"),
            (
                self.insights(),
                {**prepared, "citations": ["project · unrelated"]},
                "citation",
            ),
            (self.insights(), {**prepared, "citations": []}, "citation"),
        ]
        for insights, retro_candidate, message in cases:
            with self.subTest(message=message, insights=insights[0]["session_ids"]):
                result = run_report(insights, retro_candidate)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(message, result.stderr.lower())

    def test_all_and_none_approvals_apply_the_whole_decision_once(self):
        rule = self.prepare([self.rule_retro_candidate()])[0]

        approved = self.run_cli(
            "execute",
            "--adapter",
            "claude",
            "--approval",
            "all",
            "--retro-candidate",
            json.dumps(rule),
        )
        self.assertEqual(approved.returncode, 0, approved.stderr)
        self.assertEqual(json.loads(approved.stdout)["actions"][0]["status"], "saved")
        expected = "# Project instructions\n\n" + self.rule_retro_candidate()["text"]
        self.assertEqual((self.project / "AGENTS.md").read_text(encoding="utf-8"), expected)
        self.assertFalse((self.project / "CLAUDE.md").exists())

        other = self.rule_retro_candidate()
        other["key"] = "rule:do-not-write"
        other["text"] = "Do not write this unapproved rule.\n"
        prepared = self.prepare([other])[0]
        declined = self.run_cli(
            "execute",
            "--adapter",
            "claude",
            "--approval",
            "none",
            "--retro-candidate",
            json.dumps(prepared),
        )
        self.assertEqual(declined.returncode, 0, declined.stderr)
        self.assertEqual(json.loads(declined.stdout)["actions"], [])
        self.assertNotIn("Do not write", (self.project / "AGENTS.md").read_text(encoding="utf-8"))
        self.assertIn(
            "rule:do-not-write",
            (self.state / "declined.txt").read_text(encoding="utf-8").splitlines(),
        )

    def test_rule_falls_back_to_claude_md_and_unknown_origin_blocks_writes(self):
        (self.project / "AGENTS.md").unlink()
        prepared = self.prepare([self.rule_retro_candidate()])[0]
        self.assertEqual(Path(prepared["target"]), (self.project / "CLAUDE.md").resolve())

        result = self.run_cli(
            "execute",
            "--adapter",
            "claude",
            "--approval",
            "all",
            "--retro-candidate",
            json.dumps(prepared),
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            (self.project / "CLAUDE.md").read_text(encoding="utf-8"),
            self.rule_retro_candidate()["text"],
        )
        self.assertFalse((self.project / "AGENTS.md").exists())

        unknown = self.rule_retro_candidate()
        unknown["project"] = str(self.root / "missing-origin")
        skipped = self.prepare([unknown])[0]
        self.assertEqual(skipped["status"], "skipped")
        self.assertIn("originating project is unavailable", skipped["warning"])
        self.assertFalse((self.root / "missing-origin").exists())

    def test_duplicate_and_post_report_conflict_skip_rule_writes_with_warnings(self):
        original = (self.project / "AGENTS.md").read_text(encoding="utf-8")
        rule = self.prepare([self.rule_retro_candidate()])[0]
        (self.project / "AGENTS.md").write_text(original + "Human edit after report\n", encoding="utf-8")

        conflict = self.run_cli(
            "execute",
            "--adapter",
            "claude",
            "--approval",
            "all",
            "--retro-candidate",
            json.dumps(rule),
        )
        self.assertEqual(conflict.returncode, 0, conflict.stderr)
        self.assertEqual(json.loads(conflict.stdout)["actions"][0]["status"], "conflict")
        self.assertIn("changed after the report", conflict.stderr)
        self.assertEqual(
            (self.project / "AGENTS.md").read_text(encoding="utf-8"),
            original + "Human edit after report\n",
        )

        (self.project / "AGENTS.md").write_text(
            original + "\n" + self.rule_retro_candidate()["text"], encoding="utf-8"
        )
        duplicate = self.prepare([self.rule_retro_candidate()])[0]
        self.assertEqual(duplicate["status"], "duplicate")
        before = (self.project / "AGENTS.md").read_bytes()
        skipped = self.run_cli(
            "execute",
            "--adapter",
            "claude",
            "--approval",
            "all",
            "--retro-candidate",
            json.dumps(duplicate),
        )
        self.assertEqual(json.loads(skipped.stdout)["actions"][0]["status"], "duplicate")
        self.assertEqual((self.project / "AGENTS.md").read_bytes(), before)

    def test_skill_edit_resolves_symlink_and_refuses_upstream_and_missing_sources(self):
        canonical = self.root / "canonical" / "drain" / "SKILL.md"
        canonical.parent.mkdir(parents=True)
        canonical.write_text("# Drain\n\nRun the check.\n", encoding="utf-8")
        installed = self.project / ".claude" / "skills" / "drain" / "SKILL.md"
        installed.parent.mkdir(parents=True)
        installed.symlink_to(canonical)
        upstream = self.home / ".claude" / "plugins" / "mattpocock" / "grilling" / "SKILL.md"
        upstream.parent.mkdir(parents=True)
        upstream.write_text("# Grilling\n\nUpstream source.\n", encoding="utf-8")
        upstream_link = self.project / ".claude" / "skills" / "grilling" / "SKILL.md"
        upstream_link.parent.mkdir(parents=True)
        upstream_link.symlink_to(upstream)
        extension = self.home / ".claude" / "extensions" / "example" / "extend" / "SKILL.md"
        extension.parent.mkdir(parents=True)
        extension.write_text("# Extension\n\nUpstream extension.\n", encoding="utf-8")
        extension_link = self.project / ".claude" / "skills" / "extend" / "SKILL.md"
        extension_link.parent.mkdir(parents=True)
        extension_link.symlink_to(extension)
        retro_candidates = [
            {
                "type": "skill_edit",
                "key": "skill:drain:fixture-check",
                "project": str(self.project),
                "name": "drain",
                "old": "Run the check.\n",
                "text": "Run the check with a synthetic fixture.\n",
            },
            {
                "type": "skill_edit",
                "key": "skill:grilling:upstream",
                "project": str(self.project),
                "name": "grilling",
                "old": "Upstream source.\n",
                "text": "Do not edit the plugin cache.\n",
            },
            {
                "type": "skill_edit",
                "key": "skill:missing:no-blind-write",
                "project": str(self.project),
                "name": "missing",
                "old": "old",
                "text": "new",
            },
            {
                "type": "skill_edit",
                "key": "skill:extend:upstream",
                "project": str(self.project),
                "name": "extend",
                "old": "Upstream extension.\n",
                "text": "Do not edit the extension.\n",
            },
        ]

        prepared = self.prepare(retro_candidates)
        self.assertEqual(prepared[0]["status"], "ready")
        self.assertEqual(Path(prepared[0]["target"]), canonical.resolve())
        self.assertEqual(prepared[1]["status"], "upstream")
        self.assertEqual(prepared[2]["status"], "skipped")
        self.assertEqual(prepared[3]["status"], "upstream")
        result = self.run_cli(
            "execute",
            "--adapter",
            "claude",
            "--approval",
            "all",
            *self.retro_candidate_args(prepared),
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        actions = json.loads(result.stdout)["actions"]
        self.assertEqual(
            [action["status"] for action in actions],
            ["saved", "upstream", "skipped", "upstream"],
        )
        self.assertEqual(
            canonical.read_text(encoding="utf-8"),
            "# Drain\n\nRun the check with a synthetic fixture.\n",
        )
        self.assertTrue(installed.is_symlink())
        self.assertEqual(upstream.read_text(encoding="utf-8"), "# Grilling\n\nUpstream source.\n")
        self.assertEqual(extension.read_text(encoding="utf-8"), "# Extension\n\nUpstream extension.\n")
        self.assertFalse((self.project / ".claude" / "skills" / "missing").exists())

    def test_issue_requires_numeric_approval_and_uses_fake_origin_and_triage_boundary(self):
        binary = self.root / "fake-bin"
        binary.mkdir()
        git_log = self.root / "git.log"
        gh_log = self.root / "gh.log"
        git = binary / "git"
        git.write_text(
            "#!/bin/bash\n"
            "printf '%s\\n' \"$*\" >> \"$FAKE_GIT_LOG\"\n"
            "printf '%s\\n' 'git@github.com:example/originating-repo.git'\n",
            encoding="utf-8",
        )
        gh = binary / "gh"
        gh.write_text(
            f"#!{sys.executable}\n"
            "import json, os, sys\n"
            "with open(os.environ['FAKE_GH_LOG'], 'a', encoding='utf-8') as log:\n"
            "    log.write(json.dumps(sys.argv[1:]) + '\\n')\n"
            "if sys.argv[1] == 'label':\n"
            "    print(json.dumps([{'name': 'needs-triage'}, {'name': 'bug'}]))\n"
            "elif sys.argv[1] == 'issue':\n"
            "    print('https://github.com/example/originating-repo/issues/123')\n",
            encoding="utf-8",
        )
        git.chmod(0o755)
        gh.chmod(0o755)
        env = {
            "PATH": str(binary),
            "FAKE_GIT_LOG": str(git_log),
            "FAKE_GH_LOG": str(gh_log),
        }
        retro_candidate = {
            "type": "issue",
            "key": "issue:contract-cache",
            "project": str(self.project),
            "title": "Contract cache hides schema changes",
            "text": "Problem: cached fixtures hid schema changes.\n\nEvidence: session-0001.\n\nProposed fix: use --no-cache.",
        }
        prepared = self.prepare([retro_candidate])[0]
        self.assertEqual(prepared["status"], "ready")

        declined = self.run_cli(
            "execute",
            "--adapter",
            "claude",
            "--approval",
            "none",
            "--retro-candidate",
            json.dumps(prepared),
            env=env,
        )
        self.assertEqual(declined.returncode, 0, declined.stderr)
        self.assertFalse(git_log.exists())
        self.assertFalse(gh_log.exists())

        approved = self.run_cli(
            "execute",
            "--adapter",
            "claude",
            "--approval",
            "1",
            "--retro-candidate",
            json.dumps(prepared),
            env=env,
        )
        self.assertEqual(approved.returncode, 0, approved.stderr)
        action = json.loads(approved.stdout)["actions"][0]
        self.assertEqual(action["status"], "saved")
        self.assertEqual(action["url"], "https://github.com/example/originating-repo/issues/123")
        self.assertIn(f"-C {self.project.resolve()} remote get-url origin", git_log.read_text(encoding="utf-8"))
        commands = [
            json.loads(line) for line in gh_log.read_text(encoding="utf-8").splitlines()
        ]
        self.assertEqual(len(commands), 2)
        self.assertEqual(
            commands[0],
            ["label", "list", "--repo", "example/originating-repo", "--json", "name"],
        )
        self.assertEqual(
            commands[1],
            [
                "issue",
                "create",
                "--repo",
                "example/originating-repo",
                "--title",
                "Contract cache hides schema changes",
                "--body",
                retro_candidate["text"],
                "--label",
                "needs-triage",
            ],
        )

        before_all = gh_log.read_bytes()
        all_approval = self.run_cli(
            "execute",
            "--adapter",
            "claude",
            "--approval",
            "all",
            "--retro-candidate",
            json.dumps(prepared),
            env=env,
        )
        self.assertNotEqual(all_approval.returncode, 0)
        self.assertIn("numeric", all_approval.stderr)
        self.assertEqual(gh_log.read_bytes(), before_all)

    def test_numeric_approval_writes_selected_memory_and_finishes_bookkeeping(self):
        session_id = self.create_session()
        second_session_id = self.create_session("bbbbbbbb-0002")
        digest = self.run_cli(
            "digest", "--adapter", "claude", "--window", "today", "--include-temp"
        )
        self.assertEqual(digest.returncode, 0, digest.stderr)
        self.assertIn(session_id[:8], digest.stdout)
        self.assertIn(second_session_id[:8], digest.stdout)
        note = self.run_cli(
            "note",
            "--adapter",
            "claude",
            "--text",
            "Disable the contract-test cache.",
            "--context",
            "Synthetic correction in the originating project.",
            "--approve",
        )
        self.assertEqual(note.returncode, 0, note.stderr)
        note_id = json.loads(note.stdout)["note"]["id"]
        proposed = [self.memory_retro_candidate(), self.rule_retro_candidate()]
        for retro_candidate in proposed:
            retro_candidate.update(
                session_ids=[session_id], citations=[f"project · {session_id[:8]}"]
            )
        prepared = self.prepare(proposed)
        reported = self.report(self.insights(), prepared)
        self.assertEqual(len(reported["retro_candidates"]), 2)
        self.assertEqual(reported["report"].count("Synthetic cross-session Insight"), 4)
        self.assertIn("Run the contract tests with --no-cache after schema changes.", reported["report"])
        retro_candidates = reported["retro_candidates"]

        result = self.run_cli(
            "execute",
            "--adapter",
            "claude",
            "--approval",
            "1",
            *self.retro_candidate_args(retro_candidates),
            "--session-id",
            session_id,
            "--session-id",
            second_session_id,
            "--note-id",
            note_id,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        actions = json.loads(result.stdout)["actions"]
        self.assertEqual(actions[0]["status"], "saved")
        memory = Path(retro_candidates[0]["target"])
        self.assertEqual(
            memory.parent.parent.name,
            re.sub(r"[^A-Za-z0-9-]", "-", str(self.project.resolve())),
        )
        self.assertEqual(
            memory.read_text(encoding="utf-8"),
            "---\n"
            "name: contract-tests-no-cache\n"
            "description: Run contract tests without cache after schema changes.\n"
            "metadata:\n"
            "  type: feedback\n"
            "---\n\n"
            "Run the contract tests with --no-cache after schema changes.\n\n"
            "**Why:** Cached fixtures hid the schema change twice.\n\n"
            "**How to apply:** Use --no-cache whenever a contract fixture changes.\n",
        )
        self.assertIn(
            "- [Contract tests without cache](contract-tests-no-cache.md) — "
            "Run contract tests without cache after schema changes.",
            (memory.parent / "MEMORY.md").read_text(encoding="utf-8"),
        )
        self.assertEqual(
            (self.project / "AGENTS.md").read_text(encoding="utf-8"),
            "# Project instructions\n",
        )
        self.assertEqual(
            (self.state / "reviewed.txt").read_text(encoding="utf-8").splitlines(),
            [f"claude:{session_id}", f"claude:{second_session_id}"],
        )
        self.assertEqual(
            (self.state / "declined.txt").read_text(encoding="utf-8").splitlines(),
            ["rule:contract-tests-no-cache"],
        )
        self.assertFalse(
            any(
                json.loads(line).get("id") == note_id
                for line in (self.state / "inbox.jsonl").read_text(encoding="utf-8").splitlines()
            )
        )


if __name__ == "__main__":
    unittest.main()
