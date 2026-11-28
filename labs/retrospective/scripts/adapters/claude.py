from collections import Counter
from datetime import datetime
import json
import os
from pathlib import Path
import re

from core import atomic_write
from adapters.shared import (
    classify_skill_source,
    execute_issue,
    execute_rule,
    execute_skill_edit,
    is_temp_project,
    originating_project,
    prepare_issue,
    prepare_rule,
    prepare_skill_edit,
    read_optional,
)


CAPABILITIES = {
    "adapter": "claude",
    "operations": [
        "capabilities",
        "current-session",
        "note",
        "notes",
        "digest",
        "prepare",
        "report",
        "execute",
        "reviewed",
        "declined",
        "clear",
    ],
    "signals": ["current_session_identity", "insights_facets", "claude_reflect_queue"],
    "destinations": ["retro_inbox", "memory", "rule", "skill_edit", "issue"],
    "unsupported_destinations": [],
    "rule_destinations": {
        "project": "AGENTS.md when it exists, otherwise CLAUDE.md",
    },
    "disclosures": [
        "Current-session identity is the newest transcript by modification time, so a "
        "parallel Claude session can be mistaken for this one.",
        "The insights facets and claude-reflect queue are read-only; the queue is never "
        "cleared.",
        "Claude ignores a retro_candidate's Rule `scope`: a Rule is always the originating "
        "project's shared instructions, never a personal or global file.",
    ],
}

BUILTIN_COMMANDS = {
    "clear",
    "compact",
    "model",
    "config",
    "help",
    "resume",
    "cost",
    "exit",
    "fast",
    "effort",
    "permissions",
    "status",
    "context",
    "memory",
    "login",
    "logout",
}
COMMAND_RE = re.compile(r"<command-name>\s*(\S+?)\s*</command-name>")
ARGS_RE = re.compile(r"<command-args>(.*?)</command-args>", re.DOTALL)
INTERRUPT = "[Request interrupted by user"


def claude_home():
    return Path(os.environ.get("CLAUDE_HOME", Path.home() / ".claude"))


def capabilities():
    return CAPABILITIES


def current_session():
    transcripts = list((claude_home() / "projects").glob("*/*.jsonl"))
    if not transcripts:
        return {"adapter": "claude", "session_id": None, "status": "unavailable"}
    newest = max(transcripts, key=lambda path: path.stat().st_mtime)
    return {
        "adapter": "claude",
        "session_id": newest.stem,
        "status": "available",
        "transcript_path": str(newest),
    }


def session_exists(session_id):
    return any(
        path.stem == session_id
        for path in (claude_home() / "projects").glob("*/*.jsonl")
    )


def encode_project(path):
    return re.sub(r"[^A-Za-z0-9-]", "-", str(Path(path).expanduser()))


def timestamp(record):
    raw = record.get("timestamp")
    if not isinstance(raw, str):
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None


def is_human(record):
    origin = record.get("origin")
    if isinstance(origin, dict):
        return origin.get("kind") == "human"
    if record.get("isMeta") or record.get("isSidechain"):
        return False
    message = record.get("message")
    content = message.get("content") if isinstance(message, dict) else None
    if isinstance(content, list):
        return not any(
            isinstance(block, dict) and block.get("type") == "tool_result"
            for block in content
        )
    return isinstance(content, str)


