"""The span audit: every Span in a saved reply, and who owns its words.

`quotes_verbatim` grades a mark only when the same line offers a `[[link]]`
(`graders.quote_sources`). A mark on a line that names no note is invisible to the
whole gate, so a run can pass every case while the shipped promise — marks hold a
note's or the human's exact words — is broken in it. Machine text counts as nothing:
the log and an `AI capture` callout are words no note spoke in the human's voice. This
walks every marked span in a reply, and every `code` span besides, and classifies each,
graded or not, so a verdict can be checked at the promise level rather than at the
grader's.

Four numbers, because #26 names two defects, #28 a third, and #26's rendering half leaves a
shape that only a fourth number can count:

- **broken** — its own definition: *a real copy credited to a note that does not
  hold it, or marks that copy nothing at all*. Kinds `claim-fail`, `machine-copy`,
  `self-quote`, `human-edited`, `no-source`. This is what AC 3 counts, and what the
  exit code says.
- **unowned** — kind `note-copy-unowned`: a note's line in marks on a sentence that
  names no owner. True words, wrong place — the shape #26's cure asks for, reported
  beside the count rather than inside it.
- **wrongdoor** — `wrong_doors`: a `code` span whose characters the Corpus holds. Marks
  copy, `code` weighs, so a note's line parked in `code` is credited to no note, graded
  by no grader, and never given the quote line it owes. Neither number above can see it,
  which is how #17's 0-broken bar can be met by a copy that moved its lines out of Marks
  — `fix26d_pin2`: 9 marks, 0 of them unowned, 5 of 16 code spans the Corpus's own words.
  Not broken by #26's definition (a note does hold these words) and not a mark, so it is
  counted beside them and changes no verdict.
- **pointer** — `pointer_doors`: which door a pointer form (那句, 说的是, 记的是…) filled —
  `bare`, `marked`, `weighed`, `other`. The only one of the four that counts a *shape* rather
  than a defect, and the only way to know whether a candidate writes the door #26's rendering
  half asks for: a bare run of the reply's own words promises nothing, so no grader reads it and
  `broken` cannot see it taken. `marked` is the door that breaks the promise when its Span is in
  the reply's script; `weighed` is the shape #27's `framing_named` passes, and `wrongdoor`
  already counts it when the Corpus holds those characters. Also no verdict: the exit code is
  still only ever about `broken`.

`label` (a span too short to read as a claimed line, by the gate's own
`MIN_QUOTE_WORDS`, and by character rather than word where the script has no spaces)
is neither, and is left out of the denominator. The same floor and the same Corpus serve
`wrongdoor`, plus one exclusion: a span that is only a note's *name* (or a `# heading`,
or a `[[link]]`) is pointing at a note, not copying its text — the shape `code` exists for.

It measures. It grades nothing, and changes no verdict: `graders.py` stays the
arbiter of PASS and FAIL.

    python3 labs/evals/span_audit.py labs/evals/results/<run>            # every arm, every case
    python3 labs/evals/span_audit.py labs/evals/results/<run> --arm candidate --case lang
    python3 labs/evals/span_audit.py labs/evals/results/<run> --json

A saved run's `results/` is gitignored, so this reads the transcripts the gate left
rather than re-spending its tokens.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import vaultdiff  # noqa: E402
from graders import (CODE_SPAN, MIN_QUOTE_WORDS, OVERLAY_FILES, Evidence, _QUOTED,  # noqa: E402
                    _SENTENCE_END, _norm, _split_callouts, claim_lines, human_turns,  # noqa: E402
                    machine_text, outside_menu, path_key, quote_claim,  # noqa: E402
                    quote_sources, quoted_from_note, replies, said_by_human,  # noqa: E402
                    skipped, start_vault)  # noqa: E402


@dataclass
class Span:
    """One marked span in one companion reply, as its reader sees it."""
    case: str
    reply: int        # 1-based, among the reply texts of one arm's transcript
    line: str         # the claim line the mark sits on, wraps joined
    span: str
    kind: str         # what the words are, per KINDS
    graded: bool      # quotes_verbatim would look at this span
    broken: bool      # credited to a note that does not hold it, or copies nothing at all
    detail: str = ""


KINDS = ("claim-ok", "claim-fail", "label", "human-verbatim", "note-copy-unowned",
         "machine-copy", "self-quote", "human-edited", "no-source")


@dataclass
class CodeCopy:
    """One `code` span in one companion reply whose characters a note holds: a copy that
    took the wrong door. Marks copy, `code` weighs, so these words never reach a quote line
    and no grader reads them — the hole #28 names."""
    case: str
    reply: int
    line: str
    span: str
    holder: str      # the note whose text holds the span
    detail: str = ""


