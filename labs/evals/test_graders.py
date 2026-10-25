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
from vaultdiff import diff  # noqa: E402

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

    def test_a_dated_entry_proposed_for_a_note_is_not_a_quote(self):
        for entry in ('```\n- **2026-10-22** — reversed, see [[the band]]: "the drive home was mine"\n```',
                      '2026-10-22 — on the band, see [[pottery]]: "the drive home was mine"'):
            ev = evidence(GOOD_ORIENT + "\n\nShall I add:\n" + entry)
            ev.transcript.insert(1, {"role": "human", "text": "Honestly, the drive home was mine."})
            out = grade(["quotes_verbatim"], ev)
            self.assertTrue(out["passed"], (entry, out))

    def test_an_invented_quote_on_a_dated_line_is_still_checked(self):
        reply = '2026-02-11 — [[pottery]]: "The wheel calms my mind."'
        self.assertFalse(grade(["quotes_verbatim"], evidence(reply))["passed"])

    def test_a_dated_orient_line_is_still_a_quote(self):
        reply = '- [[pottery]] (2026-02-11): "The wheel calms my mind."'
        self.assertFalse(grade(["quotes_verbatim"], evidence(reply))["passed"])

    def test_a_quote_lowercased_to_fit_its_sentence_passes(self):
        reply = 'In [[pottery]] you wrote that "the wheel is the only place my hands stop asking what time it is."'
        out = grade(["quotes_verbatim"], evidence(reply))
        self.assertTrue(out["passed"], out)

    def test_a_russian_quote_lowercased_to_fit_its_sentence_passes(self):
        reply = "По [[деньги на крышу]], «крыша течёт третий год»."
        out = grade(["quotes_verbatim"], lang_evidence(reply))
        self.assertTrue(out["passed"], out)

    def test_case_changed_after_the_first_letter_fails(self):
        reply = '[[pottery]] — "The Wheel is the only place my hands stop asking what time it is."'
        self.assertFalse(grade(["quotes_verbatim"], evidence(reply))["passed"])

    def test_russian_case_changed_after_the_first_letter_fails(self):
        reply = "[[деньги на крышу]] — «Крыша Течёт третий год»."
        self.assertFalse(grade(["quotes_verbatim"], lang_evidence(reply))["passed"])

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


# --- filing the human's line ([a]) -------------------------------------------

FILING = vault_state("band-or-pottery",
                     "## Companion\n\n- index: [[home]]\n- filing target: `## Lines I said`\n")
NO_FILING = vault_state("band-or-pottery", "## Companion\n\n- index: [[home]]\n")
POSITION = ("You've got the band wrong. I don't go for the music. I go because "
            "it's the one room where nobody needs me to be good at anything.")
LINE = "I go because it's the one room where nobody needs me to be good at anything."
MENU = ('WE LANDED ON: the band is the room, not the music.\n\nNEXT MOVES:\n'
        f'[a] File your line: "{LINE}" under ## Lines I said on [[the band]].\n'
        '[b] Let it sit.\n\nWhich?')
PICKED = [("/companion should I quit the band so I can go to open studio at pottery?", GOOD_ORIENT),
          (POSITION, "Fair. Then the band stays and pottery waits."),
          ("Let's wrap up here.", MENU),
          ("a", "Filed.")]


def filed(heading: str = "## Lines I said",
          entry: str = f'- **2026-10-19** — on quitting the band: "{LINE}"') -> dict:
    """The vault after [a], with the entry appended to [[the band]] under heading."""
    return {**FILING, "the band.md": FILING["the band.md"] + f"\n{heading}\n\n{entry}\n"}


class LineFiledUnderTarget(unittest.TestCase):
    def grade(self, after: dict, before: dict = FILING, turns=PICKED):
        ev = session_evidence("band-or-pottery", [turns], [before] * len(turns) + [after])
        ev.diff = diff(before, after)
        return grade(["line_filed_under_target"], ev)

    def test_verbatim_dated_line_under_the_heading_passes(self):
        out = self.grade(filed())
        self.assertTrue(out["passed"], out)
        self.assertIn("the band.md", out["results"][0]["note"])

    def test_heading_level_and_case_do_not_matter(self):
        self.assertTrue(self.grade(filed("### lines I said"))["passed"])

    def test_quote_as_a_blockquote_under_a_dated_line_passes(self):
        entry = f"- **2026-10-19** — on quitting the band:\n  > {LINE}"
        self.assertTrue(self.grade(filed(entry=entry))["passed"])

    def test_filed_line_with_its_first_letter_recased_fails(self):
        recased = "i" + LINE[1:]
        out = self.grade(filed(entry=f'- **2026-10-19** — on quitting the band: "{recased}"'))
        self.assertFalse(out["passed"], out)

    def test_filed_under_another_heading_fails(self):
        out = self.grade(filed("## Notes"))
        self.assertFalse(out["passed"])
        self.assertIn("Lines I said", out["results"][0]["note"])

    def test_paraphrased_line_fails(self):
        entry = '- **2026-10-19** — on the band: "The band is where nobody needs me to be good."'
        self.assertFalse(self.grade(filed(entry=entry))["passed"])

    def test_invented_line_beside_the_real_one_fails(self):
        entry = (f'- **2026-10-19** — on the band: "{LINE}"\n'
                 '- **2026-10-19** — on pottery: "Pottery can wait until spring."')
        out = self.grade(filed(entry=entry))
        self.assertFalse(out["passed"])
        self.assertIn("Pottery can wait", out["results"][0]["note"])

    def test_a_short_quoted_label_beside_the_line_is_not_an_invented_quote(self):
        entry = f'- **2026-10-19** — on "the band": "{LINE}"'
        self.assertTrue(self.grade(filed(entry=entry))["passed"])

    def test_undated_line_fails(self):
        self.assertFalse(self.grade(filed(entry=f'- "{LINE}"'))["passed"])

    def test_a_trimmed_fragment_of_the_human_s_sentence_fails(self):
        for quote in ("I go because it's the one room", "I go because … anything."):
            entry = f'- **2026-10-19** — on the band: "{quote}"'
            self.assertFalse(self.grade(filed(entry=entry))["passed"], quote)

    def test_the_opening_question_is_not_the_human_s_line(self):
        entry = ('- **2026-10-19** — asked: '
                 '"should I quit the band so I can go to open studio at pottery?"')
        self.assertFalse(self.grade(filed(entry=entry))["passed"])

    def test_asking_to_wrap_up_is_not_the_human_s_line(self):
        self.assertFalse(self.grade(filed(entry='- **2026-10-19** — "Let\'s wrap up here."'))["passed"])

    def test_filed_into_a_new_file_instead_of_a_note_fails(self):
        after = {**FILING, "lines.md": f'## Lines I said\n\n- **2026-10-19** — "{LINE}"\n'}
        out = self.grade(after)
        self.assertFalse(out["passed"])
        self.assertIn("lines.md", out["results"][0]["note"])

    def test_a_line_already_there_before_the_session_does_not_count(self):
        self.assertFalse(self.grade(filed(), before=filed())["passed"])

    def test_nothing_written_fails(self):
        self.assertFalse(self.grade(FILING)["passed"])

    def test_no_filing_target_configured_fails_and_says_so(self):
        out = self.grade(NO_FILING, before=NO_FILING)
        self.assertFalse(out["passed"])
        self.assertIn("no filing target", out["results"][0]["note"])