def text(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(
            block.get("text", "")
            for block in content
            if isinstance(block, dict) and block.get("type") == "text"
        )
    return ""


def prompt_text(raw):
    if command := COMMAND_RE.search(raw):
        args = ARGS_RE.search(raw)
        raw = f"{command[1]} {args[1].strip() if args else ''}"
    return " ".join(raw.split())


def add_skill(session, name):
    if name and name not in BUILTIN_COMMANDS and name not in session["skills"]:
        session["skills"].append(name)


def parse_session(path):
    session = {
        "session_id": path.stem,
        "path": path,
        "project_label": path.parent.name,
        "project_path": "",
        "title": "",
        "first": None,
        "last": None,
        "prompts": [],
        "tools": Counter(),
        "skills": [],
        "errors": [],
        "error_count": 0,
        "interruptions": 0,
        "signals": {},
        "reviewed": False,
    }
    warnings = []
    with path.open(encoding="utf-8", errors="replace") as handle:
        lines = handle.readlines()
    for line_number, line in enumerate(lines, 1):
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            warnings.append(f"{path}:{line_number}: malformed JSON record skipped")
            continue
        if not isinstance(record, dict):
            warnings.append(f"{path}:{line_number}: non-object record skipped")
            continue
        record_type = record.get("type")
        if record_type == "ai-title" and record.get("aiTitle"):
            session["title"] = record["aiTitle"]
            continue
        if not session["project_path"] and isinstance(record.get("cwd"), str):
            session["project_path"] = record["cwd"]
        moment = timestamp(record)
        if moment and record_type in ("user", "assistant"):
            session["first"] = min(session["first"] or moment, moment)
            session["last"] = max(session["last"] or moment, moment)
        message = record.get("message") if isinstance(record.get("message"), dict) else {}
        content = message.get("content")
        if record_type == "user":
            if isinstance(content, list):
                for block in content:
                    if (
                        isinstance(block, dict)
                        and block.get("type") == "tool_result"
                        and block.get("is_error")
                    ):
                        session["error_count"] += 1
                        if len(session["errors"]) < 3:
                            detail = text(block.get("content")) or str(block.get("content", ""))
                            session["errors"].append(" ".join(detail.split())[:120])
            prompt = text(content)
            if INTERRUPT in prompt:
                session["interruptions"] += 1
            if is_human(record) and prompt.strip() and INTERRUPT not in prompt:
                command = COMMAND_RE.search(prompt)
                if command and command[1].lstrip("/") in BUILTIN_COMMANDS:
                    continue
                if command:
                    add_skill(session, command[1].lstrip("/"))
                session["prompts"].append(prompt_text(prompt))
        elif record_type == "assistant" and isinstance(content, list):
            add_skill(session, record.get("attributionSkill"))
            for block in content:
                if isinstance(block, dict) and block.get("type") == "tool_use":
                    session["tools"][block.get("name", "?")] += 1
                    if block.get("name") == "Skill":
                        add_skill(session, (block.get("input") or {}).get("skill"))
    return session, warnings


def load_facets(session_id):
    path = claude_home() / "usage-data" / "facets" / f"{session_id}.json"
    try:
        facets = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None, []
    except (OSError, json.JSONDecodeError) as error:
        return None, [f"{path}: unreadable insights facets ignored: {error}"]
    if not isinstance(facets, dict):
        return None, [f"{path}: non-object insights facets ignored"]
    return facets, []


def discover(start, end, project=None, session_ids=None, min_user_messages=3, include_temp=False):
    root = claude_home() / "projects"
    if not root.exists():
        return [], []
    sessions = []
    warnings = []
    paths = sorted(root.glob("*/*.jsonl"))
    if session_ids:
        for session_id in session_ids:
            if not session_id:
                raise ValueError("session ID or prefix must not be empty")
            matches = [
                path for path in paths
                if not path.name.startswith("agent-") and path.stem.startswith(session_id)
            ]
            if len(matches) > 1:
                raise ValueError(f"session prefix '{session_id}' is ambiguous")
    for path in paths:
        if path.name.startswith("agent-"):
            continue
        if session_ids and not any(path.stem.startswith(value) for value in session_ids):
            continue
        if not session_ids:
            modified = datetime.fromtimestamp(path.stat().st_mtime).date()
            if modified < start:
                continue
        try:
            session, session_warnings = parse_session(path)
        except OSError as error:
            warnings.append(f"{path}: unreadable transcript skipped: {error}")
            continue
        warnings.extend(session_warnings)
        if not include_temp and is_temp_project(session["project_path"]):
            continue
        if project and project.lower() not in (
            session["project_path"] or path.parent.name
        ).lower():
            continue
        if not session["project_path"]:
            warnings.append(
                f"{path}: originating project unavailable; project-bound writes are blocked"
            )
        first = session["first"]
        last = session["last"]
        if not first or not last:
            warnings.append(f"{path}: valid user/assistant timestamps are required")
            if not session_ids:
                continue
        if not session_ids and len(session["prompts"]) < min_user_messages:
            warnings.append(
                f"{path}: at least {min_user_messages} ordered human prompts are required"
            )
            continue
        if not session_ids and not (
            first.astimezone().date() <= end and last.astimezone().date() >= start
        ):
            continue
        facets, facet_warnings = load_facets(session["session_id"])
        warnings.extend(facet_warnings)
        if facets is not None:
            session["signals"]["insights_facets"] = facets
        sessions.append(session)
    sessions.sort(
        key=lambda session: (
            session["project_path"],
            session["first"].timestamp() if session["first"] else float("-inf"),
        )
    )
    return sessions, warnings


def load_optional_signals(sessions, start, end):
    items = []
    warnings = []
    directories = sorted({session["path"].parent for session in sessions})
    for directory in directories:
        path = directory / "learnings-queue.json"
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            continue
        except (OSError, json.JSONDecodeError) as error:
            warnings.append(f"{path}: unreadable claude-reflect queue ignored: {error}")
            continue
        if not isinstance(data, list):
            warnings.append(f"{path}: non-list claude-reflect queue ignored")
            continue
        for item in data:
            if not isinstance(item, dict):
                warnings.append(f"{path}: non-object queue item ignored")
                continue
            moment = timestamp(item)
            if moment is None or start <= moment.astimezone().date() <= end:
                items.append(item)
    return {"claude_reflect_queue": items} if items else {}, warnings


def memory_paths(retro_candidate):
    project, error = originating_project(retro_candidate)
    if error:
        return None, None, error
    name = retro_candidate.get("name", "")
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", name):
        return None, None, "Memory name must be kebab-case"
    folder = claude_home() / "projects" / encode_project(project) / "memory"
    return folder / f"{name}.md", folder / "MEMORY.md", None


def render_memory(retro_candidate):
    memory_type = retro_candidate.get("memory_type", "feedback")
    if memory_type not in {"user", "feedback", "project", "reference"}:
        raise ValueError("unsupported Memory type")
    content = (
        "---\n"
        f"name: {retro_candidate['name']}\n"
        f"description: {retro_candidate['description']}\n"
        "metadata:\n"
        f"  type: {memory_type}\n"
        "---\n\n"
        f"{retro_candidate['text'].strip()}\n"
    )
    if memory_type in {"feedback", "project"}:
        content += f"\n**Why:** {retro_candidate['why']}\n\n**How to apply:** {retro_candidate['how_to_apply']}\n"
    return content


def memory_index_line(retro_candidate):
    return (
        f"- [{retro_candidate.get('title') or retro_candidate['name']}]({retro_candidate['name']}.md) — "
        f"{retro_candidate['description']}"
    )


def rule_path(retro_candidate):
    project, error = originating_project(retro_candidate)
    if error:
        return None, error
    generic = project / "AGENTS.md"
    return (generic if generic.exists() else project / "CLAUDE.md"), None


UPSTREAM_PARTS = {"plugins", "extensions", "extension", "builtins", "builtin", "built-in"}


def find_skill(retro_candidate):
    project, error = originating_project(retro_candidate)
    if error:
        return None, "skipped", error
    name = retro_candidate.get("name", "")
    if retro_candidate.get("upstream") or ":" in name:
        return None, "upstream", f"Skill is upstream: {name}"
    return classify_skill_source(
        name,
        (
            project / ".claude" / "skills" / name / "SKILL.md",
            claude_home() / "skills" / name / "SKILL.md",
        ),
        UPSTREAM_PARTS,
        (Path(__file__).resolve().parents[2],),
    )


def prepare_retro_candidate(original):
    retro_candidate = dict(original)
    retro_candidate_type = retro_candidate.get("type")
    try:
        if retro_candidate_type == "memory":
            target, index_target, error = memory_paths(retro_candidate)
            if error:
                retro_candidate.update(status="skipped", warning=error)
                return retro_candidate
            for field in ("description", "text"):
                if not isinstance(retro_candidate.get(field), str) or not retro_candidate[field].strip():
                    retro_candidate.update(status="skipped", warning=f"Memory {field} is required")
                    return retro_candidate
            if retro_candidate.get("memory_type", "feedback") in {"feedback", "project"}:
                for field in ("why", "how_to_apply"):
                    if not isinstance(retro_candidate.get(field), str) or not retro_candidate[field].strip():
                        retro_candidate.update(status="skipped", warning=f"Memory {field} is required")
                        return retro_candidate
            current = read_optional(target)
            index_current = read_optional(index_target)
            rendered = render_memory(retro_candidate)
            retro_candidate.update(
                target=str(target),
                index_target=str(index_target),
                expected=current,
                index_expected=index_current,
                status="ready",
            )
            if current and retro_candidate["text"].strip() in current:
                retro_candidate.update(status="duplicate", warning="Memory text already exists")
            return retro_candidate
        if retro_candidate_type == "rule":
            target, error = rule_path(retro_candidate)
            return prepare_rule(retro_candidate, target, error)
        if retro_candidate_type == "skill_edit":
            target, status, warning = find_skill(retro_candidate)
            return prepare_skill_edit(retro_candidate, target, status, warning)
        if retro_candidate_type == "issue":
            return prepare_issue(retro_candidate)
    except (OSError, ValueError) as error:
        retro_candidate.update(status="skipped", warning=str(error))
        return retro_candidate
    retro_candidate.update(status="skipped", warning=f"unsupported destination: {retro_candidate_type}")
    return retro_candidate


def execute_retro_candidate(retro_candidate):
    if retro_candidate.get("status") in {"skipped", "duplicate", "upstream"}:
        return {
            "status": retro_candidate["status"],
            "key": retro_candidate.get("key"),
            "warning": retro_candidate.get("warning"),
        }
    retro_candidate_type = retro_candidate.get("type")
    if retro_candidate_type == "memory":
        target, index_target, error = memory_paths(retro_candidate)
        if error:
            return {"status": "skipped", "key": retro_candidate.get("key"), "warning": error}
        if str(target) != retro_candidate.get("target") or str(index_target) != retro_candidate.get("index_target"):
            return {"status": "conflict", "key": retro_candidate.get("key"), "warning": "Memory destination changed"}
        current = read_optional(target)
        index_current = read_optional(index_target)
        if current and retro_candidate["text"].strip() in current:
            return {"status": "duplicate", "key": retro_candidate.get("key"), "warning": "Memory text already exists"}
        if current != retro_candidate.get("expected") or index_current != retro_candidate.get("index_expected"):
            return {"status": "conflict", "key": retro_candidate.get("key"), "warning": "Memory changed after the report"}
        atomic_write(target, render_memory(retro_candidate))
        line = memory_index_line(retro_candidate)
        index_content = index_current or ""
        if f"({retro_candidate['name']}.md)" not in index_content:
            if index_content and not index_content.endswith("\n"):
                index_content += "\n"
            atomic_write(index_target, index_content + line + "\n")
        return {"status": "saved", "key": retro_candidate.get("key"), "target": str(target)}
    if retro_candidate_type == "rule":
        target, error = rule_path(retro_candidate)
        return execute_rule(retro_candidate, target, error)
    if retro_candidate_type == "skill_edit":
        target, status, warning = find_skill(retro_candidate)
        return execute_skill_edit(retro_candidate, target, status, warning)
    if retro_candidate_type == "issue":
        return execute_issue(retro_candidate)
    return {"status": "skipped", "key": retro_candidate.get("key"), "warning": "unsupported destination"}
