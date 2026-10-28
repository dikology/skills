"""Graders for the Library's eval cases.

A grader sees what a user would see or find: the session transcript and the
vault diff, plus the Fixture vault to check quotes against. It never reads the
skill's prompt text, and it never asserts wording or section order.

Each grader returns a Result. A case passes when every hard grader passes; the
score is the weighted share of graders passed, reported alongside.
"""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass, field
from pathlib import Path

import vaultdiff


@dataclass
class Evidence:
    transcript: list   # [{"role": "human" | "companion", "text": str}, ...]
    diff: dict         # vaultdiff.diff() output
    vault: Path        # the pristine Fixture vault, for resolving links and quotes
    # The vault (vaultdiff.snapshot) before the first human turn, then after each
    # human turn. snapshots[0] holds the case's Overlay, if any.
    snapshots: list = field(default_factory=list)


@dataclass
class Result:
    name: str
    passed: bool
    note: str = ""
    weight: float = 1.0
    hard: bool = True

    def as_dict(self) -> dict:
        return {"name": self.name, "passed": self.passed, "note": self.note,
                "weight": self.weight, "hard": self.hard}


# --- quotes and links --------------------------------------------------------

# A wikilink and a quoted span on the same line, in either order:
# [[note]] — "text"  or  "text" — [[note]], in "", “”, «» or 「」 marks. The gap
# between them holds no other link or quote, so a quote is credited to the link
# nearest it. Nor does it cross a sentence end (". ", "? ", 。): a quote in one
# sentence and a link in the next aren't a quote of that note.
_LINK = r"\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|[^\]]*)?\]\]"
_QUOTED = r"[\"“«「『]([^\"”»」』\n]+)[\"”»」』]"
_GAP = r"(?:(?![.!?]\s)[^\n\"“«「『\[\]。！？])*?"
QUOTE_RE = re.compile(f"{_LINK}{_GAP}{_QUOTED}|{_QUOTED}{_GAP}{_LINK}")

# A quote this short ("Pottery", "Thursday evenings") could match a heading or a
# name; it doesn't show the reply read the note.
MIN_QUOTE_WORDS = 3


# A close-menu option ("[e] Add "<question>" to [[note]]") proposes new text for a
# note. Its quotes are not claims about what the note already says.
MENU_OPTION = re.compile(r"^\s*(?:[-*]\s+)?(?:\*\*)?\[[a-z]\]", re.M)
FILE_OPTION = re.compile(r"^\s*(?:[-*]\s+)?(?:\*\*)?\[a\]", re.M)


def outside_menu(text: str) -> str:
    """The text without its close-menu option lines."""
    return "\n".join(line for line in text.splitlines() if not MENU_OPTION.match(line))


def quotes(text: str) -> list:
    """(link target, quoted text) pairs, in order of appearance, outside menu options."""
    out = []
    for m in QUOTE_RE.finditer(outside_menu(text)):
        target, quote = (m.group(1), m.group(2)) if m.group(1) else (m.group(4), m.group(3))
        out.append((target.strip(), quote))
    return out


def note_key(target: str) -> str:
    """Obsidian resolves [[folder/Name]] by its last part, case-insensitively."""
    return target.strip().lower().split("/")[-1]


def path_key(path: str) -> str:
    """The note name a vault path resolves as: "work/the studio job.md" → "the studio job"."""
    return note_key(path.removesuffix(".md"))


def notes(vault: Path) -> dict:
    """Obsidian resolves a wikilink by note name, case-insensitively."""
    return {p.stem.lower(): p for p in vault.rglob("*.md")}


def _norm(s: str) -> str:
    s = s.replace("’", "'").replace("‘", "'")
    return re.sub(r"\s+", " ", s).strip()


def verbatim(quote: str, note_text: str) -> bool:
    """Every fragment of the quote, split on an ellipsis, appears in the note."""
    body = _norm(note_text)
    frags = [_norm(f).strip(" .,;:") for f in re.split(r"\.\.\.|…", quote)]
    frags = [f for f in frags if f]
    return bool(frags) and all(f in body for f in frags)


def quoted_from_note(quote: str, note_text: str) -> bool:
    """verbatim, except the quote's first letter may differ in case: a quote set
    inside a sentence is often lowercased or capitalised to fit it."""
    return any(verbatim(q, note_text) for q in (quote, quote[:1].lower() + quote[1:],
                                                quote[:1].upper() + quote[1:]))


def check_quote(target: str, quote: str, vault: Path) -> str | None:
    """None if the quote is verbatim in the note the link resolves to; else why not."""
    path = notes(vault).get(note_key(target))
    if path is None:
        return f"[[{target}]] does not resolve"
    if not quoted_from_note(quote, path.read_text()):
        return f"not verbatim in [[{target}]]: \"{quote}\""
    return None


def replies(ev: Evidence) -> list:
    """The companion's replies, in order."""
    return [t["text"] for t in ev.transcript if t["role"] == "companion"]


def first_reply(ev: Evidence) -> str:
    return next((t["text"] for t in ev.transcript if t["role"] == "companion"), "")


# --- the Overlay, read the way a user reads their own CLAUDE.md ---------------

OVERLAY_FILES = ("CLAUDE.md", "AGENTS.md")


def overlay(snap: dict, section: str = "Companion") -> str | None:
    """The body of the skill's Overlay section (`## Companion`, `## Improve`), or
    None when the vault has none."""
    pattern = re.compile(rf"^## {re.escape(section)}[ \t]*\n(.*?)(?=^## |\Z)", re.M | re.S)
    for name in OVERLAY_FILES:
        m = pattern.search(snap.get(name, ""))
        if m:
            return m.group(1)
    return None


# "as in `## Companion`": a field read from another section, as a user would.
POINTER = re.compile(r"^as\s+in\s+`?##\s*([^`]+?)`?\s*\.?$", re.I)
FIELD_LINE = re.compile(r"^\s*[-*]?\s*(?:\*\*|__)?([^:\n]+?)(?:\*\*|__)?\s*:\s*(.+?)\s*$", re.M)


def overlay_field(snap: dict, name: str, section: str = "Companion",
                  _seen: frozenset = frozenset()) -> str | None:
    """A field's value with its [[link]] or `code` wrapper removed, or None. One line
    may set several fields ("index, log: …"), and a value may point at another
    section ("as in `## Companion`"), where the field is then read."""
    value = None
    for m in FIELD_LINE.finditer(overlay(snap, section) or ""):
        keys = re.split(r"\s*(?:,|\band\b)\s*", m.group(1).strip(), flags=re.I)
        if name.lower() in (k.strip().lower() for k in keys):
            value = m.group(2)
            break
    if value is None or re.match(r"(none|no|n/a|-|—)(\W|$)", value, re.I):
        return None
    pointer = POINTER.match(value)
    if pointer:
        target = pointer.group(1).strip()
        seen = _seen | {section.lower()}
        return None if target.lower() in seen else overlay_field(snap, name, target, seen)
    inner = re.fullmatch(r"\[\[([^\]|#]+)[^\]]*\]\]|`([^`]+)`", value)
    return (inner.group(1) or inner.group(2)).strip() if inner else value


