#!/usr/bin/env python3
"""Run companion eval cases and print one pass/fail line per case.

A case is a Fixture vault, an optional Overlay and scripted human turns, in one
session (`turns`) or several (`sessions`). For each case the runner copies the
vault to a temp directory, appends the Overlay to its CLAUDE.md, installs the skill
under .claude/skills/companion unmodified (as a Consuming vault would), and plays
each session in headless `claude -p`, resuming it for each later turn and starting
fresh for the next session. It snapshots the vault after every turn, grades the
transcript and the vault diff, and keeps both under results/.

    python3 labs/evals/run_evals.py                          # all cases, stable skill
    python3 labs/evals/run_evals.py --case orient            # cases whose id contains "orient"
    python3 labs/evals/run_evals.py --skill labs/evals/mutants/companion-paraphrase
    python3 labs/evals/run_evals.py --no-judge               # deterministic graders only

Exit status: 0 when every case passes, 1 when any fails, 2 on setup errors.
"""

from __future__ import annotations

import argparse
import inspect
import json
import re
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import graders  # noqa: E402
import vaultdiff  # noqa: E402

HERE = Path(__file__).parent
REPO = HERE.parent.parent
STABLE = REPO / "skills" / "companion"
VAULTS = HERE / "fixtures" / "vaults"
RESULTS = HERE / "results"

# Settings come from the temp vault only (no user hooks or plugins), and no MCP
# servers are loaded, so the session sees the vault and the skill and little else.
ISOLATION = ["--strict-mcp-config", "--setting-sources", "project,local"]
SESSION_FLAGS = ["--permission-mode", "bypassPermissions", *ISOLATION]


# --- the temp Consuming vault -------------------------------------------------

def build_vault(root: Path, case: dict, skill: Path) -> Path:
    ws = root / case["id"]
    shutil.copytree(VAULTS / case["vault"], ws)
    if case.get("overlay"):
        md = ws / "CLAUDE.md"
        existing = md.read_text() if md.exists() else ""
        md.write_text(existing.rstrip() + "\n\n" + case["overlay"].strip() + "\n")
    shutil.copytree(skill, ws / ".claude" / "skills" / "companion")
    return ws


def case_sessions(case: dict) -> list:
    """The human turns, one list per session."""
    return case.get("sessions") or [case["turns"]]


def play(ws: Path, sessions: list, model: str | None, timeout: int) -> dict:
    """Play each session's human turns, snapshotting the vault before the first turn
    and after each one. Stops at the first failed turn."""
    transcript, cost, error, ids = [], 0.0, None, []
    snapshots = [vaultdiff.snapshot(ws)]
    started = time.time()
    turns = [(n, text) for n, texts in enumerate(sessions) for text in texts]
    session, current = None, 0
    for n, text in turns:
        if n != current:
            session, current = None, n
        transcript.append({"role": "human", "text": text, "session": n})
        cmd = ["claude", "-p", text, "--output-format", "json", *SESSION_FLAGS]
        if session:
            cmd += ["--resume", session]
        if model:
            cmd += ["--model", model]
        try:
            proc = subprocess.run(cmd, cwd=ws, capture_output=True, text=True,
                                  timeout=timeout)
        except subprocess.TimeoutExpired:
            error = f"turn {len(snapshots)} timed out after {timeout}s"
            break
        try:
            payload = json.loads(proc.stdout)
        except json.JSONDecodeError:
            error = (proc.stderr or proc.stdout)[-2000:] or "no output"
            break
        if proc.returncode != 0 or payload.get("is_error"):
            error = payload.get("result") or proc.stderr[-2000:] or "non-zero exit"
            break
        session = payload.get("session_id", session)
        if not ids or ids[-1] != session:
            ids.append(session)
        cost += payload.get("total_cost_usd") or 0.0
        transcript.append({"role": "companion", "text": payload.get("result", ""),
                           "session": n})
        snapshots.append(vaultdiff.snapshot(ws))
    return {"transcript": transcript, "session_ids": ids, "error": error,
            "snapshots": snapshots, "cost_usd": round(cost, 4),
            "seconds": round(time.time() - started, 1)}


