"""Tests for the runner's judge settings: which rubric a case names, and when the
judge's score decides the case. No API calls.

    python3 -m unittest discover -s labs/evals -v
"""

from __future__ import annotations

import sys
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


if __name__ == "__main__":
    unittest.main()