def links(text: str) -> set:
    return {note_key(m.group(1)) for m in re.finditer(_LINK, text)}


def at_start(ev: "Evidence", fn):
    """fn applied to the vault as the session first saw it, or None with no snapshot."""
    return fn(ev.snapshots[0]) if ev.snapshots else None


def log_path(snap: dict, section: str = "Companion") -> str | None:
    """The vault path of the configured log, whether given as a path or a [[link]]."""
    value = overlay_field(snap, "log", section)
    if not value:
        return None
    value = value.strip("/")
    return value if value.endswith(".md") else value + ".md"


def log_lines(snap: dict, path: str) -> list:
    return [line for line in snap.get(path, "").splitlines() if line.strip()]


def sessions(ev: Evidence) -> list:
    """(snapshot before, snapshot after) index pairs, one per session. A turn that
    failed has no snapshot after it and is left out."""
    ids = [t.get("session", 0) for t in ev.transcript if t["role"] == "human"]
    ids = ids[:max(len(ev.snapshots) - 1, 0)]
    spans = {}
    for k, sid in enumerate(ids):
        start, _ = spans.get(sid, (k, k))
        spans[sid] = (start, k + 1)
    return [spans[sid] for sid in sorted(spans)]


def session_log_lines(ev: Evidence, section: str = "Companion") -> tuple:
    """(log path, [lines each session added]) or (None, why) when it can't be read.
    Lines written before a session must survive it unchanged."""
    path = at_start(ev, lambda snap: log_path(snap, section))
    if not path:
        return None, "no log configured in the Overlay"
    added = []
    for n, (a, b) in enumerate(sessions(ev), 1):
        before, after = log_lines(ev.snapshots[a], path), log_lines(ev.snapshots[b], path)
        if after[:len(before)] != before:
            return None, f"session {n} rewrote lines already in {path}"
        added.append(after[len(before):])
    return path, added


# --- graders -----------------------------------------------------------------

def verified(found: list, vault: Path) -> list:
    """The (target, quote) pairs long enough to show a note was read, and verbatim in it."""
    return [(t, q) for t, q in found if len(q.split()) >= MIN_QUOTE_WORDS
            and check_quote(t, q, vault) is None]


def g_orient_quotes_corpus(ev: Evidence) -> Result:
    """Orient quotes at least one real note verbatim, wrapped in a link that resolves."""
    found = quotes(first_reply(ev))
    good = verified(found, ev.vault)
    if good:
        return Result("orient_quotes_corpus", True,
                      f"{len(good)}/{len(found)} quotes verified, e.g. [[{good[0][0]}]]")
    return Result("orient_quotes_corpus", False,
                  f"no verified quote among {len(found)} linked quotes in the first reply")


def g_session_quotes_corpus(ev: Evidence) -> Result:
    """The session got past setup: some reply, in any turn, quotes a note verbatim."""
    for k, text in enumerate(t["text"] for t in ev.transcript if t["role"] == "companion"):
        good = verified(quotes(text), ev.vault)
        if good:
            return Result("session_quotes_corpus", True,
                          f"reply {k + 1} quotes [[{good[0][0]}]]")
    return Result("session_quotes_corpus", False, "no reply quotes a note verbatim")


def g_orient_quotes_from_index(ev: Evidence) -> Result:
    """Orient quotes, verbatim, a note the configured index links to."""
    name = "orient_quotes_from_index"
    index = at_start(ev, lambda snap: overlay_field(snap, "index"))
    if not index:
        return Result(name, False, "no index configured in the Overlay")
    index_path = notes(ev.vault).get(note_key(index))
    if index_path is None:
        return Result(name, False, f"index [[{index}]] does not resolve")
    reached = links(index_path.read_text()) - {index_path.stem.lower()}
    good = [t for t, _ in verified(quotes(first_reply(ev)), ev.vault)
            if note_key(t) in reached]
    if good:
        return Result(name, True, f"quoted [[{good[0]}]], linked from [[{index}]]")
    return Result(name, False, f"orient quoted no note linked from [[{index}]] "
                               f"({', '.join(sorted(reached))})")


def g_overlay_written_after_approval(ev: Evidence) -> Result:
    """First run: the Overlay lands in CLAUDE.md or AGENTS.md on the last human turn,
    which a first-run case makes the approving one, and on no turn before it."""
    name = "overlay_written_after_approval"
    snaps = ev.snapshots
    if len(snaps) < 2:
        return Result(name, False, "no turns played")
    if overlay(snaps[0]) is not None:
        return Result(name, False, "the vault already had an Overlay before the session")
    early = next((k for k in range(1, len(snaps) - 1) if overlay(snaps[k]) is not None), None)
    if early is not None:
        return Result(name, False, f"Overlay written after human turn {early}, "
                                   f"before the approving turn {len(snaps) - 1}")
    if overlay(snaps[-1]) is None:
        return Result(name, False, "no `## Companion` section written after approval")
    return Result(name, True, f"Overlay written after human turn {len(snaps) - 1}")


def g_one_log_line_per_session(ev: Evidence) -> Result:
    """Each session leaves exactly one new line in the configured log."""
    name = "one_log_line_per_session"
    path, added = session_log_lines(ev)
    if path is None:
        return Result(name, False, added)
    bad = [f"session {n} added {len(lines)}" for n, lines in enumerate(added, 1)
           if len(lines) != 1]
    if bad:
        return Result(name, False, f"{path}: " + "; ".join(bad))
    return Result(name, True, f"{path}: one line from each of {len(added)} sessions")


# A line that opens with a date ("- **2026-10-22** — reversed, see [[note]]: "…"") is an
# entry companion files or proposes to file, such as a reversal annotation.
ENTRY = re.compile(r"^\s*(?:[-*]\s+)?(?:\*\*)?\d{4}-\d{2}-\d{2}\b")


def entry_quotes(text: str) -> set:
    """The quoted spans on the reply's dated entry lines."""
    return {m.group(1) for line in text.splitlines() if ENTRY.match(line)
            for m in re.finditer(_QUOTED, line)}


def g_quotes_verbatim(ev: Evidence) -> Result:
    """Every quote the companion attributes to a note, in any turn, is in that note.
    A dated entry that quotes the human's own words, such as a proposed reversal
    annotation, is new text for the note, not a claim about it, so it is exempt."""
    found = [(t, q) for turn in ev.transcript if turn["role"] == "companion"
             for t, q in quotes(turn["text"])
             if not (q in entry_quotes(turn["text"]) and said_by_human(ev, q))]
    bad = [why for t, q in found if (why := check_quote(t, q, ev.vault))]
    if bad:
        return Result("quotes_verbatim", False, "; ".join(bad))
    return Result("quotes_verbatim", True, f"{len(found)} linked quotes, all verbatim")


