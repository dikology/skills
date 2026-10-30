#!/usr/bin/env python3
"""Run a Library skill's eval cases and print one pass/fail line per case.

The skill is named on the command line (default: companion). Its cases are
cases/<skill>.json. A case is a Fixture vault, an optional Overlay and scripted
human turns, in one session (`turns`) or several (`sessions`). For each case the
runner copies the vault to a temp directory, appends the Overlay to its CLAUDE.md,
installs the skill under .qwen/skills/<skill> unmodified (as a Consuming vault
would), and plays each session in headless `qwen`, resuming it for each later
turn and starting fresh for the next session. It snapshots the vault after every
turn, grades the transcript and the vault diff, and keeps both under results/.

Every turn runs against a qwen home of the run's own, seeded with nothing but how
to reach a model, so user settings, hooks, extensions, user skills and MCP servers
stay out. A turn that loaded an MCP server, or never invoked the skill at all, is
reported and fails: neither is a test of the skill, whatever the reply looks like.

Each skill has two arms: stable (skills/<skill>, what the plugin ships) and
candidate (labs/<skill>, what you edit). Scoring both on the same cases prints a
per-case difference; --promote then copies that skill's candidate over its stable,
unless it lost a case.

    python3 labs/evals/run_evals.py                          # companion, all cases, stable arm
    python3 labs/evals/run_evals.py improve                  # another skill, by name
    python3 labs/evals/run_evals.py --arm candidate          # iterate on the candidate
    python3 labs/evals/run_evals.py --arm both               # compare, case by case
    python3 labs/evals/run_evals.py --promote                # candidate -> stable, gated
    python3 labs/evals/run_evals.py improve --promote        # the same, for improve
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
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import Callable

sys.path.insert(0, str(Path(__file__).parent))
import graders  # noqa: E402
import vaultdiff  # noqa: E402

HERE = Path(__file__).parent
REPO = HERE.parent.parent
DEFAULT_SKILL = "companion"
VAULTS = HERE / "fixtures" / "vaults"
CASES = HERE / "cases"
RESULTS = HERE / "results"

# What the adapter records when the child produced neither stdout nor stderr: the turn
# never reached a model, so nothing about the skill was tested. `transport_flake` keys on
# this string, so it lives here once rather than at each exit path.
NO_OUTPUT = "no output"

# --- the process adapter -------------------------------------------------------
# One place holds the agent binary and every flag this harness passes it. Moving the
# harness to another CLI means changing this section, `read_turn` below, and
# SKILL_FOLDER; nothing else in the file names an agent.
BINARY = "qwen"

# Where a Consuming vault installs a skill so the agent finds it. The folder the
# plugin ships into is not the folder qwen discovers: install it in the wrong place
# and every case runs with no skill, the model improvising from the prompt, which
# reads as a green run that proves nothing. `check_run` is the guard.
SKILL_FOLDER = ".qwen"

OUTPUT = ["-o", "json"]

# No MCP server is loaded, whatever the developer running the eval has configured.
NO_MCP = ["--mcp-config", json.dumps({"mcpServers": {}})]

# History has to be on disk: `-r` resumes the session recorded there, so without it
# every turn after the first starts a stranger who has never seen the vault.
RECORD = ["--chat-recording"]

# The tools a judge must not hold. qwen has no `--disallowedTools`, so the denial is
# these two flags together: the mode says the session is read-only, the exclusion takes
# the tools out of its registry — writers, readers and shells alike, because the judge
# decides from the transcript in its prompt. `agent`, `tool_call` and the worktree tools
# go too: delegating a write, discovering a hidden tool or making a new checkout are all
# still ways of not staying inside the transcript.
DENIED_TOOLS = ",".join(["write_file", "edit", "notebook_edit", "run_shell_command",
                         "read_file", "glob", "grep_search", "monitor",
                         "enter_worktree", "exit_worktree",
                         "artifact", "record_artifact", "agent", "tool_call"])


def session_argv(prompt: str, resume: str | None = None,
                 model: str | None = None) -> list:
    """One human turn against a temp Consuming vault. yolo, because no one is
    watching the process to answer a permission prompt, and a turn that cannot
    write the vault cannot be graded on its diff."""
    argv = [BINARY, prompt, *OUTPUT, *RECORD, "--approval-mode", "yolo", *NO_MCP]
    if resume:
        argv += ["-r", resume]
    if model:
        argv += ["-m", model]
    return argv


def judge_argv(prompt: str, model: str | None = None) -> list:
    """The rubric and the transcript, in a directory that is nobody's vault, read-only:
    a judge that can edit the thing it is grading grades its own work."""
    argv = [BINARY, prompt, *OUTPUT, "--approval-mode", "plan",
            "--exclude-tools", DENIED_TOOLS, *NO_MCP]
    if model:
        argv += ["-m", model]
    return argv


def agent_env(home: Path) -> dict:
    """The child's environment: the global config dir moved to `home`, so user
    settings, hooks, extensions, user skills and MCP servers stay out of every turn."""
    return {**os.environ, "QWEN_HOME": str(home), "QWEN_CODE_SUPPRESS_YOLO_WARNING": "1"}

# An isolated home still has to reach a model, which it does with the login the
# developer already has. Everything else a qwen home holds — MCP servers, hooks,
# extensions, the user's own skills, display settings — is what a case must not be
# run against, because the case is testing a bare Consuming vault.
SEED_KEYS = ("$version", "env", "security", "model", "modelProviders", "providerMetadata")

# Auto-memory is on by default in a qwen home. Left on, a turn spends itself writing
# memories about the case instead of running it, and one case remembers its way into the
# next — so a run's home always turns it off, whatever the developer keeps set.
MEMORY_OFF = {"memory": {"enableManagedAutoMemory": False, "enableManagedAutoDream": False}}

# A login sometimes sits beside settings.json instead of inside it. These are qwen's own
# credential files; an isolated home without them can reach no model at all.
CREDENTIAL_FILES = ("oauth_creds.json", "credentials.json")


def seed_settings(real: dict) -> dict:
    """The settings.json a run's home is written with: how to reach a model, no memory,
    nothing else."""
    return {k: real[k] for k in SEED_KEYS if k in real} | MEMORY_OFF


def real_home() -> Path:
    """The developer's own qwen home, where a login lives."""
    return Path(os.environ.get("QWEN_HOME") or Path.home() / ".qwen")