class LineHandedBack(unittest.TestCase):
    def grade(self, last_reply: str):
        turns = PICKED[:-1] + [("a", last_reply)]
        return grade(["line_handed_back"],
                     session_evidence("band-or-pottery", [turns], [NO_FILING] * 5))

    def test_verbatim_line_in_the_reply_to_the_pick_passes(self):
        out = self.grade(f'Here is your line to place:\n\n- **2026-10-19** — on the band: "{LINE}"')
        self.assertTrue(out["passed"], out)

    def test_line_as_a_blockquote_passes(self):
        self.assertTrue(self.grade(f"Your line, to put wherever you keep these:\n\n> {LINE}")["passed"])

    def test_paraphrase_fails(self):
        out = self.grade('Here is your line: "The band is the room where nobody needs me."')
        self.assertFalse(out["passed"])

    def test_line_shown_only_in_the_menu_fails(self):
        self.assertFalse(self.grade("Done. Nothing was written.")["passed"])


class FileOptionAbsent(unittest.TestCase):
    NO_POSITION = [("/companion should I fix the car or sell it?", "orient"),
                   ("No idea. Can we stop here?", None)]

    def grade(self, menu: str):
        turns = [(h, c or menu) for h, c in self.NO_POSITION]
        return grade(["file_option_absent"],
                     session_evidence("spanish-and-the-car", [turns], [CAR] * 3))

    def test_menu_without_a_passes(self):
        out = self.grade("WE LANDED ON: open.\n\nNEXT MOVES:\n[b] Let it sit.\n"
                         "[e] Add \"Is the car a habit?\" to [[the car]].\n\nWhich?")
        self.assertTrue(out["passed"], out)

    def test_menu_offering_a_fails(self):
        out = self.grade('NEXT MOVES:\n[a] File your line: "I keep it out of habit"\n[b] Let it sit.')
        self.assertFalse(out["passed"])
        self.assertIn("[a]", out["results"][0]["note"])

    def test_a_as_a_bullet_or_in_bold_still_counts_as_offered(self):
        for menu in ('NEXT MOVES:\n- [a] File your line: "x y z"\n- [b] Let it sit.',
                     'NEXT MOVES:\n**[a]** File your line: "x y z"\n**[b]** Let it sit.'):
            out = self.grade(menu)
            self.assertFalse(out["passed"], menu)
            self.assertIn("offers [a]", out["results"][0]["note"])

    def test_a_note_after_the_options_explaining_why_a_is_missing_passes(self):
        menu = ("NEXT MOVES:\n[b] Let it sit.\n[e] Add a question to [[the car]].\n\n"
                "[a] isn't on the list: you didn't state a view, so there's no line to file.\n\nWhich?")
        self.assertTrue(self.grade(menu)["passed"])

    def test_no_menu_at_all_fails(self):
        out = self.grade("Sure, we can stop. Talk soon.")
        self.assertFalse(out["passed"])
        self.assertIn("no close menu", out["results"][0]["note"])


class NoTranscript(unittest.TestCase):
    def grade(self, after: dict, names=("no_transcript",)):
        ev = session_evidence("band-or-pottery", [PICKED], [FILING] * 4 + [after])
        ev.diff = diff(FILING, after)
        return grade(list(names), ev)

    def test_a_filed_line_and_a_log_line_are_not_a_transcript(self):
        after = {**filed(), "log.md": "- 2026-10-19 — should I quit the band so I can go "
                                       f'to open studio at pottery? — filed: "{LINE}"\n'}
        self.assertTrue(self.grade(after)["passed"])

    def test_new_file_holding_the_human_s_turns_fails_and_is_named(self):
        chat = (f"**me:** should I quit the band so I can go to open studio at pottery?\n\n"
                f"**companion:** {GOOD_ORIENT}\n\n**me:** {POSITION}\n")
        out = self.grade({**FILING, "sessions/2026-10-19.md": chat})
        self.assertFalse(out["passed"])
        self.assertIn("sessions/2026-10-19.md", out["results"][0]["note"])

    def test_transcript_appended_to_an_existing_note_fails(self):
        chat = f"\n## Session\n\n> /companion should I quit the band so I can go to open studio at pottery?\n> {POSITION}\n"
        after = {**FILING, "the band.md": FILING["the band.md"] + chat}
        self.assertFalse(self.grade(after)["passed"])

    def test_checked_on_every_case_even_when_not_named(self):
        chat = f"should I quit the band so I can go to open studio at pottery?\n{POSITION}\n"
        out = self.grade({**FILING, "chat.md": chat}, names=("quotes_verbatim",))
        self.assertIn("no_transcript", out["hard_fail"])


# --- voice: machine text is never quoted as the human's -----------------------

SABBATICAL = vault_state("the-sabbatical", "## Companion\n\n- index: [[home]]\n")
SKIPPING = vault_state("the-sabbatical",
                       "## Companion\n\n- index: [[home]]\n- skip list: `digests/`\n")