def touched(d: dict, allowed: tuple = ()) -> list:
    """Every changed path, marked +added ~modified -removed, except the allowed ones."""
    return ([f"+{p}" for p in d["added"] if p not in allowed]
            + [f"~{p}" for p in d["modified"] if p not in allowed]
            + [f"-{p}" for p in d["removed"] if p not in allowed])


def not_additions(d: dict) -> list:
    """The paths whose change is more than added text: a removed file, or a modified
    one that lost or altered a line. Blank lines hold none of the human's words, so
    they are left out of the comparison."""
    bad = [f"-{p}" for p in d["removed"]]
    for path, (old, new) in d["modified"].items():
        a = [l for l in old.splitlines() if l.strip()]
        b = [l for l in new.splitlines() if l.strip()]
        ops = difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes()
        if any(tag not in ("equal", "insert") for tag, *_ in ops):
            bad.append(f"~{path}")
    return bad


def g_no_writes(ev: Evidence) -> Result:
    """The vault is byte-for-byte unchanged: no log, no picked write, no transcript."""
    changed = touched(ev.diff)
    if changed:
        return Result("no_writes", False, "vault changed: " + ", ".join(changed))
    return Result("no_writes", True, "vault unchanged")


# A numbered list item: "1. Add a Definition", "2) …", "**3.** …".
NUMBERED = re.compile(r"^\s*(?:\*\*)?(\d+)[.)](?:\*\*)?\s+\S", re.M)


def g_numbered_moves(ev: Evidence) -> Result:
    """The first reply ends a diagnosis in moves the human can approve by number:
    a list numbered 1, 2, … with at least two items."""
    found = [int(n) for n in NUMBERED.findall(first_reply(ev))]
    run = best = 0
    for n in found:
        run = n if n == run + 1 else (1 if n == 1 else 0)
        best = max(best, run)
    if best < 2:
        return Result("numbered_moves", False,
                      f"no list numbered from 1 with two or more items (numbers seen: {found})")
    return Result("numbered_moves", True, f"{best} numbered moves")


# --- improve: apply only the approved moves -----------------------------------

IMPROVE = "Improve"


def improved_note(ev: Evidence) -> str | None:
    """The vault path of the note the session improves: the [[link]] in the first
    human turn, resolved against the vault as the session first saw it."""
    m = re.search(_LINK, (human_turns(ev) or [""])[0])
    if not m:
        return None
    key = note_key(m.group(1))
    return next((p for p in start_vault(ev) if p.endswith(".md") and path_key(p) == key), None)


def body(text: str) -> str:
    """A note without its frontmatter."""
    m = re.match(r"---\n.*?\n---\n", text, re.S)
    return text[m.end():] if m else text


def unframed(line: str) -> str:
    """A prose line with what a structure edit may add around its words taken off:
    [[wikilink]] brackets (an alias keeps its shown text) and HTML comments, such as
    a verification marker."""
    line = re.sub(r"\[\[(?:[^\]|]*\|)?([^\]]*)\]\]", r"\1", line)
    line = re.sub(r"<!--.*?-->", "", line)
    return re.sub(r"\s+", " ", line).strip()


def g_prose_verbatim(ev: Evidence) -> Result:
    """Every line the improved note held is still in it, word for word. Headings and
    new lines may go around it, lines may move, a word may gain [[ ]] and a line a
    marker. An AI capture callout may not change at all, marker included: it isn't
    the human's claim."""
    path = improved_note(ev)
    if not path:
        return Result("prose_verbatim", False, "no [[note]] named in the first turn")
    before = start_vault(ev)[path]
    after = ev.snapshots[-1].get(path) if ev.snapshots else None
    if after is None:
        return Result("prose_verbatim", False, f"{path} is gone")
    machine, prose = _split_callouts(body(before))
    kept = callouts(after)
    lost = [f"AI capture callout changed: \"{c[:60]}\"" for c in machine if c not in kept]
    lines = [unframed(l) for l in body(after).splitlines()]
    now, flat = set(lines), "\n".join(lines)
    for line in (unframed(l) for l in prose.splitlines() if l.strip()):
        if line not in now:
            # Quote the first sentence that went, so a long paragraph points at its change.
            gone = [s for s in re.split(r"(?<=[.!?])\s+", line) if s not in flat]
            lost.append(f"\"{(gone or [line])[0][:100]}\"")
    if lost:
        return Result("prose_verbatim", False, "not verbatim: " + "; ".join(lost))
    return Result("prose_verbatim", True, f"every line of {path} kept")


def moves(reply: str) -> dict:
    """{number: text} for the reply's list of moves: the longest run numbered 1, 2, …
    A later list that restarts at 1 (how to approve, say) doesn't replace it."""
    items, best, run = list(re.finditer(rf"{NUMBERED.pattern}.*$", reply, re.M)), {}, {}
    for m in items:
        n = int(m.group(1))
        run = {n: m.group(0)} if n == 1 else ({**run, n: m.group(0)} if n == len(run) + 1 else {})
        if len(run) > len(best):
            best = run
    return best


def numbers(text: str) -> set:
    """Every number and range ("1, 2, 4", "1-3") in the text."""
    named = set()
    for a, b in re.findall(r"(\d+)(?:\s*[-–]\s*(\d+))?", text):
        named.update(range(int(a), int(b or a) + 1))
    return named


def approved(turn: str, listed: dict) -> set:
    """The move numbers an approval names: numbers and ranges ("1, 2, 4", "1-3"),
    "all" (every move not deferred as NOT YET), or "none". Numbers after "not",
    "except" or "without" are declined, and so is anything unnamed."""
    if re.match(r"\s*none\b", turn, re.I):
        return set()
    yes, *rest = re.split(r"\b(?:but not|not|except|without)\b", turn, maxsplit=1, flags=re.I)
    no = rest[0] if rest else ""
    if re.match(r"\s*all\b", yes, re.I):
        named = {n for n, text in listed.items() if "NOT YET" not in text}
    else:
        named = numbers(yes)
    return (named - numbers(no)) & set(listed)


def maturity_property(snap: dict) -> str | None:
    """The frontmatter property the `## Improve` Overlay names for maturity: the first
    `code` span in its maturity field, else `maturity` when the field is set."""
    value = overlay_field(snap, "maturity", IMPROVE)
    if not value:
        return None
    m = re.search(r"`([^`]+)`", value)
    return m.group(1) if m else (value if re.fullmatch(r"[\w-]+", value) else "maturity")


def frontmatter_value(text: str, prop: str | None) -> str | None:
    if not prop:
        return None
    m = re.match(r"---\n(.*?)\n---\n", text, re.S)
    v = re.search(rf"^{re.escape(prop)}\s*:\s*(.*?)\s*$", m.group(1), re.M) if m else None
    return v.group(1) if v else None