# --- LLM judge ----------------------------------------------------------------

def judge_spec(case: dict):
    """(rubric path, pass mark) for a case's judge, or None when it has none.
    `"judge": true` is the default rubric, reported only. `{"rubric": "<name>",
    "pass_at": <1-5>}` reads judge-<name>.md, and a pass mark makes the score decide."""
    j = case.get("judge")
    if not j:
        return None
    if j is True:
        return HERE / "judge-rubric.md", None
    return HERE / f"judge-{j.get('rubric', '')}.md", j.get("pass_at")


def apply_judge(scored: dict, verdict: dict, pass_at) -> dict:
    """Record the judge's verdict. With a pass mark, a lower score or a broken judge
    fails the case; without one, the score is reported and never changes the verdict."""
    scored["judge"] = verdict
    if pass_at is not None and ("score" not in verdict or verdict["score"] < pass_at):
        scored["passed"] = False
        scored["hard_fail"].append("judge")
    return scored


def judge(transcript: list, rubric: Path, model: str, timeout: int) -> dict:
    """The part a regex can't decide, such as whether a reply takes a position. On
    failure returns {"error": ...} so a broken judge shows up in the report."""
    prompt = (f"{rubric.read_text()}\n\n---\n\nThe transcript under review:\n\n"
              f"{render_transcript(transcript)}\n\nReturn ONLY a JSON object.")
    try:
        proc = subprocess.run(
            ["claude", "-p", prompt, "--output-format", "json", "--model", model,
             *ISOLATION, "--disallowedTools", "Bash", "Read", "Write", "Edit", "Glob", "Grep"],
            capture_output=True, text=True, timeout=timeout, cwd=tempfile.gettempdir())
        text = json.loads(proc.stdout).get("result", "")
        m = re.search(r"\{.*\}", text, re.S)
        return json.loads(m.group(0)) if m else {"error": f"no JSON in reply: {text[:200]}"}
    except subprocess.TimeoutExpired:
        return {"error": f"timed out after {timeout}s"}
    except json.JSONDecodeError:
        return {"error": (proc.stderr or proc.stdout)[-200:] or "no output"}


# --- results ------------------------------------------------------------------

def render_transcript(transcript: list) -> str:
    out, current = [], None
    for t in transcript:
        if t.get("session", 0) != current:
            current = t.get("session", 0)
            out.append(f"# session {current + 1}")
        out.append(f"## {t['role']}\n\n{t['text']}")
    return "\n\n".join(out) + "\n"


def keep(outdir: Path, case: dict, session: dict, d: dict, scored: dict) -> None:
    out = outdir / case["id"]
    out.mkdir(parents=True, exist_ok=True)
    (out / "transcript.json").write_text(
        json.dumps(session["transcript"], indent=2, ensure_ascii=False))
    (out / "transcript.md").write_text(render_transcript(session["transcript"]))
    (out / "vault.diff").write_text(vaultdiff.render(d))
    (out / "grade.json").write_text(json.dumps(
        {**scored, "error": session["error"], "session_ids": session["session_ids"],
         "cost_usd": session["cost_usd"], "seconds": session["seconds"]},
        indent=2, ensure_ascii=False))


def run_case(case: dict, skill: Path, args, tmp: Path, outdir: Path) -> dict:
    ws = build_vault(tmp, case, skill)
    session = play(ws, case_sessions(case), args.model, args.timeout)
    snaps = session["snapshots"]
    d = vaultdiff.diff(snaps[0], snaps[-1])
    ev = graders.Evidence(transcript=session["transcript"], diff=d,
                          vault=VAULTS / case["vault"], snapshots=snaps)
    scored = graders.grade(case["graders"], ev)
    if session["error"]:
        scored["passed"] = False
        scored["hard_fail"].insert(0, "session")
    spec = judge_spec(case)
    if spec and not args.judge and spec[1] is not None:
        # Reported, not failed: --no-judge is a choice to leave posture ungraded.
        scored["judge"] = {"error": "skipped by --no-judge; posture not graded"}
    elif args.judge and spec and not session["error"]:
        rubric, pass_at = spec
        apply_judge(scored, judge(session["transcript"], rubric, args.judge_model,
                                  args.timeout), pass_at)
    keep(outdir, case, session, d, scored)
    return {"case": case["id"], **scored, "error": session["error"],
            "cost_usd": session["cost_usd"], "seconds": session["seconds"]}