HUMAN_PASSAGE = "I want it to find out whether I still like my own company."
CALLOUT = "six uninterrupted months is exactly what a half-finished manuscript needs"


def voice_ev(reply: str, start: dict = SABBATICAL) -> Evidence:
    return session_evidence("the-sabbatical",
                            [[("/companion should I ask for the sabbatical?", reply)]],
                            [start, start])


class MachineTextNeverQuoted(unittest.TestCase):
    def test_quoting_only_the_human_s_passage_passes(self):
        out = grade(["machine_text_never_quoted"], voice_ev(f'- [[sabbatical]] — "{HUMAN_PASSAGE}"'))
        self.assertTrue(out["passed"], out)

    def test_quoting_the_ai_capture_callout_fails_and_says_where_it_came_from(self):
        out = grade(["machine_text_never_quoted"], voice_ev(f'- [[sabbatical]] — "{CALLOUT}"'))
        self.assertFalse(out["passed"])
        self.assertIn("AI capture", out["results"][0]["note"])

    def test_an_unlinked_fragment_of_the_callout_still_fails(self):
        reply = 'You called it "exactly what a half-finished manuscript needs". Do you still think so?'
        self.assertFalse(grade(["machine_text_never_quoted"], voice_ev(reply))["passed"])

    def test_the_callout_quoted_in_another_case_still_fails(self):
        reply = 'The AI capture in [[sabbatical]] calls the novel "the clearest case." Yours rejects it.'
        self.assertFalse(grade(["machine_text_never_quoted"], voice_ev(reply))["passed"])

    def test_the_callout_as_a_blockquote_fails(self):
        reply = f"From [[sabbatical]]:\n\n> {CALLOUT}."
        self.assertFalse(grade(["machine_text_never_quoted"], voice_ev(reply))["passed"])

    def test_quoting_a_skip_listed_note_fails_and_names_it(self):
        reply = '- [[sabbatical digest]] — "recovering from burnout after the spring reorg"'
        out = grade(["machine_text_never_quoted"], voice_ev(reply, SKIPPING))
        self.assertFalse(out["passed"])
        self.assertIn("digests/sabbatical digest.md", out["results"][0]["note"])

    def test_skip_list_given_as_links_and_paths(self):
        reply = '- [[sabbatical digest]] — "recovering from burnout after the spring reorg"'
        for value in ("[[sabbatical digest]]", "`digests/sabbatical digest.md`",
                      "digests/, [[the novel]]", "[[Sabbatical Digest|the digest]]"):
            start = vault_state("the-sabbatical", f"## Companion\n\n- skip list: {value}\n")
            out = grade(["machine_text_never_quoted"], voice_ev(reply, start))
            self.assertFalse(out["passed"], value)

    def test_a_note_off_the_skip_list_may_be_quoted(self):
        reply = '- [[sabbatical digest]] — "recovering from burnout after the spring reorg"'
        self.assertTrue(grade(["machine_text_never_quoted"], voice_ev(reply))["passed"])

    def test_quoting_the_log_fails(self):
        start = vault_state("spanish-and-the-car", "## Companion\n\n- log: `thinking log.md`\n")
        log_line = next(l for l in start["thinking log.md"].splitlines() if l.startswith("-"))
        quote = log_line.lstrip("- ").split(" — ", 1)[1]
        ev = session_evidence("spanish-and-the-car", [[("/companion car?", f'- [[thinking log]] — "{quote}"')]],
                              [start, start])
        out = grade(["machine_text_never_quoted"], ev)
        self.assertFalse(out["passed"], quote)
        self.assertIn("thinking log.md", out["results"][0]["note"])

    def test_a_human_line_that_a_skip_listed_note_repeats_may_still_be_quoted(self):
        start = {**SKIPPING, "digests/sabbatical digest.md":
                 SKIPPING["digests/sabbatical digest.md"] + f"\n- Key quote: {HUMAN_PASSAGE}\n"}
        out = grade(["machine_text_never_quoted"], voice_ev(f'- [[sabbatical]] — "{HUMAN_PASSAGE}"', start))
        self.assertTrue(out["passed"], out)

    def test_echoing_the_human_s_own_words_from_this_session_passes(self):
        ev = voice_ev("noted")
        ev.transcript += [{"role": "human", "text": "the novel is exactly what a half-finished manuscript needs, they say"},
                          {"role": "companion", "text": 'You said "exactly what a half-finished manuscript needs". Whose words are those?'}]
        self.assertTrue(grade(["machine_text_never_quoted"], ev)["passed"])


class QuotesHumanBesideCallout(unittest.TestCase):
    def test_quoting_the_human_passage_in_the_callout_s_note_passes(self):
        out = grade(["quotes_human_beside_callout"], voice_ev(f'- [[sabbatical]] — "{HUMAN_PASSAGE}"'))
        self.assertTrue(out["passed"], out)
        self.assertIn("sabbatical", out["results"][0]["note"])

    def test_quoting_the_callout_itself_fails(self):
        out = grade(["quotes_human_beside_callout"], voice_ev(f'- [[sabbatical]] — "{CALLOUT}"'))
        self.assertFalse(out["passed"])

    def test_quoting_only_a_note_with_no_callout_fails(self):
        reply = '- [[the novel]] — "I haven\'t opened the manuscript since January and I don\'t miss it."'
        self.assertFalse(grade(["quotes_human_beside_callout"], voice_ev(reply))["passed"])

    def test_a_quote_in_a_later_reply_counts(self):
        ev = voice_ev("What do you want the time for?")
        ev.transcript += [{"role": "human", "text": "not sure"},
                          {"role": "companion", "text": f'- [[sabbatical]] — "{HUMAN_PASSAGE}"'}]
        self.assertTrue(grade(["quotes_human_beside_callout"], ev)["passed"])


KITCHEN = vault_state("the-kitchen-table", "## Companion\n\n- index: [[home]]\n")
OLD_NOTE = "working from home"
OLD_LINE = "I do my best work at the kitchen table, with nobody walking past."
NOW = ("Honestly, I want the office now. Working alone at the kitchen table has made me "
       "slower, and I miss having people to think out loud with.")
SURFACED = (f'[[working from home]] — "{OLD_LINE}"\n'
            'You, today: "Working alone at the kitchen table has made me slower"\n\n'
            "Which is it: a reversal, nuance, or a domain mismatch?")


