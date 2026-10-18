"""What a session changed in a vault: snapshot before, snapshot after, diff.

`.claude/skills/` is where the harness installs the skill, not vault content,
so it is left out of every snapshot. The rest of `.claude/` is still watched.
"""

from __future__ import annotations

import difflib
from pathlib import Path

SKILL_INSTALL = (".claude", "skills")


def snapshot(vault: Path) -> dict:
    """{relative posix path: text} for every file in the vault."""
    return {p.relative_to(vault).as_posix(): p.read_text(errors="replace")
            for p in sorted(vault.rglob("*"))
            if p.is_file() and p.relative_to(vault).parts[:2] != SKILL_INSTALL}


def diff(before: dict, after: dict) -> dict:
    return {
        "added": {p: after[p] for p in after if p not in before},
        "removed": sorted(p for p in before if p not in after),
        "modified": {p: [before[p], after[p]] for p in after
                     if p in before and before[p] != after[p]},
    }


def render(d: dict) -> str:
    """The diff as unified-diff text, for a human reading results/."""
    chunks = []
    for path, text in d["added"].items():
        chunks += difflib.unified_diff([], text.splitlines(True), "/dev/null", f"b/{path}")
    for path in d["removed"]:
        chunks.append(f"--- a/{path}\n+++ /dev/null\n(removed)\n")
    for path, (old, new) in d["modified"].items():
        chunks += difflib.unified_diff(old.splitlines(True), new.splitlines(True),
                                       f"a/{path}", f"b/{path}")
    return "".join(chunks)