def make_isolated_home(root: Path, from_home: Path) -> Path:
    """A qwen home for this one run, under `root`, seeded from `from_home`'s login.

    One home for the whole run, not one per turn: sessions are recorded inside it, and
    a resume on turn two reads the history turn one left there."""
    home = root / "agent-home"
    home.mkdir(parents=True, exist_ok=True)
    settings = from_home / "settings.json"
    seed = seed_settings(json.loads(settings.read_text())) if settings.exists() else seed_settings({})
    (home / "settings.json").write_text(json.dumps(seed))
    for name in CREDENTIAL_FILES:
        if (from_home / name).exists():
            shutil.copyfile(from_home / name, home / name)
    return home


def login_found(from_home: Path, env: dict) -> bool:
    """Whether there is anything to seed a run with: a settings block that says how to
    authenticate, one of qwen's credential files, or a key in the environment. A run
    without it would spend a turn on every case learning the same thing."""
    if env.get("OPENAI_API_KEY"):
        return True
    if any((from_home / name).exists() for name in CREDENTIAL_FILES):
        return True
    settings = from_home / "settings.json"
    if not settings.exists():
        return False
    seeded = seed_settings(json.loads(settings.read_text()))
    return bool(seeded.get("security") or seeded.get("env"))


def read_turn(stdout: str) -> dict:
    """One headless run's output, read as the harness uses it.

    `qwen -o json` prints an array of events, not one object: the last is the turn's
    result (reply, session id, whether it failed, tokens — qwen reports no price), and
    the init event says what the session was handed. Both are needed to tell a passing
    case from a run that quietly did nothing, which is what a green eval most often is.

    `init_reported` separates "the session loaded no MCP server" from "the run never
    said what it loaded", which an empty list alone cannot tell apart."""
    events = json.loads(stdout)
    if not isinstance(events, list):
        raise ValueError("qwen printed no event array")
    result = next((e for e in reversed(events)
                   if isinstance(e, dict) and e.get("type") == "result"), None)
    if result is None:
        raise ValueError("qwen printed no result event")
    init = next((e for e in events
                 if isinstance(e, dict) and e.get("type") == "system"), None)
    usage = result.get("usage") or {}
    by_name = ((result.get("stats") or {}).get("skills") or {}).get("byName") or {}
    text = result.get("result") or ""
    is_error = bool(result.get("is_error"))
    reason = ""
    if is_error:
        err = result.get("error")
        reason = ((err.get("message") if isinstance(err, dict) else str(err or ""))
                  or text or "the run gave no reason")
    return {"text": text, "session_id": result.get("session_id"), "is_error": is_error,
            "error": reason,
            "tokens": (usage.get("input_tokens") or 0) + (usage.get("output_tokens") or 0),
            "skills": sorted(by_name),
            "init_reported": init is not None,
            "mcp_servers": (init or {}).get("mcp_servers") or []}


