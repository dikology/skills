#!/usr/bin/env python3
"""Run companion eval cases and print one pass/fail line per case.

A case is a Fixture vault, an optional Overlay and scripted human turns, in one
session (`turns`) or several (`sessions`). For each case the runner copies the
vault to a temp directory, appends the Overlay to its CLAUDE.md, installs the skill
under .claude/skills/companion unmodified (as a Consuming vault would), and plays
each session in headless `claude -p`, resuming it for each later turn and starting
fresh for the next session. It snapshots the vault after every turn, grades the
transcript and the vault diff, and keeps both under results/.

There are two arms: stable (skills/companion, what the plugin ships) and candidate
(labs/companion, what you edit). Scoring both on the same cases prints a per-case
difference; --promote then copies the candidate over stable, unless it lost a case.

    python3 labs/evals/run_evals.py                          # all cases, stable arm
    python3 labs/evals/run_evals.py --arm candidate          # iterate on the candidate
    python3 labs/evals/run_evals.py --arm both               # compare, case by case
    python3 labs/evals/run_evals.py --promote                # candidate -> stable, gated
    python3 labs/evals/run_evals.py --case orient            # cases whose id contains "orient"
    python3 labs/evals/run_evals.py --skill labs/evals/mutants/companion-paraphrase
    python3 labs/evals/run_evals.py --no-judge               # deterministic graders only

Exit status: 0 when every case passes, 1 when any fails (or promotion is refused),
2 on setup errors.
"""

from __future__ import annotations

import argparse
import hashlib
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
# Stable is what the plugin ships and changes only by promotion; Candidate is the
# working copy you edit. Both start byte-identical.
ARMS = {"stable": REPO / "skills" / "companion",
        "candidate": REPO / "labs" / "companion"}
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


# --- two arms -----------------------------------------------------------------

def compare(stable: list, candidate: list) -> list:
    """One row per case: both arms' results, the score difference (candidate minus
    stable) and whether the candidate lost it. A candidate loses a case it fails
    where stable passes, one it scores lower on, and one it didn't run."""
    s = {r["case"]: r for r in stable}
    c = {r["case"]: r for r in candidate}
    out = []
    for case in [*s, *(k for k in c if k not in s)]:
        a, b = s.get(case), c.get(case)
        if a and b:
            delta = round(b["score"] - a["score"], 4)
            lost = (a["passed"] and not b["passed"]) or delta < 0
        else:
            delta, lost = None, a is not None
        out.append({"case": case, "stable": a, "candidate": b,
                    "delta": delta, "lost": lost})
    return out


def tree_hash(folder: Path) -> str:
    """A digest of every file's path and bytes, so a run can show which copy of a
    skill it scored."""
    h = hashlib.sha256()
    for p in sorted(folder.rglob("*")):
        if p.is_file() and p.name != ".DS_Store":
            h.update(p.relative_to(folder).as_posix().encode() + b"\0")
            h.update(p.read_bytes() + b"\0")
    return h.hexdigest()


def promote(summary: dict, stable: Path, candidate: Path, case_ids: list) -> str | None:
    """Copy the candidate over stable, on the evidence of a saved two-arm run.
    Returns why it refused, or None once stable has been replaced."""
    arms = summary.get("arms") or {}
    if set(arms) != {"stable", "candidate"}:
        return "this run didn't score both arms; run with --arm both"
    if summary.get("case_filter"):
        return "this run was filtered by --case; run every case"
    if not summary.get("judge"):
        return "this run used --no-judge, so posture went ungraded"
    for name, folder in (("stable", stable), ("candidate", candidate)):
        if arms[name]["hash"] != tree_hash(folder):
            return f"{name} has changed since this run; run both arms again"
    if arms["stable"]["hash"] == arms["candidate"]["hash"]:
        return "the candidate is identical to stable; nothing to promote"
    for name, arm in arms.items():
        ran = {r["case"] for r in arm["cases"]}
        missing = [case for case in case_ids if case not in ran]
        if missing:
            return f"{name} didn't score {', '.join(missing)} in this run"
    lost = [c["case"] for c in compare(arms["stable"]["cases"], arms["candidate"]["cases"])
            if c["lost"]]
    if lost:
        return f"the candidate lost {', '.join(lost)}"
    # Copy beside stable first, so a failed copy leaves stable as it was.
    incoming = stable.with_name(stable.name + ".promoting")
    shutil.rmtree(incoming, ignore_errors=True)
    shutil.copytree(candidate, incoming)
    shutil.rmtree(stable)
    incoming.rename(stable)
    return None


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