def g_only_approved_moves_applied(ev: Evidence) -> Result:
    """The diagnosis turn writes nothing; after the approving turn the only files that
    changed are the improved note, the log, the notes an approved move links to, and
    the index if an approved move names it. An approval that names moves changes the
    note; "none" changes nothing."""
    name = "only_approved_moves_applied"
    path, snaps = improved_note(ev), ev.snapshots
    if not path or len(snaps) < 3:
        return Result(name, False, "no improved note, or the session stopped before approval")
    early = touched(vaultdiff.diff(snaps[0], snaps[1]))
    if early:
        return Result(name, False, "the diagnosis turn wrote: " + ", ".join(early))
    listed = moves(first_reply(ev))
    chosen = approved(human_turns(ev)[1], listed)
    shown = f"approved {sorted(chosen) or 'none'}"
    allowed = set()
    if chosen:
        text = "\n".join(listed[n] for n in chosen)
        named = links(text)
        index = overlay_field(snaps[0], "index", IMPROVE)
        if index and re.search(r"\bindex\b", text, re.I):
            named.add(note_key(index.removesuffix(".md")))
        allowed = {path, log_path(snaps[0], IMPROVE)}
        allowed |= {p for p in snaps[-1] if p.endswith(".md") and path_key(p) in named}
    stray = touched(ev.diff, tuple(a for a in allowed if a))
    if stray:
        return Result(name, False, f"{shown}, but changed: " + ", ".join(stray))
    if chosen and path not in ev.diff["modified"]:
        return Result(name, False, f"{shown}, but {path} is unchanged")
    prop = maturity_property(snaps[0])
    was, now = (frontmatter_value(snap.get(path, ""), prop) for snap in (snaps[0], snaps[-1]))
    if prop and was != now and not any(re.search(r"promot", listed[n], re.I) for n in chosen):
        return Result(name, False, f"{shown}, none a promotion, but {prop} went {was} → {now}")
    return Result(name, True, f"approved {sorted(chosen) or 'none'} of {len(listed)}; "
                              "only their files changed")


def g_one_improve_log_line(ev: Evidence, op: str = "improve",
                           promote: str = "promote", split: str = "split") -> Result:
    """Each session leaves one `improve` line in the configured log that links the
    note, plus at most a separate `promote` and `split` line. A vault whose Overlay
    renames the ops passes them as parameters."""
    name = "one_improve_log_line"
    path, added = session_log_lines(ev, IMPROVE)
    if not path:
        return Result(name, False, added)
    key = path_key(improved_note(ev) or "")

    def has(line, word):
        return re.search(rf"(?<!\w){re.escape(word)}(?!\w)", line, re.I) is not None

    for n, lines in enumerate(added, 1):
        other_op = [l for l in lines if has(l, promote) or has(l, split)]
        main = [l for l in lines if l not in other_op and has(l, op) and key in links(l)]
        extra = [l for l in lines if l not in main and l not in other_op]
        if len(main) != 1 or extra:
            return Result(name, False, f"session {n}: {len(main)} `{op}` line(s) linking "
                                       f"[[{key}]], {len(extra)} other line(s) in {path}")
    return Result(name, True, f"one `{op}` line per session in {path}")


# --- improve: no Overlay, fallbacks named ------------------------------------

# Each `## Improve` field: how a reply names it, and how it names that field's
# fallback. A clause (a line, cut at , ; |) names the fallback when it labels the
# field unset ("log: none") or names the field and its fallback together ("no
# schema, inferred from siblings"). A bare "no" beside the field's name doesn't
# count: "no index entry" says nothing about the Overlay.
IMPROVE_FIELDS = {
    "index": (r"\bindex\b", r"skip(?![\s-]*list)"),
    "log": (r"\blog(?:ged|ging)?\b", r"nothing|not\s+(?:be\s+)?logged|won't log"),
    "schema": (r"\bschema\b", r"infer|sibling"),
    "maturity": (r"\bmaturity\b|\bladder\b", r"promot"),
    "verification marker": (r"verification", r"NEEDS VERIFICATION|HTML comment"),
    "skip list": (r"skip[\s-]*list", r"AI capture"),
}
UNSET = r"(?:none|not (?:set|configured|found)|missing|absent|unset)\b"


def clauses(reply: str) -> list:
    return [c for line in reply.splitlines() for c in re.split(r"[,;|]", line)]


def labelled_unset(field: str, clause: str) -> bool:
    """The clause labels the field unset: "log: none", "**index** — not set"."""
    return re.search(rf"(?:{field})\W{{0,6}}{UNSET}", clause, re.I) is not None


def fallbacks_in(reply: str, fields: list) -> list:
    """The fields some clause of the reply names together with their fallback."""
    named = []
    for f in fields:
        field, fallback = IMPROVE_FIELDS[f]
        if any(labelled_unset(field, c) or (re.search(field, c, re.I) and re.search(fallback, c, re.I))
               for c in clauses(reply)):
            named.append(f)
    return named


def g_fallbacks_named(ev: Evidence) -> Result:
    """Every `## Improve` field the Overlay leaves unset is named with its fallback in
    the first reply, once: a later reply naming two or more again fails. A field the
    Overlay sets, through a pointer to another section or not, is never called unset."""
    name = "fallbacks_named"
    snap = ev.snapshots[0] if ev.snapshots else {}
    missing = [f for f in IMPROVE_FIELDS if overlay_field(snap, f, IMPROVE) is None]
    first = first_reply(ev)
    wrong = [f for f in IMPROVE_FIELDS if f not in missing
             and any(labelled_unset(IMPROVE_FIELDS[f][0], c) for c in clauses(first))]
    if wrong:
        return Result(name, False, "calls a field the Overlay sets unset: " + ", ".join(wrong))
    if not missing:
        return Result(name, True, "the Overlay sets every field")
    unnamed = [f for f in missing if f not in fallbacks_in(first, missing)]
    if unnamed:
        return Result(name, False, "first reply names no fallback for: " + ", ".join(unnamed))
    # Again means listed again ("log: none"), not a report of what was done
    # ("nothing was logged", "added <!-- NEEDS VERIFICATION -->").
    for k, text in enumerate(replies(ev)[1:], 2):
        again = [f for f in missing if any(labelled_unset(IMPROVE_FIELDS[f][0], c) for c in clauses(text))]
        if len(again) >= 2:
            return Result(name, False, f"reply {k} names the fallbacks again: " + ", ".join(again))
    return Result(name, True, "fallbacks named once for: " + ", ".join(missing))


PROMOTING = re.compile(r"promot|(?:set|change|raise|move|bump)\w*\s+(?:the\s+|its\s+)?maturity"
                       r"|maturity\s*(?:to|→|->)\s*\w", re.I)


