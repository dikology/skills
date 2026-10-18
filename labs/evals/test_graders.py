"""Tests for graders.py.

A grader that cannot fail turns every run green and hides the regression the
harness exists to catch. So each grader gets a reply that should satisfy it and a
mutant that should trip it.

    python3 -m unittest discover -s labs/evals -v
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from graders import Evidence, grade  # noqa: E402

VAULT = Path(__file__).parent / "fixtures" / "vaults" / "band-or-pottery"

GOOD_ORIENT = """FROM YOUR NOTES:
- [[pottery]] — "The wheel is the only place my hands stop asking what time it is."
- [[thursday evenings]] — "If I add one more thing to Thursday, something else has to come off it."

TENSION:
Open studio and rehearsal both sit on Thursday.

MY TAKE: The band was always about leaving the house. Where am I wrong?"""


def evidence(reply: str, diff: dict | None = None) -> Evidence:
    return Evidence(
        transcript=[{"role": "human", "text": "/companion band or pottery?"},
                    {"role": "companion", "text": reply}],
        diff=diff or {"added": {}, "removed": [], "modified": {}},
        vault=VAULT,
    )


def result(out: dict, name: str) -> dict:
    return next(r for r in out["results"] if r["name"] == name)


class OrientQuotesCorpus(unittest.TestCase):
    def test_verbatim_quote_with_resolving_link_passes(self):
        out = grade(["orient_quotes_corpus"], evidence(GOOD_ORIENT))
        self.assertTrue(out["passed"], out)

    def test_curly_quotes_and_alias_links_pass(self):
        reply = "- [[Pottery|the studio]] — “Week six: first bowl that didn’t collapse.”"
        self.assertTrue(grade(["orient_quotes_corpus"], evidence(reply))["passed"])

    def test_ellipsis_between_verbatim_fragments_passes(self):
        reply = '- [[the band]] — "We play covers, mostly badly. … Nobody says no"'
        self.assertTrue(grade(["orient_quotes_corpus"], evidence(reply))["passed"])

    def test_paraphrase_without_quotes_fails(self):
        reply = ("Your notes on [[pottery]] say the wheel calms you, and [[the band]] "
                 "was about getting out of the house. My take: keep the band.")
        out = grade(["orient_quotes_corpus"], evidence(reply))
        self.assertFalse(out["passed"])
        self.assertEqual(out["hard_fail"], ["orient_quotes_corpus"])

    def test_link_that_does_not_resolve_fails(self):
        reply = '- [[ceramics]] — "The wheel is the only place my hands stop asking what time it is."'
        self.assertFalse(grade(["orient_quotes_corpus"], evidence(reply))["passed"])

    def test_altered_quote_fails(self):
        reply = '- [[pottery]] — "The wheel is the only place my mind stops racing."'
        self.assertFalse(grade(["orient_quotes_corpus"], evidence(reply))["passed"])

    def test_quote_under_the_wrong_note_fails(self):
        reply = '- [[the band]] — "The wheel is the only place my hands stop asking what time it is."'
        self.assertFalse(grade(["orient_quotes_corpus"], evidence(reply))["passed"])

    def test_quote_only_after_orient_does_not_count(self):
        ev = evidence("What's pulling you toward pottery right now?")
        ev.transcript += [{"role": "human", "text": "the calm"},
                          {"role": "companion", "text": GOOD_ORIENT}]
        self.assertFalse(grade(["orient_quotes_corpus"], ev)["passed"])


class QuotesVerbatim(unittest.TestCase):
    def test_all_quotes_verbatim_passes(self):
        self.assertTrue(grade(["quotes_verbatim"], evidence(GOOD_ORIENT))["passed"])

    def test_one_invented_quote_among_real_ones_fails(self):
        reply = GOOD_ORIENT + '\n- [[the band]] — "I only stay for Mira."'
        out = grade(["quotes_verbatim"], evidence(reply))
        self.assertFalse(out["passed"])
        self.assertIn("the band", out["results"][0]["note"])

    def test_invented_quote_in_a_later_turn_fails(self):
        ev = evidence(GOOD_ORIENT)
        ev.transcript += [{"role": "human", "text": "and money?"},
                          {"role": "companion", "text": '[[money 2026]] — "Pottery is cheap."'}]
        self.assertFalse(grade(["quotes_verbatim"], ev)["passed"])

    def test_quoting_the_human_in_chat_is_not_checked_against_notes(self):
        ev = evidence('You said "I hate Thursdays" a minute ago. Which is it?')
        self.assertTrue(grade(["quotes_verbatim"], ev)["passed"])


class NoWrites(unittest.TestCase):
    def test_untouched_vault_passes(self):
        self.assertTrue(grade(["no_writes"], evidence(GOOD_ORIENT))["passed"])

    def test_any_added_or_modified_file_fails_and_is_named(self):
        for diff in ({"added": {"session.md": "chat"}, "removed": [], "modified": {}},
                     {"added": {}, "removed": [], "modified": {"pottery.md": ["a", "b"]}},
                     {"added": {}, "removed": ["home.md"], "modified": {}}):
            out = grade(["no_writes"], evidence(GOOD_ORIENT, diff))
            self.assertFalse(out["passed"], diff)
            path = next(iter(diff["added"] or diff["modified"] or diff["removed"]))
            self.assertIn(path, out["results"][0]["note"])


if __name__ == "__main__":
    unittest.main()
