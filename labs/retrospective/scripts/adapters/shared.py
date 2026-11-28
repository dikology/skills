"""Destination behaviour that more than one Agent adapter performs identically.

An adapter owns the native paths of its runtime. What two adapters do the same way —
recovering an originating project, snapshotting a target before writing it, resolving a
loaded Skill to its canonical source, and the GitHub Issue boundary — lives here, so a fix
to execution safety cannot land in one adapter only.
"""

import json
from pathlib import Path
import re
import subprocess
import tempfile
from urllib.parse import urlparse

from core import atomic_write

TRIAGE_LABEL = "needs-triage"
TEMP_ROOTS = (Path(tempfile.gettempdir()).resolve(), Path("/private/var/folders"))


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


def is_temp_project(project_path):
    if not project_path:
        return False
    path = Path(project_path).expanduser().resolve()
    return any(path == root or root in path.parents for root in TEMP_ROOTS)


def action(key, status, warning=None, **extra):
    result = {"status": status, "key": key}
    if warning:
        result["warning"] = warning
    result.update(extra)
    return result


def prepare_rule(retro_candidate, target, error):
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


def execute_rule(retro_candidate, target, error):
    if error:
        return action(retro_candidate.get("key"), "skipped", error)
    if str(target) != retro_candidate.get("target"):
        return action(retro_candidate.get("key"), "conflict", "Rule destination changed")
    current = read_optional(target)
    if current and retro_candidate["text"].strip() in current:
        return action(retro_candidate.get("key"), "duplicate", "Rule text already exists")
    if current != retro_candidate.get("expected"):
        return action(
            retro_candidate.get("key"), "conflict", "Rule target changed after the report"
        )
    content = current or ""
    anchor = retro_candidate.get("anchor")
    if anchor:
        if anchor not in content:
            return action(retro_candidate.get("key"), "conflict", "Rule anchor is missing")
        content = content.replace(anchor, anchor + retro_candidate["text"], 1)
    else:
        if content and not content.endswith("\n"):
            content += "\n"
        if content and not retro_candidate["text"].startswith("\n"):
            content += "\n"
        content += retro_candidate["text"]
    atomic_write(target, content)
    return action(retro_candidate.get("key"), "saved", target=str(target))


def prepare_skill_edit(retro_candidate, target, status, warning):
    if status != "ready":
        retro_candidate.update(status=status, warning=warning)
        return retro_candidate
    if not all(
        isinstance(retro_candidate.get(field), str) and retro_candidate[field]
        for field in ("old", "text")
    ):
        retro_candidate.update(
            status="skipped", warning="Skill edit requires old and exact new text"
        )
        return retro_candidate
    current = read_optional(target)
    retro_candidate.update(target=str(target), expected=current, status="ready")
    if current and retro_candidate["old"] not in current and retro_candidate["text"] in current:
        retro_candidate.update(status="duplicate", warning="Skill edit text already exists")
    return retro_candidate


def execute_skill_edit(retro_candidate, target, status, warning):
    if status != "ready":
        return action(retro_candidate.get("key"), status, warning)
    if str(target) != retro_candidate.get("target"):
        return action(
            retro_candidate.get("key"), "conflict", "Skill source changed after the report"
        )
    current = read_optional(target)
    if current and retro_candidate["old"] not in current and retro_candidate["text"] in current:
        return action(retro_candidate.get("key"), "duplicate", "Skill edit text already exists")
    if current != retro_candidate.get("expected"):
        return action(
            retro_candidate.get("key"), "conflict", "Skill source changed after the report"
        )
    if retro_candidate["old"] not in current:
        return action(
            retro_candidate.get("key"), "conflict", "Skill edit source text is missing"
        )
    atomic_write(target, current.replace(retro_candidate["old"], retro_candidate["text"], 1))
    return action(retro_candidate.get("key"), "saved", target=str(target))


def classify_skill_source(name, candidates, upstream_parts, protected_roots):
    """Resolve a loaded Skill to the canonical file its installed copy points at.

    Returns (path, status, warning) with status in ready / upstream / skipped: an installed
    copy that resolves into an upstream cache is never edited in place, and a Skill with no
    source is skipped rather than written blind.
    """
    if not re.fullmatch(r"[A-Za-z0-9._-]+", str(name or "")):
        return None, "skipped", "invalid Skill name"
    installed = next((path for path in candidates if path.exists()), None)
    if installed is None:
        return None, "skipped", f"Skill source not found: {name}"
    resolved = installed.resolve()
    if any(part in upstream_parts for part in resolved.parts):
        return None, "upstream", f"Skill is upstream: {name}"
    if any(
        resolved == root or (root and root in resolved.parents) for root in protected_roots
    ):
        return None, "skipped", "retrospective's own Skill is not a write destination"
    return resolved, "ready", None


def prepare_issue(retro_candidate):
    _, error = originating_project(retro_candidate)
    if error:
        retro_candidate.update(status="skipped", warning=error)
        return retro_candidate
    if not all(
        isinstance(retro_candidate.get(field), str) and retro_candidate[field].strip()
        for field in ("title", "text")
    ):
        retro_candidate.update(status="skipped", warning="Issue title and body are required")
        return retro_candidate
    retro_candidate.update(status="ready")
    return retro_candidate


def execute_issue(retro_candidate):
    key = retro_candidate.get("key")
    project, error = originating_project(retro_candidate)
    if error:
        return action(key, "skipped", error)
    try:
        remote_result = subprocess.run(
            ["git", "-C", str(project), "remote", "get-url", "origin"],
            text=True,
            capture_output=True,
            check=False,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        return action(key, "skipped", str(error))
    if remote_result.returncode != 0:
        return action(key, "skipped", "origin remote is unavailable")
    repository = github_repository(remote_result.stdout)
    if not repository:
        return action(key, "skipped", "origin is not a GitHub repository")
    label_result = subprocess.run(
        ["gh", "label", "list", "--repo", repository, "--json", "name"],
        text=True,
        capture_output=True,
        check=False,
        timeout=30,
    )
    if label_result.returncode != 0:
        return action(key, "skipped", "GitHub labels could not be checked; issue not created")
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
        isinstance(label, dict) and label.get("name") == TRIAGE_LABEL for label in labels
    ):
        command.extend(["--label", TRIAGE_LABEL])
    issue_result = subprocess.run(
        command, text=True, capture_output=True, check=False, timeout=60
    )
    if issue_result.returncode != 0:
        return action(key, "skipped", "GitHub issue creation failed")
    return action(key, "saved", url=issue_result.stdout.strip())


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