def g_no_maturity_ladder(ev: Evidence) -> Result:
    """With no maturity field in the Overlay, the diagnosis has no maturity: no move
    promotes the note or sets its maturity, deferred or not; no line (other than a
    question) reads its level off the note and no MATURITY section judges it; and its `maturity` property
    doesn't change."""
    name = "no_maturity_ladder"
    start = ev.snapshots[0] if ev.snapshots else {}
    if overlay_field(start, "maturity", IMPROVE):
        return Result(name, True, "the Overlay sets a maturity ladder")
    reply = first_reply(ev)
    promoting = [text.strip() for text in moves(reply).values() if PROMOTING.search(text)]
    if promoting:
        return Result(name, False, "proposed: " + "; ".join(f"\"{t[:80]}\"" for t in promoting))
    if re.search(r"^\W*(?:#+\s*)?maturity\W*$", reply, re.M | re.I):
        return Result(name, False, "a MATURITY section with no ladder to judge by")
    path = improved_note(ev)
    level = frontmatter_value(start.get(path or "", ""), "maturity")
    if level:
        # Asking about the level, or naming the fallback beside it, isn't a guess.
        guess = next((l.strip() for l in reply.splitlines()
                      if "?" not in l and not fallbacks_in(l, ["maturity"])
                      and re.search(r"\bmat(?:urity)?\b", l, re.I)
                      and re.search(rf"\b{re.escape(level)}\b", l, re.I)), None)
        if guess:
            return Result(name, False, f"reads a level with no ladder: \"{guess[:80]}\"")
    if path and ev.snapshots:
        was, now = (frontmatter_value(snap.get(path, ""), "maturity") for snap in (start, ev.snapshots[-1]))
        if was != now:
            return Result(name, False, f"maturity went {was} → {now}")
    return Result(name, True, "no maturity proposed, read or changed")


def numbered_lists(reply: str) -> int:
    """How many lists numbered 1, 2, … the reply holds."""
    count = run = 0
    for n in (int(n) for n in NUMBERED.findall(reply)):
        run = n if n in (1, run + 1) else 0
        count += run == 2
    return count


# A candidate list is a line per note and a question; a diagnosis runs longer.
CANDIDATE_LIST_LINES = 25


def g_candidates_listed(ev: Evidence) -> Result:
    """For "improve <folder>": the first reply names two or more notes in the folder and
    asks a question, and diagnoses none of them: no more than one numbered list,
    and short."""
    name = "candidates_listed"
    turn = (human_turns(ev) or [""])[0]
    vault = start_vault(ev)
    folders = {p.rsplit("/", 1)[0] for p in vault if "/" in p}
    folder = next((f for f in sorted(folders, key=len, reverse=True)
                   if re.search(rf"(?<!\w){re.escape(f)}(?!\w)", turn, re.I)), None)
    if not folder:
        return Result(name, False, "no folder of the vault named in the first turn")
    reply = first_reply(ev)
    inside = sorted({path_key(p) for p in vault if p.startswith(folder + "/") and p.endswith(".md")})
    named = [n for n in inside if n in reply.lower()]
    if len(named) < 2:
        return Result(name, False, f"names {len(named)} of {len(inside)} notes in {folder}/")
    if "?" not in reply and "？" not in reply:
        return Result(name, False, "lists candidates but asks no question")
    lists, lines = numbered_lists(reply), len([l for l in reply.splitlines() if l.strip()])
    if lists > 1 or lines > CANDIDATE_LIST_LINES:
        return Result(name, False, f"diagnoses instead of listing: {lists} numbered lists, {lines} lines")
    return Result(name, True, f"lists {len(named)} notes in {folder}/ and asks which first")


def g_writes_only_log(ev: Evidence) -> Result:
    """With a log and no write option picked, the log is the only file that changes."""
    path = at_start(ev, log_path)
    if not path:
        return Result("writes_only_log", False, "no log configured in the Overlay")
    other = touched(ev.diff, (path,))
    if other:
        return Result("writes_only_log", False, "wrote beyond the log: " + ", ".join(other))
    return Result("writes_only_log", True, f"only {path} changed")


def g_unpicked_menu_logged(ev: Evidence) -> Result:
    """A first session that ends on the menu, with no pick, is logged as `menu unpicked`."""
    name = "unpicked_menu_logged"
    path, added = session_log_lines(ev)
    if path is None:
        return Result(name, False, added)
    if not added or len(added[0]) != 1:
        return Result(name, False, f"session 1 left {len(added[0]) if added else 0} lines in {path}")
    line = added[0][0]
    if "menu unpicked" not in line.lower():
        return Result(name, False, f"session 1 logged without `menu unpicked`: {line}")
    return Result(name, True, line)


SECOND_SESSION = 1  # transcript session ids count from 0


def g_unpicked_menu_named_once(ev: Evidence, topic: str) -> Result:
    """The second session's first reply names the menu the first session left unpicked,
    before orient quotes any note, and no later reply in that session names it again. `topic` is a regex for the
    first session's subject, which nothing in the second session's notes mentions."""
    name = "unpicked_menu_named_once"
    replies = [t["text"] for t in ev.transcript
               if t["role"] == "companion" and t.get("session", 0) == SECOND_SESSION]
    if not replies:
        return Result(name, False, "no second session")
    named = re.search(topic, replies[0], re.I)
    if not named:
        return Result(name, False, f"the second session's first reply does not name /{topic}/")
    first_quote = QUOTE_RE.search(replies[0])
    if first_quote and first_quote.start() < named.start():
        return Result(name, False, "named only after orient had started quoting notes")
    again = [k for k, text in enumerate(replies[1:], 2) if re.search(topic, text, re.I)]
    if again:
        return Result(name, False, f"named again in reply {again[0]} of the second session")
    return Result(name, True, "named once, in the second session's first reply")


# --- the human's line ([a]) and transcripts -------------------------------------

def human_turns(ev: Evidence, session: int | None = None) -> list:
    return [t["text"] for t in ev.transcript if t["role"] == "human"
            and (session is None or t.get("session", 0) == session)]


def said_by_human(ev: Evidence, text: str) -> bool:
    """The text is long enough to be a line, and verbatim somewhere the human said it.
    Loose on purpose: used to catch a quote the human never said."""
    return (len(text.split()) >= MIN_QUOTE_WORDS
            and any(verbatim(text, turn) for turn in human_turns(ev)))


def thinking_turns(ev: Evidence) -> list:
    """The human turns a fileable line can come from: not a /command that opens a
    session, and nothing from the turn that asked to close onwards."""
    out = []
    for t in ev.transcript:
        if t["role"] == "human":
            out.append(t["text"])
        elif MENU_OPTION.search(t["text"]):
            out = out[:-1]
            break
    return [t for t in out if not _COMMAND.match(t)]


def _sentences(turn: str) -> list:
    return [s for s in re.split(r"(?<=[.!?])\s+", _norm(turn)) if s]


def fileable(ev: Evidence, text: str) -> bool:
    """The text is one or more whole sentences of a turn the human thought aloud in,
    copied exactly: no trimmed fragment, no ellipsis, no closing request."""
    line = _norm(text).rstrip(".!?")
    if len(line.split()) < MIN_QUOTE_WORDS or "…" in line or "..." in line:
        return False
    for turn in thinking_turns(ev):
        sents = _sentences(turn)
        for i in range(len(sents)):
            for j in range(i + 1, len(sents) + 1):
                if " ".join(sents[i:j]).rstrip(".!?") == line:
                    return True
    return False


