from datetime import date, timedelta
import os
from pathlib import Path
import re
import tempfile


DEFAULT_WINDOW = "14d"
PROMPT_CHARS = 160
HEAD_PROMPTS = 5
CORRECTION_RE = re.compile(
    r"^(no\b|nope|wrong|stop|don't|do not|instead|actually|not that|that's not|why did you|"
    r"нет\b|не надо|не так|неправильно|стоп|зачем)",
    re.IGNORECASE,
)


def atomic_write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent, prefix=f".{path.name}."
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, path)
    except BaseException:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise


def parse_approval(value, retro_candidate_count):
    value = value.strip().lower()
    if value == "all":
        return set(range(retro_candidate_count))
    if value == "none":
        return set()
    try:
        selected = {int(number) for number in value.split()}
    except ValueError as error:
        raise ValueError("approval must be numbers, all, or none") from error
    if not selected or any(number < 1 or number > retro_candidate_count for number in selected):
        raise ValueError("approval numbers must refer to reported Retro candidates")
    return {number - 1 for number in selected}


def parse_window(spec, today=None):
    today = today or date.today()
    spec = spec.strip().lower()
    if spec == "today":
        return today, today
    if spec == "yesterday":
        yesterday = today - timedelta(days=1)
        return yesterday, yesterday
    if spec == "week":
        return today - timedelta(days=6), today
    if match := re.fullmatch(r"(\d+)d", spec):
        days = int(match[1])
        if days < 1:
            raise ValueError(f"Unknown window '{spec}': use 14d, week, today, yesterday, Nd or YYYY-MM-DD")
        return today - timedelta(days=days - 1), today
    try:
        selected = date.fromisoformat(spec)
    except ValueError as error:
        raise ValueError(
            f"Unknown window '{spec}': use 14d, week, today, yesterday, Nd or YYYY-MM-DD"
        ) from error
    return selected, selected


def render_digest(
    sessions,
    start,
    end,
    full=False,
    language=None,
    notes=None,
    declined=None,
    optional_signals=None,
):
    lines = [f"# Retro digest — {start} → {end}", ""]
    if language:
        lines.append(f"Insight language: {language}; Retro candidate language: destination")
    reviewed = sum(session["reviewed"] for session in sessions)
    projects = {session["project_path"] for session in sessions}
    lines.append(
        f"{len(sessions)} sessions across {len(projects)} projects "
        f"({reviewed} already reviewed: insights only, no Retro candidates)"
    )
    current_project = None
    for session in sessions:
        project_path = session["project_path"]
        if project_path != current_project:
            current_project = project_path
            count = sum(item["project_path"] == project_path for item in sessions)
            project_name = (
                Path(project_path).name
                if project_path
                else session["path"].parent.name
            )
            lines.extend(["", f"## {project_name} — {project_path or '?'} ({count})"])
        day = session["first"].astimezone().strftime("%Y-%m-%d") if session["first"] else "?"
        flag = " · reviewed" if session["reviewed"] else ""
        lines.extend(
            [
                "",
                f"### {session['session_id'][:8]} · {session['title'] or '(untitled)'} · "
                f"{day} · {len(session['prompts'])} prompts{flag}",
            ]
        )
        lines.append(f"- session-id: {session['session_id']}")
        tools = " ".join(
            f"{name}×{count}" for name, count in session["tools"].most_common(8)
        )
        lines.append(
            f"- tools: {tools or 'none'} · errors: {session['error_count']} · "
            f"interruptions: {session['interruptions']}"
        )
        if session["skills"]:
            lines.append(f"- skills: {', '.join(session['skills'])}")
        facets = session["signals"].get("insights_facets")
        if facets:
            lines.append(
                f"- insights facets: outcome={facets.get('outcome')} · "
                f"helpfulness={facets.get('claude_helpfulness')} · "
                f"friction={facets.get('friction_counts') or {}}"
            )
            if facets.get("friction_detail"):
                lines.append(f"  - friction: {facets['friction_detail']}")
            if facets.get("brief_summary"):
                lines.append(f"  - summary: {facets['brief_summary']}")
        for error in session["errors"]:
            lines.append(f"- error: {error}")
        lines.append("- prompts (⚑ = reads like a correction):")
        hidden = 0
        for index, prompt in enumerate(session["prompts"], 1):
            flagged = index > 1 and bool(CORRECTION_RE.search(prompt))
            if not full and index > HEAD_PROMPTS and not flagged:
                hidden += 1
                continue
            marker = "⚑ " if flagged else ""
            value = prompt if full else prompt[:PROMPT_CHARS]
            lines.append(f"  {index}. {marker}{value}")
        if hidden:
            lines.append(f"  … {hidden} more (--session {session['session_id'][:8]})")
    notes = notes or []
    lines.extend(["", f"## Retro notes ({len(notes)})"])
    for note in notes:
        project = note.get("project") or "?"
        context = f" (context: {note['context']})" if note.get("context") else ""
        lines.append(f"- [{note['id']}] {project} — {note['text']}{context}")
    queue = (optional_signals or {}).get("claude_reflect_queue") or []
    if queue:
        lines.extend(["", f"## claude-reflect queue ({len(queue)}, read-only)"])
        for item in queue:
            project = Path(str(item.get("project", ""))).name
            message = str(item.get("message", ""))[:PROMPT_CHARS]
            lines.append(f"- [{item.get('type')}] {project}: {message}")
    declined = declined or []
    lines.extend(["", f"## Declined before ({len(declined)}) — do not re-propose"])
    lines.extend(f"- {retro_candidate}" for retro_candidate in declined[-30:])
    return "\n".join(lines)


