"""Tests for the runner's judge settings: which rubric a case names, and when the
judge's score decides the case, and for the qwen process adapter. No API calls.

    python3 -m unittest discover -s labs/evals -v
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).parent))

import run_evals  # noqa: E402

def scored() -> dict:
    """A deterministic verdict that passed."""
    return {"passed": True, "score": 1.0, "hard_fail": [], "results": []}


class JudgeSettings(unittest.TestCase):
    def test_true_uses_the_default_rubric_and_only_reports(self):
        self.assertEqual(run_evals.judge_spec({"judge": True}),
                         (run_evals.HERE / "judge-rubric.md", None))

    def test_a_named_rubric_with_a_pass_mark(self):
        rubric, pass_at = run_evals.judge_spec({"judge": {"rubric": "soft-posture", "pass_at": 4}})
        self.assertEqual(rubric.name, "judge-soft-posture.md")
        self.assertEqual(pass_at, 4)

    def test_no_judge(self):
        self.assertIsNone(run_evals.judge_spec({}))

    def test_a_rubric_with_no_file_is_a_setup_error(self):
        case = {"id": "x", "vault": "band-or-pottery", "turns": ["hi"], "graders": [],
                "judge": {"rubric": "no-such-rubric"}}
        self.assertIn("no-such-rubric", run_evals.check_case(case))

    def test_a_pass_mark_with_no_rubric_or_out_of_range_is_a_setup_error(self):
        base = {"id": "x", "vault": "band-or-pottery", "turns": ["hi"], "graders": []}
        self.assertIsNotNone(run_evals.check_case({**base, "judge": {"pass_at": 4}}))
        self.assertIn("pass_at", run_evals.check_case(
            {**base, "judge": {"rubric": "soft-posture", "pass_at": 7}}))


class JudgeVerdict(unittest.TestCase):
    def test_a_score_under_the_pass_mark_fails_the_case(self):
        out = run_evals.apply_judge(scored(), {"score": 2, "why": "argued"}, pass_at=4)
        self.assertFalse(out["passed"])
        self.assertIn("judge", out["hard_fail"])

    def test_a_score_at_the_pass_mark_passes(self):
        self.assertTrue(run_evals.apply_judge(scored(), {"score": 4}, pass_at=4)["passed"])

    def test_a_judge_error_fails_a_gating_case(self):
        self.assertFalse(run_evals.apply_judge(scored(), {"error": "timeout"}, pass_at=4)["passed"])

    def test_without_a_pass_mark_the_judge_only_reports(self):
        out = run_evals.apply_judge(scored(), {"score": 1}, pass_at=None)
        self.assertTrue(out["passed"])
        self.assertEqual(out["judge"], {"score": 1})


class SkillByName(unittest.TestCase):
    """A skill name picks the arms, the case set, and where the skill is installed."""

    def test_the_arms_resolve_from_the_name(self):
        self.assertEqual(run_evals.arms_for("improve"),
                         {"stable": run_evals.REPO / "skills" / "improve",
                          "candidate": run_evals.REPO / "labs" / "improve"})

    def test_each_skill_reads_only_its_own_case_set(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            for name in ("companion", "improve"):
                (folder / f"{name}.json").write_text(json.dumps(
                    {"skill_name": name, "cases": [{"id": f"{name}-case"}]}))
            self.assertEqual(run_evals.load_cases("improve", folder), [{"id": "improve-case"}])

    def test_a_skill_with_no_case_set_is_a_setup_error(self):
        with self.assertRaisesRegex(ValueError, "no-such-skill"):
            run_evals.load_cases("no-such-skill")

    def test_a_case_set_naming_another_skill_is_a_setup_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "improve.json").write_text(
                json.dumps({"skill_name": "companion", "cases": []}))
            with self.assertRaisesRegex(ValueError, "companion"):
                run_evals.load_cases("improve", Path(tmp))

    def test_companions_cases_are_its_own_set(self):
        ids = [c["id"] for c in run_evals.load_cases("companion")]
        self.assertIn("orient-quotes-corpus", ids)
        self.assertEqual(len(ids), len(set(ids)))

    def test_the_skill_is_installed_where_qwen_discovers_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            mutant = root / "improve-writes-before-approval"
            mutant.mkdir()
            (mutant / "SKILL.md").write_text("mutant\n")
            case = {"id": "x", "vault": "band-or-pottery", "overlay": None}
            ws = run_evals.build_vault(root / "ws", case, mutant, "improve")
            installed = ws / ".qwen" / "skills"
            self.assertEqual([p.name for p in installed.iterdir()], ["improve"])
            self.assertEqual((installed / "improve" / "SKILL.md").read_text(), "mutant\n")


class IsolatedHome(unittest.TestCase):
    """Every turn runs against its own QWEN_HOME: the vault's Overlay and installed
    skill are read, the developer's own settings, hooks and servers are not."""

    REAL = {"$version": 2, "env": {"QWENCLOUD_TOKEN_PLAN_API_KEY": "sk-1"},
            "mcpServers": {"playwright": {"command": "npx"}},
            "hooks": {"PreToolUse": [{"type": "command"}]}, "ui": {"theme": "dark"},
            "security": {"auth": {"selectedType": "openai"}},
            "model": {"name": "qwen3.8-flash", "baseUrl": "https://api.example/v1"},
            "modelProviders": {"openai": [{"id": "qwen3.8-flash"}]},
            "providerMetadata": {"qwencloud": {"version": "abc"}}}

    def test_the_seed_carries_only_how_to_reach_a_model(self):
        seed = run_evals.seed_settings(self.REAL)
        self.assertEqual(sorted(seed), ["$version", "env", "memory", "model",
                                        "modelProviders", "providerMetadata", "security"])
        self.assertEqual(seed["model"]["name"], "qwen3.8-flash")

    def test_the_seed_turns_memory_off_for_the_run(self):
        """A case is graded on the vault in front of it. A session that stops to write
        memories spends its turn on the harness, and carries one case into the next."""
        seed = run_evals.seed_settings(self.REAL)
        self.assertFalse(seed["memory"]["enableManagedAutoMemory"])
        self.assertFalse(seed["memory"]["enableManagedAutoDream"])

    def test_memory_stays_off_even_when_the_developer_keeps_it_on(self):
        real = dict(self.REAL, memory={"enableManagedAutoMemory": True,
                                       "enableStructuredRecall": True})
        seed = run_evals.seed_settings(real)
        self.assertFalse(seed["memory"]["enableManagedAutoMemory"])
        self.assertNotIn("enableStructuredRecall", seed["memory"])

    def test_a_turn_looks_at_that_home_and_not_the_developers_own(self):
        env = run_evals.agent_env(Path("/tmp/eval-home"))
        self.assertEqual(env["QWEN_HOME"], "/tmp/eval-home")
        self.assertEqual(env["PATH"], os.environ["PATH"])

    def test_the_run_writes_its_home_from_the_settings_it_is_given(self):
        with tempfile.TemporaryDirectory() as tmp:
            real = Path(tmp) / "real"
            real.mkdir()
            (real / "settings.json").write_text(json.dumps(self.REAL))
            home = run_evals.make_isolated_home(Path(tmp) / "run", real)
            self.assertEqual(json.loads((home / "settings.json").read_text()),
                             run_evals.seed_settings(self.REAL))

    def test_a_login_kept_in_a_file_of_its_own_travels_with_the_seed(self):
        with tempfile.TemporaryDirectory() as tmp:
            real = Path(tmp) / "real"
            real.mkdir()
            (real / "settings.json").write_text(json.dumps(
                {"security": {"auth": {"selectedType": "qwen-oauth"}}}))
            (real / "oauth_creds.json").write_text('{"access_token": "t"}')
            home = run_evals.make_isolated_home(Path(tmp) / "run", real)
            self.assertEqual(json.loads((home / "settings.json").read_text()),
                             {"security": {"auth": {"selectedType": "qwen-oauth"}},
                              "memory": {"enableManagedAutoMemory": False,
                                         "enableManagedAutoDream": False}})
            self.assertEqual((home / "oauth_creds.json").read_text(), '{"access_token": "t"}')

    def test_a_home_with_no_settings_is_seeded_empty_rather_than_crashing(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = run_evals.make_isolated_home(Path(tmp) / "run", Path(tmp) / "nothing")
            self.assertEqual(json.loads((home / "settings.json").read_text()),
                             {"memory": {"enableManagedAutoMemory": False,
                                         "enableManagedAutoDream": False}})

    def test_a_login_is_found_before_any_case_costs_a_turn(self):
        with tempfile.TemporaryDirectory() as tmp:
            bare = Path(tmp)
            self.assertFalse(run_evals.login_found(bare, {}))
            (bare / "settings.json").write_text(json.dumps(
                {"security": {"auth": {"selectedType": "openai"}}, "env": {"K": "v"}}))
            self.assertTrue(run_evals.login_found(bare, {}))
            keys = bare / "keys"
            keys.mkdir()
            (keys / "oauth_creds.json").write_text("{}")
            self.assertTrue(run_evals.login_found(keys, {}))

    def test_a_key_handed_over_by_the_environment_counts_as_a_login(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertTrue(run_evals.login_found(Path(tmp), {"OPENAI_API_KEY": "sk-1"}))


class PlaySession(unittest.TestCase):
    """The turn chain, against a recorded stand-in for qwen: turn 2 resumes the session
    turn 1 reported, and a turn that quietly starts a stranger is caught, not graded."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.ws = Path(self._tmp.name)
        (self.ws / "note.md").write_text("one\n")
        self.argv = []

    def event(self, text, sid, init=True, skills=("companion",)):
        events = []
        if init:
            events.append({"type": "system", "subtype": "init", "session_id": sid,
                           "mcp_servers": []})
        events.append({"type": "result", "session_id": sid, "is_error": False, "result": text,
                       "usage": {"input_tokens": 10, "output_tokens": 1},
                       "stats": {"skills": {"byName": {k: {} for k in skills}}}})
        return json.dumps(events)

    def play(self, sessions, replies):
        replies = iter(replies)

        def fake_run(argv, **kwargs):
            self.argv.append(argv)
            return subprocess.CompletedProcess(argv, 0, next(replies), "")

        with mock.patch.object(run_evals.subprocess, "run", side_effect=fake_run):
            return run_evals.play(self.ws, sessions, None, 60, {})

    def test_turn_two_resumes_the_session_turn_one_reported(self):
        session = self.play([["what should I file?", "yes, write it"]],
                            [self.event("I'd file this.", "s-1"),
                             self.event("Written.", "s-1", skills=())])
        self.assertIn("-r", self.argv[1])
        self.assertEqual(self.argv[1][self.argv[1].index("-r") + 1], "s-1")
        self.assertEqual(session["session_ids"], ["s-1"])
        self.assertIsNone(session["error"])
        self.assertEqual([t["role"] for t in session["transcript"]],
                         ["human", "companion", "human", "companion"])

    def test_a_turn_that_answered_as_a_stranger_is_an_error_not_a_memory(self):
        session = self.play([["first", "second"]],
                            [self.event("one", "s-1"), self.event("two", "s-2")])
        self.assertIn("s-1", session["error"])
        self.assertEqual([t["role"] for t in session["transcript"]],
                         ["human", "companion", "human"])  # turn 2's reply was not trusted

    def test_the_next_session_starts_fresh_instead_of_resuming_the_last_one(self):
        self.play([["a session"], ["another"]],
                  [self.event("one", "s-1"), self.event("two", "s-2")])
        self.assertNotIn("-r", self.argv[1])
        self.assertEqual(len(self.argv), 2)

    def test_a_turn_that_reported_no_session_setup_cannot_claim_isolation(self):
        session = self.play([["hello"]], [self.event("hi", "s-1", init=False)])
        self.assertFalse(session["init_reported"])
        self.assertIn("isolat", run_evals.check_run("companion", session))


class RunIntegrity(unittest.TestCase):
    """A case whose session ran the wrong thing passes quietly, which is the failure
    this harness fears most: it is graded by what the run reports about itself."""

    def session(self, **over) -> dict:
        return {"skills_invoked": ["companion"], "mcp_servers": [], "error": None,
                "init_reported": True, **over}

    def test_a_session_that_invoked_the_skill_and_loaded_nothing_is_evidence(self):
        self.assertIsNone(run_evals.check_run("companion", self.session()))

    def test_a_session_where_the_skill_was_never_invoked_proves_nothing(self):
        problem = run_evals.check_run("companion", self.session(skills_invoked=[]))
        self.assertIsNotNone(problem)
        self.assertIn("companion", problem)

    def test_a_skill_installed_where_nothing_looks_for_it_is_the_usual_way_to_fail(self):
        problem = run_evals.check_run("companion", self.session(skills_invoked=["pdf"]))
        self.assertIn("never invoked", problem)

    def test_a_session_that_loaded_an_mcp_server_is_not_the_isolated_vault(self):
        problem = run_evals.check_run("companion",
                                      self.session(mcp_servers=[{"name": "playwright"}]))
        self.assertIn("MCP", problem)


class SessionTurn(unittest.TestCase):
    """The process adapter: one place holds the binary and every flag a turn needs."""

    def test_a_turn_runs_qwen_with_the_prompt_positional(self):
        argv = run_evals.session_argv("should I quit the band?")
        self.assertEqual(argv[0], "qwen")
        self.assertIn("should I quit the band?", argv)
        self.assertNotIn("-p", argv)

    def test_the_adapter_names_no_other_binary(self):
        joined = " ".join(run_evals.session_argv("x")) + " " + " ".join(run_evals.judge_argv("x"))
        self.assertNotIn("claude", joined)

    def test_a_later_turn_resumes_the_session_it_was_handed(self):
        self.assertNotIn("-r", run_evals.session_argv("x"))
        argv = run_evals.session_argv("x", resume="9d21")
        self.assertEqual(argv[argv.index("-r") + 1], "9d21")

    def test_history_is_recorded_because_resume_reads_it_from_disk(self):
        self.assertIn("--chat-recording", run_evals.session_argv("x"))

    def test_a_turn_answers_without_asking_and_loads_no_mcp_server(self):
        argv = run_evals.session_argv("x")
        self.assertEqual(argv[argv.index("--approval-mode") + 1], "yolo")
        self.assertEqual(json.loads(argv[argv.index("--mcp-config") + 1]), {"mcpServers": {}})

    def test_a_named_model_reaches_qwen(self):
        argv = run_evals.session_argv("x", model="glm-5.3")
        self.assertEqual(argv[argv.index("-m") + 1], "glm-5.3")

    def test_the_default_model_is_the_one_the_vault_settings_pick(self):
        self.assertNotIn("-m", run_evals.session_argv("x"))

    def test_no_flag_of_the_agent_this_harness_left_behind_survives(self):
        """The runner drives one agent. Its `CLAUDE.md` stays a filename, not a CLI."""
        source = Path(run_evals.__file__).read_text()
        for gone in ("claude", "--permission-mode", "--strict-mcp-config",
                     "--setting-sources", "--output-format", "--resume ",
                     "total_cost_usd"):
            self.assertNotIn(gone, source)


class JudgeTurn(unittest.TestCase):
    """The judge reads a transcript and scores it. Editing the vault it graded is not
    on the table, and qwen has no --disallowedTools, so the lever is stated here."""

    def test_the_judge_is_told_not_to_edit_and_cannot_even_if_it_wants(self):
        argv = run_evals.judge_argv("rubric")
        self.assertEqual(argv[argv.index("--approval-mode") + 1], "plan")
        excluded = argv[argv.index("--exclude-tools") + 1].split(",")
        for tool in ("write_file", "edit", "notebook_edit", "run_shell_command", "agent"):
            self.assertIn(tool, excluded)

    def test_the_judge_reads_the_transcript_in_its_prompt_and_nothing_else(self):
        argv = run_evals.judge_argv("rubric")
        excluded = argv[argv.index("--exclude-tools") + 1].split(",")
        for tool in ("read_file", "glob", "grep_search"):
            self.assertIn(tool, excluded)

    def test_the_judge_is_headless_and_isolated_like_the_session(self):
        argv = run_evals.judge_argv("rubric")
        self.assertEqual(argv[0], "qwen")
        self.assertEqual(argv[argv.index("-o") + 1], "json")
        self.assertEqual(json.loads(argv[argv.index("--mcp-config") + 1]), {"mcpServers": {}})

    def test_the_judge_model_can_be_named(self):
        argv = run_evals.judge_argv("x", model="deepseek-v4-pro")
        self.assertEqual(argv[argv.index("-m") + 1], "deepseek-v4-pro")


class ReadTurn(unittest.TestCase):
    """`qwen -o json` prints an array of events whose last one is the turn's result.
    fixtures/qwen-turns.json is that shape as qwen 0.26.3 printed it on this machine,
    with the vault text, paths and ids replaced by placeholders."""

    @classmethod
    def setUpClass(cls):
        cls.turns = json.loads((run_evals.HERE / "fixtures" / "qwen-turns.json").read_text())

    def read(self, name):
        return run_evals.read_turn(json.dumps(self.turns[name]))

    def test_the_reply_and_the_session_come_from_the_result_event(self):
        turn = self.read("turn")
        self.assertEqual(turn["text"],
                         "Pottery. Go — the band can wait a week, open studio cannot.")
        self.assertEqual(turn["session_id"], "9829dc82-6462-40ef-af75-3324f2399e86")
        self.assertFalse(turn["is_error"])
        self.assertEqual(turn["error"], "")

    def test_a_turn_that_failed_says_why_instead_of_coming_back_empty(self):
        turn = self.read("failed_turn")
        self.assertTrue(turn["is_error"])
        self.assertIn("Missing API key", turn["error"])
        self.assertEqual(turn["text"], "")

    def test_tokens_are_counted_because_qwen_reports_no_price(self):
        self.assertEqual(self.read("turn")["tokens"], 59645)

    def test_the_skills_a_turn_ran_are_named(self):
        self.assertEqual(self.read("turn")["skills"], ["companion"])

    def test_the_mcp_servers_a_turn_loaded_are_reported(self):
        self.assertFalse(self.read("turn")["mcp_servers"])
        self.assertTrue(self.read("second_turn")["mcp_servers"])

    def test_a_run_with_no_init_event_reports_that_it_saw_no_setup(self):
        """The failed turn in the fixture is a real auth failure: a result event and
        nothing else. Emptiness must not read as "no MCP server was loaded"."""
        self.assertFalse(self.read("failed_turn")["init_reported"])
        self.assertTrue(self.read("turn")["init_reported"])

    def test_a_resumed_turn_keeps_the_session_it_was_resumed_into(self):
        self.assertEqual(self.read("turn")["session_id"],
                         self.read("second_turn")["session_id"])

    def test_output_that_is_not_an_event_array_is_not_silently_a_passing_turn(self):
        with self.assertRaises(ValueError):
            run_evals.read_turn("[]")
        with self.assertRaises(ValueError):
            run_evals.read_turn('{"result": "an object, not an array"}')


class ReportLine(unittest.TestCase):
    """What a case cost is reported in tokens: qwen's result event prices nothing, and
    a run that prints $0.00 reads like it was free."""

    def row(self, **over) -> dict:
        return {"case": "orient-quotes-corpus", "passed": True, "score": 1.0, "results": [],
                "error": None, "judge": {}, "tokens": 59645, "seconds": 17.4, **over}

    def test_a_passing_line_counts_tokens_and_never_dollars(self):
        line = run_evals.report_line(self.row())
        self.assertIn("59645 tok", line)
        self.assertNotIn("$", line)
        self.assertIn("PASS", line)

    def test_the_session_that_never_ran_still_shows_why(self):
        line = run_evals.report_line(self.row(passed=False, tokens=0,
                                              error="Missing API key",
                                              results=[{"name": "no_writes", "passed": False,
                                                        "note": "wrote 2 files"}]))
        self.assertIn("Missing API key", line)
        self.assertIn("no_writes", line)

    def test_a_kept_grade_records_the_tokens_it_spent(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            session = {"transcript": [{"role": "human", "text": "hi", "session": 0}],
                       "session_ids": ["9d21"], "error": None, "tokens": 1234, "seconds": 3.0,
                       "skills_invoked": ["companion"], "mcp_servers": []}
            d = {"added": {}, "removed": [], "modified": {}}
            run_evals.keep(out, {"id": "orient"}, session, d,
                           {"passed": True, "score": 1.0, "hard_fail": [], "results": []})
            grade = json.loads((out / "orient" / "grade.json").read_text())
            self.assertEqual(grade["tokens"], 1234)
            self.assertEqual(grade["session_ids"], ["9d21"])
            self.assertNotIn("cost_usd", grade)


def row(case: str, passed: bool, score: float) -> dict:
    return {"case": case, "passed": passed, "score": score}


class EmptyTurnRetry(unittest.TestCase):
    """A turn that reached no model, graded as a skill FAIL, is a verdict on the pipe.
    The run retries that one case once, and says that it did."""

    def test_an_empty_turn_that_spent_nothing_is_a_flake(self):
        self.assertTrue(run_evals.transport_flake({"error": "no output", "tokens": 0}))

    def test_a_session_that_ran_is_never_a_flake(self):
        # 295k tokens and a session id: the session happened and misbehaved, which is
        # the case's own verdict, not the pipe's.
        self.assertFalse(run_evals.transport_flake({"error": "no output", "tokens": 295883}))

    def test_only_an_empty_turn_qualifies(self):
        for err in (None, "turn 1 timed out after 600s", "non-zero exit",
                    "qwen answered as a different session"):
            self.assertFalse(run_evals.transport_flake({"error": err, "tokens": 0}), err)

    def test_the_flaked_case_runs_again_and_says_so(self):
        tries = []
        flaked = {"case": "no-overlay", "passed": False, "error": "no output", "tokens": 0}
        good = {"case": "no-overlay", "passed": True, "error": None, "tokens": 389355}

        def fake_run(n):
            tries.append(n)
            return flaked if n == 1 else good

        out = run_evals.run_with_retry(fake_run)
        self.assertEqual(tries, [1, 2])
        self.assertTrue(out["passed"])
        self.assertEqual(out["attempts"], 2)
        self.assertEqual(out["discarded_error"], "no output")

    def test_a_clean_case_is_not_run_twice(self):
        tries = []

        def fake_run(n):
            tries.append(n)
            return {"case": "x", "passed": True, "error": None, "tokens": 10}

        out = run_evals.run_with_retry(fake_run)
        self.assertEqual(tries, [1])
        self.assertEqual(out["attempts"], 1)
        self.assertNotIn("discarded_error", out)

    def test_a_second_empty_turn_still_fails_after_two_attempts(self):
        def fake_run(n):
            return {"case": "x", "passed": False, "error": "no output", "tokens": 0}

        out = run_evals.run_with_retry(fake_run)
        self.assertEqual(out["attempts"], 2)
        self.assertFalse(out["passed"])

    def test_a_retry_gets_a_workspace_of_its_own(self):
        """The first attempt leaves its copy of the fixture vault where build_vault put
        it; a retry into the same folder would either collide or merge into a vault that
        was already read."""
        root = Path("/tmp/evals")
        first = run_evals.case_workspace(root, "stable", 1)
        second = run_evals.case_workspace(root, "stable", 2)
        self.assertEqual(first, root / "stable")
        self.assertEqual(second, root / "stable" / "try2")
        self.assertNotEqual(first, second)


class CompareArms(unittest.TestCase):
    def test_reports_the_score_difference_per_case(self):
        out = run_evals.compare([row("orient", True, 0.5)], [row("orient", True, 0.75)])
        self.assertEqual(out, [{"case": "orient", "stable": row("orient", True, 0.5),
                                "candidate": row("orient", True, 0.75),
                                "delta": 0.25, "lost": False}])

    def test_a_case_the_candidate_fails_and_stable_passes_is_lost(self):
        [c] = run_evals.compare([row("voice", True, 1.0)], [row("voice", False, 1.0)])
        self.assertTrue(c["lost"])

    def test_a_lower_score_is_lost_even_when_both_pass(self):
        [c] = run_evals.compare([row("voice", True, 1.0)], [row("voice", True, 0.8)])
        self.assertTrue(c["lost"])

    def test_failing_where_stable_also_fails_at_the_same_score_is_not_lost(self):
        [c] = run_evals.compare([row("voice", False, 0.5)], [row("voice", False, 0.5)])
        self.assertFalse(c["lost"])

    def test_a_case_only_one_arm_ran_is_lost(self):
        [c] = run_evals.compare([row("voice", True, 1.0)], [])
        self.assertTrue(c["lost"])
        self.assertIsNone(c["candidate"])


class Promote(unittest.TestCase):
    """Promotion reads a saved two-arm run and copies the candidate over stable."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        self.stable, self.candidate = root / "stable", root / "candidate"
        self.stable.mkdir()
        self.candidate.mkdir()
        (self.stable / "SKILL.md").write_text("old\n")
        (self.stable / "dropped.md").write_text("only in stable\n")
        (self.candidate / "SKILL.md").write_text("new\n")

    def summary(self, stable_rows, candidate_rows, **over) -> dict:
        s = {"arms": {"stable": {"hash": run_evals.tree_hash(self.stable),
                                 "cases": stable_rows},
                      "candidate": {"hash": run_evals.tree_hash(self.candidate),
                                    "cases": candidate_rows}},
             "skill": "companion", "agent": run_evals.BINARY, "case_filter": None,
             "judge": True}
        s.update(over)
        return s

    def promote(self, summary, case_ids=("orient", "voice")):
        return run_evals.promote(summary, self.stable, self.candidate, list(case_ids),
                                 "companion")

    def winning(self) -> dict:
        return self.summary([row("orient", True, 0.5), row("voice", True, 1.0)],
                            [row("orient", True, 1.0), row("voice", True, 1.0)])

    def test_a_winning_candidate_replaces_stable_exactly(self):
        self.assertIsNone(self.promote(self.winning()))
        self.assertEqual(sorted(p.name for p in self.stable.iterdir()), ["SKILL.md"])
        self.assertEqual((self.stable / "SKILL.md").read_text(), "new\n")

    def assertRefused(self, problem, mentions):
        self.assertIsNotNone(problem)
        self.assertIn(mentions, problem)
        self.assertEqual((self.stable / "SKILL.md").read_text(), "old\n")
        self.assertTrue((self.stable / "dropped.md").exists())  # not replaced

    def test_refuses_when_the_candidate_loses_any_case(self):
        s = self.summary([row("orient", True, 0.5), row("voice", True, 1.0)],
                         [row("orient", True, 1.0), row("voice", False, 1.0)])
        self.assertRefused(self.promote(s), "voice")

    def test_refuses_when_the_candidate_changed_since_the_run(self):
        s = self.winning()
        (self.candidate / "SKILL.md").write_text("edited after the run\n")
        self.assertRefused(self.promote(s), "candidate")

    def test_refuses_when_stable_changed_since_the_run(self):
        s = self.winning()
        (self.stable / "dropped.md").write_text("edited after the run\n")
        self.assertRefused(self.promote(s), "stable")

    def test_refuses_a_run_of_one_arm(self):
        s = self.winning()
        del s["arms"]["stable"]
        self.assertRefused(self.promote(s), "both arms")

    def test_refuses_a_run_that_skipped_a_case(self):
        self.assertRefused(self.promote(self.winning(), ("orient", "voice", "dacha")),
                           "dacha")

    def test_refuses_a_run_filtered_by_case(self):
        self.assertRefused(self.promote({**self.winning(), "case_filter": "orient"}),
                           "--case")

    def test_refuses_a_run_without_the_judge(self):
        self.assertRefused(self.promote({**self.winning(), "judge": False}), "--no-judge")

    def test_refuses_when_the_candidate_is_already_stable(self):
        shutil.rmtree(self.candidate)
        shutil.copytree(self.stable, self.candidate)
        self.assertRefused(self.promote(self.winning()), "identical")

    def test_refuses_a_run_of_another_skill(self):
        self.assertRefused(self.promote({**self.winning(), "skill": "improve"}), "improve")

    def test_refuses_evidence_gathered_by_another_agent(self):
        """A saved run from the claude days scores the same folders and hashes the
        same files. It is no longer evidence about what a qwen run does."""
        self.assertRefused(self.promote({**self.winning(), "agent": "claude"}), "claude")

    def test_refuses_a_run_that_recorded_no_agent(self):
        s = self.winning()
        del s["agent"]
        self.assertRefused(self.promote(s), "unknown")

    def test_a_run_saved_before_skill_names_counts_as_companion(self):
        s = self.winning()
        del s["skill"]
        self.assertIsNone(self.promote(s))

    def test_refuses_a_run_where_stable_skipped_a_case(self):
        s = self.summary([row("orient", True, 0.5)],
                         [row("orient", True, 1.0), row("voice", True, 1.0)])
        self.assertRefused(self.promote(s), "voice")


class LatestRun(unittest.TestCase):
    """--promote with no run named reads the newest two-arm run of the named skill."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.results = Path(tmp.name)
        self.mtime = 1_000_000

    def saved(self, run: str, skill: str, arms=("stable", "candidate")) -> Path:
        folder = self.results / run
        folder.mkdir()
        summary = folder / "summary.json"
        summary.write_text(json.dumps({"skill": skill, "arms": {a: {} for a in arms}}))
        self.mtime += 60
        os.utime(summary, (self.mtime, self.mtime))
        return folder

    def test_the_newest_two_arm_run_of_that_skill(self):
        self.saved("old", "companion")
        mine = self.saved("mine", "companion")
        self.saved("one-arm", "companion", arms=("candidate",))
        self.saved("other-skill", "improve")
        self.assertEqual(run_evals.latest_run("companion", self.results), mine)

    def test_a_run_saved_before_skill_names_counts_as_companion(self):
        old = self.saved("old", "companion")
        (old / "summary.json").write_text(json.dumps({"arms": {"stable": {}, "candidate": {}}}))
        self.assertEqual(run_evals.latest_run("companion", self.results), old)
        self.assertIsNone(run_evals.latest_run("improve", self.results))

    def test_none_when_the_skill_has_no_two_arm_run(self):
        self.saved("other-skill", "companion")
        self.assertIsNone(run_evals.latest_run("improve", self.results))


if __name__ == "__main__":
    unittest.main()