_DECORATION = re.compile(r"^[\s>*\-`\"“«]+|[\s`\"”»*]+$")


def possible_lines(text: str) -> list:
    """Every "quoted" span, and every line with its bullet, blockquote marker or
    wrapping quotes removed: the forms a filed or handed-back line can take."""
    spans = [m.group(1) for m in re.finditer(_QUOTED, text)]
    return spans + [_DECORATION.sub("", line) for line in text.splitlines()]


def human_line_in(ev: Evidence, text: str) -> str | None:
    return next((c for c in possible_lines(text) if fileable(ev, c)), None)


def written(ev: Evidence) -> dict:
    """{path: text the session wrote}: an added file whole, a modified file's new lines."""
    out = dict(ev.diff["added"])
    out.update({p: "\n".join(new_lines(old, new.splitlines()))
                for p, (old, new) in ev.diff["modified"].items()})
    return out


_HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")


def heading_name(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lstrip("#").strip()).lower()


def under_heading(text: str, name: str) -> list:
    """The lines of every section whose heading reads `name`, at any level."""
    out, level = [], None
    for line in text.splitlines():
        h = _HEADING.match(line)
        if h and level is not None and len(h.group(1)) <= level:
            level = None
        if h and heading_name(h.group(2)) == name:
            level = len(h.group(1))
            continue
        if level is not None:
            out.append(line)
    return out


def new_lines(before: str, after: list) -> list:
    """The lines in `after` that `before` did not already hold, counting repeats."""
    left = {}
    for line in before.splitlines():
        left[line] = left.get(line, 0) + 1
    out = []
    for line in after:
        if left.get(line):
            left[line] -= 1
        else:
            out.append(line)
    return out


_COMMAND = re.compile(r"^\s*/\S+\s*")
DATE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")


def g_line_filed_under_target(ev: Evidence) -> Result:
    """[a] wrote, under the configured filing target on a note that was already in the
    vault, a dated line the human said, whole and verbatim, and quoted nothing there
    that the human didn't say."""
    name = "line_filed_under_target"
    target = at_start(ev, lambda snap: overlay_field(snap, "filing target"))
    if not target:
        return Result(name, False, "no filing target configured in the Overlay")
    heading = heading_name(target)
    before = ev.snapshots[0] if ev.snapshots else {}
    after = ev.snapshots[-1] if ev.snapshots else {}
    for path in sorted(set(ev.diff["added"]) | set(ev.diff["modified"])):
        added = [l for l in new_lines(before.get(path, ""), under_heading(after.get(path, ""), heading))
                 if l.strip()] if ev.snapshots else []
        if not added:
            continue
        if path not in before or path in OVERLAY_FILES or path == at_start(ev, log_path):
            return Result(name, False, f"filed into {path}, not a note the session was about")
        block = "\n".join(added)
        invented = [q for q in (m.group(1) for m in re.finditer(_QUOTED, block))
                    if len(q.split()) >= MIN_QUOTE_WORDS and not said_by_human(ev, q)]
        if invented:
            return Result(name, False, f"{path}: quoted under {target} but never said: "
                                       f"\"{invented[0]}\"")
        if not DATE.search(block):
            return Result(name, False, f"{path}: the line under {target} has no date")
        line = human_line_in(ev, block)
        if line:
            return Result(name, True, f"{path}: \"{line}\" under {target}")
        return Result(name, False, f"{path}: nothing under {target} is a whole sentence "
                                   "the human said")
    return Result(name, False, f"no new line under a {target} heading anywhere in the vault")


def g_line_handed_back(ev: Evidence) -> Result:
    """With no filing target, the reply to the [a] pick gives the human their own line,
    verbatim, to place themselves."""
    name = "line_handed_back"
    last = next((t["text"] for t in reversed(ev.transcript) if t["role"] == "companion"), "")
    line = human_line_in(ev, last)
    if line:
        return Result(name, True, f"handed back: \"{line}\"")
    return Result(name, False, "the last reply holds no line the human said verbatim")


def offers_a(menu: str) -> str | None:
    """The menu's [a] option line, or None. Options run in letter order, so an [a] line
    after another option is a note about the menu (why [a] is missing), not an offer."""
    first = next((l for l in menu.splitlines() if MENU_OPTION.match(l)), None)
    return first if first and FILE_OPTION.match(first) else None


def g_file_option_absent(ev: Evidence) -> Result:
    """The human never said a fileable line, so no close menu offers [a]."""
    name = "file_option_absent"
    menus = [t["text"] for t in ev.transcript
             if t["role"] == "companion" and MENU_OPTION.search(t["text"])]
    if not menus:
        return Result(name, False, "no close menu shown")
    for menu in menus:
        line = offers_a(menu)
        if line:
            return Result(name, False, f"menu offers [a]: {line.strip()[:120]}")
    return Result(name, True, f"{len(menus)} menu(s), none offering [a]")


def g_no_transcript(ev: Evidence) -> Result:
    """No file the session wrote holds two or more of one session's human turns.
    A filed line or a log topic holds one; a transcript holds them all. A one-turn
    session can't be told apart this way, so cases like that grade `no_writes`."""
    name = "no_transcript"
    files = written(ev)
    sids = sorted({t.get("session", 0) for t in ev.transcript if t["role"] == "human"})
    for path, text in files.items():
        for sid in sids:
            turns = [_COMMAND.sub("", t) for t in human_turns(ev, sid)]
            hits = [t for t in turns if len(t.split()) >= MIN_QUOTE_WORDS and verbatim(t, text)]
            if len(hits) >= 2:
                return Result(name, False, f"{path} holds {len(hits)} of the human's turns "
                                           f"from session {sid + 1}")
    return Result(name, True, f"{len(files)} written file(s), none a transcript")


# --- voice: machine text is never fed back as the human's ----------------------

# A folded `> [!quote]- AI capture` callout runs from its title line to the first
# line that is no longer part of the blockquote.
_CALLOUT_TITLE = re.compile(r"^>\s*\[!quote\][-+]?\s*AI capture", re.I)


def _split_callouts(text: str) -> tuple:
    """([body of every AI capture callout, `>` markers removed], the rest of the note)."""
    out, rest, body = [], [], None
    for line in text.splitlines() + [""]:
        if body is not None and line.startswith(">"):
            body.append(line.lstrip(">").strip())
            continue
        if body is not None:
            out.append("\n".join(body))
            body = None
        if _CALLOUT_TITLE.match(line):
            body = []
        else:
            rest.append(line)
    return out, "\n".join(rest)


def callouts(text: str) -> list:
    """The body of every AI capture callout in a note, `>` markers removed."""
    return _split_callouts(text)[0]