@dataclass
class VaultView:
    """The vault as the session saw it: the Corpus a mark may credit, and the machine text
    it may not. Built once per arm-run from `start_vault`, which is the case's Overlay plus
    the Fixture vault — without the Overlay the log is just another note and gets credited
    as one. Machine text is never the human's voice, so a mark holding it copies no note."""
    corpus: dict
    machine: list

    @classmethod
    def of(cls, ev: Evidence) -> "VaultView":
        snap = start_vault(ev)
        skip = set(skipped(snap)) | set(OVERLAY_FILES)
        return cls({path_key(p): _split_callouts(t)[1] for p, t in snap.items()
                    if p.endswith(".md") and p not in skip},
                   machine_text(snap))

    def holders(self, frag: str) -> list:
        """Every note whose human text holds this span, by name."""
        return sorted(n for n, text in self.corpus.items() if quoted_from_note(frag, text))

    def machine_from(self, frag: str) -> list:
        """Where this span's words live if they are machine text, as `machine_text` names it."""
        return [where for where, body in self.machine if quoted_from_note(frag, body)]


_STOPWORDS = frozenset("""a an and as at be but by for from if in into is it its of on or
so that the their them then there these this to too up was we were what when where which
who why will with you your""".split())


def _content_words(text: str) -> set:
    """The span's own words, three characters or more, minus the connective ones.
    Counted across scripts, because the recalled lines that hurt are Russian and 中文 —
    and in a script that writes no spaces, one run of characters is one long word."""
    return {w for w in re.findall(r"\w{3,}", _norm(text).lower())
            if w not in _STOPWORDS}


def recalled_human_words(ev: Evidence, frag: str) -> bool:
    """The span is not verbatim anywhere the human spoke, but is built mostly of their
    words: the compressed quotation #23's audit calls a recalled line, slightly edited.
    Two shared content words, or one of six letters or more, is the threshold; a
    misfiled span still counts as broken either way."""
    mine = _content_words(frag)
    if not mine:
        return False
    for turn in human_turns(ev):
        shared = mine & _content_words(turn)
        if len(shared) >= 2 or (shared and max(len(w) for w in shared) >= 6):
            return True
    return False


def carries_a_claim(frag: str) -> bool:
    """Is this span long enough that a reader takes it for a line, not a label?

    The gate's own floor (`MIN_QUOTE_WORDS`): "Pottery", "Thursday evenings" could match
    a heading or a name, so a short span says nothing about a note. That floor counts by
    whitespace, which mis-counts 中文, where one character is a whole word and 「」 is
    still a quotation mark making the same promise an English `"` does: there, length is
    no exemption at all."""
    if re.search(r"[\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]", frag):
        return True
    return len(frag.split()) >= MIN_QUOTE_WORDS


def _ungraded(ev: Evidence, view: VaultView, case: str, n: int, line: str, frag: str,
              earlier: list) -> Span:
    """A mark on a line the gate credits to no note: then whose words are these?"""
    if not carries_a_claim(frag):
        return Span(case, n, line, frag, "label", False, False,
                    "too short to read as a claimed line")
    if any(quoted_from_note(frag, t) for t in human_turns(ev)):
        # Not `said_by_human`: its whitespace floor is the gate's, and it never hands a
        # 中文 line back to the human who said it. Here there is no claim about a note to
        # check, only whose words these are.
        return Span(case, n, line, frag, "human-verbatim", False, False,
                    "the human's words, on a line naming no note")
    held = view.holders(frag)
    if held:
        # Not broken by #26's definition — "a real copy credited to a note that does not
        # hold it, or marks that copy nothing at all": a note does hold these words. It is
        # the shape the new rule binds on, so it is reported as `unowned`.
        return Span(case, n, line, frag, "note-copy-unowned", False, False,
                    "a copy of " + " or ".join(f"[[{h}]]" for h in held)
                    + ", named on no line of its own")
    machine = view.machine_from(frag)
    if machine:
        return Span(case, n, line, frag, "machine-copy", False, True,
                    "a copy of " + "; ".join(machine) + " — machine text speaks for no note")
    if any(quoted_from_note(frag, t) for t in earlier):
        return Span(case, n, line, frag, "self-quote", False, True,
                    "the companion's own sentence, put in marks")
    if recalled_human_words(ev, frag):
        return Span(case, n, line, frag, "human-edited", False, True,
                    "the human's line, recalled rather than copied")
    return Span(case, n, line, frag, "no-source", False, True,
                "no note, no human line, no earlier reply holds it")


