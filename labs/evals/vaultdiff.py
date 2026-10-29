"""What a session changed in a vault: snapshot before, snapshot after, diff.

Two folders the runtime makes inside the vault are not vault content and are left
out of every snapshot: `.qwen/skills/`, where the harness installs the skill, and
`.qwen/tmp/`, where qwen writes the human turn's own text — so a session that wrote
nothing at all still shows a new file, and a grader watching writes would blame the
session for it. The rest of `.qwen/` is still watched.
"""

from __future__ import annotations

import difflib
from pathlib import Path

RUNTIME_PATHS = ((".qwen", "skills"), (".qwen", "tmp"))


def snapshot(vault: Path) -> dict:
    """{relative posix path: text} for every file in the vault but the runtime's own."""
    return {p.relative_to(vault).as_posix(): p.read_text(errors="replace")
            for p in sorted(vault.rglob("*"))
            if p.is_file() and p.relative_to(vault).parts[:2] not in RUNTIME_PATHS}


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