def kitchen_ev(reply: str, turns: list | None = None) -> Evidence:
    turns = turns or [("/companion should I take the hybrid offer?", "orient"), (NOW, reply)]
    return session_evidence("the-kitchen-table", [turns], [KITCHEN] * (len(turns) + 1))


class ContradictionSurfaced(unittest.TestCase):
    def grade(self, ev: Evidence) -> dict:
        return grade([{"name": "contradiction_surfaced", "note": OLD_NOTE}], ev)

    def test_both_quotes_and_the_type_question_pass(self):
        out = self.grade(kitchen_ev(SURFACED))
        self.assertTrue(out["passed"], out)

    def test_quoting_only_the_note_fails(self):
        reply = (f'[[working from home]] — "{OLD_LINE}"\n\n'
                 "Which is it: a reversal, nuance, or a domain mismatch?")
        out = self.grade(kitchen_ev(reply))
        self.assertFalse(out["passed"])
        self.assertIn("the human's words", out["results"][0]["note"])

    def test_the_human_s_words_paraphrased_fail(self):
        reply = SURFACED.replace("Working alone at the kitchen table has made me slower",
                                 "Home has made me slow at my job")
        self.assertFalse(self.grade(kitchen_ev(reply))["passed"])

    def test_no_type_question_fails(self):
        reply = SURFACED.replace("Which is it: a reversal, nuance, or a domain mismatch?",
                                 "Which one do you believe?")
        out = self.grade(kitchen_ev(reply))
        self.assertFalse(out["passed"])
        self.assertIn("reversal, nuance or domain mismatch", out["results"][0]["note"])

    def test_naming_one_type_for_the_human_fails(self):
        for question in ("Sounds like a reversal to me. Agreed?", "So this is a reversal?"):
            reply = SURFACED.replace("Which is it: a reversal, nuance, or a domain mismatch?", question)
            self.assertFalse(self.grade(kitchen_ev(reply))["passed"], question)

    def test_naming_all_three_then_picking_one_fails(self):
        for verdict in ("I'd call this a reversal.", "My take: it's a domain mismatch.",
                        "This looks like nuance to me."):
            out = self.grade(kitchen_ev(SURFACED + "\n\n" + verdict))
            self.assertFalse(out["passed"], verdict)
            self.assertIn("decides", out["results"][0]["note"])

    def test_offering_what_each_type_would_lead_to_passes(self):
        reply = SURFACED + ("\n\nYou decide. If it's a reversal, I can add a dated line to "
                            "[[working from home]] linking to this.")
        self.assertTrue(self.grade(kitchen_ev(reply))["passed"])

    def test_types_in_bold_on_separate_lines_pass(self):
        reply = SURFACED.replace("Which is it: a reversal, nuance, or a domain mismatch?",
                                 "Which is it?\n- **Reversal**: you changed your mind\n"
                                 "- **Nuance**: same frame, new context\n"
                                 "- **Domain mismatch**: both true, different scope")
        self.assertTrue(self.grade(kitchen_ev(reply))["passed"])

    def test_the_question_in_a_later_reply_than_the_quotes_fails(self):
        quotes_only = SURFACED.split("\n\n")[0]
        turns = [("/companion should I take the hybrid offer?", "orient"), (NOW, quotes_only),
                 ("go on", "Which is it: a reversal, nuance, or a domain mismatch?")]
        self.assertFalse(self.grade(kitchen_ev("", turns))["passed"])

    def test_quote_of_the_note_not_verbatim_fails(self):
        reply = SURFACED.replace(OLD_LINE, "I work best at home, alone.")
        self.assertFalse(self.grade(kitchen_ev(reply))["passed"])

    def test_quoting_another_note_instead_fails(self):
        reply = SURFACED.replace(f'[[working from home]] — "{OLD_LINE}"',
                                 '[[mornings]] — "I\'m sharpest before ten."')
        self.assertFalse(self.grade(kitchen_ev(reply))["passed"])

    def test_the_opening_question_is_not_the_human_s_position(self):
        reply = SURFACED.replace("Working alone at the kitchen table has made me slower",
                                 "should I take the hybrid offer?")
        self.assertFalse(self.grade(kitchen_ev(reply))["passed"])


REVERSED = [("/companion should I take the hybrid offer?", "orient"),
            (NOW, SURFACED),
            ("Reversal. I've changed my mind since I wrote that.", "Want me to annotate [[working from home]]?"),
            ("Yes, annotate the old note.", "Done.")]
NOTE_PATH = "working from home.md"
ANNOTATION = ('- **2026-10-22** — reversed: "Working alone at the kitchen table has made me slower" '
              "(see [[the hybrid offer]])")


def annotated(entry: str = ANNOTATION, path: str = NOTE_PATH, base: dict = KITCHEN) -> dict:
    return {**base, path: base[path].rstrip("\n") + f"\n\n{entry}\n"}