def _graded(ev: Evidence, view: VaultView, case: str, n: int, line: str, frag: str,
            targets: list) -> Span:
    """A mark the gate does credit to notes. `quote_claim` answers for it, unchanged, so
    this bucket is the gate's own verdict and the audit can be checked against it."""
    if said_by_human(ev, frag):
        return Span(case, n, line, frag, "human-verbatim", True, False,
                    "the human's words, handed back")
    why = quote_claim(targets, frag, ev.vault)
    if why is None:
        return Span(case, n, line, frag, "claim-ok", True, False,
                    "verbatim in " + " or ".join(targets))
    held = view.holders(frag)
    where = ("held by " + " or ".join(f"[[{h}]]" for h in held)
             if held else "no note holds these words")
    return Span(case, n, line, frag, "claim-fail", True, True, f"{why} — {where}")


def _credit_for(claims: list, frag: str):
    """The first credit still unconsumed that was made for this fragment, in order."""
    for i, (targets, claim) in enumerate(claims):
        if claim == frag:
            return claims.pop(i)
    return None


def audit(ev: Evidence, case: str = "") -> list:
    """Every marked span in every reply of one arm's run, and who owns its words."""
    out = []
    texts = replies(ev)
    view = VaultView.of(ev)
    for n, text in enumerate(texts, 1):
        claims = list(quote_sources(text))  # exactly what the gate credits, whole reply
        for line in claim_lines(outside_menu(text)):
            for m in re.finditer(_QUOTED, line):
                frag = m.group(1)
                found = _credit_for(claims, frag)
                if found is None:
                    out.append(_ungraded(ev, view, case, n, line, frag, texts[:n - 1]))
                else:
                    out.append(_graded(ev, view, case, n, line, frag, found[0]))
    return out


def names_a_note(frag: str, view: VaultView) -> bool:
    """The span is a note's own name, not a line taken out of it.

    The harness writes note names and filing targets in `code` (`working from home`,
    `# Thursday evenings`), and the Corpus holds a name — in its own title line and in
    every index bullet that links it — so `holders` alone reads all of that as a copy.
    Pointing at a note by name credits no line, which is what `code` is for."""
    bare = _norm(frag).lower().strip()
    for prefix in ("#", "[["):
        bare = bare.removeprefix(prefix)
    return bare.removesuffix("]]").strip() in view.corpus


def wrong_doors(ev: Evidence, case: str = "") -> list:
    """Every `code` span in every reply whose characters a note holds: a copy that took the
    wrong door, invisible to `quotes_verbatim` and to the mark audit.

    It is counted, never graded: #26's `broken` is about marks, and this number sits beside
    it. A span is skipped when it is too short to read as a line (the gate's own floor), when
    it is a note's name rather than its text, when the human said it this session, or when the
    Corpus does not hold it at all — which covers the model's own weighing phrase, the Overlay's
    field vocabulary, and machine text, since `VaultView.corpus` is built without the Overlay,
    the skip list or a callout.

    The human's turns are read before the Corpus, as `_ungraded` reads them: a line the human
    carried in is their words, and #27's `framing_named` *requires* those words in `code` on a
    line holding no link. Without this the instrument counts as a wrong door the one shape that
    grader passes — `framing-carried-over`'s `what I paid against what came back`, which the
    human said and [[the evening class]] happens to hold."""
    out = []
    view = VaultView.of(ev)
    said = human_turns(ev)
    for n, text in enumerate(replies(ev), 1):
        for line in claim_lines(outside_menu(text)):
            for frag in CODE_SPAN.findall(line):
                if not carries_a_claim(frag) or names_a_note(frag, view):
                    continue
                if any(quoted_from_note(frag, turn) for turn in said):
                    continue
                held = view.holders(frag)
                if held:
                    also = ", ".join(f"[[{h}]]" for h in held[1:])
                    out.append(CodeCopy(case, n, line, frag, held[0],
                                        f"[[{held[0]}]] holds these words; in `code` they are"
                                        f" weighed, so no quote line was ever owed to them"
                                        + (f" (also in {also})" if also else "")))
    return out


