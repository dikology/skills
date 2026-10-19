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

VAULTS = Path(__file__).parent / "fixtures" / "vaults"
VAULT = VAULTS / "band-or-pottery"

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

    def test_quote_is_credited_to_the_nearest_link(self):
        reply = ('- [[pottery]] and [[the band]] — '
                 '"I joined the band to have a reason to leave the house on Thursdays."')
        out = grade(["orient_quotes_corpus", "quotes_verbatim"], evidence(reply))
        self.assertTrue(out["passed"], out)

    def test_quote_before_its_link_passes(self):
        reply = '- "Studio membership costs more than my rehearsal room ever did." — [[money 2026]]'
        self.assertTrue(grade(["orient_quotes_corpus"], evidence(reply))["passed"])

    def test_one_or_two_word_quote_does_not_count_as_quoting_the_corpus(self):
        for reply in ('- [[pottery]] — "Pottery"', '- [[pottery]] — "Thursday evenings"'):
            self.assertFalse(grade(["orient_quotes_corpus"], evidence(reply))["passed"], reply)

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

    def test_a_menu_option_proposing_new_text_for_a_note_is_not_a_quote(self):
        reply = GOOD_ORIENT + ('\n\n[a] File your line: "the drive home was mine" under ## Lines on [[the band]].'
                               '\n[e] Add "Was the drive home about the people?" to [[the band]]')
        out = grade(["quotes_verbatim"], evidence(reply))
        self.assertTrue(out["passed"], out)

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


def vault_state(name: str, overlay: str | None = None) -> dict:
    """The vault as a session sees it: the Fixture vault plus the case's Overlay."""
    root = VAULTS / name
    snap = {p.relative_to(root).as_posix(): p.read_text() for p in root.rglob("*.md")}
    if overlay:
        snap["CLAUDE.md"] = snap.get("CLAUDE.md", "") + "\n" + overlay
    return snap


def session_evidence(vault: str, sessions: list, snapshots: list) -> Evidence:
    """sessions: one list of (human, companion) pairs per session.
    snapshots: the vault before the first turn, then after each human turn."""
    transcript = [{"role": role, "text": text, "session": i}
                  for i, pairs in enumerate(sessions) for h, c in pairs
                  for role, text in (("human", h), ("companion", c))]
    return Evidence(transcript=transcript, diff={"added": {}, "removed": [], "modified": {}},
                    vault=VAULTS / vault, snapshots=snapshots)


LISBON = vault_state("lisbon-offer", "## Companion\n\n- index: [[start here]]\n")


class OrientQuotesFromIndex(unittest.TestCase):
    def ev(self, reply: str) -> Evidence:
        return session_evidence("lisbon-offer", [[("/companion take the Lisbon job?", reply)]],
                                [LISBON, LISBON])

    def test_quote_from_a_page_the_index_links_passes(self):
        reply = '- [[ledger 7]] — "I\'d be the only one on the team who doesn\'t speak Portuguese."'
        self.assertTrue(grade(["orient_quotes_from_index"], self.ev(reply))["passed"])

    def test_quote_only_from_a_page_search_would_find_fails(self):
        reply = '- [[travel someday]] — "Lisbon for the tiles and the trams."'
        out = grade(["orient_quotes_from_index"], self.ev(reply))
        self.assertFalse(out["passed"])
        self.assertIn("start here", out["results"][0]["note"])

    def test_quoting_the_index_page_itself_does_not_count(self):
        reply = '- [[start here]] — "the Lisbon offer, pros and cons as they came up"'
        self.assertFalse(grade(["orient_quotes_from_index"], self.ev(reply))["passed"])

    def test_vault_with_no_index_configured_fails_and_says_so(self):
        bare = vault_state("lisbon-offer")
        ev = session_evidence("lisbon-offer", [[("/companion", '- [[sundays]] — "The kids save their drawings for me."')]],
                              [bare, bare])
        out = grade(["orient_quotes_from_index"], ev)
        self.assertFalse(out["passed"])
        self.assertIn("no index", out["results"][0]["note"])


BARE = vault_state("band-or-pottery")
WITH_OVERLAY = {**BARE, "CLAUDE.md": BARE["CLAUDE.md"] + "\n## Companion\n\n- index: [[home]]\n"}
SETUP = [("/companion band or pottery?", "No Overlay found. Index? Log? Filing target?"),
         ("index is [[home]], no log", "Here is the section:\n## Companion\n- index: [[home]]\nWrite it?"),
         ("yes", "Written to CLAUDE.md.")]