def comparison_table(rows: list) -> str:
    """Both arms side by side, one line per case, and a verdict on promotion."""
    def cell(r):
        return f"{'PASS' if r['passed'] else 'FAIL'} {r['score']:.2f}" if r else "not run"
    lines = [f"{'case':<30}{'stable':<12}{'candidate':<12}delta"]
    for c in rows:
        delta = "" if c["delta"] is None else f"{c['delta']:+.2f}"
        lines.append(f"{c['case']:<30}{cell(c['stable']):<12}{cell(c['candidate']):<12}"
                     f"{delta:<7}{'  LOST' if c['lost'] else ''}".rstrip())
    lost = [c["case"] for c in rows if c["lost"]]
    lines.append(f"\ncandidate lost {len(lost)}: {', '.join(lost)}; do not promote" if lost
                 else "\ncandidate lost no case")
    return "\n".join(lines)


def latest_run() -> Path | None:
    """The newest saved run that scored both arms, so a quick one-arm run made
    after it doesn't hide it."""
    runs = []
    for summary in RESULTS.glob("*/summary.json"):
        try:
            arms = json.loads(summary.read_text()).get("arms") or {}
        except (OSError, json.JSONDecodeError):
            continue
        if set(arms) == {"stable", "candidate"}:
            runs.append(summary)
    return max(runs, key=lambda s: s.stat().st_mtime).parent if runs else None


def run_promote(run: Path | None, cases: list) -> int:
    run = run or latest_run()
    if not run or not (run / "summary.json").exists():
        print("error: no saved two-arm run to promote from; run --arm both",
              file=sys.stderr)
        return 2
    summary = json.loads((run / "summary.json").read_text())
    problem = promote(summary, ARMS["stable"], ARMS["candidate"], [c["id"] for c in cases])
    if problem:
        print(f"not promoted ({run.name}): {problem}", file=sys.stderr)
        return 1
    print(f"promoted {ARMS['candidate'].relative_to(REPO)} -> "
          f"{ARMS['stable'].relative_to(REPO)} on the evidence of {run.name}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--case", help="run only cases whose id contains this")
    ap.add_argument("--arm", choices=["stable", "candidate", "both"],
                    help="which copy of companion to score (default: stable)")
    ap.add_argument("--skill", help="score this skill folder instead of an arm, e.g. a mutant")
    ap.add_argument("--promote", nargs="?", const="", metavar="RUN",
                    help="copy the candidate over stable on the evidence of a saved "
                         "two-arm run (default: the latest under results/), then exit")
    ap.add_argument("--model", help="model for the session under test")
    ap.add_argument("--judge-model", default="claude-sonnet-5-5")
    ap.add_argument("--no-judge", dest="judge", action="store_false", default=True)
    ap.add_argument("--timeout", type=int, default=600, help="seconds per turn")
    ap.add_argument("--output-dir", help="default: labs/evals/results/<timestamp>")
    args = ap.parse_args()

    all_cases = json.loads((HERE / "cases.json").read_text())["cases"]
    if args.promote is not None:
        return run_promote(Path(args.promote) if args.promote else None, all_cases)

    if args.skill and args.arm:
        print("error: --skill and --arm are alternatives", file=sys.stderr)
        return 2
    if args.skill:
        skill = Path(args.skill).resolve()
        arms = {skill.name: skill}
    else:
        names = ["stable", "candidate"] if args.arm == "both" else [args.arm or "stable"]
        arms = {n: ARMS[n] for n in names}
    for name, skill in arms.items():
        if not (skill / "SKILL.md").exists():
            print(f"error: no SKILL.md for {name} in {skill}", file=sys.stderr)
            return 2
    if not shutil.which("claude"):
        print("error: `claude` not on PATH", file=sys.stderr)
        return 2

    cases = [c for c in all_cases if args.case in c["id"]] if args.case else all_cases
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

    summary = {"arms": {}, "case_filter": args.case, "judge": args.judge}
    with tempfile.TemporaryDirectory(prefix="companion-evals-") as tmpdir:
        for name, skill in arms.items():
            where = skill.relative_to(REPO) if skill.is_relative_to(REPO) else skill
            print(f"\n{name}: {where}")
            # Hashed before the run, so an edit made while it runs reads as a change.
            entry = {"skill": str(skill), "hash": tree_hash(skill), "cases": []}
            for case in cases:
                row = run_case(case, skill, args, Path(tmpdir) / name, outdir / name)
                print(report_line(row), flush=True)
                entry["cases"].append(row)
            summary["arms"][name] = entry

    (outdir / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False))
    rows = [r for a in summary["arms"].values() for r in a["cases"]]
    failed = sum(not r["passed"] for r in rows)
    if set(arms) == {"stable", "candidate"}:
        print("\n" + comparison_table(compare(summary["arms"]["stable"]["cases"],
                                              summary["arms"]["candidate"]["cases"])))
    print(f"\n{len(rows) - failed}/{len(rows)} passed, "
          f"${sum(r['cost_usd'] for r in rows):.2f}. results: {outdir}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
