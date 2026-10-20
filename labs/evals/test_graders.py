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


if __name__ == "__main__":
    unittest.main()