# The words a 中文 reply uses to name a note's line before supplying its content. companion
# prints three of them by name (那句, 说的是, 记的是); the other three are the same family
# found in the saved replies. A pointer form points; it does not quote — so what sits in
# front of it is the door the reply chose, and the one shape no Span audit can read: bare
# words are not a Span, carry no promise, and are graded by nothing.
POINTER_FORMS = ("那句", "那条", "说的是", "记的是", "写的是", "讲的是")
POINTER_DOORS = ("bare", "marked", "weighed", "other")
_POINTER_FORM = re.compile("|".join(POINTER_FORMS))
_CJK_RANGE = r"\u3400-\u4dbf\u4e00-\u9fff"
_CJK_RUN = re.compile(f"[{_CJK_RANGE}]+")
# A pointer form is followed by its content past the punctuation that joins the clauses:
# `说的是：砍掉的是这圈人`, `那句——它假设只有一个周四`. The sentence itself is the bound, and
# the harness's own `_SENTENCE_END` draws it.
_POINTER_LEAD = re.compile(r"^[\s，、：:；;—–\-]+")
# The reply's own script ends an unmarked run: `那句 Of course it is 说明这…` carries the note's
# English up to the first 中文 character, and that stretch is what the Corpus is asked about.
_UNMARKED_RUN = re.compile(f"^[^{_CJK_RANGE}]+")


@dataclass
class PointerDoor:
    """One pointer form in one companion reply, and which door its content took."""
    case: str
    reply: int
    line: str
    form: str     # the pointer form that was found
    door: str     # bare | marked | weighed | other
    content: str  # what the pointer form points at, as far as this walk reads it
    detail: str = ""