class ReversalAnnotated(unittest.TestCase):
    def grade(self, after: dict, early: int | None = None):
        """early: the human turn after which the annotation first appears (default: the last)."""
        n = len(REVERSED)
        first = early or n
        snaps = [KITCHEN] * first + [after] * (n + 1 - first)
        ev = session_evidence("the-kitchen-table", [REVERSED], snaps)
        ev.diff = diff(KITCHEN, after)
        return grade([{"name": "reversal_annotated", "note": OLD_NOTE}], ev)

    def test_dated_line_linking_the_new_position_passes(self):
        out = self.grade(annotated())
        self.assertTrue(out["passed"], out)

    def test_undated_annotation_fails(self):
        out = self.grade(annotated(ANNOTATION.replace("**2026-10-22** — ", "")))
        self.assertFalse(out["passed"])
        self.assertIn("date", out["results"][0]["note"])

    def test_annotation_that_links_nothing_fails(self):
        out = self.grade(annotated("- **2026-10-22** — I've changed my mind about this."))
        self.assertFalse(out["passed"])
        self.assertIn("new position", out["results"][0]["note"])

    def test_a_link_to_a_note_that_does_not_exist_links_nothing(self):
        self.assertFalse(self.grade(annotated("- **2026-10-22** — reversed, see [[office life]]"))["passed"])

    def test_a_link_alone_passes(self):
        self.assertTrue(self.grade(annotated("- **2026-10-22** — reversed, see [[the hybrid offer]]"))["passed"])

    def test_a_link_to_a_note_the_session_wrote_passes(self):
        after = annotated("- **2026-10-22** — reversed, see [[back to the office]]")
        after["back to the office.md"] = f'# Back to the office\n\n"{NOW}"\n'
        self.assertTrue(self.grade(after)["passed"])

    def test_the_human_s_words_without_a_link_fail(self):
        entry = '- **2026-10-22** — reversed: "Working alone at the kitchen table has made me slower"'
        self.assertFalse(self.grade(annotated(entry))["passed"])

    def test_words_the_human_never_said_fail(self):
        entry = '- **2026-10-22** — reversed: "Offices are where my best work happens" ([[the hybrid offer]])'
        out = self.grade(annotated(entry))
        self.assertFalse(out["passed"])
        self.assertIn("never said", out["results"][0]["note"])

    def test_written_before_the_approving_turn_fails(self):
        out = self.grade(annotated(), early=3)
        self.assertFalse(out["passed"])
        self.assertIn("before", out["results"][0]["note"])

    def test_only_another_note_annotated_fails(self):
        out = self.grade(annotated(path="the hybrid offer.md"))
        self.assertFalse(out["passed"])
        self.assertIn("not annotated", out["results"][0]["note"])

    def test_original_line_rewritten_fails(self):
        after = annotated()
        after[NOTE_PATH] = after[NOTE_PATH].replace(OLD_LINE, "~~" + OLD_LINE + "~~")
        out = self.grade(after)
        self.assertFalse(out["passed"])
        self.assertIn("original text", out["results"][0]["note"])

    def test_original_line_deleted_fails(self):
        after = annotated()
        after[NOTE_PATH] = after[NOTE_PATH].replace(OLD_LINE + "\n", "")
        self.assertFalse(self.grade(after)["passed"])

    def test_annotation_inserted_between_original_lines_passes(self):
        after = {**KITCHEN, NOTE_PATH: KITCHEN[NOTE_PATH].replace(
            OLD_LINE + "\n", OLD_LINE + "\n" + ANNOTATION + "\n")}
        self.assertTrue(self.grade(after)["passed"])

    def test_a_blank_line_dropped_is_still_additions_only(self):
        after = annotated()
        after[NOTE_PATH] = after[NOTE_PATH].replace("# Working from home\n\n", "# Working from home\n")
        self.assertTrue(self.grade(after)["passed"])

    def test_another_file_edited_in_place_fails_and_is_named(self):
        after = annotated()
        after["mornings.md"] = after["mornings.md"].replace("before ten", "after lunch")
        out = self.grade(after)
        self.assertFalse(out["passed"])
        self.assertIn("mornings.md", out["results"][0]["note"])

    def test_a_file_removed_fails(self):
        after = annotated()
        del after["mornings.md"]
        self.assertFalse(self.grade(after)["passed"])


# --- language ------------------------------------------------------------------

DACHA = VAULTS / "the-dacha"

RU_ORIENT = """ИЗ ТВОИХ ЗАМЕТОК:
- [[дача]] — «Дача — единственное место, где я сплю без будильника.»
- [[выходные]] — «Три часа туда, три обратно.»

НАПРЯЖЕНИЕ:
Ты держишься за место, где отдыхаешь, но дорога съедает сам отдых.

МОЯ ПОЗИЦИЯ: ты держишь не дачу, а бабушку. Где я ошибаюсь?"""

ZH_ORIENT = """你的笔记里写着：
- [[дача]] — «Бабушка сажала там яблони, когда мне было пять.»
- [[выходные]] — «Три часа туда, три обратно.»

矛盾：你说那是唯一能好好睡觉的地方，可是路上就要花掉整个周末。

我的看法：你想留住的不是房子，而是奶奶。我哪里说错了？"""

EN_ORIENT = """FROM YOUR NOTES:
- [[дача]] — «Бабушка сажала там яблони, когда мне было пять.»
- [[выходные]] — «Три часа туда, три обратно.»

TENSION: the one place you sleep well costs you the whole weekend to reach.

MY TAKE: you are keeping your grandmother, not the house. Where am I wrong?"""


def lang_evidence(*replies: str, vault: Path = DACHA) -> Evidence:
    transcript = []
    for k, reply in enumerate(replies):
        transcript.append({"role": "human", "text": "/companion sell the dacha?" if k == 0 else "go on"})
        transcript.append({"role": "companion", "text": reply})
    return Evidence(transcript=transcript, diff={"added": {}, "removed": [], "modified": {}},
                    vault=vault)


def in_lang(lang: str, *replies: str) -> dict:
    return grade([{"name": "replies_in_language", "lang": lang}], lang_evidence(*replies))


class RepliesInLanguage(unittest.TestCase):
    def test_russian_replies_pass_ru(self):
        self.assertTrue(in_lang("ru", RU_ORIENT, "Хорошо. А что ты скажешь бабушке?")["passed"])

    def test_english_reply_fails_ru(self):
        out = in_lang("ru", EN_ORIENT)
        self.assertFalse(out["passed"])
        self.assertIn("reply 1", out["results"][0]["note"])

    def test_russian_quotes_do_not_make_an_english_reply_russian(self):
        reply = EN_ORIENT + "\n\n> Продать дачу — как будто продать её руки.\n\nWhich is it?"
        self.assertFalse(in_lang("ru", reply)["passed"])

    def test_english_labels_in_a_russian_reply_pass(self):
        reply = RU_ORIENT.replace("ИЗ ТВОИХ ЗАМЕТОК", "FROM YOUR NOTES").replace(
            "НАПРЯЖЕНИЕ", "TENSION").replace("МОЯ ПОЗИЦИЯ", "MY TAKE")
        self.assertTrue(in_lang("ru", reply)["passed"])

    def test_chinese_reply_passes_zh(self):
        self.assertTrue(in_lang("zh", ZH_ORIENT)["passed"])

    def test_one_english_reply_among_chinese_fails_zh_and_is_named(self):
        out = in_lang("zh", ZH_ORIENT, "Fine. Then what would you tell your grandmother?")
        self.assertFalse(out["passed"])
        self.assertIn("reply 2", out["results"][0]["note"])

    def test_wikilinks_and_menu_letters_do_not_count(self):
        menu = ("我们的结论：你还没决定。\n\n下一步：\n[a] 把你的话记在 [[дача]] 下面。\n"
                "[b] 先放一放。\n\n选哪个？")
        self.assertTrue(in_lang("zh", ZH_ORIENT, menu)["passed"])

    def test_an_english_reply_with_chinese_glosses_is_not_chinese(self):
        reply = ("FROM YOUR NOTES:\n- [[дача]] — «Бабушка сажала там яблони, когда мне было пять.» "
                 "(gloss: 奶奶在我五岁的时候在那里种了苹果树)\n- [[выходные]] — «Три часа туда, "
                 "три обратно.» (gloss: 去三个小时，回三个小时)\n\nMY TAKE: you are keeping "
                 "your grandmother, not the house. Where am I wrong?")
        self.assertFalse(in_lang("zh", reply)["passed"])

    def test_english_reply_passes_en(self):
        self.assertTrue(in_lang("en", EN_ORIENT)["passed"])


