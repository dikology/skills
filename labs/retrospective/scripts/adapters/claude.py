from collections import Counter
from datetime import datetime
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
from urllib.parse import urlparse

from core import atomic_write


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


def is_temp_project(project_path):
    if not project_path:
        return False
    path = Path(project_path).expanduser().resolve()
    temp_roots = (Path(tempfile.gettempdir()).resolve(), Path("/private/var/folders"))
    return any(path == root or root in path.parents for root in temp_roots)


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


def originating_project(retro_candidate):
    raw = retro_candidate.get("project")
    if not isinstance(raw, str) or not raw.strip():
        return None, "originating project is unavailable"
    project = Path(raw).expanduser().resolve()
    if not project.is_dir():
        return None, f"originating project is unavailable: {project}"
    return project, None


def read_optional(path):
    return path.read_text(encoding="utf-8") if path.exists() else None


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


def find_skill(retro_candidate):
    project, error = originating_project(retro_candidate)
    if error:
        return None, "skipped", error
    name = retro_candidate.get("name", "")
    if retro_candidate.get("upstream") or ":" in name:
        return None, "upstream", f"Skill is upstream: {name}"
    if not re.fullmatch(r"[A-Za-z0-9._-]+", name):
        return None, "skipped", "invalid Skill name"
    retro_candidates = (
        project / ".claude" / "skills" / name / "SKILL.md",
        claude_home() / "skills" / name / "SKILL.md",
    )
    installed = next((path for path in retro_candidates if path.exists()), None)
    if installed is None:
        return None, "skipped", f"Skill source not found: {name}"
    resolved = installed.resolve()
    upstream_parts = {"plugins", "extensions", "extension", "builtins", "builtin", "built-in"}
    if any(part in upstream_parts for part in resolved.parts):
        return None, "upstream", f"Skill is upstream: {name}"
    retrospective_root = Path(__file__).resolve().parents[2]
    if resolved == retrospective_root or retrospective_root in resolved.parents:
        return None, "skipped", "retrospective's own Skill is not a write destination"
    return resolved, "ready", None


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
            if error:
                retro_candidate.update(status="skipped", warning=error)
                return retro_candidate
            if not isinstance(retro_candidate.get("text"), str) or not retro_candidate["text"].strip():
                retro_candidate.update(status="skipped", warning="Rule text is required")
                return retro_candidate
            current = read_optional(target)
            retro_candidate.update(target=str(target), expected=current, status="ready")
            if current and retro_candidate["text"].strip() in current:
                retro_candidate.update(status="duplicate", warning="Rule text already exists")
            return retro_candidate
        if retro_candidate_type == "skill_edit":
            target, status, warning = find_skill(retro_candidate)
            if status != "ready":
                retro_candidate.update(status=status, warning=warning)
                return retro_candidate
            if not all(isinstance(retro_candidate.get(field), str) and retro_candidate[field] for field in ("old", "text")):
                retro_candidate.update(status="skipped", warning="Skill edit requires old and exact new text")
                return retro_candidate
            current = read_optional(target)
            retro_candidate.update(target=str(target), expected=current, status="ready")
            if current and retro_candidate["old"] not in current and retro_candidate["text"] in current:
                retro_candidate.update(status="duplicate", warning="Skill edit text already exists")
            return retro_candidate
        if retro_candidate_type == "issue":
            _, error = originating_project(retro_candidate)
            if error:
                retro_candidate.update(status="skipped", warning=error)
                return retro_candidate
            if not all(isinstance(retro_candidate.get(field), str) and retro_candidate[field].strip() for field in ("title", "text")):
                retro_candidate.update(status="skipped", warning="Issue title and body are required")
                return retro_candidate
            retro_candidate.update(status="ready")
            return retro_candidate
    except (OSError, ValueError) as error:
        retro_candidate.update(status="skipped", warning=str(error))
        return retro_candidate
    retro_candidate.update(status="skipped", warning=f"unsupported destination: {retro_candidate_type}")
    return retro_candidate


