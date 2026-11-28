"""Qwen Code adapter for the shared retrospective core.

Shapes here are read from Qwen Code 0.28.3 on macOS: the record fields this parser depends
on are `type`, `provenance`, `timestamp`, `cwd`, `message.parts[]`, `toolCallResult` and the
`system` subtypes `slash_command` and `custom_title`. Unknown fields, unknown subtypes and
unknown record types are ignored rather than rejected, because Qwen publishes no versioned
transcript schema; compatibility is claimed for the tested version only.
"""

from collections import Counter
from datetime import datetime
import json
import os
from pathlib import Path
import re

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
)

SUPPORTED_VERSION = "0.28.3"
CHATS_DIR = "chats"

CAPABILITIES = {
    "adapter": "qwen",
    "supported_version": SUPPORTED_VERSION,
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
    "signals": [
        "current_session_identity",
        "session_titles",
        "slash_commands",
        "skill_attribution",
    ],
    "destinations": ["retro_inbox", "rule", "skill_edit", "issue"],
    "unsupported_destinations": ["memory"],
    "rule_destinations": {
        "project": "QWEN.md",
        "cross_tool": "AGENTS.md",
        "global": "explicit user direction only",
    },
    "disclosures": [
        "Memory is unsupported: Qwen's generated memory indexes are never edited, and a "
        "Memory Retro candidate is reported rather than written.",
        "Skill attribution is partial: it comes from slash commands recorded as sent to the "
        "model and from Skill tool calls, so a Skill loaded another way leaves no trace and a "
        "custom slash command can be counted as one. A headless run that invokes a Skill by "
        "name records neither, so an empty skills line there proves nothing.",
        "Sessions exist only where transcript recording was enabled; an empty storage root is "
        "a data limitation, not an empty history.",
        "Subagent transcripts under projects/<slug>/subagents/ are not sessions and their "
        "contents are not merged into the parent session.",
        "The current session comes from QWEN_CODE_SESSION_ID, so parallel sessions are told "
        "apart; identity is unavailable when the CLI exported no session environment.",
        "Shapes were read from Qwen Code 0.28.3 on macOS; no older or newer release is "
        "claimed. `current-session` reports the running version, so a different one is "
        "visible in the summary rather than assumed.",
    ],
}

# Slash commands that name a runtime feature rather than a Skill. A command the CLI never
# sent to the model is dropped before this set is consulted.
BUILTIN_COMMANDS = {
    "about", "approval-mode", "approvals", "auth", "bug", "chat", "clear", "compress",
    "config", "context", "copy", "cost", "diff", "doctor", "docs", "effort", "exit",
    "export", "fast", "feedback", "help", "ide", "import-config", "init", "insight",
    "language", "login", "logout", "mcp", "memory", "model", "new", "output-format",
    "permissions", "plan", "quit", "redo", "rename", "restore", "resume", "settings",
    "stats", "status", "summary", "terminal", "theme", "tools", "usage", "vim",
}

# The project instruction files Qwen loads, and the generic one it shares with other agents.
QWEN_INSTRUCTION_FILE = "QWEN.md"
GENERIC_INSTRUCTION_FILE = "AGENTS.md"

# Qwen reads installed Skills from both config folders.
SKILL_CONFIG_DIRS = (".qwen", ".agents")

UPSTREAM_PARTS = {
    "plugins", "plugin", "extensions", "extension", "builtins", "builtin", "built-in",
    "bundled", "node_modules",
}

MEMORY_UNSUPPORTED = (
    "Qwen Memory is unsupported: generated memory indexes are never edited"
)


def qwen_home():
    """Qwen's own directory: `$QWEN_HOME`, else `~/.qwen`."""
    configured = os.environ.get("QWEN_HOME")
    if configured:
        return Path(configured).expanduser()
    return Path.home() / ".qwen"


def runtime_base():
    """Where Qwen writes runtime data (`projects/`, `tmp/`).

    `QWEN_RUNTIME_DIR` takes priority, then the `advanced.runtimeOutputDir` setting, then the
    config directory. All three are documented in Qwen's own settings reference."""
    configured = os.environ.get("QWEN_RUNTIME_DIR")
    if configured:
        return Path(configured).expanduser()
    redirect = configured_runtime_dir()
    if redirect is not None:
        return redirect
    return qwen_home()