def pointer_doors(ev: Evidence, case: str = "") -> list:
    """Every pointer form in every reply of one arm's run, and the door its content took.

    This counts a *shape*, not a defect: `broken` and `unowned` read Marks, `wrongdoor` reads
    `code`, and the cure #26's rendering half asks for puts a note's content in the reply's own
    words with nothing around them, which none of the three can see. So the adoption of the
    shape — whether a candidate writes it at all — is only knowable here.

    The four doors, in the order the walk reads them:

    - `bare` — two or more characters of the reply's own script immediately after the form
      (`记的是加一样就得卸一样`). One character is not a rendering but the noun the determiner
      governs (`是那条手`), so it falls to `other` with that said: the adoption count is the one
      number here that a false positive would quietly inflate.
    - `marked` — the content opens in Marks. What the promise is worth is `broken`'s question,
      not this one; the Span inside is reported so the two can be read side by side.
    - `weighed` — the content opens in `code`: the shape #27's `framing_named` passes. When the
      Corpus holds those characters, `wrong_doors` already counts it.
    - `other` — the form filled no slot: it points at a note by name, or the sentence stops, or
      the run after it is in another script. The last of those is asked of the Corpus, not
      assumed: above the mark audit's own claim floor and held by a note, it is that note's
      characters left unmarked, which promises nothing and credits nothing; below the floor it is
      a term, and if no note holds it the walk says so.

    A form inside someone else's characters is not the reply pointing: a note's own line, or the
    human's, may hold 那句, and the words after it belong to that speaker. Marked spans and `code`
    spans are masked before the walk for that reason. Close-menu option lines are skipped whole,
    as the mark audit skips them — `[e]` proposes text for a note rather than pointing at one."""
    out = []
    view = VaultView.of(ev)
    for n, text in enumerate(replies(ev), 1):
        for line in claim_lines(outside_menu(text)):
            # Whose words the form sits inside: a 那句 that is part of a copied span or a
            # weighed span was not written by the reply pointing at anything.
            hidden = ([s.span() for s in re.finditer(_QUOTED, line)]
                      + [s.span() for s in CODE_SPAN.finditer(line)])
            for m in _POINTER_FORM.finditer(line):
                if any(a <= m.start() < b for a, b in hidden):
                    continue
                window = _SENTENCE_END.split(line[m.end():], 1)[0]
                tail = _POINTER_LEAD.sub("", window)
                cjk = _CJK_RUN.match(tail)
                marked = re.match(_QUOTED, tail)
                weighed = CODE_SPAN.match(tail)
                if cjk and len(cjk.group(0)) >= 2:
                    out.append(PointerDoor(case, n, line, m.group(0), "bare", cjk.group(0),
                                           "the content sits bare, so no Mark promises a voice"))
                elif marked:
                    out.append(PointerDoor(case, n, line, m.group(0), "marked", marked.group(1),
                                           "the content is in Marks, so the line promises a voice"))
                elif weighed:
                    out.append(PointerDoor(case, n, line, m.group(0), "weighed", weighed.group(1),
                                           "the content is in `code`: weighed, not claimed — and"
                                           " `wrong_doors` counts it when the Corpus holds it"))
                elif tail.startswith("[["):
                    out.append(PointerDoor(case, n, line, m.group(0), "other", tail[:40],
                                           "points at a note by name, which fills no slot"))
                elif cjk:
                    out.append(PointerDoor(case, n, line, m.group(0), "other", cjk.group(0),
                                           "one character after the form: the determiner governs a"
                                           " noun (那条手), it points at no line and renders nothing"))
                elif not tail:
                    out.append(PointerDoor(case, n, line, m.group(0), "other", "",
                                           "the sentence stops at the pointer form: no content"))
                else:
                    run = _UNMARKED_RUN.match(tail).group(0).strip().rstrip("，,、；;：:")
                    if not carries_a_claim(run):
                        why = (f"a term, not a line: {run!r} is below the floor the mark audit "
                               "uses, so no note's characters are claimed either way")
                    elif view.holders(run):
                        why = ("the note's characters left unmarked — "
                               + " or ".join(f"[[{h}]]" for h in view.holders(run))
                               + " holds them; no Mark, so the line promises nothing and the note"
                                 " gets no quote line")
                    else:
                        why = ("characters no note holds, left unmarked: no Mark, so the line"
                               " promises nothing")
                    out.append(PointerDoor(case, n, line, m.group(0), "other", run, why))
    return out


ARMS = ("stable", "candidate")
FIXTURE_VAULTS = Path(__file__).parent / "fixtures" / "vaults"
CASES_DIR = Path(__file__).parent / "cases"
EMPTY_DIFF = {"added": {}, "removed": [], "modified": {}}


def case_vaults(skill: str) -> dict:
    """{case id: {"vault": name, "overlay": text}} from the skill's own case set."""
    data = json.loads((CASES_DIR / f"{skill}.json").read_text(encoding="utf-8"))
    return {c["id"]: {"vault": c["vault"], "overlay": c.get("overlay")} for c in data["cases"]}


def vault_view(vault_name: str, overlay) -> dict:
    """The Fixture vault with the case's Overlay appended to `CLAUDE.md`, which is how the
    runner builds the vault a session starts in — and how the log and skip list get known."""
    root = FIXTURE_VAULTS / vault_name
    snap = {p.relative_to(root).as_posix(): p.read_text(errors="replace")
            for p in sorted(root.rglob("*.md"))}
    if overlay:
        snap["CLAUDE.md"] = snap.get("CLAUDE.md", "") + "\n\n" + overlay.strip() + "\n"
    return snap