def github_repository(remote):
    remote = remote.strip()
    if remote.startswith("git@github.com:"):
        path = remote.removeprefix("git@github.com:")
    else:
        parsed = urlparse(remote)
        if parsed.hostname != "github.com":
            return None
        path = parsed.path.lstrip("/")
    path = path.removesuffix(".git")
    parts = path.split("/")
    if len(parts) != 2 or not all(parts):
        return None
    return "/".join(parts)


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
        if error:
            return {"status": "skipped", "key": retro_candidate.get("key"), "warning": error}
        if str(target) != retro_candidate.get("target"):
            return {"status": "conflict", "key": retro_candidate.get("key"), "warning": "Rule destination changed"}
        current = read_optional(target)
        if current and retro_candidate["text"].strip() in current:
            return {"status": "duplicate", "key": retro_candidate.get("key"), "warning": "Rule text already exists"}
        if current != retro_candidate.get("expected"):
            return {"status": "conflict", "key": retro_candidate.get("key"), "warning": "Rule target changed after the report"}
        content = current or ""
        anchor = retro_candidate.get("anchor")
        if anchor:
            if anchor not in content:
                return {"status": "conflict", "key": retro_candidate.get("key"), "warning": "Rule anchor is missing"}
            content = content.replace(anchor, anchor + retro_candidate["text"], 1)
        else:
            if content and not content.endswith("\n"):
                content += "\n"
            if content and not retro_candidate["text"].startswith("\n"):
                content += "\n"
            content += retro_candidate["text"]
        atomic_write(target, content)
        return {"status": "saved", "key": retro_candidate.get("key"), "target": str(target)}
    if retro_candidate_type == "skill_edit":
        target, status, warning = find_skill(retro_candidate)
        if status != "ready":
            return {"status": status, "key": retro_candidate.get("key"), "warning": warning}
        if str(target) != retro_candidate.get("target"):
            return {"status": "conflict", "key": retro_candidate.get("key"), "warning": "Skill source changed after the report"}
        current = read_optional(target)
        if current and retro_candidate["old"] not in current and retro_candidate["text"] in current:
            return {"status": "duplicate", "key": retro_candidate.get("key"), "warning": "Skill edit text already exists"}
        if current != retro_candidate.get("expected"):
            return {"status": "conflict", "key": retro_candidate.get("key"), "warning": "Skill source changed after the report"}
        if retro_candidate["old"] not in current:
            return {"status": "conflict", "key": retro_candidate.get("key"), "warning": "Skill edit source text is missing"}
        content = current.replace(retro_candidate["old"], retro_candidate["text"], 1)
        atomic_write(target, content)
        return {"status": "saved", "key": retro_candidate.get("key"), "target": str(target)}
    if retro_candidate_type == "issue":
        project, error = originating_project(retro_candidate)
        if error:
            return {"status": "skipped", "key": retro_candidate.get("key"), "warning": error}
        try:
            remote_result = subprocess.run(
                ["git", "-C", str(project), "remote", "get-url", "origin"],
                text=True,
                capture_output=True,
                check=False,
                timeout=30,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            return {"status": "skipped", "key": retro_candidate.get("key"), "warning": str(error)}
        if remote_result.returncode != 0:
            return {"status": "skipped", "key": retro_candidate.get("key"), "warning": "origin remote is unavailable"}
        repository = github_repository(remote_result.stdout)
        if not repository:
            return {"status": "skipped", "key": retro_candidate.get("key"), "warning": "origin is not a GitHub repository"}
        label_result = subprocess.run(
            ["gh", "label", "list", "--repo", repository, "--json", "name"],
            text=True,
            capture_output=True,
            check=False,
            timeout=30,
        )
        if label_result.returncode != 0:
            return {"status": "skipped", "key": retro_candidate.get("key"), "warning": "GitHub labels could not be checked; issue not created"}
        try:
            labels = json.loads(label_result.stdout)
        except json.JSONDecodeError:
            labels = []
        command = [
            "gh",
            "issue",
            "create",
            "--repo",
            repository,
            "--title",
            retro_candidate["title"],
            "--body",
            retro_candidate["text"],
        ]
        if isinstance(labels, list) and any(
            isinstance(label, dict) and label.get("name") == "needs-triage"
            for label in labels
        ):
            command.extend(["--label", "needs-triage"])
        issue_result = subprocess.run(
            command,
            text=True,
            capture_output=True,
            check=False,
            timeout=60,
        )
        if issue_result.returncode != 0:
            return {"status": "skipped", "key": retro_candidate.get("key"), "warning": "GitHub issue creation failed"}
        return {
            "status": "saved",
            "key": retro_candidate.get("key"),
            "url": issue_result.stdout.strip(),
        }
    return {"status": "skipped", "key": retro_candidate.get("key"), "warning": "unsupported destination"}
