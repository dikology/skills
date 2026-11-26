#!/usr/bin/env python3

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import sys
import tempfile
import uuid

from adapters import get_adapter


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


def atomic_write(path, content):
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


def selected_adapter_name(requested):
    if requested:
        return requested
    if os.environ.get("RETROSPECTIVE_ADAPTER"):
        return os.environ["RETROSPECTIVE_ADAPTER"]
    if os.environ.get("RETROSPECTIVE_RUNTIME"):
        return os.environ["RETROSPECTIVE_RUNTIME"]
    if os.environ.get("CLAUDECODE"):
        return "claude"
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
    declined_parser.add_argument("--retro_candidate", action="append", required=True)
    declined_parser.add_argument("--check", action="store_true")
    clear_parser = subparsers.add_parser("clear")
    clear_parser.add_argument("--adapter")
    clear_parser.add_argument("--note-id", action="append", required=True)
    args = parser.parse_args(argv)
    if args.operation == "note" and (
        not args.context.strip()
        or len(args.context) > 240
        or "\n" in args.context
        or "\r" in args.context
    ):
        parser.error("note context must be one non-empty line of at most 240 characters")

    adapter_name = selected_adapter_name(args.adapter)
    adapter = get_adapter(adapter_name)
    if args.operation == "reviewed":
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
