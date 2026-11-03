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
from span_audit import audit, audit_run  # noqa: E402

VAULTS = Path(__file__).parent / "fixtures" / "vaults"
DACHA = VAULTS / "the-dacha"
KITCHEN = VAULTS / "the-kitchen-table"
SABBATICAL = VAULTS / "the-sabbatical"
CAR = VAULTS / "spanish-and-the-car"


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