# --- a skill by name ----------------------------------------------------------

def arms_for(name: str) -> dict:
    """Both copies of a Library skill. Stable is what the plugin ships and changes
    only by promotion; Candidate is the working copy you edit."""
    return {"stable": REPO / "skills" / name, "candidate": REPO / "labs" / name}


def load_cases(name: str, folder: Path = CASES) -> list:
    """The skill's own case set, cases/<name>.json. Raises ValueError when there is
    none, or when the file says it belongs to another skill."""
    path = folder / f"{name}.json"
    if not path.exists():
        raise ValueError(f"no case set for skill {name!r} at {path}")
    data = json.loads(path.read_text())
    if data.get("skill_name", name) != name:
        raise ValueError(f"{path.name} holds cases for {data['skill_name']!r}, not {name!r}")
    return data["cases"]


# --- the temp Consuming vault -------------------------------------------------

def build_vault(root: Path, case: dict, skill: Path, name: str) -> Path:
    """A temp Consuming vault: the case's Fixture vault, its Overlay, and the skill
    folder installed unmodified as SKILL_FOLDER/skills/<name>, whatever the folder is
    called."""
    ws = root / case["id"]
    shutil.copytree(VAULTS / case["vault"], ws)
    if case.get("overlay"):
        md = ws / "CLAUDE.md"
        existing = md.read_text() if md.exists() else ""
        md.write_text(existing.rstrip() + "\n\n" + case["overlay"].strip() + "\n")
    shutil.copytree(skill, ws / SKILL_FOLDER / "skills" / name)
    return ws


def check_run(name: str, session: dict):
    """Why a session that ran without error is still no evidence about the skill, or None.

    All three ways this goes wrong are invisible in a transcript. A skill nothing looked
    for leaves a model that improvises from the prompt and answers much like the skill; a
    session that loaded the developer's MCP servers was never the bare Consuming vault the
    case describes; and a run that reported no init event proved neither of those things,
    so it cannot claim them. The skill is looked for across the whole run rather than turn
    by turn: turn 1 invokes it, and "1, 2" or "yes, write it" are follow-ups in the same
    session that need not invoke it again."""
    if not session["init_reported"]:
        return ("a turn printed no init event, so nothing shows what the session was "
                "given — isolation not proven")
    if session["mcp_servers"]:
        return (f"a session loaded an MCP server ({session['mcp_servers']}) — this run is "
                f"not the isolated vault the case describes")
    if name not in session["skills_invoked"]:
        return (f"skill {name!r} was never invoked (the session ran: "
                f"{', '.join(session['skills_invoked']) or 'no skill'}) — its replies came "
                f"from the prompt, not the skill")
    return None


def case_sessions(case: dict) -> list:
    """The human turns, one list per session."""
    return case.get("sessions") or [case["turns"]]