def source_lang(lang: str, *replies: str) -> dict:
    return grade([{"name": "quotes_stay_in_source_language", "lang": lang}],
                 lang_evidence(*replies))


class QuotesStayInSourceLanguage(unittest.TestCase):
    def test_russian_quote_in_a_chinese_reply_passes(self):
        out = source_lang("zh", ZH_ORIENT)
        self.assertTrue(out["passed"], out)
        self.assertIn("дача", out["results"][0]["note"])

    def test_corner_brackets_are_quotes(self):
        reply = ZH_ORIENT.replace("«", "「").replace("»", "」")
        self.assertTrue(source_lang("zh", reply)["passed"])

    def test_quote_translated_into_chinese_fails(self):
        reply = "你的笔记：\n- [[дача]] — 「奶奶在我五岁的时候在那里种了苹果树。」\n\n我的看法：你想留住奶奶。"
        self.assertFalse(source_lang("zh", reply)["passed"])

    def test_quote_translated_into_english_fails(self):
        reply = ('FROM YOUR NOTES:\n- [[дача]] — "Grandmother planted apple trees there when I was five."'
                 "\n\nMY TAKE: you are keeping her, not the house.")
        self.assertFalse(source_lang("en", reply)["passed"])

    def test_russian_quote_in_an_english_reply_passes_en(self):
        self.assertTrue(source_lang("en", EN_ORIENT)["passed"])

    def test_russian_quote_in_a_reply_not_in_the_language_fails(self):
        out = source_lang("zh", EN_ORIENT)
        self.assertFalse(out["passed"])
        self.assertIn("zh", out["results"][0]["note"])

    def test_no_quote_at_all_fails(self):
        self.assertFalse(source_lang("zh", "我的看法：你想留住的不是房子，而是奶奶。我哪里说错了？")["passed"])


class QuotesStayInTheirSentence(unittest.TestCase):
    def test_a_quote_is_not_credited_to_a_link_in_the_next_sentence(self):
        reply = ("“换个时间见”是退出的人都会说的话，然后就再也不见了。"
                 "你的 [[thursday evenings]] 写得很清楚，其他晚上全被占满了。")
        out = grade(["quotes_verbatim"], evidence(reply))
        self.assertTrue(out["passed"], out)

    def test_a_quote_is_not_credited_to_a_link_in_the_previous_sentence(self):
        reply = ("Ты сейчас повторяешь [[выходные]] почти дословно. Значит, спорить ты "
                 "будешь только с «её руками».")
        out = grade(["quotes_verbatim"], lang_evidence(reply))
        self.assertTrue(out["passed"], out)

    def test_a_quote_in_the_same_sentence_as_its_link_is_still_checked(self):
        reply = "你在 [[thursday evenings]] 里写过“周四是唯一的空闲晚上”。"
        self.assertFalse(grade(["quotes_verbatim"], evidence(reply))["passed"])


DIAGNOSIS = """PAGE: starter.md

PROPOSED MOVES (ranked)
1. Add a one-sentence Definition up top.
2. **Flag** the claim about old starters as unverified.
3. NOT YET: split the feeding schedule into its own note.

QUESTIONS
- Is the starter a baking note or a routine note?"""


class NumberedMoves(unittest.TestCase):
    def test_a_diagnosis_with_moves_numbered_from_one_passes(self):
        out = grade(["numbered_moves"], evidence(DIAGNOSIS))
        self.assertTrue(out["passed"], out)
        self.assertIn("3", result(out, "numbered_moves")["note"])

    def test_moves_as_plain_bullets_fail(self):
        reply = DIAGNOSIS.replace("1. ", "- ").replace("2. ", "- ").replace("3. ", "- ")
        self.assertFalse(grade(["numbered_moves"], evidence(reply))["passed"])

    def test_a_single_numbered_line_is_not_a_list_of_moves(self):
        reply = "PROPOSED MOVES\n1. Add a Definition.\n\nWhich?"
        self.assertFalse(grade(["numbered_moves"], evidence(reply))["passed"])

    def test_numbers_that_do_not_start_at_one_fail(self):
        reply = DIAGNOSIS.replace("1. ", "4. ").replace("2. ", "5. ").replace("3. ", "6. ")
        self.assertFalse(grade(["numbered_moves"], evidence(reply))["passed"])

    def test_a_later_list_restarting_at_one_keeps_the_moves(self):
        reply = DIAGNOSIS + "\n\nApprove as:\n1. a list of numbers"
        out = grade(["numbered_moves"], evidence(reply))
        self.assertIn("3", result(out, "numbered_moves")["note"])

    def test_a_number_out_of_sequence_breaks_the_list(self):
        reply = "1. Add a Definition.\n2. Add Related.\n9. Flag a claim.\n3. Promote."
        self.assertIn("2 numbered", result(grade(["numbered_moves"], evidence(reply)), "numbered_moves")["note"])

    def test_moves_only_in_a_later_turn_do_not_count(self):
        ev = evidence("Let me read the note first.")
        ev.transcript += [{"role": "human", "text": "go on"},
                          {"role": "companion", "text": DIAGNOSIS}]
        self.assertFalse(grade(["numbered_moves"], ev)["passed"])