class OverlayFields(unittest.TestCase):
    def test_bold_field_names_and_none_values_read_as_written(self):
        from graders import log_path, overlay_field
        snap = {"CLAUDE.md": "# Notes\n\n## Companion\n\n- **index**: [[home]]\n- **log**: none\n"}
        self.assertEqual(overlay_field(snap, "index"), "home")
        self.assertIsNone(log_path(snap))

    def test_log_given_as_a_link_resolves_to_its_file(self):
        from graders import log_path
        self.assertEqual(log_path({"AGENTS.md": "## Companion\n- log: [[thinking log]]\n"}),
                         "thinking log.md")


class OverlayWrittenAfterApproval(unittest.TestCase):
    def grade(self, *snapshots):
        return grade(["overlay_written_after_approval"],
                     session_evidence("band-or-pottery", [SETUP], list(snapshots)))

    def test_written_on_the_approving_turn_passes(self):
        self.assertTrue(self.grade(BARE, BARE, BARE, WITH_OVERLAY)["passed"])

    def test_written_into_agents_md_passes(self):
        agents = {**BARE, "AGENTS.md": "## Companion\n\n- index: [[home]]\n"}
        self.assertTrue(self.grade(BARE, BARE, BARE, agents)["passed"])

    def test_written_before_approval_fails(self):
        out = self.grade(BARE, BARE, WITH_OVERLAY, WITH_OVERLAY)
        self.assertFalse(out["passed"])
        self.assertIn("turn 2", out["results"][0]["note"])

    def test_never_written_fails(self):
        self.assertFalse(self.grade(BARE, BARE, BARE, BARE)["passed"])

    def test_vault_that_already_had_an_overlay_fails(self):
        self.assertFalse(self.grade(WITH_OVERLAY, WITH_OVERLAY, WITH_OVERLAY, WITH_OVERLAY)["passed"])


class SessionQuotesCorpus(unittest.TestCase):
    DECLINE = ("/companion band or pottery?", "No Overlay found. Want to set one up?")

    def ev(self, second_reply: str) -> Evidence:
        return session_evidence("band-or-pottery", [[self.DECLINE, ("no thanks", second_reply)]],
                                [BARE, BARE, BARE])

    def test_orient_after_declining_setup_passes(self):
        self.assertTrue(grade(["session_quotes_corpus"], self.ev(GOOD_ORIENT))["passed"])

    def test_session_that_stops_after_decline_fails(self):
        out = grade(["session_quotes_corpus"], self.ev("Okay, no setup. Come back any time."))
        self.assertFalse(out["passed"])


CAR = vault_state("spanish-and-the-car",
                  "## Companion\n\n- index: [[home]]\n- log: `thinking log.md`\n")
OLD_LOG = CAR["thinking log.md"]
LINE_1 = "- 2026-10-19 — drop the Spanish class? — menu unpicked: [a] file line, [b] let it sit\n"
LINE_2 = "- 2026-10-19 — fix or sell the car — let it sit\n"
TWO_SESSIONS = [[("/companion drop the Spanish class?", "orient"), ("let's stop", "menu")],
                [("/companion fix or sell the car?", "orient"), ("b", "Logged.")]]


def log_states(*logs: str) -> list:
    """Vault snapshots that differ only in the log."""
    return [{**CAR, "thinking log.md": log} for log in logs]


class OneLogLinePerSession(unittest.TestCase):
    def grade(self, *logs: str, names=("one_log_line_per_session",)):
        return grade(list(names), session_evidence("spanish-and-the-car", TWO_SESSIONS,
                                                   log_states(*logs)))

    def test_one_line_each_session_passes(self):
        out = self.grade(OLD_LOG, OLD_LOG, OLD_LOG + LINE_1,
                         OLD_LOG + LINE_1, OLD_LOG + LINE_1 + LINE_2)
        self.assertTrue(out["passed"], out)

    def test_rewriting_the_session_s_own_line_when_a_pick_comes_passes(self):
        unpicked = "- 2026-10-19 — fix or sell the car — menu unpicked: [a], [b]\n"
        out = self.grade(OLD_LOG, OLD_LOG + LINE_1, OLD_LOG + LINE_1,
                         OLD_LOG + LINE_1 + unpicked, OLD_LOG + LINE_1 + LINE_2)
        self.assertTrue(out["passed"], out)

    def test_two_lines_in_one_session_fails(self):
        out = self.grade(OLD_LOG, OLD_LOG + LINE_1, OLD_LOG + LINE_1 + LINE_1,
                         OLD_LOG + LINE_1 + LINE_1, OLD_LOG + LINE_1 + LINE_1 + LINE_2)
        self.assertFalse(out["passed"])
        self.assertIn("session 1", out["results"][0]["note"])

    def test_a_session_with_no_line_fails(self):
        out = self.grade(OLD_LOG, OLD_LOG, OLD_LOG + LINE_1, OLD_LOG + LINE_1, OLD_LOG + LINE_1)
        self.assertFalse(out["passed"])
        self.assertIn("session 2", out["results"][0]["note"])

    def test_rewriting_an_earlier_session_s_line_fails(self):
        out = self.grade(OLD_LOG, OLD_LOG, OLD_LOG + LINE_1, OLD_LOG + LINE_1, LINE_1 + LINE_2)
        self.assertFalse(out["passed"])

    def test_a_turn_that_failed_before_its_snapshot_is_left_out(self):
        ev = session_evidence("spanish-and-the-car", TWO_SESSIONS,
                              log_states(OLD_LOG, OLD_LOG, OLD_LOG + LINE_1))
        out = grade(["one_log_line_per_session"], ev)
        self.assertTrue(out["passed"], out)

    def test_log_written_somewhere_else_fails(self):
        ev = session_evidence("spanish-and-the-car", TWO_SESSIONS, log_states(*[OLD_LOG] * 5))
        ev.snapshots[-1] = {**ev.snapshots[-1], "log.md": LINE_1 + LINE_2}
        self.assertFalse(grade(["one_log_line_per_session"], ev)["passed"])