def start_vault(ev: Evidence) -> dict:
    """The vault as the session first saw it: the first snapshot, else the Fixture."""
    if ev.snapshots:
        return ev.snapshots[0]
    return {p.relative_to(ev.vault).as_posix(): p.read_text() for p in ev.vault.rglob("*.md")}


def overlay_items(snap: dict, name: str) -> list:
    """A list-valued Overlay field ("`digests/`, [[the novel]]") as bare items:
    a folder ends in `/`, anything else is a note name or a vault path."""
    value = overlay_field(snap, name)
    if not value:
        return []
    items = []
    for raw in re.split(r"[,;]", value):
        item = raw.strip().strip("`\"'")
        link = re.fullmatch(r"\[\[([^\]|#]+)[^\]]*\]\]", item)
        item = (link.group(1) if link else item).strip().strip("`").strip()
        if item:
            items.append(item)
    return items


def listed(path: str, items: list) -> bool:
    """The vault path is one of the items, or sits in a folder among them."""
    stem = path.lower().removesuffix(".md")
    for item in (i.lower() for i in items):
        if item.endswith("/"):
            folder = item.strip("/") + "/"
            if stem.startswith(folder) or f"/{folder}" in stem:
                return True
        elif item.removesuffix(".md") in (stem, note_key(stem)):
            return True
    return False


def skipped(snap: dict) -> list:
    """The vault paths that are never the human's voice: the Overlay's skip list,
    plus the log, which companion writes."""
    items = overlay_items(snap, "skip list")
    log = log_path(snap)
    return [p for p in snap if p.endswith(".md") and p not in OVERLAY_FILES
            and (listed(p, items) or p == log)]


def machine_text(snap: dict) -> list:
    """(where, text) for everything that is never the human's voice."""
    out = [(path, snap[path]) for path in skipped(snap)]
    return out + [(f"an AI capture callout in {path}", body)
                  for path, text in snap.items() if path.endswith(".md")
                  for body in callouts(text)]


def human_text(snap: dict) -> str:
    """The corpus: every note that isn't skipped or the Overlay's file, callouts removed."""
    skip = set(skipped(snap)) | set(OVERLAY_FILES)
    out = []
    for path, text in snap.items():
        if path.endswith(".md") and path not in skip:
            out.append(_split_callouts(text)[1])
    return "\n".join(out)


def quoted_spans(text: str) -> list:
    """Every quoted span and blockquote line long enough to be a quote, outside menu options."""
    text = outside_menu(text)
    spans = [m.group(1) for m in re.finditer(_QUOTED, text)]
    spans += [line.lstrip("> ").strip() for line in text.splitlines() if line.startswith(">")]
    return [s for s in spans if len(s.split()) >= MIN_QUOTE_WORDS]


def g_machine_text_never_quoted(ev: Evidence) -> Result:
    """No reply quotes text from an AI capture callout or a skip-listed note. A quote
    in a reply reads as evidence from the human's notes, so machine text is argued
    with in the human's terms, never quoted."""
    name = "machine_text_never_quoted"
    snap = start_vault(ev)
    machine, human = machine_text(snap), human_text(snap).lower()
    for text in replies(ev):
        for span in quoted_spans(text):
            where = next((w for w, body in machine
                          if verbatim(span.lower(), body.lower())), None)
            if where and not said_by_human(ev, span) and not verbatim(span.lower(), human):
                return Result(name, False, f"quoted {where}: \"{span}\"")
    return Result(name, True, f"no quote from {len(machine)} machine-written block(s)")


def g_quotes_human_beside_callout(ev: Evidence) -> Result:
    """Some reply quotes, verbatim, the human's own writing in a note that also holds
    an AI capture callout: the machine text is skipped, the note around it is not."""
    name = "quotes_human_beside_callout"
    snap = start_vault(ev)
    with_callout = {path_key(p): p for p, text in snap.items()
                    if p.endswith(".md") and callouts(text)}
    if not with_callout:
        return Result(name, False, "no note in the vault holds an AI capture callout")
    for text in replies(ev):
        for target, quote in verified(quotes(text), ev.vault):
            path = with_callout.get(note_key(target))
            if path and not any(verbatim(quote, body) for body in callouts(snap[path])):
                return Result(name, True, f"quoted [[{target}]] outside its callout")
    return Result(name, False, "no reply quotes the human's writing in "
                               + ", ".join(f"[[{k}]]" for k in sorted(with_callout)))


# --- contradictions -------------------------------------------------------------

# The three kinds a contradiction can be. Naming all three, as a question, leaves the
# choice to the human; naming one ("so this is a reversal?") makes it for them.
CONTRADICTION_TYPES = (r"\breversal", r"\bnuance", r"\bdomain[\s-]+mismatch")


def asks_type(text: str) -> bool:
    return "?" in text and all(re.search(t, text, re.I) for t in CONTRADICTION_TYPES)


_VERDICT = re.compile(r"\b(?:i'd call(?: it| this| that)?|i would call(?: it| this| that)?|it's|it is|this is|that's|that is|"
                      r"looks like|sounds like|reads as|reads like)\s+"
                      r"(?:(?:a|an|clearly|plainly|probably|really)\s+)*"
                      r"(reversal|nuance|domain[\s-]+mismatch)", re.I)


def decided_type(text: str) -> str | None:
    """The sentence that names the type for the human, if any. A question, or a
    sentence about what would follow ("if it's a reversal, I can…"), decides nothing."""
    for sentence in re.split(r"(?<=[.!?])\s+|\n", text.replace("’", "'")):
        s = sentence.strip()
        if s.endswith("?") or re.search(r"\b(?:if|whether|unless)\b", s, re.I):
            continue
        if _VERDICT.search(s):
            return s
    return None


def g_contradiction_surfaced(ev: Evidence, note: str) -> Result:
    """One reply puts the older note and the human's new position side by side, both
    quoted verbatim, the note's quote in a [[wikilink]] to `note`, and asks the human
    which kind of contradiction it is without deciding it for them."""
    name = "contradiction_surfaced"
    said = [t for t in human_turns(ev) if not _COMMAND.match(t)]
    best = f"no reply quotes [[{note}]]"
    for k, text in enumerate(replies(ev), 1):
        if not any(note_key(t) == note_key(note) for t, _ in verified(quotes(text), ev.vault)):
            continue
        if not any(verbatim(span, turn) for span in quoted_spans(text) for turn in said):
            best = f"reply {k} quotes [[{note}]] but not the human's words verbatim"
            continue
        if not asks_type(text):
            best = (f"reply {k} quotes both positions but doesn't ask whether it is a "
                    "reversal, nuance or domain mismatch")
            continue
        verdict = decided_type(text)
        if verdict:
            return Result(name, False, f"reply {k} decides the type for the human: {verdict}")
        return Result(name, True, f"reply {k} quotes [[{note}]] and the human's words, "
                                  "and asks the type")
    return Result(name, False, best)