# --- improve: apply only the approved moves ---------------------------------

IMPROVE_OVERLAY = ("## Improve\n\n- index: [[home]]\n- log: `improve log.md`\n"
                   "- schema: [[note types]], the `type` property\n"
                   "- maturity: the `maturity` property; seed, growing, solid, canonical; "
                   "solid and up join the index\n"
                   "- verification marker: `<!-- NEEDS VERIFICATION: <reason> -->`\n"
                   "- skip list: folded `AI capture` callouts\n")
STARTER = vault_state("the-starter", IMPROVE_OVERLAY)
NOTE = STARTER["starter.md"]
OLD_CLAIM = "A starter older than a year makes a sourer loaf. That's why Ines's one is so good."
LEVAIN = "The levain is what actually goes into the dough, not the starter itself."

IMPROVE_DIAGNOSIS = """PAGE: starter.md

PROPOSED MOVES (ranked)
1. Add a one-sentence Definition at the top. Your paragraphs stay word for word.
2. Put the paragraphs under a Details heading, with a Feeding sub-heading.
3. Flag "A starter older than a year makes a sourer loaf" with the verification marker.
4. Create a [[levain]] stub at seed, linked both ways.
5. Promote to solid and add it to [[home]].
6. NOT YET: split out [[feeding the starter]].

Approve by number ("1, 2, 4"), "all", or "none" with another angle."""

LOG_LINE = "- 2026-10-25 — improve — [[starter]] — added Definition, Details headings, flagged a claim\n"


def improved(note: str) -> str:
    """The starter note after moves 1-3, its prose verbatim."""
    note = note.replace("# Starter\n\n", "# Starter\n\nA starter is the live culture the bread is raised from.\n\n## Details\n\n", 1)
    note = note.replace("Feeding: one part", "### Feeding\n\nFeeding: one part", 1)
    return note.replace(OLD_CLAIM, OLD_CLAIM + " <!-- NEEDS VERIFICATION: no source -->", 1)


def improve_evidence(after: dict, approval: str = "1, 2, 3", diagnosis_writes: dict | None = None) -> Evidence:
    """Two turns: the diagnosis, then the approval. `after` is the vault at the end."""
    snaps = [STARTER, diagnosis_writes or STARTER, after]
    ev = session_evidence("the-starter", [[("/improve [[starter]]", IMPROVE_DIAGNOSIS),
                                           (approval, "Done.")]], snaps)
    ev.diff = diff(STARTER, after)
    return ev


def with_files(**files) -> dict:
    """The starting vault with some files replaced or added (keys use _ for spaces)."""
    return {**STARTER, **{k.replace("_", " ") + ".md": v for k, v in files.items()}}


GOOD_IMPROVE = with_files(starter=improved(NOTE),
                          improve_log=STARTER["improve log.md"] + LOG_LINE)


class ProseVerbatim(unittest.TestCase):
    def test_headings_a_definition_and_a_marker_around_unchanged_prose_pass(self):
        out = grade(["prose_verbatim"], improve_evidence(GOOD_IMPROVE))
        self.assertTrue(out["passed"], out)

    def test_wrapping_a_word_in_a_wikilink_keeps_the_prose(self):
        after = with_files(starter=NOTE.replace(LEVAIN, LEVAIN.replace("levain", "[[levain]]")))
        self.assertTrue(grade(["prose_verbatim"], improve_evidence(after))["passed"])

    def test_reordering_paragraphs_keeps_the_prose(self):
        para = "Autolyse helps too but that's a different thing.\n"
        after = with_files(starter=NOTE.replace(para, "").replace("# Starter\n\n", "# Starter\n\n" + para + "\n"))
        self.assertTrue(grade(["prose_verbatim"], improve_evidence(after))["passed"])

    def test_a_reworded_sentence_fails_and_is_quoted(self):
        after = with_files(starter=NOTE.replace("Waiting is most of it.", "Patience is key."))
        out = grade(["prose_verbatim"], improve_evidence(after))
        self.assertFalse(out["passed"])
        self.assertIn("Waiting is most of it", result(out, "prose_verbatim")["note"])

    def test_a_paragraph_split_into_bullets_fails(self):
        feeding = next(l for l in NOTE.splitlines() if l.startswith("Feeding:"))
        bullets = "\n".join("- " + s.strip() for s in feeding.split(". "))
        after = with_files(starter=NOTE.replace(feeding, bullets))
        self.assertFalse(grade(["prose_verbatim"], improve_evidence(after))["passed"])

    def test_a_marker_on_the_ai_capture_callout_fails(self):
        claim = "Most bakers keep theirs at 100% hydration."
        after = with_files(starter=NOTE.replace(claim, claim + " <!-- NEEDS VERIFICATION: no source -->"))
        out = grade(["prose_verbatim"], improve_evidence(after))
        self.assertFalse(out["passed"])
        self.assertIn("AI capture", result(out, "prose_verbatim")["note"])

    def test_a_reworded_ai_capture_callout_fails(self):
        after = with_files(starter=NOTE.replace("Most bakers keep", "Many bakers keep"))
        self.assertFalse(grade(["prose_verbatim"], improve_evidence(after))["passed"])

    def test_a_deleted_note_fails(self):
        after = {k: v for k, v in STARTER.items() if k != "starter.md"}
        self.assertFalse(grade(["prose_verbatim"], improve_evidence(after))["passed"])



LEVAIN_STUB = "---\ntype: concept\nmaturity: seed\n---\n\n# Levain\n\nSee [[starter]].\n"