def audit_run(root, cases: dict, arms: list | None = None) -> list:
    """One row per arm and case saved under `root`, auditing its transcript."""
    root = Path(root)
    rows = []
    for arm in arms or [a for a in ARMS if (root / a).is_dir()]:
        for case, spec in sorted(cases.items()):
            path = root / arm / case / "transcript.json"
            if not path.exists():
                continue
            name = spec if isinstance(spec, str) else spec["vault"]
            overlay = None if isinstance(spec, str) else spec.get("overlay")
            ev = Evidence(transcript=json.loads(path.read_text(encoding="utf-8")),
                          diff=dict(EMPTY_DIFF), vault=FIXTURE_VAULTS / name,
                          snapshots=[vault_view(name, overlay)])
            spans = audit(ev, case)
            doors = wrong_doors(ev, case)
            pforms = pointer_doors(ev, case)
            counts = Counter(s.kind for s in spans)
            pcounts = Counter(d.door for d in pforms)
            meaningful = [s for s in spans if s.kind != "label"]
            rows.append({"arm": arm, "case": case, "spans": len(spans),
                         "meaningful": len(meaningful),
                         "graded": sum(1 for s in spans if s.graded),
                         "broken": sum(1 for s in spans if s.broken),
                         "unowned": counts.get("note-copy-unowned", 0),
                         "wrongdoor": len(doors),
                         "pointer": {k: pcounts.get(k, 0) for k in POINTER_DOORS},
                         "by_kind": {k: counts[k] for k in KINDS if counts[k]},
                         "details": [asdict(s) for s in spans
                                     if s.broken or s.kind == "note-copy-unowned"],
                         "wrongdoor_details": [asdict(s) for s in doors],
                         "pointer_details": [asdict(d) for d in pforms]})
    return rows


def main(argv: list | None = None) -> int:
    ap = argparse.ArgumentParser(description="Audit every marked span in a saved run.")
    ap.add_argument("run", help="a results/<run> directory, or one arm's directory")
    ap.add_argument("--skill", default="companion", help="whose case set names the vaults")
    ap.add_argument("--arm", choices=list(ARMS), help="audit one arm only")
    ap.add_argument("--case", help="audit only cases whose id contains this")
    ap.add_argument("--json", action="store_true", help="rows as JSON")
    args = ap.parse_args(argv)
    cases = case_vaults(args.skill)
    if args.case:
        cases = {k: v for k, v in cases.items() if args.case in k}
    arms = [args.arm] if args.arm else None
    rows = audit_run(args.run, cases, arms)
    if not rows:
        print(f"no transcripts for {args.skill} under {args.run}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
    else:
        for r in rows:
            base = r["meaningful"]
            rate = f"{100.0 * r['broken'] / base:.1f}%" if base else "—"
            print(f"{r['arm']:9} {r['case']:28} marks {r['spans']:3} (graded {r['graded']:2})"
                  f"  broken {r['broken']:2} ({rate})  unowned {r['unowned']:2}"
                  f"  wrongdoor {r['wrongdoor']:2}  pointer {r['pointer']}  {r['by_kind']}")
            for d in r["details"]:
                print(f"    reply {d['reply']} [{d['kind']}] {d['span']!r}\n"
                      f"      {d['detail']}\n      {d['line'][:160]}")
            for d in r["wrongdoor_details"]:
                print(f"    reply {d['reply']} [wrong-door copy] {d['span']!r}\n"
                      f"      {d['detail']}\n      {d['line'][:160]}")
            for d in r["pointer_details"]:
                if d["door"] == "bare":
                    continue  # the adoption count is in the row; a bare door has nothing to read
                print(f"    reply {d['reply']} [pointer {d['door']}] {d['form']} → {d['content']!r}"
                      f"\n      {d['detail']}\n      {d['line'][:160]}")
    broken = sum(r["broken"] for r in rows)
    unowned = sum(r["unowned"] for r in rows)
    doors = sum(r["wrongdoor"] for r in rows)
    base = sum(r["meaningful"] for r in rows)
    graded_fail = sum(r["by_kind"].get("claim-fail", 0) for r in rows)
    print(f"\n{broken} broken of {base} marks that carry a claim, across {len(rows)}"
          f" arm-cases: {graded_fail} graded by the gate, {broken - graded_fail} invisible"
          f" to it. {unowned} more copy a note's line with no owner named, and {doors}"
          f" sit in `code`, where no grader looks at all.")
    p = Counter()
    for r in rows:
        p.update(r["pointer"])
    slot = p["bare"] + p["marked"]
    print(f"\n{sum(p.values())} pointer forms: {p['bare']} bare, {p['marked']} in Marks,"
          f" {p['weighed']} in `code`, {p['other']} filling nothing (a name, a term, a"
          f" single noun, or the sentence stopping)")
    if slot:
        print(f"{100.0 * p['bare'] / slot:.1f}% filled the slot bare — the denominator is"
              f" bare+Marks ({slot}), not all {sum(p.values())} forms. A door is a shape, not"
              " a verdict: the three defect numbers above still grade the copy.")
    return 1 if broken else 0


if __name__ == "__main__":
    sys.exit(main())