def g_reversal_annotated(ev: Evidence, note: str) -> Result:
    """On a confirmed reversal, `note` gains a dated line with a [[wikilink]] to the
    new position, in another note that exists afterwards. It lands after the last human
    turn, which a reversal case makes the approving one, and on no turn before it. The
    vault diff is additions only, so the original text stays as written."""
    name = "reversal_annotated"
    if not ev.snapshots:
        return Result(name, False, "no snapshots to tell when the note changed")
    start = ev.snapshots[0]
    path = next((p for p in start if path_key(p) == note_key(note)), None)
    if path is None:
        return Result(name, False, f"[[{note}]] is not in the vault")
    if path not in ev.diff["modified"]:
        return Result(name, False, f"[[{note}]] was not annotated")
    early = next((k for k in range(1, len(ev.snapshots) - 1)
                  if ev.snapshots[k].get(path) != start[path]), None)
    if early is not None:
        return Result(name, False, f"[[{note}]] changed after human turn {early}, "
                                   f"before the approving turn {len(ev.snapshots) - 1}")
    changed = not_additions(ev.diff)
    if changed:
        return Result(name, False, "original text changed, not only added to: "
                                   + ", ".join(changed))
    block = written(ev)[path]
    if not DATE.search(block):
        return Result(name, False, f"the annotation on [[{note}]] has no date")
    human = human_text(start)
    invented = [q for q in quoted_spans(block)
                if not said_by_human(ev, q) and not verbatim(q, human)]
    if invented:
        return Result(name, False, f"the annotation quotes words the human never said: "
                                   f"\"{invented[0]}\"")
    after = {path_key(p) for p in ev.snapshots[-1] if p.endswith(".md")}
    linked = sorted((links(block) & after) - {note_key(note)})
    if linked:
        return Result(name, True, f"[[{note}]] annotated, linking [[{linked[0]}]]")
    return Result(name, False, f"the annotation on [[{note}]] links no new position "
                               "in another note")


# --- language -------------------------------------------------------------------

# A reply's language is the one most of its own words are in. A word is a Latin or
# Cyrillic run of two letters or more, so menu letters ("[a]") say nothing; Chinese
# has no spaces, so two Han characters count as one word.
WORDS = {
    "zh": (re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]"), 0.5),
    "ru": (re.compile(r"[\u0400-\u04ff]{2,}"), 1.0),
    "en": (re.compile(r"[A-Za-z]{2,}"), 1.0),
}


def language(text: str) -> str | None:
    """The language most of the text is written in, or None with no words at all."""
    counts = {lang: len(rx.findall(text)) * weight for lang, (rx, weight) in WORDS.items()}
    lang = max(counts, key=counts.get)
    return lang if counts[lang] else None


def own_words(text: str) -> str:
    """The reply without what it quotes or links: quoted spans, blockquote lines,
    wikilinks and code. Quotes keep their source language, so they don't count."""
    text = re.sub(r"```.*?```|`[^`\n]*`", " ", text, flags=re.S)
    text = "\n".join(line for line in text.splitlines() if not line.lstrip().startswith(">"))
    return re.sub(_QUOTED, " ", re.sub(_LINK, " ", text))


def reply_language(text: str) -> str | None:
    return language(own_words(text))


def g_replies_in_language(ev: Evidence, lang: str) -> Result:
    """Every reply is written in `lang`, counting only its own words: what it quotes
    or links stays in the language it was written in."""
    name = "replies_in_language"
    texts = replies(ev)
    for k, text in enumerate(texts, 1):
        found = reply_language(text)
        if found not in (lang, None):
            return Result(name, False, f"reply {k} is in {found}, not {lang}")
    return Result(name, True, f"{len(texts)} replies in {lang}")


def g_quotes_stay_in_source_language(ev: Evidence, lang: str) -> Result:
    """A reply written in `lang` quotes a note verbatim, in a [[wikilink]], in the
    note's own language: the quote was not translated into the reply's."""
    name = "quotes_stay_in_source_language"
    written_in = [(k, text) for k, text in enumerate(replies(ev), 1)
                  if reply_language(text) == lang]
    if not written_in:
        return Result(name, False, f"no reply is in {lang}")
    for k, text in written_in:
        kept = [(t, q) for t, q in verified(quotes(text), ev.vault) if language(q) != lang]
        if kept:
            t, q = kept[0]
            return Result(name, True, f"reply {k} quotes [[{t}]] in {language(q)}: \"{q}\"")
    return Result(name, False, f"no reply in {lang} quotes a note verbatim in its own language")


GRADERS = {
    "orient_quotes_corpus": g_orient_quotes_corpus,
    "quotes_verbatim": g_quotes_verbatim,
    "no_writes": g_no_writes,
    "numbered_moves": g_numbered_moves,
    "prose_verbatim": g_prose_verbatim,
    "only_approved_moves_applied": g_only_approved_moves_applied,
    "one_improve_log_line": g_one_improve_log_line,
    "fallbacks_named": g_fallbacks_named,
    "no_maturity_ladder": g_no_maturity_ladder,
    "candidates_listed": g_candidates_listed,
    "orient_quotes_from_index": g_orient_quotes_from_index,
    "overlay_written_after_approval": g_overlay_written_after_approval,
    "session_quotes_corpus": g_session_quotes_corpus,
    "one_log_line_per_session": g_one_log_line_per_session,
    "writes_only_log": g_writes_only_log,
    "unpicked_menu_logged": g_unpicked_menu_logged,
    "unpicked_menu_named_once": g_unpicked_menu_named_once,
    "line_filed_under_target": g_line_filed_under_target,
    "line_handed_back": g_line_handed_back,
    "file_option_absent": g_file_option_absent,
    "no_transcript": g_no_transcript,
    "machine_text_never_quoted": g_machine_text_never_quoted,
    "quotes_human_beside_callout": g_quotes_human_beside_callout,
    "contradiction_surfaced": g_contradiction_surfaced,
    "reversal_annotated": g_reversal_annotated,
    "replies_in_language": g_replies_in_language,
    "quotes_stay_in_source_language": g_quotes_stay_in_source_language,
}

# Graded on every case, named or not: no session may leave a transcript in the vault.
EVERY_CASE = ("no_transcript",)


def spec(entry) -> tuple:
    """A case names a grader as "name", or as {"name": ..., <parameter>: ...}."""
    if isinstance(entry, str):
        return entry, {}
    params = dict(entry)
    return params.pop("name"), params


def grade(entries: list, ev: Evidence) -> dict:
    named = [spec(e) for e in entries]
    named += [(n, {}) for n in EVERY_CASE if n not in {name for name, _ in named}]
    results = [GRADERS[name](ev, **params) for name, params in named]
    total = sum(r.weight for r in results) or 1.0
    return {
        "passed": all(r.passed for r in results if r.hard),
        "score": round(sum(r.weight for r in results if r.passed) / total, 3),
        "hard_fail": [r.name for r in results if r.hard and not r.passed],
        "results": [r.as_dict() for r in results],
    }