def play(ws: Path, sessions: list, model: str | None, timeout: int, env: dict) -> dict:
    """Play each session's human turns, snapshotting the vault before the first turn
    and after each one. Stops at the first failed turn.

    The first turn of a session starts fresh, every later one resumes the session id the
    agent reported. A resume that quietly did not happen is a failure, not a smaller
    success: the turn would be answering with no memory of the one before, and a case
    that grades only replies and files would never notice."""
    transcript, error, ids = [], None, []
    tokens, skills, mcp, no_init = 0, [], [], False
    snapshots = [vaultdiff.snapshot(ws)]
    started = time.time()
    turns = [(n, text) for n, texts in enumerate(sessions) for text in texts]
    session, current = None, 0
    for n, text in turns:
        if n != current:
            session, current = None, n
        transcript.append({"role": "human", "text": text, "session": n})
        resumed = session
        try:
            proc = subprocess.run(session_argv(text, resume=resumed, model=model),
                                  cwd=ws, capture_output=True, text=True,
                                  timeout=timeout, env=env)
        except subprocess.TimeoutExpired:
            error = f"turn {len(snapshots)} timed out after {timeout}s"
            break
        try:
            turn = read_turn(proc.stdout)
        except ValueError:
            error = (proc.stderr or proc.stdout)[-2000:] or NO_OUTPUT
            break
        if proc.returncode != 0 or turn["is_error"]:
            error = turn["error"] or (proc.stderr or "")[-2000:] or "non-zero exit"
            break
        if resumed and turn["session_id"] != resumed:
            error = (f"turn {len(snapshots)} did not resume {resumed}: qwen answered as "
                     f"{turn['session_id']}")
            break
        no_init = no_init or not turn["init_reported"]
        session = turn["session_id"] or session
        if not ids or ids[-1] != session:
            ids.append(session)
        tokens += turn["tokens"]
        skills += turn["skills"]
        mcp = mcp or turn["mcp_servers"]
        transcript.append({"role": "companion", "text": turn["text"], "session": n})
        snapshots.append(vaultdiff.snapshot(ws))
    return {"transcript": transcript, "session_ids": ids, "error": error,
            "snapshots": snapshots, "tokens": tokens, "seconds": round(time.time() - started, 1),
            "skills_invoked": sorted(set(skills)), "mcp_servers": mcp,
            "init_reported": not no_init}


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


def judge(transcript: list, rubric: Path, model: str | None, timeout: int, env: dict) -> dict:
    """The part a regex can't decide, such as whether a reply takes a position. On
    failure returns {"error": ...} so a broken judge shows up in the report.

    The transcript arrives in the prompt, so the judge needs no tools: `judge_argv`
    runs it read-only, and a judge that could edit the vault would grade its own work."""
    prompt = (f"{rubric.read_text()}\n\n---\n\nThe transcript under review:\n\n"
              f"{render_transcript(transcript)}\n\nReturn ONLY a JSON object.")
    try:
        proc = subprocess.run(judge_argv(prompt, model), capture_output=True, text=True,
                              timeout=timeout, cwd=tempfile.gettempdir(), env=env)
        turn = read_turn(proc.stdout)
        if proc.returncode != 0 or turn["is_error"]:
            return {"error": turn["error"] or "non-zero exit"}
        text = turn["text"]
        m = re.search(r"\{.*\}", text, re.S)
        return json.loads(m.group(0)) if m else {"error": f"no JSON in reply: {text[:200]}"}
    except subprocess.TimeoutExpired:
        return {"error": f"timed out after {timeout}s"}
    except ValueError:
        return {"error": (proc.stderr or proc.stdout)[-200:] or NO_OUTPUT}


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
         "tokens": session["tokens"], "seconds": session["seconds"],
         "skills_invoked": session["skills_invoked"], "mcp_servers": session["mcp_servers"]},
        indent=2, ensure_ascii=False))


