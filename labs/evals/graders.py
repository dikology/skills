"""Graders for companion eval cases.

A grader sees what a user would see or find: the session transcript and the
vault diff, plus the Fixture vault to check quotes against. It never reads the
skill's prompt text, and it never asserts wording or section order.

Each grader returns a Result. A case passes when every hard grader passes; the
score is the weighted share of graders passed, reported alongside.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path


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
# [[note]] — "text"  or  "text" — [[note]]. The gap between them holds no other
# link or quote, so a quote is credited to the link nearest it.
_LINK = r"\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|[^\]]*)?\]\]"
_QUOTED = r"[\"“«]([^\"”»\n]+)[\"”»]"
_GAP = r"[^\n\"“«\[\]]*?"
QUOTE_RE = re.compile(f"{_LINK}{_GAP}{_QUOTED}|{_QUOTED}{_GAP}{_LINK}")

# A quote this short ("Pottery", "Thursday evenings") could match a heading or a
# name; it doesn't show the reply read the note.
MIN_QUOTE_WORDS = 3


# A close-menu option ("[e] Add "<question>" to [[note]]") proposes new text for a
# note. Its quotes are not claims about what the note already says.
MENU_OPTION = re.compile(r"^\s*(?:[-*]\s+)?(?:\*\*)?\[[a-z]\]", re.M)
FILE_OPTION = re.compile(r"^\s*(?:[-*]\s+)?(?:\*\*)?\[a\]", re.M)


def quotes(text: str) -> list:
    """(link target, quoted text) pairs, in order of appearance, outside menu options."""
    out = []
    text = "\n".join(line for line in text.splitlines() if not MENU_OPTION.match(line))
    for m in QUOTE_RE.finditer(text):
        target, quote = (m.group(1), m.group(2)) if m.group(1) else (m.group(4), m.group(3))
        out.append((target.strip(), quote))
    return out


def note_key(target: str) -> str:
    """Obsidian resolves [[folder/Name]] by its last part, case-insensitively."""
    return target.strip().lower().split("/")[-1]


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


def check_quote(target: str, quote: str, vault: Path) -> str | None:
    """None if the quote is verbatim in the note the link resolves to; else why not."""
    path = notes(vault).get(note_key(target))
    if path is None:
        return f"[[{target}]] does not resolve"
    if not verbatim(quote, path.read_text()):
        return f"not verbatim in [[{target}]]: \"{quote}\""
    return None


def first_reply(ev: Evidence) -> str:
    return next((t["text"] for t in ev.transcript if t["role"] == "companion"), "")


# --- the Overlay, read the way a user reads their own CLAUDE.md ---------------

OVERLAY_FILES = ("CLAUDE.md", "AGENTS.md")
_SECTION = re.compile(r"^## Companion[ \t]*\n(.*?)(?=^## |\Z)", re.M | re.S)


def overlay(snap: dict) -> str | None:
    """The body of the `## Companion` section, or None when the vault has none."""
    for name in OVERLAY_FILES:
        m = _SECTION.search(snap.get(name, ""))
        if m:
            return m.group(1)
    return None


def overlay_field(snap: dict, name: str) -> str | None:
    """A field's value with its [[link]] or `code` wrapper removed, or None."""
    m = re.search(rf"^\s*[-*]?\s*(\*\*|__)?{re.escape(name)}(\*\*|__)?\s*:\s*(.+?)\s*$",
                  overlay(snap) or "", re.M | re.I)
    if not m:
        return None
    value = m.group(3)
    if re.match(r"(none|no|n/a|-|—)(\W|$)", value, re.I):
        return None
    inner = re.fullmatch(r"\[\[([^\]|#]+)[^\]]*\]\]|`([^`]+)`", value)
    return (inner.group(1) or inner.group(2)).strip() if inner else value


def links(text: str) -> set:
    return {note_key(m.group(1)) for m in re.finditer(_LINK, text)}


def at_start(ev: "Evidence", fn):
    """fn applied to the vault as the session first saw it, or None with no snapshot."""
    return fn(ev.snapshots[0]) if ev.snapshots else None


def log_path(snap: dict) -> str | None:
    """The vault path of the configured log, whether given as a path or a [[link]]."""
    value = overlay_field(snap, "log")
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


def session_log_lines(ev: Evidence) -> tuple:
    """(log path, [lines each session added]) or (None, why) when it can't be read.
    Lines written before a session must survive it unchanged."""
    path = at_start(ev, log_path)
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


def g_quotes_verbatim(ev: Evidence) -> Result:
    """Every quote the companion attributes to a note, in any turn, is in that note."""
    found = [(t, q) for turn in ev.transcript if turn["role"] == "companion"
             for t, q in quotes(turn["text"])]
    bad = [why for t, q in found if (why := check_quote(t, q, ev.vault))]
    if bad:
        return Result("quotes_verbatim", False, "; ".join(bad))
    return Result("quotes_verbatim", True, f"{len(found)} linked quotes, all verbatim")


def touched(d: dict, allowed: tuple = ()) -> list:
    """Every changed path, marked +added ~modified -removed, except the allowed ones."""
    return ([f"+{p}" for p in d["added"] if p not in allowed]
            + [f"~{p}" for p in d["modified"] if p not in allowed]
            + [f"-{p}" for p in d["removed"] if p not in allowed])


def g_no_writes(ev: Evidence) -> Result:
    """The vault is byte-for-byte unchanged: no log, no picked write, no transcript."""
    changed = touched(ev.diff)
    if changed:
        return Result("no_writes", False, "vault changed: " + ", ".join(changed))
    return Result("no_writes", True, "vault unchanged")


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


GRADERS = {
    "orient_quotes_corpus": g_orient_quotes_corpus,
    "quotes_verbatim": g_quotes_verbatim,
    "no_writes": g_no_writes,
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
