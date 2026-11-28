"""Kimi Code adapter for the shared retrospective core.

Native shapes and storage locations are versioned against Kimi Code 2.7.2 on macOS.
Unknown fields and events are ignored because the wire stream is not a stable public schema.
"""

from collections import Counter
from datetime import datetime, timezone
import json
import os
from pathlib import Path

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

SUPPORTED_VERSION = "2.7.2"
KIMI_INSTRUCTION_FILE = Path(".kimi-code") / "AGENTS.md"
GENERIC_INSTRUCTION_FILE = "AGENTS.md"
MEMORY_UNSUPPORTED = (
    "Kimi Memory is unsupported: durable observations are not instructions and are never written"
)
UPSTREAM_PARTS = {
    "plugins", "plugin", "extensions", "extension", "builtins", "builtin", "built-in",
    "bundled", "node_modules",
}

CAPABILITIES = {
    "adapter": "kimi",
    "supported_version": SUPPORTED_VERSION,
    "operations": [
        "capabilities", "current-session", "note", "notes", "digest", "prepare",
        "report", "execute", "reviewed", "declined", "clear",
    ],
    "signals": ["current_session_identity", "session_titles", "skill_attribution"],
    "destinations": ["retro_inbox", "rule", "skill_edit", "issue"],
    "unsupported_destinations": ["memory"],
    "rule_destinations": {
        "project": ".kimi-code/AGENTS.md",
        "cross_tool": "AGENTS.md",
        "global": "explicit user direction only",
    },
    "disclosures": [
        "Memory is unsupported: durable observations are not instructions and are never "
        "silently converted into Rules or another durable store.",
        "Skill attribution comes from native skill.activated events and activation origins; "
        "older or imported sessions without those records cannot prove that no Skill was used.",
        "Subagent wire streams and lifecycle events are not independent sessions and never "
        "contribute to the main session's human-prompt count.",
        "Persistent print sessions are saved. Missing or damaged native metadata is a data "
        "limitation, not evidence of an empty history.",
        "Shapes were verified against Kimi Code 2.7.2 on macOS; other versions and platforms "
        "are not claimed.",
    ],
}


def capabilities():
    return CAPABILITIES


def kimi_home():
    configured = os.environ.get("KIMI_CODE_HOME")
    return Path(configured).expanduser() if configured else Path.home() / ".kimi-code"


def current_session():
    session_id = (os.environ.get("KIMI_CODE_SESSION_ID") or "").strip()
    workspace_id = (os.environ.get("KIMI_CODE_WORKSPACE_ID") or "").strip()
    if not session_id:
        return {
            "adapter": "kimi",
            "session_id": None,
            "workspace_id": workspace_id or None,
            "status": "unavailable",
        }
    identity = {
        "adapter": "kimi",
        "session_id": session_id,
        "workspace_id": workspace_id or None,
        "status": "available",
        "identity_source": "environment",
    }
    wire = transcript_path(session_id)
    if wire is not None:
        identity["transcript_path"] = str(wire)
    else:
        identity["recording"] = "absent"
    return identity


def sessions_root():
    return kimi_home() / "sessions"


def contained_session_dir(value):
    if not isinstance(value, str) or not value.strip():
        return None
    configured = Path(value).expanduser()
    candidates = [configured] if configured.is_absolute() else [kimi_home() / configured, sessions_root() / configured]
    root = sessions_root().resolve()
    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved != root and root in resolved.parents and resolved.parent.parent == root:
            return resolved
    return None