def run_case(case: dict, skill: Path, args, tmp: Path, outdir: Path, env: dict) -> dict:
    ws = build_vault(tmp, case, skill, args.name)
    session = play(ws, case_sessions(case), args.model, args.timeout, env)
    snaps = session["snapshots"]
    d = vaultdiff.diff(snaps[0], snaps[-1])
    ev = graders.Evidence(transcript=session["transcript"], diff=d,
                          vault=VAULTS / case["vault"], snapshots=snaps)
    scored = graders.grade(case["graders"], ev)
    if session["error"]:
        scored["passed"] = False
        scored["hard_fail"].insert(0, "session")
    else:
        # A session can satisfy every grader while having tested the prompt rather than
        # the skill. Nothing in the transcript tells you, so the run says what it ran.
        problem = check_run(args.name, session)
        if problem:
            session["error"] = problem
            scored["passed"] = False
            scored["hard_fail"].insert(0, "integrity")
    spec = judge_spec(case)
    if spec and not args.judge and spec[1] is not None:
        # Reported, not failed: --no-judge is a choice to leave posture ungraded.
        scored["judge"] = {"error": "skipped by --no-judge; posture not graded"}
    elif args.judge and spec and not session["error"]:
        rubric, pass_at = spec
        apply_judge(scored, judge(session["transcript"], rubric, args.judge_model,
                                  args.timeout, env), pass_at)
    keep(outdir, case, session, d, scored)
    return {"case": case["id"], **scored, "error": session["error"],
            "tokens": session["tokens"], "seconds": session["seconds"]}


def transport_flake(row: dict) -> bool:
    """Whether this case never reached the model at all: qwen printed nothing, spent no
    tokens, and so graded no skill. Observed when several runs share one quota. A turn
    that timed out, exited non-zero, or ran and misbehaved is not this — the second is
    the case's own verdict and must not be retried away."""
    return row.get("error") == NO_OUTPUT and not row.get("tokens")


def case_workspace(root: Path, arm: str, attempt: int) -> Path:
    """One workspace per attempt. The first attempt leaves its copy of the fixture vault
    in `root/<arm>`; a retry that wrote into the same folder would collide, or merge into
    a vault the session had already read."""
    return root / arm if attempt == 1 else root / arm / f"try{attempt}"


def run_with_retry(run_at_attempt: Callable[[int], dict]) -> dict:
    """Run one case, and again if the first attempt reached no model. The retry is
    recorded, so a saved run says which verdicts came from a second attempt; the flaked
    attempt leaves only a human turn behind, so nothing of its evidence is kept."""
    row = run_at_attempt(1)
    if not transport_flake(row):
        return dict(row, attempts=1)
    row = dict(run_at_attempt(2), attempts=2, discarded_error=row["error"])
    return row


def report_line(row: dict) -> str:
    verdict = "PASS" if row["passed"] else "FAIL"
    j = row.get("judge") or {}
    judged = (f"  judge {j['score']}/5" if "score" in j else
              f"  judge error: {j['error'][:80]}" if "error" in j else "")
    line = (f"{verdict}  {row['case']:<28} score {row['score']:.2f}{judged}"
            f"  {row['tokens']} tok  {row['seconds']}s")
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


def scored_skill(summary: dict) -> str:
    """The skill a saved run scored. Runs saved before the harness took a name
    scored companion."""
    return summary.get("skill", DEFAULT_SKILL)


def promote(summary: dict, stable: Path, candidate: Path, case_ids: list,
            skill_name: str) -> str | None:
    """Copy the named skill's candidate over its stable, on the evidence of a saved
    two-arm run of that skill made by the agent this harness drives. Returns why it
    refused, or None once stable has been replaced."""
    arms = summary.get("arms") or {}
    ran_by = summary.get("agent") or "unknown"
    if ran_by != BINARY:
        return (f"this run was made by {ran_by!r}, not {BINARY!r}; its evidence is about "
                f"another agent — run both arms again")
    if scored_skill(summary) != skill_name:
        return f"this run scored {scored_skill(summary)!r}, not {skill_name!r}"
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