def configured_runtime_dir():
    """Only `advanced.runtimeOutputDir` is read out of settings.json.

    That file can hold secrets in other keys, so its contents are never returned, printed, or
    carried into a warning."""
    settings = qwen_home() / "settings.json"
    try:
        data = json.loads(settings.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    advanced = data.get("advanced") if isinstance(data, dict) else None
    value = advanced.get("runtimeOutputDir") if isinstance(advanced, dict) else None
    if isinstance(value, str) and value.strip():
        return Path(value.strip().replace("~", str(Path.home()), 1))
    return None


def projects_root():
    return runtime_base() / "projects"


def capabilities():
    return CAPABILITIES


def safe_session_id(session_id):
    value = str(session_id or "")
    return bool(re.fullmatch(r"[A-Za-z0-9._-]+", value)) and ".." not in value


def project_storage_dir():
    """The native pointer to this run's transcript folder, `QWEN_CODE_PROJECT_DIR`.

    It is a lossy slug of the working directory, so it names a storage folder only: it is
    never reverse-decoded back into a project path."""
    configured = os.environ.get("QWEN_CODE_PROJECT_DIR")
    if not configured:
        return None
    directory = Path(configured).expanduser()
    return directory if directory.is_dir() else None


def transcript_path(session_id):
    if not safe_session_id(session_id):
        return None
    native = project_storage_dir()
    if native is not None:
        candidate = native / CHATS_DIR / f"{session_id}.jsonl"
        if candidate.is_file():
            return candidate
    for path in chat_paths():
        if path.stem == session_id:
            return path
    return None


def current_session():
    """Native current-session identity: the environment Qwen exports to its own tools.

    Unlike a newest-transcript guess, `QWEN_CODE_SESSION_ID` belongs to this process, so
    parallel sessions cannot be confused with one another."""
    session_id = (os.environ.get("QWEN_CODE_SESSION_ID") or "").strip()
    if not session_id:
        return {"adapter": "qwen", "session_id": None, "status": "unavailable"}
    identity = {
        "adapter": "qwen",
        "session_id": session_id,
        "status": "available",
        "identity_source": "environment",
    }
    version = (os.environ.get("QWEN_CODE_STARTUP_VERSION") or "").strip()
    if version:
        identity["qwen_version"] = version
    transcript = transcript_path(session_id)
    if transcript is not None:
        identity["transcript_path"] = str(transcript)
    else:
        identity["recording"] = "absent"
    return identity


def chat_paths():
    """Session transcripts under the storage root.

    Only `projects/<slug>/chats/*.jsonl` is a session. `projects/<slug>/subagents/` holds the
    transcripts of delegated agents, `<runtime>/sessions/` is a pid-keyed process registry
    that carries an IPC token, and neither is read here."""
    root = projects_root()
    if not root.is_dir():
        return []
    paths = []
    for chats in sorted(root.glob(f"*/{CHATS_DIR}")):
        for path in sorted(chats.glob("*.jsonl")):
            if path.name.startswith("agent-"):
                continue
            paths.append(path)
    return paths


def session_exists(session_id):
    return transcript_path(session_id) is not None


def timestamp(record):
    raw = record.get("timestamp")
    if not isinstance(raw, str):
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None


def valid_cwd(value):
    return value if isinstance(value, str) and value.startswith("/") else None


def parts(message):
    content = message.get("parts") if isinstance(message, dict) else None
    return [part for part in content if isinstance(part, dict)] if isinstance(content, list) else []


def part_text(message):
    return "\n".join(
        part.get("text", "")
        for part in parts(message)
        if isinstance(part.get("text"), str) and not part.get("thought")
    )


def origin(record):
    """Which voice spoke this record: human, assistant, tool, system — or unknown.

    Qwen stores injected prompts (`provenance: system`) as `user` records, so the role alone
    is not evidence that a human typed them. A record with no provenance marker predates the
    field and is read by shape instead."""
    record_type = record.get("type")
    if record_type == "assistant":
        return "assistant"
    if record_type == "tool_result":
        return "tool"
    if record_type == "system":
        return "system"
    if record_type != "user":
        return "unknown"
    message = record.get("message")
    if any("functionResponse" in part for part in parts(message)):
        return "tool"
    provenance = record.get("provenance")
    if isinstance(provenance, str):
        return "human" if provenance == "real_user" else "system"
    if record.get("subtype") or record.get("isMeta") or record.get("isSidechain"):
        return "system"
    return "human" if part_text(message).strip() else "unknown"


def add_skill(session, name):
    if name and name not in BUILTIN_COMMANDS and name not in session["skills"]:
        session["skills"].append(name)


def command_name(raw):
    return str(raw or "").strip().lstrip("/").split()[0] if str(raw or "").strip() else ""


def read_sidecar(path, kind):
    """`<session>.title.json` / `<session>.runtime.json`: native session metadata."""
    sidecar = path.with_name(f"{path.stem}.{kind}.json")
    if not sidecar.is_file():
        return None, []
    try:
        data = json.loads(sidecar.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        return None, [f"{sidecar}: unreadable {kind} metadata ignored: {error}"]
    if not isinstance(data, dict):
        return None, [f"{sidecar}: non-object {kind} metadata ignored"]
    return data, []


def parse_session(path):
    session = {
        "session_id": path.stem,
        "path": path,
        "project_label": path.parent.parent.name,
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
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError as error:
        return session, [f"{path}: unreadable transcript skipped: {error}"]
    records = []
    for line_number, line in enumerate(lines, 1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            warnings.append(f"{path}:{line_number}: malformed JSON record skipped")
            continue
        if not isinstance(record, dict):
            warnings.append(f"{path}:{line_number}: non-object record skipped")
            continue
        if record.get("sessionId") and str(record["sessionId"]) != path.stem:
            warnings.append(
                f"{path}:{line_number}: record names another session and is not this session's evidence"
            )
            continue
        records.append(record)

    local_commands = set()
    slash_commands = []
    record_title = ""
    for record in records:
        if record.get("subtype") != "slash_command":
            continue
        payload = record.get("systemPayload")
        if not isinstance(payload, dict):
            warnings.append(f"{path}: malformed slash-command record ignored")
            continue
        raw = payload.get("rawCommand")
        if not isinstance(raw, str) or not raw.strip():
            continue
        raw = " ".join(raw.split())
        if payload.get("phase") == "invocation":
            if raw not in slash_commands:
                slash_commands.append(raw)
            if payload.get("hiddenInvocation") is True or payload.get("sentToModel") is False:
                local_commands.add(raw)
            elif command_name(raw) not in BUILTIN_COMMANDS:
                add_skill(session, command_name(raw))
    for record in records:
        if record.get("subtype") == "custom_title" and isinstance(
            record.get("systemPayload"), dict
        ):
            title = record["systemPayload"].get("customTitle")
            if isinstance(title, str) and title.strip():
                record_title = " ".join(title.split())

    for record in records:
        voice = origin(record)
        moment = timestamp(record)
        if moment and voice in ("human", "assistant", "tool"):
            session["first"] = min(session["first"] or moment, moment)
            session["last"] = max(session["last"] or moment, moment)
        if not session["project_path"]:
            session["project_path"] = valid_cwd(record.get("cwd")) or ""
        message = record.get("message")
        if voice == "assistant":
            for part in parts(message):
                call = part.get("functionCall")
                if not isinstance(call, dict):
                    continue
                name = call.get("name") or "?"
                session["tools"][name] += 1
                if name == "skill":
                    add_skill(session, (call.get("args") or {}).get("skill"))
        elif voice == "tool":
            result = record.get("toolCallResult")
            result = result if isinstance(result, dict) else {}
            status = result.get("status")
            execution = result.get("executionStatus")
            if status == "cancelled" or execution == "cancelled":
                session["interruptions"] += 1
            elif status == "error" or execution == "error":
                # 0.28.3 also reports `status: error` with `executionStatus: not_started`: the
                # tool never ran because its params were invalid, it isn't registered, or the
                # human refused it. That is a failed call, not the human stopping one, so it
                # counts as an error and not as an interruption.
                session["error_count"] += 1
                if len(session["errors"]) < 3:
                    detail = " ".join(str(result.get("error") or "").split())
                    kind = str(result.get("errorType") or "").strip()
                    session["errors"].append(
                        (f"{kind}: {detail}" if kind else detail)[:120] or "tool error"
                    )
        elif voice == "human":
            prompt = " ".join(part_text(message).split())
            if prompt and prompt not in local_commands:
                session["prompts"].append(prompt)
        elif voice == "unknown":
            continue

    title, title_warnings = read_sidecar(path, "title")
    warnings.extend(title_warnings)
    session["title"] = (
        " ".join(str(title.get("displayName", "")).split()) if title else ""
    ) or record_title
    runtime, runtime_warnings = read_sidecar(path, "runtime")
    warnings.extend(runtime_warnings)
    recorded = valid_cwd((runtime or {}).get("work_dir"))
    if recorded and session["project_path"] and recorded != session["project_path"]:
        warnings.append(
            f"{path}: runtime work_dir {recorded} disagrees with the transcript's earliest "
            "cwd; the transcript is used"
        )
    if slash_commands:
        session["signals"]["slash_commands"] = slash_commands
    session["signals"]["skill_attribution"] = {
        "complete": False,
        "recorded_as": ["slash_command", "skill_tool_call"],
    }
    return session, warnings


def discover(start, end, project=None, session_ids=None, min_user_messages=3, include_temp=False):
    paths = chat_paths()
    if not paths:
        return [], [
            f"{projects_root()}: no Qwen transcripts found; recording may be disabled, so "
            "this is a data limitation rather than an empty history"
        ]
    if session_ids:
        for session_id in session_ids:
            if not session_id:
                raise ValueError("session ID or prefix must not be empty")
            matches = [path for path in paths if path.stem.startswith(session_id)]
            if len(matches) > 1:
                raise ValueError(f"session prefix '{session_id}' is ambiguous")
    sessions = []
    warnings = []
    for path in paths:
        if session_ids and not any(
            path.stem.startswith(value) for value in session_ids
        ):
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
        label = session["project_path"] or session["project_label"]
        if project and project.lower() not in label.lower():
            continue
        if not session["project_path"]:
            warnings.append(
                f"{path}: originating project unavailable; project-bound writes are blocked"
            )
        first = session["first"]
        last = session["last"]
        if not first or not last:
            warnings.append(f"{path}: valid human/assistant/tool timestamps are required")
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
        sessions.append(session)
    sessions.sort(
        key=lambda session: (
            session["project_path"],
            session["first"].timestamp() if session["first"] else float("-inf"),
        )
    )
    return sessions, warnings


def rule_path(retro_candidate):
    project, error = originating_project(retro_candidate)
    if error:
        return None, error
    scope = retro_candidate.get("scope", "project")
    if scope == "project":
        return project / QWEN_INSTRUCTION_FILE, None
    if scope == "cross_tool":
        return project / GENERIC_INSTRUCTION_FILE, None
    if scope == "global":
        if retro_candidate.get("explicit_user_direction") is not True:
            return None, (
                "personal or global instruction destinations require explicit user direction"
            )
        return qwen_home() / QWEN_INSTRUCTION_FILE, None
    return None, f"unsupported Rule scope: {scope}"


def find_skill(retro_candidate):
    project, error = originating_project(retro_candidate)
    if error:
        return None, "skipped", error
    name = retro_candidate.get("name", "")
    if retro_candidate.get("upstream") or ":" in name:
        return None, "upstream", f"Skill is upstream: {name}"
    home = qwen_home()
    candidates = tuple(
        directory / name / "SKILL.md"
        for directory in (
            *(project / folder / "skills" for folder in SKILL_CONFIG_DIRS),
            home / "skills",
            *(Path.home() / folder / "skills" for folder in SKILL_CONFIG_DIRS if folder != ".qwen"),
        )
    )
    return classify_skill_source(
        name,
        candidates,
        UPSTREAM_PARTS,
        (Path(__file__).resolve().parents[2],),
    )


def prepare_retro_candidate(original):
    retro_candidate = dict(original)
    retro_candidate_type = retro_candidate.get("type")
    try:
        if retro_candidate_type == "memory":
            retro_candidate.update(status="skipped", warning=MEMORY_UNSUPPORTED)
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
    retro_candidate.update(
        status="skipped", warning=f"unsupported destination: {retro_candidate_type}"
    )
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
        return {"status": "skipped", "key": retro_candidate.get("key"), "warning": MEMORY_UNSUPPORTED}
    if retro_candidate_type == "rule":
        target, error = rule_path(retro_candidate)
        return execute_rule(retro_candidate, target, error)
    if retro_candidate_type == "skill_edit":
        target, status, warning = find_skill(retro_candidate)
        return execute_skill_edit(retro_candidate, target, status, warning)
    if retro_candidate_type == "issue":
        return execute_issue(retro_candidate)
    return {
        "status": "skipped",
        "key": retro_candidate.get("key"),
        "warning": "unsupported destination",
    }