def session_descriptors():
    """Native index records first, then storage traversal for unindexed sessions."""
    descriptors = []
    warnings = []
    seen = set()
    index = kimi_home() / "session_index.jsonl"
    if index.is_file():
        try:
            lines = index.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError as error:
            warnings.append(f"{index}: unreadable session index; using storage fallback: {error}")
            lines = []
        for line_number, line in enumerate(lines, 1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                warnings.append(f"{index}:{line_number}: malformed JSON session metadata skipped")
                continue
            if not isinstance(record, dict):
                warnings.append(f"{index}:{line_number}: non-object session metadata skipped")
                continue
            session_id = record.get("sessionId")
            directory = contained_session_dir(record.get("sessionDir"))
            if not isinstance(session_id, str) or not session_id or directory is None:
                warnings.append(f"{index}:{line_number}: incomplete or unsafe session metadata skipped")
                continue
            if directory.name != session_id:
                warnings.append(f"{index}:{line_number}: session identity disagrees with sessionDir; skipped")
                continue
            key = (directory.parent.name, session_id)
            if key in seen:
                descriptors = [item for item in descriptors if item["key"] != key]
            seen.add(key)
            descriptors.append({
                "key": key, "session_id": session_id, "workspace_id": directory.parent.name,
                "directory": directory, "work_dir": record.get("workDir"),
            })
    root = sessions_root()
    if root.is_dir():
        for wire in sorted(root.glob("*/*/agents/main/wire.jsonl")):
            directory = wire.parents[2]
            key = (directory.parent.name, directory.name)
            if key not in seen:
                descriptors.append({
                    "key": key, "session_id": directory.name, "workspace_id": directory.parent.name,
                    "directory": directory, "work_dir": None,
                })
    return descriptors, warnings


def transcript_path(session_id):
    descriptors, _ = session_descriptors()
    for descriptor in descriptors:
        if descriptor["session_id"] == session_id:
            wire = descriptor["directory"] / "agents" / "main" / "wire.jsonl"
            return wire if wire.is_file() else None
    return None


def session_exists(session_id):
    return transcript_path(session_id) is not None


def wire_time(record):
    value = record.get("time")
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return None
    try:
        return datetime.fromtimestamp(value / 1000, timezone.utc)
    except (OverflowError, OSError, ValueError):
        return None


def content_text(content):
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    return "\n".join(
        part.get("text", "") for part in content
        if isinstance(part, dict) and isinstance(part.get("text"), str)
    )


def input_text(record):
    return " ".join(content_text(record.get("input")).split())


def add_skill(session, name):
    if isinstance(name, str) and name.strip() and name not in session["skills"]:
        session["skills"].append(name)


def read_state(directory):
    path = directory / "state.json"
    if not path.is_file():
        return {}, [f"{path}: native session metadata is unavailable"]
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        return {}, [f"{path}: unreadable native session metadata ignored: {error}"]
    if not isinstance(state, dict):
        return {}, [f"{path}: non-object native session metadata ignored"]
    return state, []


def state_project(state):
    for value in (state.get("cwd"), state.get("workDir")):
        if isinstance(value, str) and value.startswith("/"):
            return value
    custom = state.get("custom")
    if isinstance(custom, dict):
        value = custom.get("cwd")
        if isinstance(value, str) and value.startswith("/"):
            return value
    return ""


def parse_session(descriptor):
    directory = descriptor["directory"]
    path = directory / "agents" / "main" / "wire.jsonl"
    state, warnings = read_state(directory)
    project_path = state_project(state)
    indexed_project = descriptor.get("work_dir")
    if not project_path and isinstance(indexed_project, str) and indexed_project.startswith("/"):
        project_path = indexed_project
    session = {
        "session_id": descriptor["session_id"],
        "workspace_id": descriptor["workspace_id"],
        "path": path,
        "project_label": descriptor["workspace_id"],
        "project_path": project_path,
        "title": " ".join(str(state.get("title") or "").split()),
        "first": None,
        "last": None,
        "prompts": [],
        "tools": Counter(),
        "skills": [],
        "errors": [],
        "error_count": 0,
        "interruptions": 0,
        "signals": {
            "skill_attribution": {
                "complete": False,
                "recorded_as": ["skill.activated", "activation_origin"],
            },
        },
        "reviewed": False,
    }
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError as error:
        return session, warnings + [f"{path}: unreadable main wire skipped: {error}"]
    subagent_events = 0
    for line_number, line in enumerate(lines, 1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            warnings.append(f"{path}:{line_number}: malformed JSON event skipped")
            continue
        if not isinstance(record, dict):
            warnings.append(f"{path}:{line_number}: non-object event skipped")
            continue
        if not isinstance(record.get("type"), str):
            warnings.append(f"{path}:{line_number}: event without a type skipped")
            continue
        event_type = record["type"]
        moment = wire_time(record)
        voice = None
        if event_type in {"turn.prompt", "turn.steer"}:
            origin = record.get("origin")
            kind = origin.get("kind") if isinstance(origin, dict) else None
            if kind == "user":
                voice = "human"
                text = input_text(record)
                if text:
                    session["prompts"].append(text)
                for activation in (origin.get("skillActivations") or []):
                    if isinstance(activation, dict):
                        add_skill(session, activation.get("skillName"))
            elif kind == "skill_activation":
                add_skill(session, origin.get("skillName"))
        elif event_type == "skill.activated":
            add_skill(session, record.get("skillName"))
        elif event_type == "context.append_message":
            payload = record.get("message")
            if not isinstance(payload, dict):
                warnings.append(f"{path}:{line_number}: malformed message event skipped")
                continue
            role = payload.get("role")
            voice = role if role in {"assistant", "tool"} else None
            origin = payload.get("origin")
            kind = origin.get("kind") if isinstance(origin, dict) else None
            if kind == "skill_activation":
                add_skill(session, origin.get("skillName"))
            if role == "assistant":
                calls = payload.get("toolCalls")
                for call in calls if isinstance(calls, list) else []:
                    if not isinstance(call, dict):
                        continue
                    function = call.get("function")
                    name = call.get("name") or (function.get("name") if isinstance(function, dict) else None) or "?"
                    session["tools"][str(name)] += 1
                    if str(name).lower() == "skill":
                        args = call.get("arguments") or (function.get("arguments") if isinstance(function, dict) else None)
                        if isinstance(args, str):
                            try:
                                args = json.loads(args)
                            except json.JSONDecodeError:
                                args = {}
                        if isinstance(args, dict):
                            add_skill(session, args.get("skill") or args.get("name"))
            if role == "tool" and payload.get("isError") is True:
                session["error_count"] += 1
                if len(session["errors"]) < 3:
                    detail = " ".join(content_text(payload.get("content")).split())
                    session["errors"].append(detail[:120] or "tool error")
        elif event_type == "turn.ended":
            reason = record.get("reason")
            if reason == "cancelled":
                session["interruptions"] += 1
            elif reason in {"failed", "blocked"}:
                session["error_count"] += 1
                if len(session["errors"]) < 3:
                    session["errors"].append(f"turn {reason}")
        elif event_type.startswith("subagent."):
            subagent_events += 1
        if moment and voice in {"human", "assistant", "tool"}:
            session["first"] = min(session["first"] or moment, moment)
            session["last"] = max(session["last"] or moment, moment)
    if subagent_events:
        session["signals"]["subagent_events"] = subagent_events
    return session, warnings


def discover(start, end, project=None, session_ids=None, min_user_messages=3, include_temp=False):
    descriptors, warnings = session_descriptors()
    if not descriptors:
        return [], warnings + [
            f"{sessions_root()}: no Kimi main wire streams found; native session metadata may be "
            "unavailable, so this is a data limitation rather than an empty history"
        ]
    if session_ids:
        for session_id in session_ids:
            if not session_id:
                raise ValueError("session ID or prefix must not be empty")
            matches = [item for item in descriptors if item["session_id"].startswith(session_id)]
            if len(matches) > 1:
                raise ValueError(f"session prefix '{session_id}' is ambiguous")
    sessions = []
    for descriptor in descriptors:
        session_id = descriptor["session_id"]
        if session_ids and not any(session_id.startswith(value) for value in session_ids):
            continue
        wire = descriptor["directory"] / "agents" / "main" / "wire.jsonl"
        if not wire.is_file():
            warnings.append(f"{wire}: main wire is unavailable; session skipped")
            continue
        if not session_ids:
            modified = datetime.fromtimestamp(wire.stat().st_mtime).date()
            if modified < start:
                continue
        session, session_warnings = parse_session(descriptor)
        warnings.extend(session_warnings)
        if not include_temp and is_temp_project(session["project_path"]):
            continue
        label = session["project_path"] or session["project_label"]
        if project and project.lower() not in label.lower():
            continue
        if not session["project_path"]:
            warnings.append(f"{wire}: originating project unavailable; project-bound writes are blocked")
        first, last = session["first"], session["last"]
        if not first or not last:
            warnings.append(f"{wire}: valid human/assistant/tool timestamps are required")
            if not session_ids:
                continue
        if not session_ids and len(session["prompts"]) < min_user_messages:
            warnings.append(f"{wire}: at least {min_user_messages} ordered human prompts are required")
            continue
        if not session_ids and not (
            first.astimezone().date() <= end and last.astimezone().date() >= start
        ):
            continue
        sessions.append(session)
    sessions.sort(key=lambda session: (
        session["project_path"],
        session["first"].timestamp() if session["first"] else float("-inf"),
    ))
    return sessions, warnings


def rule_path(retro_candidate):
    project, error = originating_project(retro_candidate)
    if error:
        return None, error
    scope = retro_candidate.get("scope", "project")
    if scope == "project":
        return project / KIMI_INSTRUCTION_FILE, None
    if scope == "cross_tool":
        return project / GENERIC_INSTRUCTION_FILE, None
    if scope == "global":
        if retro_candidate.get("explicit_user_direction") is not True:
            return None, "personal or global instruction destinations require explicit user direction"
        return kimi_home() / GENERIC_INSTRUCTION_FILE, None
    return None, f"unsupported Rule scope: {scope}"


def find_skill(retro_candidate):
    project, error = originating_project(retro_candidate)
    if error:
        return None, "skipped", error
    name = retro_candidate.get("name", "")
    if retro_candidate.get("upstream") or ":" in name:
        return None, "upstream", f"Skill is upstream: {name}"
    candidates = tuple(
        directory / name / "SKILL.md"
        for directory in (
            project / ".kimi-code" / "skills",
            project / ".agents" / "skills",
            kimi_home() / "skills",
            Path.home() / ".agents" / "skills",
        )
    )
    return classify_skill_source(
        name, candidates, UPSTREAM_PARTS, (Path(__file__).resolve().parents[2],),
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
        "status": "skipped", "key": retro_candidate.get("key"),
        "warning": "unsupported destination",
    }