class WritesOnlyLog(unittest.TestCase):
    def ev(self, diff: dict) -> Evidence:
        ev = session_evidence("spanish-and-the-car", TWO_SESSIONS, log_states(*[OLD_LOG] * 5))
        ev.diff = diff
        return ev

    def test_only_the_log_changed_passes(self):
        diff = {"added": {}, "removed": [], "modified": {"thinking log.md": [OLD_LOG, OLD_LOG + LINE_1]}}
        self.assertTrue(grade(["writes_only_log"], self.ev(diff))["passed"])

    def test_a_transcript_beside_the_log_fails_and_is_named(self):
        diff = {"added": {"session.md": "chat"}, "removed": [],
                "modified": {"thinking log.md": [OLD_LOG, OLD_LOG + LINE_1]}}
        out = grade(["writes_only_log"], self.ev(diff))
        self.assertFalse(out["passed"])
        self.assertIn("session.md", out["results"][0]["note"])


UNPICKED_LOGS = (OLD_LOG, OLD_LOG + LINE_1, OLD_LOG + LINE_1,
                 OLD_LOG + LINE_1 + LINE_2, OLD_LOG + LINE_1 + LINE_2)


class UnpickedMenuLogged(unittest.TestCase):
    def test_first_session_logged_as_menu_unpicked_passes(self):
        ev = session_evidence("spanish-and-the-car", TWO_SESSIONS, log_states(*UNPICKED_LOGS))
        self.assertTrue(grade(["unpicked_menu_logged"], ev)["passed"])

    def test_first_session_logged_with_an_invented_outcome_fails(self):
        picked = "- 2026-10-19 — drop the Spanish class? — let it sit\n"
        ev = session_evidence("spanish-and-the-car", TWO_SESSIONS,
                              log_states(OLD_LOG, OLD_LOG + picked, OLD_LOG + picked,
                                         OLD_LOG + picked + LINE_2, OLD_LOG + picked + LINE_2))
        out = grade(["unpicked_menu_logged"], ev)
        self.assertFalse(out["passed"])
        self.assertIn("let it sit", out["results"][0]["note"])


class UnpickedMenuNamedOnce(unittest.TestCase):
    SPEC = {"name": "unpicked_menu_named_once", "topic": "spanish"}

    def ev(self, first: str, second: str) -> Evidence:
        sessions = [TWO_SESSIONS[0], [("/companion fix or sell the car?", first),
                                      ("the clutch is the real question", second)]]
        return session_evidence("spanish-and-the-car", sessions, log_states(*UNPICKED_LOGS))

    def test_named_in_the_first_reply_only_passes(self):
        out = grade([self.SPEC], self.ev("Last time, Spanish class, menu unpicked. Now: the car.",
                                         "900 for a clutch on a car worth 1,200."))
        self.assertTrue(out["passed"], out)

    def test_named_only_after_orient_quotes_fails(self):
        out = grade([self.SPEC], self.ev('- [[the car]] — "The car is fourteen years old."\n'
                                         "Also: last time, Spanish class, menu unpicked.", "Sell it."))
        self.assertFalse(out["passed"])
        self.assertIn("after", out["results"][0]["note"])

    def test_not_named_fails(self):
        out = grade([self.SPEC], self.ev("The car. 900 for the clutch.", "Sell it."))
        self.assertFalse(out["passed"])

    def test_named_again_later_fails(self):
        out = grade([self.SPEC], self.ev("Last time, Spanish class, menu unpicked.",
                                         "Still want to pick up the Spanish menu?"))
        self.assertFalse(out["passed"])
        self.assertIn("reply 2", out["results"][0]["note"])

    def test_a_grader_without_its_parameter_is_a_setup_error(self):
        with self.assertRaises(TypeError):
            grade(["unpicked_menu_named_once"], self.ev("x", "y"))


if __name__ == "__main__":
    unittest.main()