def citation_matches(evidence_id, citations):
    short_id = evidence_id[:8]
    return any(
        evidence_id in citation or short_id in citation for citation in citations
    )


def build_report(
    insights,
    retro_candidates,
    reviewed_session_ids,
    declined_keys,
    digest_session_ids,
    digest_note_ids,
):
    digest_session_ids = set(digest_session_ids)
    digest_note_ids = set(digest_note_ids)
    if not 4 <= len(insights) <= 6:
        raise ValueError("a multi-session Retrospective requires 4–6 Insights")
    for insight in insights:
        if not isinstance(insight, dict) or not insight.get("text"):
            raise ValueError("each Insight requires text")
        session_ids = insight.get("session_ids") or []
        citations = insight.get("citations") or []
        if len(set(session_ids)) < 2:
            raise ValueError("each Insight must cite at least two distinct sessions")
        if not set(session_ids) <= digest_session_ids:
            raise ValueError("Insight evidence must come from digest sessions")
        if len(citations) < 2 or not all(
            citation_matches(session_id, citations) for session_id in session_ids
        ):
            raise ValueError("each Insight requires citations tied to its evidence sessions")
    included = []
    suppressed = []
    for retro_candidate in retro_candidates:
        key = retro_candidate["key"]
        session_ids = retro_candidate.get("session_ids") or []
        note_ids = retro_candidate.get("note_ids") or []
        citations = retro_candidate.get("citations") or []
        if not session_ids and not note_ids:
            raise ValueError(f"Retro candidate '{key}' requires session or note evidence IDs")
        if not set(session_ids) <= digest_session_ids or not set(note_ids) <= digest_note_ids:
            raise ValueError(f"Retro candidate '{key}' evidence must come from the digest")
        if not citations or not all(
            citation_matches(evidence_id, citations)
            for evidence_id in [*session_ids, *note_ids]
        ):
            raise ValueError(f"Retro candidate '{key}' requires citations tied to its evidence")
        reason = None
        if key in declined_keys:
            reason = "declined before"
        elif retro_candidate.get("status") in {"duplicate", "skipped"}:
            reason = retro_candidate.get("status")
        elif session_ids and all(
            session_id in reviewed_session_ids for session_id in session_ids
        ) and not note_ids:
            reason = "reviewed sessions inform Insights only"
        if reason:
            suppressed.append({"key": key, "reason": reason})
        else:
            included.append(retro_candidate)
    if len(included) > 7:
        raise ValueError("a Retrospective can report at most seven Retro candidates")
    lines = ["# Retrospective", "", "## Insights", ""]
    for insight in insights:
        citations = "; ".join(insight["citations"])
        lines.append(f"- {insight['text']} — {citations}")
    lines.extend(["", "## Retro candidates", ""])
    labels = {
        "memory": "Memory",
        "rule": "Rule",
        "skill_edit": "Skill edit",
        "issue": "Issue",
    }
    for number, retro_candidate in enumerate(included, 1):
        label = labels.get(retro_candidate["type"], retro_candidate["type"])
        if retro_candidate.get("status") == "upstream":
            label = "Skill edit (upstream)"
        elif retro_candidate["type"] == "memory":
            label = f"Memory ({retro_candidate.get('memory_type', 'feedback')})"
        lines.append(f"{number}. {label} → {retro_candidate.get('project') or '?'}")
        exact_text = retro_candidate["text"].replace("\n", "\n   ")
        lines.append(f'   "{exact_text}"')
        citations = retro_candidate.get("citations") or retro_candidate.get("note_ids") or []
        lines.append(f"   from: {', '.join(citations)}")
        lines.append("")
    lines.append("Reply with numbers (e.g. 1 3), all, or none.")
    return "\n".join(lines), included, suppressed
