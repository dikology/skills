"""Tests for span_audit.py.

The gate grades a mark only when its own line offers a `[[link]]` (`quote_sources`), so a run
can go 20/20 with marks that copy nothing still in its replies. This audits every marked span
instead, and says who owns each one's words. Expected classifications are worked out by hand
against the Fixture vault's text, never recomputed from the code under test.

    python3 -m unittest discover -s labs/evals -v
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from graders import Evidence  # noqa: E402
from span_audit import audit, audit_run, wrong_doors  # noqa: E402

VAULTS = Path(__file__).parent / "fixtures" / "vaults"
DACHA = VAULTS / "the-dacha"
BAND = VAULTS / "band-or-pottery"
KITCHEN = VAULTS / "the-kitchen-table"
SABBATICAL = VAULTS / "the-sabbatical"
CAR = VAULTS / "spanish-and-the-car"
CLASS = VAULTS / "the-studio-and-the-class"


def vault_view(name: str, overlay: str | None = None) -> dict:
    """The Fixture vault plus the case's Overlay — how the runner builds the vault a session
    starts in, and the only way the log and skip list are known as machine text."""
    root = VAULTS / name
    snap = {p.relative_to(root).as_posix(): p.read_text(errors="replace")
            for p in sorted(root.rglob("*.md"))}
    if overlay:
        snap["CLAUDE.md"] = snap.get("CLAUDE.md", "") + "\n\n" + overlay.strip() + "\n"
    return snap


def evidence(*replies: str, vault: Path = DACHA, human: str = "/companion sell the dacha?",
             overlay: str | None = None) -> Evidence:
    transcript = []
    for k, reply in enumerate(replies):
        transcript.append({"role": "human",
                           "text": human if k == 0 else "go on"})
        transcript.append({"role": "companion", "text": reply})
    return Evidence(transcript=transcript,
                    diff={"added": {}, "removed": [], "modified": {}}, vault=vault,
                    snapshots=[vault_view(vault.name, overlay)])


class MarksTheGateNeverGrades(unittest.TestCase):
    def test_a_mark_on_a_line_that_names_no_note_is_audited_though_it_is_not_graded(self):
        # gate25_candidate lang-quote-stays-source: 「留」 is the model's own word for the
        # option it is weighing. No note holds it, and the line offers no link, so
        # quotes_verbatim never looks at it.
        got = audit(evidence("我的判断：该卖。你说的「留」不是选择。"))
        self.assertEqual(len(got), 1)
        span = got[0]
        self.assertEqual(span.span, "留")
        self.assertFalse(span.graded)
        self.assertTrue(span.broken)
        self.assertEqual(span.kind, "no-source")


class GradedClaims(unittest.TestCase):
    def test_a_quote_line_that_copies_its_note_holds(self):
        got = audit(evidence('- [[дача]] — «Дача — единственное место, где я сплю без будильника.»'))
        self.assertEqual([s.kind for s in got], ["claim-ok"])
        self.assertTrue(got[0].graded)
        self.assertFalse(got[0].broken)

    def test_a_copy_credited_to_a_note_that_does_not_hold_it_fails(self):
        # gate25_candidate reversal-annotated: the copy is exact, and the sentence that
        # carries it names [[the hybrid offer]], so the mark claims a line that note
        # never said. [[mornings]] holds it — which is the shape's whole defect.
        reply = ('1. [[mornings]] is not reversed. "The train would eat the first hour '
                 'of that." still stands on the three office days in [[the hybrid offer]].')
        got = audit(evidence(reply, vault=KITCHEN, human="I want the office now."))
        self.assertEqual([s.kind for s in got], ["claim-fail"])
        self.assertTrue(got[0].graded)
        self.assertTrue(got[0].broken)
        self.assertIn("the hybrid offer", got[0].detail)
        self.assertIn("mornings", got[0].detail)


class InvisibleShapes(unittest.TestCase):
    def test_the_human_s_words_on_a_line_naming_no_note_are_their_line_not_a_claim(self):
        # The shape the skill prescribes: `- You, today — "…"`. Nothing to credit, so
        # nothing is broken — the same exemption quotes_verbatim gives it.
        reply = 'You, today — "Working alone at the kitchen table has made me slower."'
        got = audit(evidence(reply, vault=KITCHEN,
                             human="Working alone at the kitchen table has made me slower"))
        self.assertEqual([s.kind for s in got], ["human-verbatim"])
        self.assertFalse(got[0].graded)
        self.assertFalse(got[0].broken)
    def test_a_note_s_line_in_marks_on_a_line_naming_no_note_is_an_unowned_copy(self):
        # The words are a perfect copy, so #26 does not count this as broken. It is the
        # other half of the shape: an owner no line names, which the gate cannot see.
        reply = ('Two things the reversal does not settle.\n'
                 '"The train would eat the first hour of that." still stands.')
        got = audit(evidence(reply, vault=KITCHEN, human="I want the office now."))
        self.assertEqual([s.kind for s in got], ["note-copy-unowned"])
        self.assertFalse(got[0].graded)
        self.assertFalse(got[0].broken)
        self.assertIn("mornings", got[0].detail)

    def test_the_model_quoting_its_own_earlier_reply_is_a_broken_mark(self):
        # gate25_candidate: "let it sit and I'll note it" is the model's own sentence,
        # put in marks as if it were evidence. Nothing in the vault or from the human
        # holds it.
        first = "Let it sit and I'll note it. Nothing else is written."
        second = "So \"let it sit and I'll note it\" is the plan, then the Close menu."
        got = audit(evidence(first, second, vault=KITCHEN, human="just the log"))
        self.assertEqual([s.kind for s in got], ["self-quote"])
        self.assertTrue(got[0].broken)
    def test_the_human_s_words_recalled_slightly_edited_are_a_broken_mark(self):
        # audit25r1 reversal-annotated: the human said "Working alone at the kitchen
        # table has made me slower"; the reply put a compressed version of it in marks.
        human = ("Working alone at the kitchen table has made me slower, and I miss "
                 "having people to think out loud with.")
        reply = 'Which is the trade: "I got slower" is not the same deal as losing the hour.'
        got = audit(evidence(reply, vault=KITCHEN, human=human))
        self.assertEqual([s.kind for s in got], ["human-edited"])
        self.assertFalse(got[0].graded)
        self.assertTrue(got[0].broken)
    def test_a_span_too_short_to_be_a_line_is_a_label_not_a_broken_mark(self):
        # The gate's own floor: "only" matches a word inside any note's sentence, so a
        # short span naming no owner reads as emphasis on a term, not a claimed line.
        got = audit(evidence('Each hobby gets a superlative. "only" is the word.',
                             vault=KITCHEN, human="I want the office now."))
        self.assertEqual([s.kind for s in got], ["label"])
        self.assertFalse(got[0].broken)
    def test_chinese_words_the_human_said_on_a_line_naming_no_note_are_theirs_too(self):
        # The gate's exemption counts by whitespace, so a 中文 line the human typed is
        # never handed back to them there (that is how "必须有事从周四下来" cost
        # lang-pin-zh). The audit asks whose words they are instead: verbatim, they are.
        human = "必须有事从周四下来"
        got = audit(evidence("你说过「必须有事从周四下来」。", vault=DACHA, human=human))
        self.assertEqual([s.kind for s in got], ["human-verbatim"])
        self.assertFalse(got[0].broken)
    def test_a_russian_line_of_the_human_s_compressed_in_marks_is_recalled_not_sourceless(self):
        # fix26_lang2 lang-follows-human reply 2: the human said "Мне жалко бабушкины
        # яблони, но…"; the reply weighed «мне жалко, но». Broken either way, and the
        # habit matters to the copy fix, so the group has to read the Cyrillic words.
        human = ("Мне жалко бабушкины яблони, но я там бываю четыре раза в год, "
                 "и каждый раз что-то чиню.")
        got = audit(evidence('Ваше «мне жалко, но» — это разворот.', vault=DACHA, human=human))
        self.assertEqual([s.kind for s in got], ["human-edited"])
        self.assertTrue(got[0].broken)


class MachineTextHasNoOwner(unittest.TestCase):
    def test_a_span_copied_from_an_ai_capture_callout_claims_no_note(self):
        # The callout in the-sabbatical/sabbatical.md. A mark holding it is not "a true
        # copy with no owner named": machine text is never the human's voice, so the
        # mark holds nothing it may claim — and calling it unowned hides the defect
        # `machine_text_never_quoted` exists to catch.
        line = "six uninterrupted months is exactly what a half-finished manuscript needs"
        got = audit(evidence(f'The note argues it plainly: "{line}".', vault=SABBATICAL,
                             human="should I take the sabbatical?"))
        self.assertEqual([s.kind for s in got], ["machine-copy"])
        self.assertTrue(got[0].broken)

    def test_a_span_copied_from_the_log_claims_no_note(self):
        # A line of spanish-and-the-car/thinking log.md, which companion itself writes. The
        # Overlay is what makes it the log: read without it, the file is just another note
        # and the mark would be credited to one.
        got = audit(evidence('The log still reads "whether to sell the car — let it sit".',
                             vault=CAR, human="should I fix the car or sell it?",
                             overlay="## Companion\n\n- index: [[home]]\n- log: `thinking log.md`\n"))
        self.assertEqual([s.kind for s in got], ["machine-copy"])
        self.assertTrue(got[0].broken)


    def test_a_span_copied_from_a_skip_listed_note_claims_no_note(self):
        # The third way into machine text: `digests/` on the Overlay's skip list. The
        # digest is generated, so [[sabbatical digest]] holds no line a reply may quote —
        # the same exclusion `skip_list_never_quoted` grades, applied to who owns a mark.
        line = "Main motivation identified: recovering from burnout after the spring reorg"
        got = audit(evidence(f'The digest puts it plainly: "{line}".', vault=SABBATICAL,
                             human="should I take the sabbatical?",
                             overlay="## Companion\n\n- index: [[home]]\n- skip list: `digests/`\n"))
        self.assertEqual([s.kind for s in got], ["machine-copy"])
        self.assertTrue(got[0].broken)


class CreditsTheWayTheGateCredits(unittest.TestCase):
    def test_a_second_span_on_a_joined_quote_line_is_credited_only_as_the_gate_credits_it(self):
        # `graders.claim_lines()` joins a soft wrap, so both spans below land on one claim
        # line — and `quote_sources` still credits only the first, because a quoted span
        # divides the walk to the link. The audit must not call the second one a graded
        # claim (that would be a span the gate does not grade, silently marked broken), nor
        # let the join hide that its words are the note's.
        reply = ('- [[sabbatical]] — "I don\'t want the sabbatical to finish the novel."\n'
                 'And it says: "I want it to find out whether I still like my own company."')
        got = audit(evidence(reply, vault=SABBATICAL, human="should I take the sabbatical?"))
        self.assertEqual([s.kind for s in got], ["claim-ok", "note-copy-unowned"])
        self.assertEqual([s.graded for s in got], [True, False])
        self.assertEqual([s.broken for s in got], [False, False])


class TheWrongDoor(unittest.TestCase):
    """#28: a code span holding the Corpus's own characters is a copy that took the wrong
    door — Marks copy, `code` weighs, so a note's line in `code` never gets a quote line and
    neither `quotes_verbatim` nor the mark audit can see it. Expected counts are worked by
    hand against the band-or-pottery Fixture vault."""

    def test_a_note_s_line_in_code_is_counted_though_it_is_a_true_copy(self):
        # fix26d_pin2 reply 1: [[the band]]'s whole sentence, copied correctly two lines
        # above, re-housed in `code` as the thing being weighed. True words, wrong door.
        reply = ('如果 `The drive home was the best part.` 说的其实是回程，那乐队就不是负担。')
        got = wrong_doors(evidence(reply, vault=BAND, human="should I quit the band?"))
        self.assertEqual([s.span for s in got], ["The drive home was the best part."])
        self.assertEqual([s.holder for s in got], ["the band"])

    def test_a_fragment_of_a_note_s_line_in_code_is_counted_too(self):
        # fix26d_pin2 reply 2: `nobody has a claim on` is [[thursday evenings]]'s words, and
        # the reply weighs them as its own term. A fragment is still the note's characters.
        got = wrong_doors(evidence('所谓 `nobody has a claim on` 只是没有排期。',
                                   vault=BAND, human="should I quit the band?"))
        self.assertEqual([s.holder for s in got], ["thursday evenings"])

    def test_the_same_line_in_code_twice_is_counted_twice(self):
        # fix26d_pin2 puts `Nobody says no and nobody writes anything` in `code` twice in
        # one reply; the number counts copies, not distinct strings.
        reply = ('`Nobody says no and nobody writes anything` 是事实。\n\n'
                 '而 `Nobody says no and nobody writes anything` 还没有答案。')
        got = wrong_doors(evidence(reply, vault=BAND, human="should I quit the band?"))
        self.assertEqual(len(got), 2)

    def test_the_model_s_own_term_in_code_is_not_counted(self):
        # The door `code` exists for: 用退乐队换三小时 is the reply's own compression, weighed
        # not copied. No note holds it, so it is not a copy in the wrong door.
        got = wrong_doors(evidence('你把这件事说成 `用退乐队换三小时`。',
                                   vault=BAND, human="should I quit the band?"))
        self.assertEqual(got, [])

    def test_machine_text_in_code_is_no_copy_because_the_corpus_holds_it_not(self):
        # What SKILL.md itself writes in `code`: `this is raw`. It lives in an AI capture
        # callout, and the digest line below on the Overlay's skip list, so neither is in
        # the Corpus the number is read against — the exclusion the issue asks for comes
        # from how the Corpus is built, not from a list of banned strings.
        line = "Main motivation identified: recovering from burnout after the spring reorg"
        reply = f'The file writes `this is raw`, the digest `"{line}"`.'
        got = wrong_doors(evidence(reply, vault=SABBATICAL, human="should I take the sabbatical?",
                                   overlay="## Companion\n\n- index: [[home]]\n"
                                           "- skip list: `digests/`\n"))
        self.assertEqual(got, [])

    def test_naming_a_note_or_a_filing_target_in_code_is_not_a_copy(self):
        # The harness vocabulary that IS corpus-held: a note's own name appears in the index
        # and in its title line, so `working from home` matches the Corpus and clears the
        # word floor. Pointing at a note by name is what SKILL.md prescribes ("every note
        # name … stay in their source language"), so it is not a copy that took the wrong
        # door. Same for the filing target `# Thursday evenings`.
        reply = ('The index lists `working from home` and `the hybrid offer`, filed under '
                 '`# Thursday evenings`.')
        got = wrong_doors(evidence(reply, vault=KITCHEN, human="I want the office now."))
        self.assertEqual(got, [])

    def test_a_link_in_code_is_naming_not_copying(self):
        # 63 spans across the saved runs are `[[note]]` written in `code`. The brackets are
        # the pointing shape; no note's line is inside them.
        got = wrong_doors(evidence('Read `[[working from home]]` first.', vault=KITCHEN,
                                   human="I want the office now."))
        self.assertEqual(got, [])

    def test_a_span_below_the_claim_floor_is_a_term_not_a_line(self):
        # `pottery` is one word: the gate's own floor says a span that short says nothing
        # about a note, so it is a term being weighed, not a line that took the wrong door.
        got = wrong_doors(evidence('`pottery` 是那间 studio。', vault=BAND,
                                   human="should I quit the band?"))
        self.assertEqual(got, [])

    def test_the_human_s_own_line_in_code_is_weighing_not_a_wrong_door(self):
        # framing-carried-over: the human said "weighing what I paid against what came
        # back" in their own turn, and #27's graded shape *requires* it in `code` on a line
        # holding no link. The mark audit checks the human's turns before the Corpus for
        # exactly this reason; a code span must, or the instrument counts the one shape
        # another ticket grades a pass.
        human = ("should I take the studio job? I keep doing the thing I did with the "
                 "evening class: weighing what I paid against what came back.")
        got = wrong_doors(evidence('你在用 `what I paid against what came back` 量这件事。',
                                   vault=CLASS, human=human))
        self.assertEqual(got, [])

    def test_the_wrong_door_number_leaves_broken_and_unowned_alone(self):
        # AC 2: a third number must not move the two the audit already reports. The same
        # span in marks and in `code`: the mark is graded, the code copy is the third number.
        reply = ('- [[the band]] — "The drive home was the best part."\n'
                 '如果 `The drive home was the best part.` 说的是回程，那乐队就不是负担。')
        marks = audit(evidence(reply, vault=BAND, human="should I quit the band?"))
        self.assertEqual([s.kind for s in marks], ["claim-ok"])
        self.assertEqual([s.broken for s in marks], [False])
        self.assertEqual(len(wrong_doors(evidence(reply, vault=BAND,
                                                  human="should I quit the band?"))), 1)


class AuditingASavedRun(unittest.TestCase):
    def test_a_saved_case_is_audited_from_its_transcript_and_fixture_vault(self):
        # The transcripts themselves are gitignored, so this checks the walk over a run
        # directory on a run written for the test, not on any gate that happens to exist.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "candidate" / "orient-quotes-corpus").mkdir(parents=True)
            (root / "candidate" / "orient-quotes-corpus" / "transcript.json").write_text(
                json.dumps([
                    {"role": "human", "text": "/companion band or pottery?"},
                    {"role": "companion", "text": "- [[дача]] — «Дача — единственное место, "
                                                  "где я сплю без будильника.»"},
                ]), encoding="utf-8")
            rows = audit_run(root, cases={"orient-quotes-corpus": "the-dacha"})
            self.assertEqual([r["case"] for r in rows], ["orient-quotes-corpus"])
            self.assertEqual(rows[0]["spans"], 1)
            self.assertEqual(rows[0]["meaningful"], 1)
            self.assertEqual(rows[0]["broken"], 0)
            self.assertEqual(rows[0]["unowned"], 0)


if __name__ == "__main__":
    unittest.main()