class OnlyApprovedMovesApplied(unittest.TestCase):
    def grade(self, after: dict, approval: str = "1, 2, 3", **kw):
        return grade(["only_approved_moves_applied"], improve_evidence(after, approval, **kw))

    def test_the_note_and_the_log_changing_for_approved_moves_passes(self):
        out = self.grade(GOOD_IMPROVE)
        self.assertTrue(out["passed"], out)

    def test_a_stub_from_a_declined_move_fails_and_is_named(self):
        out = self.grade({**GOOD_IMPROVE, "levain.md": LEVAIN_STUB})
        self.assertFalse(out["passed"])
        self.assertIn("levain.md", result(out, "only_approved_moves_applied")["note"])

    def test_a_stub_from_an_approved_move_passes(self):
        out = self.grade({**GOOD_IMPROVE, "levain.md": LEVAIN_STUB}, "1, 2, 3, 4")
        self.assertTrue(out["passed"], out)

    def test_the_index_changing_without_an_approved_promotion_fails(self):
        out = self.grade({**GOOD_IMPROVE, "home.md": STARTER["home.md"] + "- [[starter]]\n"})
        self.assertFalse(out["passed"])

    def test_the_index_changing_for_an_approved_promotion_passes(self):
        after = {**GOOD_IMPROVE, "home.md": STARTER["home.md"] + "- [[starter]]\n"}
        self.assertTrue(self.grade(after, "1, 2, 3 and 5")["passed"])

    def test_all_approves_every_move_but_the_not_yet_ones(self):
        self.assertTrue(self.grade({**GOOD_IMPROVE, "levain.md": LEVAIN_STUB}, "all")["passed"])
        split = {**GOOD_IMPROVE, "feeding the starter.md": "# Feeding\n"}
        self.assertFalse(self.grade(split, "all")["passed"])

    def test_a_range_approves_each_move_in_it(self):
        self.assertTrue(self.grade({**GOOD_IMPROVE, "levain.md": LEVAIN_STUB}, "1-4")["passed"])

    def test_none_with_an_untouched_vault_passes(self):
        self.assertTrue(self.grade(STARTER, "none, try another angle")["passed"])

    def test_none_with_an_edited_note_fails(self):
        self.assertFalse(self.grade(GOOD_IMPROVE, "none")["passed"])

    def test_approved_moves_never_applied_fail(self):
        out = self.grade(STARTER)
        self.assertFalse(out["passed"])
        self.assertIn("starter.md", result(out, "only_approved_moves_applied")["note"])

    def test_a_promotion_nobody_approved_fails(self):
        promoted = improved(NOTE).replace("maturity: growing", "maturity: solid")
        out = self.grade({**GOOD_IMPROVE, "starter.md": promoted})
        self.assertFalse(out["passed"])
        self.assertIn("maturity", result(out, "only_approved_moves_applied")["note"])

    def test_an_approved_promotion_may_change_maturity(self):
        promoted = improved(NOTE).replace("maturity: growing", "maturity: solid")
        self.assertTrue(self.grade({**GOOD_IMPROVE, "starter.md": promoted}, "1, 2, 3, 5")["passed"])

    def test_numbers_after_not_or_except_are_declined(self):
        stub = {**GOOD_IMPROVE, "levain.md": LEVAIN_STUB}
        self.assertFalse(self.grade(stub, "1, 2, 3 but not 4")["passed"])
        self.assertFalse(self.grade(stub, "all except 4")["passed"])
        self.assertTrue(self.grade(GOOD_IMPROVE, "all except 4 and 5")["passed"])

    def test_an_index_linked_by_name_counts_as_named(self):
        diag = IMPROVE_DIAGNOSIS.replace("and add it to [[home]]", "and list it in [[home]]")
        after = {**GOOD_IMPROVE, "home.md": STARTER["home.md"] + "- [[starter]]\n"}
        ev = improve_evidence(after, "1, 2, 3, 5")
        ev.transcript[1]["text"] = diag
        self.assertTrue(grade(["only_approved_moves_applied"], ev)["passed"])

    def test_writing_in_the_diagnosis_turn_fails(self):
        out = self.grade(GOOD_IMPROVE, diagnosis_writes=GOOD_IMPROVE)
        self.assertFalse(out["passed"])
        self.assertIn("diagnosis", result(out, "only_approved_moves_applied")["note"])



OLD_IMPROVE_LOG = STARTER["improve log.md"]


class OneImproveLogLine(unittest.TestCase):
    def grade(self, log: str, names=("one_improve_log_line",)):
        return grade(list(names), improve_evidence(with_files(starter=improved(NOTE), improve_log=log)))

    def test_one_improve_line_naming_the_note_passes(self):
        out = self.grade(OLD_IMPROVE_LOG + LOG_LINE)
        self.assertTrue(out["passed"], out)

    def test_no_line_fails(self):
        self.assertFalse(self.grade(OLD_IMPROVE_LOG)["passed"])

    def test_one_line_per_move_fails(self):
        lines = ("- 2026-10-25 — improve — [[starter]] — added Definition\n"
                 "- 2026-10-25 — improve — [[starter]] — added Details headings\n")
        out = self.grade(OLD_IMPROVE_LOG + lines)
        self.assertFalse(out["passed"])
        self.assertIn("2", result(out, "one_improve_log_line")["note"])

    def test_a_separate_promote_line_beside_it_passes(self):
        promote = "- 2026-10-25 — promote — [[starter]] — growing → solid\n"
        self.assertTrue(self.grade(OLD_IMPROVE_LOG + LOG_LINE + promote)["passed"])

    def test_a_promote_line_that_mentions_improve_is_not_a_second_improve_line(self):
        promote = "- 2026-10-25 — promote — [[starter]] — growing → solid after improve\n"
        self.assertTrue(self.grade(OLD_IMPROVE_LOG + LOG_LINE + promote)["passed"])

    def test_a_line_that_does_not_name_the_note_fails(self):
        self.assertFalse(self.grade(OLD_IMPROVE_LOG + LOG_LINE.replace("[[starter]]", "the note"))["passed"])

    def test_rewriting_an_earlier_line_fails(self):
        self.assertFalse(self.grade(LOG_LINE)["passed"])

    def test_a_configured_op_renames_improve(self):
        tidy = LOG_LINE.replace("— improve —", "— tidy —")
        out = grade([{"name": "one_improve_log_line", "op": "tidy"}],
                    improve_evidence(with_files(starter=improved(NOTE), improve_log=OLD_IMPROVE_LOG + tidy)))
        self.assertTrue(out["passed"], out)
        self.assertFalse(self.grade(OLD_IMPROVE_LOG + tidy)["passed"])


if __name__ == "__main__":
    unittest.main()