def latest_run(skill_name: str, results: Path = RESULTS) -> Path | None:
    """The newest saved run that scored both arms of the named skill, so a quick
    one-arm run, or a run of another skill, made after it doesn't hide it."""
    runs = []
    for summary in results.glob("*/summary.json"):
        try:
            saved = json.loads(summary.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        if scored_skill(saved) == skill_name and set(saved.get("arms") or {}) == {"stable", "candidate"}:
            runs.append(summary)
    return max(runs, key=lambda s: s.stat().st_mtime).parent if runs else None


def run_promote(skill_name: str, run: Path | None, cases: list) -> int:
    run = run or latest_run(skill_name)
    if not run or not (run / "summary.json").exists():
        print(f"error: no saved two-arm run of {skill_name} to promote from; "
              f"run {skill_name} --arm both", file=sys.stderr)
        return 2
    summary = json.loads((run / "summary.json").read_text())
    arms = arms_for(skill_name)
    problem = promote(summary, arms["stable"], arms["candidate"],
                      [c["id"] for c in cases], skill_name)
    if problem:
        print(f"not promoted ({run.name}): {problem}", file=sys.stderr)
        return 1
    print(f"promoted {arms['candidate'].relative_to(REPO)} -> "
          f"{arms['stable'].relative_to(REPO)} on the evidence of {run.name}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("name", nargs="?", default=DEFAULT_SKILL, metavar="SKILL",
                    help="the Library skill to score: its arms are skills/SKILL and "
                         "labs/SKILL, its cases cases/SKILL.json (default: companion)")
    ap.add_argument("--case", help="run only cases whose id contains this")
    ap.add_argument("--arm", choices=["stable", "candidate", "both"],
                    help="which copy of the skill to score (default: stable)")
    ap.add_argument("--skill", help="score this folder instead of an arm, e.g. a "
                                    "mutant; it is installed under SKILL's name")
    ap.add_argument("--promote", nargs="?", const="", metavar="RUN",
                    help="copy the candidate over stable on the evidence of a saved "
                         "two-arm run (default: the latest under results/), then exit")
    ap.add_argument("--model", help="model for the session under test (default: the one "
                                    "your qwen settings pick)")
    ap.add_argument("--judge-model", help="model for the judge (default: the one your "
                                          "qwen settings pick)")
    ap.add_argument("--no-judge", dest="judge", action="store_false", default=True)
    ap.add_argument("--timeout", type=int, default=600, help="seconds per turn")
    ap.add_argument("--output-dir", help="default: labs/evals/results/<timestamp>")
    args = ap.parse_args()

    try:
        all_cases = load_cases(args.name)
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    if args.promote is not None:
        return run_promote(args.name, Path(args.promote) if args.promote else None,
                           all_cases)

    if args.skill and args.arm:
        print("error: --skill and --arm are alternatives", file=sys.stderr)
        return 2
    if args.skill:
        skill = Path(args.skill).resolve()
        arms = {skill.name: skill}
    else:
        names = ["stable", "candidate"] if args.arm == "both" else [args.arm or "stable"]
        both = arms_for(args.name)
        arms = {n: both[n] for n in names}
    for name, skill in arms.items():
        if not (skill / "SKILL.md").exists():
            print(f"error: no SKILL.md for {name} in {skill}", file=sys.stderr)
            return 2
    if not shutil.which(BINARY):
        print(f"error: `{BINARY}` not on PATH", file=sys.stderr)
        return 2
    if not login_found(real_home(), os.environ):
        print(f"error: no {BINARY} login to seed a run with — sign in first, or set the "
              f"API key your {BINARY} settings use", file=sys.stderr)
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

    summary = {"skill": args.name, "agent": BINARY, "arms": {}, "case_filter": args.case,
               "judge": args.judge}
    with tempfile.TemporaryDirectory(prefix=f"{args.name}-evals-") as tmpdir:
        # One isolated home for the run: it holds the login and the session history
        # every resume reads back, and nothing of the developer's own.
        env = agent_env(make_isolated_home(Path(tmpdir), real_home()))
        for name, skill in arms.items():
            where = skill.relative_to(REPO) if skill.is_relative_to(REPO) else skill
            print(f"\n{name}: {where}")
            # Hashed before the run, so an edit made while it runs reads as a change.
            entry = {"skill": str(skill), "hash": tree_hash(skill), "cases": []}
            for case in cases:
                def attempt(n, case=case):
                    return run_case(case, skill, args,
                                    case_workspace(Path(tmpdir), name, n),
                                    outdir / name, env)

                row = run_with_retry(attempt)
                if row["attempts"] > 1:
                    print(f"retry  {case['id']:<28} the first attempt reached no model "
                          f"({row['discarded_error']})", flush=True)
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
          f"{sum(r['tokens'] for r in rows)} tokens. results: {outdir}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