def report_line(row: dict) -> str:
    verdict = "PASS" if row["passed"] else "FAIL"
    j = row.get("judge") or {}
    judged = (f"  judge {j['score']}/5" if "score" in j else
              f"  judge error: {j['error'][:80]}" if "error" in j else "")
    line = (f"{verdict}  {row['case']:<28} score {row['score']:.2f}{judged}"
            f"  ${row['cost_usd']:.2f}  {row['seconds']}s")
    if row["error"]:
        line += f"\n      session: {row['error'][:200]}"
    for r in row["results"]:
        if not r["passed"]:
            line += f"\n      {r['name']}: {r['note'][:200]}"
    return line


def check_case(case: dict) -> str | None:
    """Why a case can't run, or None. Catches a typo before any API call is made."""
    if not (VAULTS / case["vault"]).is_dir():
        return f"no Fixture vault {case['vault']!r}"
    if not all(case_sessions(case)):
        return "a session with no turns"
    for entry in case["graders"]:
        name, params = graders.spec(entry)
        if name not in graders.GRADERS:
            return f"unknown grader {name!r}"
        try:
            inspect.signature(graders.GRADERS[name]).bind(None, **params)
        except TypeError as e:
            return f"grader {name}: {e}"
    spec = judge_spec(case)
    if spec and not spec[0].exists():
        return f"no judge rubric {spec[0].name}"
    if spec and spec[1] is not None and spec[1] not in range(1, 6):
        return f"judge pass_at must be 1-5, not {spec[1]!r}"
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--case", help="run only cases whose id contains this")
    ap.add_argument("--skill", default=str(STABLE),
                    help="skill folder to install (default: the stable skills/companion)")
    ap.add_argument("--model", help="model for the session under test")
    ap.add_argument("--judge-model", default="claude-sonnet-5-5")
    ap.add_argument("--no-judge", dest="judge", action="store_false", default=True)
    ap.add_argument("--timeout", type=int, default=600, help="seconds per turn")
    ap.add_argument("--output-dir", help="default: labs/evals/results/<timestamp>")
    args = ap.parse_args()

    skill = Path(args.skill).resolve()
    if not (skill / "SKILL.md").exists():
        print(f"error: no SKILL.md in {skill}", file=sys.stderr)
        return 2
    if not shutil.which("claude"):
        print("error: `claude` not on PATH", file=sys.stderr)
        return 2

    cases = json.loads((HERE / "cases.json").read_text())["cases"]
    if args.case:
        cases = [c for c in cases if args.case in c["id"]]
    if not cases:
        print("no cases matched", file=sys.stderr)
        return 2
    for c in cases:
        problem = check_case(c)
        if problem:
            print(f"error: case {c['id']}: {problem}", file=sys.stderr)
            return 2

    outdir = (Path(args.output_dir) if args.output_dir
              else RESULTS / datetime.now().strftime("%Y-%m-%d_%H%M%S"))
    outdir.mkdir(parents=True, exist_ok=True)
    print(f"skill: {skill.relative_to(REPO) if skill.is_relative_to(REPO) else skill}")

    rows = []
    with tempfile.TemporaryDirectory(prefix="companion-evals-") as tmpdir:
        for case in cases:
            row = run_case(case, skill, args, Path(tmpdir), outdir)
            print(report_line(row), flush=True)
            rows.append(row)

    (outdir / "summary.json").write_text(json.dumps(
        {"skill": str(skill), "cases": rows}, indent=2, ensure_ascii=False))
    failed = sum(not r["passed"] for r in rows)
    print(f"\n{len(rows) - failed}/{len(rows)} passed, "
          f"${sum(r['cost_usd'] for r in rows):.2f}. results: {outdir}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
