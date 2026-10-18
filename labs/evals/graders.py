"""Graders for companion eval cases.

A grader sees what a user would see or find: the session transcript and the
vault diff, plus the Fixture vault to check quotes against. It never reads the
skill's prompt text, and it never asserts wording or section order.

Each grader returns a Result. A case passes when every hard grader passes; the
score is the weighted share of graders passed, reported alongside.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Evidence:
    transcript: list   # [{"role": "human" | "companion", "text": str}, ...]
    diff: dict         # vaultdiff.diff() output
    vault: Path        # the pristine Fixture vault, for resolving links and quotes


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


def quotes(text: str) -> list:
    """(link target, quoted text) pairs, in order of appearance."""
    out = []
    for m in QUOTE_RE.finditer(text):
        target, quote = (m.group(1), m.group(2)) if m.group(1) else (m.group(4), m.group(3))
        out.append((target.strip(), quote))
    return out


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
    path = notes(vault).get(target.lower().split("/")[-1])
    if path is None:
        return f"[[{target}]] does not resolve"
    if not verbatim(quote, path.read_text()):
        return f"not verbatim in [[{target}]]: \"{quote}\""
    return None


def first_reply(ev: Evidence) -> str:
    return next((t["text"] for t in ev.transcript if t["role"] == "companion"), "")


# --- graders -----------------------------------------------------------------

def g_orient_quotes_corpus(ev: Evidence) -> Result:
    """Orient quotes at least one real note verbatim, wrapped in a link that resolves."""
    found = quotes(first_reply(ev))
    good = [(t, q) for t, q in found if len(q.split()) >= MIN_QUOTE_WORDS
            and check_quote(t, q, ev.vault) is None]
    if good:
        return Result("orient_quotes_corpus", True,
                      f"{len(good)}/{len(found)} quotes verified, e.g. [[{good[0][0]}]]")
    return Result("orient_quotes_corpus", False,
                  f"no verified quote among {len(found)} linked quotes in the first reply")


def g_quotes_verbatim(ev: Evidence) -> Result:
    """Every quote the companion attributes to a note, in any turn, is in that note."""
    found = [(t, q) for turn in ev.transcript if turn["role"] == "companion"
             for t, q in quotes(turn["text"])]
    bad = [why for t, q in found if (why := check_quote(t, q, ev.vault))]
    if bad:
        return Result("quotes_verbatim", False, "; ".join(bad))
    return Result("quotes_verbatim", True, f"{len(found)} linked quotes, all verbatim")


def g_no_writes(ev: Evidence) -> Result:
    """The vault is byte-for-byte unchanged: no log, no picked write, no transcript."""
    d = ev.diff
    touched = ([f"+{p}" for p in d["added"]] + [f"~{p}" for p in d["modified"]]
               + [f"-{p}" for p in d["removed"]])
    if touched:
        return Result("no_writes", False, "vault changed: " + ", ".join(touched))
    return Result("no_writes", True, "vault unchanged")


GRADERS = {
    "orient_quotes_corpus": g_orient_quotes_corpus,
    "quotes_verbatim": g_quotes_verbatim,
    "no_writes": g_no_writes,
}


def grade(names: list, ev: Evidence) -> dict:
    results = [GRADERS[n](ev) for n in names]
    total = sum(r.weight for r in results) or 1.0
    return {
        "passed": all(r.passed for r in results if r.hard),
        "score": round(sum(r.weight for r in results if r.passed) / total, 3),
        "hard_fail": [r.name for r in results if r.hard and not r.passed],
        "results": [r.as_dict() for r in results],
    }
