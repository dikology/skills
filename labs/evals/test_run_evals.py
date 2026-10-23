"""Tests for the runner's judge settings: which rubric a case names, and when the
judge's score decides the case. No API calls.

    python3 -m unittest discover -s labs/evals -v
"""

from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

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


def row(case: str, passed: bool, score: float) -> dict:
    return {"case": case, "passed": passed, "score": score}


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
             "case_filter": None, "judge": True}
        s.update(over)
        return s

    def promote(self, summary, case_ids=("orient", "voice")):
        return run_evals.promote(summary, self.stable, self.candidate, list(case_ids))

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

    def test_refuses_a_run_where_stable_skipped_a_case(self):
        s = self.summary([row("orient", True, 0.5)],
                         [row("orient", True, 1.0), row("voice", True, 1.0)])
        self.assertRefused(self.promote(s), "voice")


if __name__ == "__main__":
    unittest.main()
