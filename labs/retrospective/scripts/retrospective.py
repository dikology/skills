#!/usr/bin/env python3

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import sys
import uuid

from adapters import get_adapter
from core import DEFAULT_WINDOW, atomic_write, build_report, parse_approval, parse_window, render_digest


def state_directory():
    configured = os.environ.get("RETROSPECTIVE_STATE_DIR")
    return Path(configured) if configured else Path.home() / ".retrospective"


@contextmanager
def state_lock():
    state = state_directory()
    state.mkdir(parents=True, exist_ok=True)
    with (state / ".state.lock").open("a", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield state
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def append_lines(path, lines):
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    if existing and not existing.endswith("\n"):
        existing += "\n"
    atomic_write(path, existing + "".join(line + "\n" for line in lines))


def save_note(adapter, adapter_name, text, context):
    identity = adapter.current_session() if adapter else {"session_id": None}
    note = {
        "id": str(uuid.uuid4()),
        "adapter": adapter_name,
        "session_id": identity["session_id"],
        "project": str(Path.cwd()),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "text": text,
        "context": context,
    }
    with state_lock() as state:
        inbox = state / "inbox.jsonl"
        append_lines(inbox, [json.dumps(note, ensure_ascii=False, sort_keys=True)])
    return {"status": "saved", "note": note, "inbox": str(inbox)}


def read_ledger(ledger):
    return set(ledger.read_text(encoding="utf-8").splitlines()) if ledger.exists() else set()


def read_notes():
    inbox = state_directory() / "inbox.jsonl"
    if not inbox.exists():
        return []
    notes = []
    for line in inbox.read_text(encoding="utf-8").splitlines():
        try:
            note = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(note, dict) and note.get("id") and note.get("text"):
            notes.append(note)
    return notes


def note_in_window(note, start, end):
    try:
        created = datetime.fromisoformat(note["created_at"].replace("Z", "+00:00"))
    except (KeyError, TypeError, ValueError):
        return False
    return start <= created.astimezone().date() <= end


def note_in_scope(note, start, end, project=None, session_ids=None):
    if project and project.lower() not in str(note.get("project") or "").lower():
        return False
    if session_ids:
        session_id = note.get("session_id")
        return bool(
            session_id and any(session_id.startswith(value) for value in session_ids)
        )
    return note_in_window(note, start, end)


def is_reviewed(existing, adapter_name, session_id):
    identity = f"{adapter_name}:{session_id}"
    if identity in existing:
        return True
    if adapter_name != "claude" or session_id not in existing:
        return False
    try:
        uuid.UUID(session_id)
    except ValueError:
        return False
    return True


def reviewed_sessions(adapter_name, session_ids, check):
    ledger = state_directory() / "reviewed.txt"
    if check:
        existing = read_ledger(ledger)
    else:
        with state_lock():
            existing = read_ledger(ledger)
            additions = []
            for session_id in session_ids:
                if not is_reviewed(existing, adapter_name, session_id):
                    identity = f"{adapter_name}:{session_id}"
                    additions.append(identity)
                    existing.add(identity)
            append_lines(ledger, additions)
    return {
        "sessions": [
            {
                "adapter": adapter_name,
                "session_id": session_id,
                "reviewed": True
                if not check
                else is_reviewed(existing, adapter_name, session_id),
            }
            for session_id in session_ids
        ]
    }


def declined_retro_candidates(retro_candidates, check):
    ledger = state_directory() / "declined.txt"
    if check:
        existing = read_ledger(ledger)
    else:
        with state_lock():
            existing = read_ledger(ledger)
            additions = []
            for retro_candidate in retro_candidates:
                if retro_candidate not in existing:
                    additions.append(retro_candidate)
                    existing.add(retro_candidate)
            append_lines(ledger, additions)
    return {
        "retro_candidates": [
            {
                "retro_candidate": retro_candidate,
                "declined": True if not check else retro_candidate in existing,
            }
            for retro_candidate in retro_candidates
        ]
    }


def clear_notes(note_ids):
    requested = set(note_ids)
    found = set()
    with state_lock() as state:
        inbox = state / "inbox.jsonl"
        lines = (
            inbox.read_text(encoding="utf-8").splitlines(keepends=True)
            if inbox.exists()
            else []
        )
        kept = []
        for line in lines:
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                kept.append(line)
                continue
            if isinstance(record, dict) and record.get("id") in requested:
                found.add(record["id"])
            else:
                kept.append(line)
        atomic_write(inbox, "".join(kept))
    return {
        "status": "cleared",
        "cleared": [note_id for note_id in note_ids if note_id in found],
        "missing": [note_id for note_id in note_ids if note_id not in found],
    }


def parse_retro_candidates(parser, values):
    retro_candidates = []
    for value in values:
        try:
            retro_candidate = json.loads(value)
        except json.JSONDecodeError as error:
            parser.error(f"invalid Retro candidate JSON: {error}")
        if not isinstance(retro_candidate, dict) or not retro_candidate.get("key") or not retro_candidate.get("type"):
            parser.error("each Retro candidate needs a key and type")
        retro_candidates.append(retro_candidate)
    return retro_candidates


def selected_adapter_name(requested):
    if requested:
        return requested
    if os.environ.get("RETROSPECTIVE_ADAPTER"):
        return os.environ["RETROSPECTIVE_ADAPTER"]
    if os.environ.get("RETROSPECTIVE_RUNTIME"):
        return os.environ["RETROSPECTIVE_RUNTIME"]
    if os.environ.get("CLAUDECODE"):
        return "claude"
    if os.environ.get("QWEN_CODE_SESSION_ID") or os.environ.get("QWEN_CODE") == "1":
        return "qwen"
    return None


def main(argv=None):
    parser = argparse.ArgumentParser(prog="retrospective")
    subparsers = parser.add_subparsers(dest="operation", required=True)
    for operation in ("capabilities", "current-session"):
        operation_parser = subparsers.add_parser(operation)
        operation_parser.add_argument("--adapter")
    note_parser = subparsers.add_parser("note")
    note_parser.add_argument("--adapter")
    note_parser.add_argument("--text", required=True)
    note_parser.add_argument("--context", required=True)
    note_parser.add_argument("--approve", action="store_true")
    reviewed_parser = subparsers.add_parser("reviewed")
    reviewed_parser.add_argument("--adapter")
    reviewed_parser.add_argument("--session-id", action="append", required=True)
    reviewed_parser.add_argument("--check", action="store_true")
    declined_parser = subparsers.add_parser("declined")
    declined_parser.add_argument("--adapter")
    declined_parser.add_argument(
        "--retro-candidate", "--retro_candidate", dest="retro_candidate", action="append", required=True
    )
    declined_parser.add_argument("--check", action="store_true")
    clear_parser = subparsers.add_parser("clear")
    clear_parser.add_argument("--adapter")
    clear_parser.add_argument("--note-id", action="append", required=True)
    digest_parser = subparsers.add_parser("digest")
    digest_parser.add_argument("--adapter")
    digest_parser.add_argument("--window", default=DEFAULT_WINDOW)
    digest_parser.add_argument("--project")
    digest_parser.add_argument("--session", action="append", dest="session_ids")
    digest_parser.add_argument("--min-user-messages", type=int, default=3)
    digest_parser.add_argument("--include-temp", action="store_true")
    digest_parser.add_argument("--lang")
    notes_parser = subparsers.add_parser("notes")
    notes_parser.add_argument("--adapter")
    notes_parser.add_argument("--session-id")
    prepare_parser = subparsers.add_parser("prepare")
    prepare_parser.add_argument("--adapter")
    prepare_parser.add_argument("--retro-candidate", action="append", required=True)
    report_parser = subparsers.add_parser("report")
    report_parser.add_argument("--adapter")
    report_parser.add_argument("--insight", action="append", required=True)
    report_parser.add_argument("--retro-candidate", action="append", default=[])
    report_parser.add_argument("--digest-session-id", action="append", required=True)
    report_parser.add_argument("--digest-note-id", action="append", default=[])
    execute_parser = subparsers.add_parser("execute")
    execute_parser.add_argument("--adapter")
    execute_parser.add_argument("--retro-candidate", action="append", required=True)
    execute_parser.add_argument("--approval", required=True)
    execute_parser.add_argument("--session-id", action="append", default=[])
    execute_parser.add_argument("--note-id", action="append", default=[])
    args = parser.parse_args(argv)
    if args.operation == "digest" and args.session_ids and len(args.session_ids) > 5:
        parser.error("at most five full sessions may be requested")
    if args.operation == "note" and not args.text.strip():
        parser.error("note text must not be empty")
    if args.operation == "note" and (
        not args.context.strip()
        or len(args.context) > 240
        or "\n" in args.context
        or "\r" in args.context
    ):
        parser.error("note context must be one non-empty line of at most 240 characters")

    adapter_name = selected_adapter_name(args.adapter)
    adapter = get_adapter(adapter_name)
    if args.operation in {"prepare", "report", "execute"} and len(args.retro_candidate) > 7:
        parser.error("a Retrospective can execute at most seven Retro candidates")
    if args.operation == "prepare":
        if adapter is None:
            parser.error("an explicit supported adapter is required")
        retro_candidates = parse_retro_candidates(parser, args.retro_candidate)
        result = {"retro_candidates": [adapter.prepare_retro_candidate(retro_candidate) for retro_candidate in retro_candidates]}
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0
    if args.operation == "report":
        if adapter is None:
            parser.error("an explicit supported adapter is required")
        try:
            insights = [json.loads(value) for value in args.insight]
        except json.JSONDecodeError as error:
            parser.error(f"invalid Insight JSON: {error}")
        retro_candidates = parse_retro_candidates(parser, args.retro_candidate)
        reviewed = read_ledger(state_directory() / "reviewed.txt")
        evidence_session_ids = {
            session_id
            for retro_candidate in retro_candidates
            for session_id in retro_candidate.get("session_ids") or []
        }
        reviewed_session_ids = {
            session_id
            for session_id in evidence_session_ids
            if is_reviewed(reviewed, adapter_name, session_id)
        }
        if hasattr(adapter, "session_exists"):
            missing = [
                session_id
                for session_id in args.digest_session_id
                if not adapter.session_exists(session_id)
            ]
            if missing:
                parser.error(f"digest sessions not found: {', '.join(missing)}")
        declined = read_ledger(state_directory() / "declined.txt")
        try:
            report, included, suppressed = build_report(
                insights,
                retro_candidates,
                reviewed_session_ids,
                declined,
                args.digest_session_id,
                args.digest_note_id,
            )
        except ValueError as error:
            parser.error(str(error))
        result = {
            "report": report,
            "retro_candidates": included,
            "suppressed": suppressed,
        }
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0
    if args.operation == "execute":
        if adapter is None:
            parser.error("an explicit supported adapter is required")
        retro_candidates = parse_retro_candidates(parser, args.retro_candidate)
        if args.approval.strip().lower() == "all" and any(
            retro_candidate.get("type") == "issue" for retro_candidate in retro_candidates
        ):
            parser.error("GitHub Issue Retro candidates require explicit numeric approval")
        try:
            selected = parse_approval(args.approval, len(retro_candidates))
        except ValueError as error:
            parser.error(str(error))
        actions = []
        for index, retro_candidate in enumerate(retro_candidates):
            if index not in selected:
                continue
            action = adapter.execute_retro_candidate(retro_candidate)
            action["number"] = index + 1
            actions.append(action)
            if action.get("warning"):
                print(f"warning: {action['warning']}", file=sys.stderr)
        declined = [retro_candidate["key"] for index, retro_candidate in enumerate(retro_candidates) if index not in selected]
        if declined:
            declined_retro_candidates(declined, check=False)
        if args.session_id:
            if not adapter_name:
                parser.error("an explicit adapter is required")
            reviewed_sessions(adapter_name, args.session_id, check=False)
        cleared = clear_notes(args.note_id) if args.note_id else None
        result = {
            "actions": actions,
            "bookkeeping": {
                "reviewed": args.session_id,
                "declined": declined,
                "notes": cleared,
            },
        }
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0
    if args.operation == "digest":
        if adapter is None:
            parser.error("an explicit supported adapter is required")
        try:
            start, end = parse_window(args.window)
        except ValueError as error:
            parser.error(str(error))
        try:
            sessions, warnings = adapter.discover(
                start,
                end,
                project=args.project,
                session_ids=args.session_ids,
                min_user_messages=args.min_user_messages,
                include_temp=args.include_temp,
            )
        except ValueError as error:
            parser.error(str(error))
        reviewed = read_ledger(state_directory() / "reviewed.txt")
        for session in sessions:
            session["reviewed"] = is_reviewed(
                reviewed, adapter_name, session["session_id"]
            )
        optional_signals = {}
        if hasattr(adapter, "load_optional_signals"):
            optional_signals, signal_warnings = adapter.load_optional_signals(
                sessions, start, end
            )
            warnings.extend(signal_warnings)
        notes = [
            note
            for note in read_notes()
            if note_in_scope(
                note,
                start,
                end,
                project=args.project,
                session_ids=args.session_ids,
            )
        ]
        declined = sorted(read_ledger(state_directory() / "declined.txt"))
        for warning in warnings:
            print(f"warning: {warning}", file=sys.stderr)
        print(
            render_digest(
                sessions,
                start,
                end,
                full=bool(args.session_ids),
                language=args.lang,
                notes=notes,
                declined=declined,
                optional_signals=optional_signals,
            )
        )
        return 0
    if args.operation == "notes":
        notes = read_notes()
        if args.session_id:
            notes = [note for note in notes if note.get("session_id") == args.session_id]
        result = {"notes": notes}
    elif args.operation == "reviewed":
        if not adapter_name:
            parser.error("an explicit adapter is required")
        result = reviewed_sessions(adapter_name, args.session_id, args.check)
    elif args.operation == "declined":
        result = declined_retro_candidates(args.retro_candidate, args.check)
    elif args.operation == "clear":
        result = clear_notes(args.note_id)
    elif args.operation == "note":
        if args.approve:
            if not adapter_name:
                parser.error("an explicit adapter is required")
            result = save_note(adapter, adapter_name, args.text, args.context)
        else:
            note = {"text": args.text, "context": args.context}
            result = {"status": "approval_required", "note": note}
    elif args.operation == "current-session" and adapter is None:
        result = {"adapter": None, "session_id": None, "status": "unavailable"}
    else:
        if adapter is None:
            parser.error("an explicit supported adapter is required")
        if args.operation == "capabilities":
            result = adapter.capabilities()
        else:
            result = adapter.current_session()
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
